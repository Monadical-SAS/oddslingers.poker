import logging

from django.conf import settings
from django.db import transaction
from django.contrib.auth import get_user_model

from oddslingers.utils import ANSI
from oddslingers.tasks import track_analytics_event
from oddslingers.mutations import execute_mutations

from banker.utils import buyins_for_table
from banker.mutations import buy_chips, create_transfer

from sockets.handlers import RoutedSocketHandler
from oddslingers.tasks import ticket_from_table_report_bug

from ..tablebeat import (
    queue_tablebeat_dispatch, start_tablebeat, stop_tablebeat,
    tablebeat_pid,
)
from ..botbeat import stop_botbeat
from ..game_utils import (
    fuzzy_get_game, featured_game, start_tournament, suspend_table,
    get_or_create_bot_user, get_n_random_bot_names
)
from ..megaphone import gamestate_json, table_sockets, tournament_sockets
from ..models import ChatLine, Freezeout, PokerTable
from ..subscribers import json_for_chatline
from ..constants import (
    CASH_GAME_BBS, TOURNEY_BUYIN_AMTS,
    N_BB_TO_NEXT_LEVEL, TOURNEY_BUYIN_TIMES
)

logger = logging.getLogger('poker')


class BasePokerSocketHandler(RoutedSocketHandler):
    # spectators can view a game without logging in
    login_required = False

    routes = (
        *RoutedSocketHandler.routes,
        ('GET_GAMESTATE', 'on_get_gamestate'),
        ('GET_HANDHISTORY', 'on_get_handhistory'),
        ('GET_PLAYER_WINNINGS', 'on_get_player_winnings'),
        ('NEW_PEER', 'on_new_peer'),
        ('AWAKEN', 'on_awaken'),
        ('REPORT_BUG', 'on_report_bug'),
        ('DEBUG_FORCE_ACTION', 'on_debug_force_action'),
        ('DEBUG_PAUSE_ACTION', 'on_debug_pause_action'),
        ('DEBUG_RESUME_ACTION', 'on_debug_resume_action'),
        ('DEBUG_GIVE_CHIPS', 'on_debug_give_chips'),
        ('DEBUG_UP_LEVEL_CASHTABLES', 'on_debug_up_level_cashtables'),
        ('DEBUG_DOWN_LEVEL_CASHTABLES', 'on_debug_down_level_cashtables'),
        ('DEBUG_UP_LEVEL_TOURNAMENTS', 'on_debug_up_level_tournaments'),
        ('DEBUG_DOWN_LEVEL_TOURNAMENTS', 'on_debug_down_level_tournaments'),
    )

    _game_controller = None

    @property
    def table_id(self):
        actual_path = self.message.content['path']
        if actual_path == '/':
            return featured_game().table.short_id
        split_path = actual_path.split('/')
        assert len(split_path) > 3 and split_path[-2], \
                'Table id is not in the socket URL, please manually '\
                'override the handler.table_id property to get it '\
                'from the message contents.'
        return split_path[-2]

    @property
    def path(self):
        """
        path used by self.setup_session to save the socket session to DB
        !!do not delete!!
        """
        actual_path = self.message.content['path']
        if actual_path == '/':
            return featured_game().table.path
        return self.message.content['path']

    @path.setter
    def path(self, _):
        """do not delete, see above"""
        pass

    @property
    def controller(self):
        """
        A single instance of HoldemController used for the full
        lifecycle of the request
        """
        if self._game_controller is None:
            self._game_controller = fuzzy_get_game(self.table_id)
        return self._game_controller

    @property
    def accessor(self):
        return self.controller.accessor

    @property
    def table(self):
        return self.controller.table

    @property
    def player(self):
        if not self.user or not self.user.is_authenticated:
            return None
        return self.accessor.player_by_user_id(self.user.id)

    def connect(self, message=None):
        super().connect(message=message)
        if settings.DEBUG:
            what = 'Player' if self.player else 'Spectator'
            who = self.user or self.socket.user_ip
            print(f'{ANSI["green"]}[+] {what} "{who}" joined table: '
                  f'{self.table_id} ({self.table}) '
                  f'{ANSI["reset"]}')
        player_is_seated = self.player in self.accessor.seated_players()
        spectator = self.user if not player_is_seated and self.user else None
        self.send_action(
            'UPDATE_GAMESTATE',
            **gamestate_json(
                self.accessor,
                self.player,
                self.controller.subscribers,
                spectator
            )
        )
        start_tablebeat(self.table)

    def disconnect(self, message=None):
        self.setup_session()
        if settings.DEBUG:
            print('{}[-] {} "{}" left table: {} ({}){}'.format(
                ANSI['red'],
                'Player' if self.player else 'Spectator',
                self.user or self.socket.user_ip,
                self.table_id,
                self.table,
                ANSI['reset'],
            ))
        super().disconnect(message)

        # if active player closed window/tab deliberately
        if self.player and message.content.get('code') != 1006:
            queue_tablebeat_dispatch(self.table.id, {
                                    'type': 'PLAYER_CLOSE_TABLE',
                                    'player_id': self.player.id})

    def default_route(self, content):
        if not self.user:
            self.send_action(
                'ERROR',
                details='You must be logged in to perform game actions.'
            )
            return

        assert content['type'], 'All websocket messages must have a type key.'

        if content['type'].upper() == 'JOIN_TABLE':
            content['user_id'] = self.user.id
            if not self.user.can_access_table(self.table.bb):
                raise ValueError(
                    f"Table {self.table.name} "
                    f"is locked for {self.user.username}.")

        elif '_SIDEBET' in content['type'].upper():
            content['user_id'] = self.user.id
        else:
            # enforce the player_id as the user making the request
            content['player_id'] = self.player.id if self.player else None
            if not self.player and self.table:
                raise ValueError(
                    'You must be a player at this table to dispatch '
                    'table events.')

        queue_tablebeat_dispatch(self.table.id, content)

        # they may be joining an empty table with no heartbeat running yet
        if content['type'].upper() == 'JOIN_TABLE':
            start_tablebeat(self.table)
            track_analytics_event.send(
                self.user.username if self.user else 'anon',
                f'joined table: {self.accessor.table.name}',
                topic=self.table.zulip_topic,
                stream="Tables",
            )

    def on_new_peer(self, content):
        if not settings.SHOW_VIDEO_STREAMS:
            return None

        table_sockets_qs = table_sockets(self.table)
        table_sockets_qs.send_action('NEW_PEER', **{
            'nick': content.get('nick'),
            'people_online': table_sockets_qs.filter(active=True).count()
        })

    def on_get_gamestate(self, message=None):
        self.setup_session()
        self.send_action(
            'SET_GAMESTATE',
            **gamestate_json(
                self.accessor,
                self.player,
                self.controller.subscribers,
                self.user
            ),
        )

    def on_report_bug(self, content=None):
        frontend_log = content.get('frontend_log') or {}
        notes = frontend_log.get('notes', '').strip()

        args = (
            str(self.socket.id),
            str(self.table.id),
            notes,
            frontend_log,
            self.user.username if self.user else None,
        )

        sync = self.table.hand_number < 100
        if sync:
            ticket_from_table_report_bug(*args)
        else:
            self.send_action(
                'NOTIFICATION', notifications=[{
                    'type': 'admin',
                    'bsStyle': 'success',
                    'title': 'Submitting support ticket...',
                    'delay': 5000,
                    'description': (
                        'Collecting table info and generating support ticket.'
                    ),
                }],
            )
            ticket_from_table_report_bug.send(*args)
        
        if settings.POKER_PAUSE_ON_REPORT_BUG:
            suspend_table(self.table)

    def on_get_handhistory(self, content):
        hand_history = self.controller.log.frontend_log(
            self.player,
            content['hand_gte'],
            content['hand_lt']
        )
        self.send_action(
            'UPDATE_HANDHISTORY',
            hand_history=hand_history
        )

    def on_get_player_winnings(self, content):
        players = self.accessor.active_players()
        player_winnings = {
            player.username: {
                'winnings': player.stack - buyins_for_table(player.user,
                                                            self.table),
                'stack': player.stack,
                'buyins': buyins_for_table(player.user, self.table)
            }
            for player in players
        }
        self.send_action(
            'UPDATE_PLAYER_WINNINGS',
            player_winnings=player_winnings
        )

    def on_awaken(self, content):
        """
        kick the heartbeat in case a player times out but someones
        frontend doesn't get an update in time
        """
        pre_pid = tablebeat_pid(self.table)

        color = ANSI['lightyellow' if pre_pid else 'red']
        did_start = 'and started' if not pre_pid else 'for'
        tbl_id = self.table.short_id
        tbl = self.table

        pid = start_tablebeat(self.table)

        print(f'{color}[*] Backend got AWAKEN {did_start} tablebeat '\
              f'{tbl_id} ({tbl}) pid={pid}{ANSI["reset"]}')

    def on_debug_force_action(self, content):
        if settings.DEBUG and self.user and self.user.is_superuser:
            suggested = content.get('action')
            queue_tablebeat_dispatch(self.table.id, {
                'type': 'FORCE_ACTION',
                'suggested': suggested,
            })
            tbl_id = self.table.short_id
            tbl = self.table
            print(f'{ANSI["lightyellow"]}[*] Backend got forced next '\
                  f'bot action {tbl_id} ({tbl}): {suggested or "random"}'\
                  f'{ANSI["reset"]}')

            start_tablebeat(self.table)
        else:
            raise Exception("You don't have permission for DEBUG actions")

    def on_debug_pause_action(self, content):
        if self.user and self.user.is_superuser:
            stop_tablebeat(self.table)
            stop_botbeat()
            tbl_id = self.table.short_id
            tbl = self.table
            print(f'{ANSI["lightyellow"]}[*] Pausing action for '\
                  f'tablebeat {tbl_id} ({tbl}){ANSI["reset"]}')

            track_analytics_event.send(
                self.user.username,
                f'paused table {self.accessor.table.name}',
                topic=self.accessor.table.zulip_topic,
                stream="Tables",
            )
        else:
            raise Exception("You don't have permission for DEBUG actions")

    def on_debug_resume_action(self, content):
        if self.user and self.user.is_superuser:
            start_tablebeat(self.table)
            tbl_id = self.table.short_id
            tbl = self.table
            print(f'{ANSI["lightyellow"]}[*] Resuming action for '\
                  f'tablebeat {tbl_id} ({tbl}){ANSI["reset"]}')
        else:
            raise Exception("You don't have permission for DEBUG actions")

    def on_debug_give_chips(self, content):
        if settings.DEBUG and self.user and self.user.is_superuser:
            amt = 10000000
            execute_mutations(
                buy_chips(self.user, amt, notes="Debug chips")
            )

            print(f'{ANSI["lightyellow"]}[*] Giving {amt} playtesting '
                  f'chips to {self.user}{ANSI["reset"]}')
        else:
            raise Exception("You don't have permission for DEBUG actions")

    def on_debug_up_level_cashtables(self, content):
        if settings.DEBUG and self.user and self.user.is_staff:
            userstats = self.user.userstats()
            userstats.games_level = min(
                lvl for lvl in CASH_GAME_BBS
                if lvl > self.user.cashtables_level
            ) * N_BB_TO_NEXT_LEVEL
            userstats.save()
            print(f'{ANSI["lightyellow"]}[*] {self.user.username} changed'
                  f' level to {self.user.cashtables_level}{ANSI["reset"]}')
        else:
            self.default_route(content)

    def on_debug_down_level_cashtables(self, content):
        if settings.DEBUG and self.user and self.user.is_staff:
            userstats = self.user.userstats()
            userstats.games_level = max(
                lvl for lvl in CASH_GAME_BBS
                if lvl < self.user.cashtables_level
            ) * N_BB_TO_NEXT_LEVEL
            userstats.save()
            print(f'{ANSI["lightyellow"]}[*] {self.user.username} changed'
                  f' level to {self.user.cashtables_level}{ANSI["reset"]}')
        else:
            self.default_route(content)

    def on_debug_up_level_tournaments(self, content):
        if settings.DEBUG and self.user and self.user.is_staff:
            userstats = self.user.userstats()
            userstats.games_level = min(
                lvl for lvl in TOURNEY_BUYIN_AMTS
                if lvl > self.user.tournaments_level
            ) * TOURNEY_BUYIN_TIMES
            userstats.save()
            print(f'{ANSI["lightyellow"]}[*] {self.user.username} changed'
                  f' tournaments level to {self.user.tournaments_level}{ANSI["reset"]}')
        else:
            self.default_route(content)

    def on_debug_down_level_tournaments(self, content):
        if settings.DEBUG and self.user and self.user.is_staff:
            userstats = self.user.userstats()
            userstats.games_level = max(
                lvl for lvl in TOURNEY_BUYIN_AMTS
                if lvl < self.user.tournaments_level
            ) * TOURNEY_BUYIN_TIMES
            userstats.save()
            print(f'{ANSI["lightyellow"]}[*] {self.user.username} changed'
                  f' tournaments level to {self.user.tournaments_level}{ANSI["reset"]}')
        else:
            self.default_route(content)



class PokerWithChatSocketHandler(BasePokerSocketHandler):
    routes = (
        *BasePokerSocketHandler.routes,
        ('CHAT', 'on_chat'),
    )

    def on_chat(self, content):
        if not (self.user and self.user.is_authenticated):
            return self.send_action(
                'ERROR',
                details='Only logged in users can chat.'
            )
        args = content['args']
        text = args['text'].strip()
        tournament = self.table.tournament
        target = tournament or self.table

        if text:
            line = ChatLine(
                chat_history=target.chat_history,
                user=self.user,
                speaker=self.user.username,
                message=text,
            )
            line.save()
            chat_line = [json_for_chatline(line, accessor=self.accessor)]

            self.table.sockets.send_action('UPDATE_CHAT', chat=chat_line)

            if tournament:
                tourney_sockets = tournament_sockets(tournament)
                tourney_sockets.send_action('UPDATE_CHAT', chat=chat_line)

            track_analytics_event.send(
                self.user.username,
                f'chat: {text}',
                topic=target.zulip_topic,
                stream="Tables",
            )


class TournamentSocketHandler(RoutedSocketHandler):
    routes = (
        *RoutedSocketHandler.routes,
        ('CHAT', 'on_chat'),
        ('JOIN_TOURNAMENT', 'on_join_tournament'),
        ('LEAVE_TOURNAMENT', 'on_leave_tournament'),
    )

    @property
    def tournament_id(self):
        actual_path = self.message.content['path']
        split_path = actual_path.split('/')
        assert len(split_path) > 3 and split_path[-2], \
                'Tournament id is not in the socket URL, please manually '\
                'override the handler.tournament_id property to get it '\
                'from the message contents.'
        return split_path[-2]

    @property
    def tournament(self):
        return Freezeout.objects.get(id__startswith=str(self.tournament_id))

    @property
    def table(self):
        return PokerTable.objects.filter(tournament=self.tournament).first()

    def user_has_balance(self, user):
        return user and user.userbalance().balance >= self.tournament.buyin_amt

    def connect(self, message=None):
        super().connect(message=message)
        self._update_entrants_presence()

    def disconnect(self, message=None):
        super().disconnect(message)
        self._update_entrants_presence()

    def _update_entrants_presence(self):
        tournament_sockets(self.tournament).send_action(
            'UPDATE_PRESENCE',
            presence=self._get_entrants_presence()
        )

    def _get_entrants_presence(self):
        path = self.tournament.path
        return {
            entrant.username: entrant.socket_set.filter(
                active=True,
                path=path
            ).exists()
            for entrant in self.tournament.entrants.all()
        }

    def change_admin_if_necessary(self, user):
        tournament = self.tournament
        if tournament.tournament_admin is None and not user.is_robot:
            tournament.tournament_admin = user
            tournament.save()
            self.send_action_to_user(
                'UPDATE_TOURNAMENT_STATE',
                target=tournament.tournament_admin,
                notifications=[self.create_notification(
                    title='New Tournament Admin',
                    msg='You have been promoted to tournament admin'
                )]
            )
        return tournament

    def assign_new_admin_if_necessary(self, leaving_user):
        tournament = self.tournament
        if leaving_user == tournament.tournament_admin:
            entrants = list(tournament.entrants.all())
            new_admin = None
            while new_admin is None and entrants:
                candidate = entrants.pop()
                new_admin = None if candidate.is_robot else candidate
            tournament.tournament_admin = new_admin
            tournament.save()
            if new_admin is not None:
                self.send_action_to_user(
                    'UPDATE_TOURNAMENT_STATE',
                    target=new_admin,
                    notifications=[self.create_notification(
                        title='New Tournament Admin',
                        msg='You have been promoted to tournament admin'
                    )]
                )
        return tournament

    def send_action_to_tournament(self, action, **kwargs):
        tournament_sockets(self.tournament).send_action(
            action,
            **kwargs
        )

    def send_action_to_user(self, action, target=None, **kwargs):
        user = target or self.user
        user.socket_set.filter(
            active=True,
            path=self.tournament.path
        ).send_action(action, **kwargs)

    def create_notification(self, title, msg):
        return {
            'type': 'tourney_notification',
            'subtype': None,
            'bsStyle': 'info',
            'title': title,
            'description': msg,
        }

    def start_tournament(self):
        tournament = self.tournament
        table = start_tournament(tournament)
        start_tablebeat(table)
        self.send_action_to_tournament(
            'START_TOURNAMENT',
            tournament_status=tournament.get_status_display(),
            table_path=tournament.table_path
        )
        track_analytics_event.send(
            self.user.username,
            f'{tournament.name} tourney has started!',
            topic=tournament.zulip_topic,
            stream="Tournaments",
        )

    def on_chat(self, content):
        if not (self.user and self.user.is_authenticated):
            return self.send_action(
                'ERROR',
                details='Only logged in users can chat.'
            )
        args = content['args']
        text = args['text'].strip()
        tournament = self.tournament

        if text:
            line = ChatLine(
                chat_history=tournament.chat_history,
                user=self.user,
                speaker=self.user.username,
                message=text,
            )
            line.save()
            entrants = tournament.entrants.values_list('username', flat=True)
            chat_line = [json_for_chatline(line, tourney_entrants=entrants)]

            tournament_sockets(tournament).send_action(
                'UPDATE_CHAT',
                chat=chat_line
            )
            if self.table:
                self.table.sockets.send_action('UPDATE_CHAT', chat=chat_line)

            track_analytics_event.send(
                self.user.username,
                f'tourney chat: {text}',
                topic=tournament.zulip_topic,
                stream="Tournaments",
            )

    def on_join_tournament(self, content):
        tournament = self.tournament
        robot = content.get('robot', False)

        with transaction.atomic():
            if robot:
                bot_name = ""
                entrants_username = [
                    e.username for e in self.tournament.entrants.all()
                ]
                while bot_name == "" or bot_name in entrants_username:
                    bot_name = get_n_random_bot_names(tournament, 1)[0]
                user = get_or_create_bot_user(bot_name)
            else:
                user = self.user

            if not user.can_access_tourney(tournament.buyin_amt):
                raise ValueError(
                    f"Tournament {tournament.name} "
                    f"is locked for {user.username}."
                )

            if tournament.entrants.count() >= tournament.max_entrants:
                raise ValueError(
                    'Trying to join a tournament with no seats left'
                )

            if not self.user_has_balance(user):
                raise ValueError(
                    'Trying to join a tournament without enough balance'
                )

            tournament.entrants.add(user)
            execute_mutations(create_transfer(
                user,
                tournament,
                tournament.buyin_amt,
                "Tournament buyin"
            ))

            tournament = self.change_admin_if_necessary(user)
            self.send_action_to_tournament(
                'UPDATE_TOURNAMENT_STATE',
                entrants=tournament.get_entrants(),
                presence=self._get_entrants_presence(),
                tournament_admin=tournament.tournament_admin
            )
            self.send_action_to_user(
                'UPDATE_TOURNAMENT_STATE',
                target=self.user,
                user_funds=self.user.userbalance().balance,
            )

            track_analytics_event.send(
                self.user.username,
                f'{user.username} {"[BOT]" if user.is_robot else ""} joined '
                f'tournament {tournament.name}',
                topic=tournament.zulip_topic,
                stream="Tournaments",
            )

            everybody_is_robot = all(
                e.is_robot for e in tournament.entrants.all()
            )

            if tournament.entrants.count() == tournament.max_entrants\
               and not everybody_is_robot:
                self.start_tournament()

    def on_leave_tournament(self, content):
        tournament = self.tournament
        notifications = []
        kicking = False
        try:
            leaving_user = get_user_model().objects.get(
                username=content['kicked_user']
            )
            kicking = True
        except KeyError:
            leaving_user = self.user
        except get_user_model().DoesNotExist:
            raise ValueError('User to kick not found')

        with transaction.atomic():
            if not self.user:
                raise ValueError(
                    'Trying to kick or leave from a tournament '
                    'without being logged in'
                )

            if kicking:
                self.check_kicking_conditions()

            tournament.entrants.remove(leaving_user)
            execute_mutations(create_transfer(
                tournament,
                leaving_user,
                tournament.buyin_amt,
                "Tournament withdrawal"
            ))

            # If tournament admin leaves we assign a new one
            tournament = self.assign_new_admin_if_necessary(leaving_user)

            if kicking:
                notifications.append(self.create_notification(
                    title='Kicked from tournament',
                    msg=f'You were kicked by {tournament.tournament_admin}'
                ))
            self.send_action_to_tournament(
                'UPDATE_TOURNAMENT_STATE',
                entrants=tournament.get_entrants(),
                presence=self._get_entrants_presence(),
                tournament_admin=tournament.tournament_admin
            )
            self.send_action_to_user(
                'UPDATE_TOURNAMENT_STATE',
                target=leaving_user,
                notifications=notifications,
                user_funds=self.user.userbalance().balance,
            )

            reason = 'was kicked from' if kicking else 'left'
            track_analytics_event.send(
                self.user.username,
                f'{leaving_user.username} {reason} tournament {tournament.name}',
                topic=tournament.zulip_topic,
                stream="Tournaments",
            )

    def check_kicking_conditions(self):
        tournament = self.tournament
        username = self.user.username
        if self.user != tournament.tournament_admin:
            raise ValueError(
                f'Non-tourney admin {username} tried to kick out a player'
            )
        if tournament.get_status_display() != 'PENDING':
            raise ValueError(
                f'{username} tried to kick from a non-pending tourney'
            )
