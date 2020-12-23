from collections import defaultdict
from decimal import Decimal
from typing import Union

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Sum

from oddslingers.utils import camelcase_to_capwords
from oddslingers.tasks import track_analytics_event
from oddslingers.mutations import MutationList, execute_mutations

from banker.mutations import create_transfer

import poker.animations as anims
from poker.constants import (
    Event, AnimationEvent, HAND_SAMPLING_CAP, ANALYTIC_HAND_THRESHOLDS,
)
from poker.models import (
    ChatLine, Player, PokerTable, HandHistory, TournamentResult
)
from poker.level_utils import update_levels, earned_chips

User = get_user_model()


class Subscriber:
    """
    Subscribers receive all controller dispatched events,
    and are able to apply changes to the outgoing gamestate json.

    They exist to encapsulate game side effects like animations,
    chat, or bank transfer, and act as a sort of middleware for game
    events and broadcasts.

    the order in which Subscribers receive events is not guaranteed,
    but they always receive them after changes have been applied to
    the subj model.
    """

    def dispatch(self, subj, event, changes=None, **kwargs):
        desc = 'This should decide what to do based on the event '\
               'passed from the controller. Events are received '\
               '_after_ the passed changes have been applied.'
        raise NotImplementedError(desc)

    def commit(self):
        desc = 'This should commit anything that changes state and '\
               'update broadcast state'
        raise NotImplementedError(desc)

    def updates_for_broadcast(self, player=None, spectator=None):
        desc = 'This should return a dict with whatever state needs '\
               'to be broadcasted to the given player (None means '\
               'public info only)'
        raise NotImplementedError(desc)


class MutationSubscriber(Subscriber):
    def __init__(self, accessor):
        self.accessor = accessor
        self.mutations: MutationList = []

    def commit(self):
        execute_mutations(self.mutations)
        self.mutations = []

    def updates_for_broadcast(self, player=None, spectator=None):
        return {}


class NotificationSubscriber(Subscriber):
    def __init__(self, accessor):
        self.notifications = defaultdict(list)
        self.to_broadcast = defaultdict(list)

    def dispatch(self, subj, event, changes=None, **kwargs):
        if event == Event.NOTIFICATION:
            self.queue_notification(**kwargs)

    def queue_notification(self, notification_type: str, msg: str,
                           player: Union[Player, str]=None,
                           spectator: User=None):
        receiver = player or spectator or 'all'
        self.notifications[receiver].append({
            'type': notification_type,
            'subtype': None,
            'bsStyle': 'info',
            'ts': timezone.now(),
            'title': camelcase_to_capwords(notification_type),
            'description': msg,
        })

    def commit(self):
        self.to_broadcast = self.notifications
        self.notifications = defaultdict(list)

    def updates_for_broadcast(self, player=None, spectator=None):
        receiver = player or spectator or 'all'
        return {'notifications': self.to_broadcast[receiver]}


class ChatSubscriber(Subscriber):
    def __init__(self, accessor):
        self.accessor = accessor
        # Who this chat belongs to
        self.target = self.accessor.table
        self.to_broadcast = defaultdict(dict)
        self.to_broadcast['all'] = {'chat': []}
        for player in self.accessor.seated_players():
            self.to_broadcast[player.id] = {'chat': []}
        self.cards_dealt_chat = {}
        self.chats = []

    def dispatch(self, subj, event, changes=None, **kwargs):
        if event == Event.CHAT:
            self.chats.append(kwargs)
        elif event == Event.FOLD and not self._has_folded_out_of_time():
            self.chats.append({
                'speaker': 'Dealer',
                'msg': f'{subj.username} folded'
            })
        elif event == Event.BET:
            self.chats.append({
                'speaker': 'Dealer',
                'msg': f'{subj.username} bet {kwargs["amt"]}'
            })
        elif event == Event.RAISE_TO:
            self.chats.append({
                'speaker': 'Dealer',
                'msg': f'{subj.username} raised to {kwargs["amt"]}'
            })
        elif event == Event.CALL:
            self.chats.append({
                'speaker': 'Dealer',
                'msg': f'{subj.username} called {kwargs["amt"]}'
            })
        elif event == Event.CHECK:
            self.chats.append({
                'speaker': 'Dealer',
                'msg': f'{subj.username} checked'
            })
        elif event == Event.DEAL and isinstance(subj, Player):
            if self.cards_dealt_chat.get(subj):
                pretty_card = kwargs["card"].pretty()
                self.cards_dealt_chat[subj]['msg'] += f'{pretty_card} '
            else:
                self.cards_dealt_chat[subj] = {
                    'speaker': 'Dealer',
                    'msg': f'You ({subj.stack_available}) '\
                           f'were dealt {kwargs["card"].pretty()} '
                }

    def _has_folded_out_of_time(self):
        msg = 'ran out of time and folded'
        return self.chats and msg in self.chats[-1]['msg']

    def create_chatline(self, speaker: str, msg: str, player_id: str=None):
        # in the case of a dealer message (e.g. flop dealt),
        #   speaker='Dealer' and player is None
        if player_id is None:
            user = None
        else:
            user = self.accessor.player_by_player_id(player_id).user

        assert self.target.chat_history, 'Chat history cannot be None!'

        # TODO: ChatLine should just be called DealerChat or something,
        #   and we can implement a separate app for chat
        new_line = ChatLine(
            chat_history=self.target.chat_history,
            speaker=speaker,
            message=msg[:1000],
            user=user
        )
        return new_line

    def commit(self):
        output = []
        self.to_broadcast = defaultdict(dict)
        self.to_broadcast['all'] = {'chat': []}

        for player in self.accessor.seated_players():
            self.to_broadcast[player.id] = {'chat': []}

        for chat in self.chats:
            chat_line = self.create_chatline(**chat)
            output.append(chat_line)
            self.to_broadcast['all']['chat'].append(
                json_for_chatline(chat_line, accessor=self.accessor)
            )

        for player, deal_chat in self.cards_dealt_chat.items():
            chat_line = self.create_chatline(**deal_chat)
            self.to_broadcast[player.id] = {
                'chat': [json_for_chatline(chat_line, accessor=self.accessor)]
            }
        self.chats = []
        self.cards_dealt_chat = {}
        for chat in output:
            chat.save()


    def updates_for_broadcast(self, player=None, spectator=None):
        receiver = 'all'
        if player and self.to_broadcast[player.id]:
            receiver = player.id
            my_chat = self.to_broadcast[receiver]['chat']
            all_chat = self.to_broadcast['all']['chat']
            self.to_broadcast[receiver]['chat'] = all_chat + my_chat
        return self.to_broadcast[receiver]


class TournamentChatSubscriber(ChatSubscriber):
    def __init__(self, accessor):
        super().__init__(accessor)
        self.target = self.accessor.table.tournament


def json_for_chatline(chatline, accessor=None, tourney_entrants=None):
    species = ''
    output = chatline.__json__()
    output.pop('user')
    speaker = chatline.speaker
    is_player = accessor and speaker in (
        p.username for p in accessor.seated_players()
    )
    is_entrant = tourney_entrants and speaker in tourney_entrants

    if chatline.user and chatline.user.is_staff:
        species = 'staff'
    elif is_player or is_entrant:
        species = 'player'
    elif chatline.speaker.lower() in ['dealer', 'winner_info']:
        species = 'dealer'
    else:
        species = 'observer'

    output['species'] = species
    return output


class LogSubscriber(Subscriber):
    def __init__(self, log):
        self.log = log

    def dispatch(self, subj, event, changes=None, **kwargs):
        self.log.write_event(subj, event, **kwargs)

    def commit(self):
        self.log.commit()

    def updates_for_broadcast(self, player=None, spectator=None):
        return {}


class AnimationSubscriber(Subscriber):
    '''
    A series of animation events get sent to the front end on every
    broadcast. They take the following form:
    {
        'type': <animation_type: str>,
        'subj': <subj: dict>,
        'value': <whatever args are needed, e.g. bet_amt>,
        'patches': <list of RFC 6902 patches: list>,
    }
    for patches spec see: https://tools.ietf.org/html/rfc6902
    '''

    def __init__(self, accessor):
        self.accessor = accessor
        self.last_known_sidepot_summary = {}
        self.to_broadcast = []
        self._init_eventstream()

    def _init_eventstream(self):
        """
        add UPDATE with initial state (before dispatches) to
        animation events
        """
        self.eventstream = [anims.snapto_for_accessor_state(self.accessor)]
        # ending gamestate UPDATE is added at the end of eventstream
        #   in self.commit

    def dispatch(self, subj, event, changes, **kwargs):
        if (event.name in AnimationEvent.__members__
                and event != Event.SIT_IN):
            animation_event = AnimationEvent.from_event(event)
            self.eventstream.append(anims.process_event(
                self.accessor,
                subj,
                animation_event,
                changes,
                **kwargs
            ))

        # if this is not an animation event, update the most recent
        #   animation with the changes for this event
        elif len(self.eventstream):
            self.eventstream[-1]['changes'].update({
                anims.patch_path(subj, k): v for k, v in changes
            })

    def updates_for_broadcast(self, player=None, spectator=None):
        return {
            'animations': [
                anims.event_for_player(event, player)
                for event in self.to_broadcast
            ]
        }

    def commit(self):
        # expected final gamestate after animations
        final_snapto = anims.snapto_for_accessor_state(self.accessor)
        if len(self.eventstream) != 1:
            self.eventstream.append(final_snapto)
        else:
            # there was only the init snapto; if there was any change
            #   it was a passive (non-animated) change, so we should
            #   just send the final state
            assert self.eventstream[0]['type'] == 'SNAPTO', \
                    'Sanity check fail: expected just an initial ' \
                    'SNAPTO animation in eventstream, but got:\n' \
                    f'{self.eventstream}'
            self.eventstream = [final_snapto]

        self.to_broadcast = anims.process_eventstream(self.accessor,
                                                      self.eventstream)
        self._init_eventstream()


class BankerSubscriber(MutationSubscriber):

    def dispatch(self, subj, event, changes=None, **kwargs):
        # Tutorials ignore the cashier altogether.
        if self.accessor.table.is_tutorial:
            return

        if event == Event.CREATE_TRANSFER:
            self.mutations += create_transfer(**kwargs)


class LevelSubscriber(MutationSubscriber):
    def __init__(self, accessor):
        super().__init__(accessor)
        self.winners = set()
        self.notifications = defaultdict(list)
        self.to_broadcast = defaultdict(list)

    def dispatch(self, subj, event, changes=None, **kwargs):
        if event == Event.WIN:
            self.winners.add(subj)

        if event == Event.SHOWDOWN_COMPLETE:
            self.recalculate_all_levels()

    def recalculate_all_levels(self):
        for plyr in self.winners:
            self.recalculate_levels(plyr)
        self.winners = set()

    def recalculate_levels(self, plyr):
        if plyr.is_robot:
            return

        all_winnings = plyr.user\
                           .player_set\
                           .filter(seated=True, table__is_private=False)\
                           .exclude(id=plyr.id)\
                           .aggregate(Sum('stack'))['stack__sum'] or 0

        if not plyr.table.is_private:
            all_winnings += plyr.stack

        mutations, leveledup = update_levels(
            plyr.user,
            earned_chips(plyr.user),
            all_winnings
        )
        self.mutations += mutations

        if leveledup:
            msg = 'New level unlocked!'
            self.notifications[plyr].append({
                'type': 'level_up',
                'bsStyle': 'success',
                'ts': timezone.now(),
                'title': 'Congratulations!',
                'description': msg,
                'icon': '/static/images/logo.png',
            })

    def commit(self):
        super().commit()
        self.to_broadcast = self.notifications
        self.notifications = defaultdict(list)

    def updates_for_broadcast(self, player=None, spectator=None):
        if player:
            return {'level_notifications': self.to_broadcast[player]}
        return {}


class InMemoryLogSubscriber(Subscriber):
    def __init__(self, accessor=None):
        self.log = []

    def dispatch(self, subj, event, changes=None, **kwargs):
        self.log.append((subj, event, kwargs, changes))

    def commit(self):
        pass

    def updates_for_broadcast(self, player=None, spectator=None):
        return {}


class AnalyticsEventSubscriber(Subscriber):
    def __init__(self, accessor):
        self.accessor = accessor
        table = accessor.table
        is_cashtable = table.tournament is None
        self.template = {
            'username': None,
            'event': 'something went wrong',
            'topic': table.zulip_topic if is_cashtable else table.tournament.zulip_topic,
            'stream': "Tables" if is_cashtable else "Tournaments",
        }
        self.to_track = []

    def dispatch(self, subj, event, changes=None, **kwargs):
        if event == Event.END_HAND and isinstance(subj, PokerTable):
            self.to_track += self._track_analytics_for_hands_played()

        # too noisy with many ysers, uncomment if you need it for debugging
        # elif event == Event.LEAVE_SEAT and isinstance(subj, Player):
        #     event_data = self.template.copy()
        #     event_data.update({
        #         'username': subj.user.username,
        #         'event': 'is leaving' if subj.seated else 'left seat',
        #     })
        #     self.to_track.append(event_data)

    def _track_analytics_for_hands_played(self):
        events_data = []
        for plyr in self.accessor.active_players():
            if plyr.user and not plyr.user.is_robot:
                if plyr.user.hands_played in ANALYTIC_HAND_THRESHOLDS:
                    event_data = self.template.copy()
                    event_data.update({
                        'username': plyr.user.username,
                        'event': f'played {plyr.user.hands_played} hands',
                    })
                    events_data.append(event_data)
        return events_data


    def commit(self):
        while self.to_track:
            track_analytics_event.send(**self.to_track.pop())

    def updates_for_broadcast(self, player=None, spectator=None):
        return {}


class TableStatsSubscriber(Subscriber):
    def __init__(self, accessor):
        self.accessor = accessor
        self.table_stats = accessor.table.stats

    def dispatch(self, subj, event, changes=None, **kwargs):
        self.table_stats.avg_stack = self._get_avg_stack()

        if event == Event.NEW_HAND:
            self._increase_num_samples()
            hands_per_hour = self._get_hands_per_hour()
            self.table_stats.hands_per_hour = hands_per_hour

        elif event == Event.DEAL and isinstance(subj, PokerTable):
            if self.accessor.is_flop():
                players_per_flop_pct = self._get_players_per_flop_pct()
                self.table_stats.players_per_flop_pct = players_per_flop_pct

        elif event == Event.SHOWDOWN_COMPLETE:
            new_sample = self.accessor.current_pot()
            avg_pot = self._get_rolling_avg(
                num_samples=self.table_stats.num_samples,
                new_sample=new_sample,
                prev_avg=self.table_stats.avg_pot
            )
            self.table_stats.avg_pot = avg_pot

        elif event == Event.END_HAND and isinstance(subj, PokerTable):
            if self.accessor.is_preflop():
                players_per_flop_pct = self._get_rolling_avg(
                    num_samples=self.table_stats.num_samples,
                    new_sample=0,
                    prev_avg=self.table_stats.players_per_flop_pct
                )
                self.table_stats.players_per_flop_pct = players_per_flop_pct


    def _get_rolling_avg(self, num_samples, new_sample, prev_avg):
        try:
            prev_avg_sample = (num_samples - 1) * (prev_avg or 0)
            return (prev_avg_sample + new_sample) / num_samples
        except ZeroDivisionError:
            return None

    def _get_avg_stack(self):
        players_stacks = [player.stack for player in self.accessor.players]

        sum_stacks = sum(players_stacks) + self.accessor.current_pot()
        try:
            return sum_stacks / len(players_stacks)
        except ZeroDivisionError:
            return None

    def _increase_num_samples(self):
        if self.table_stats.num_samples < HAND_SAMPLING_CAP:
            self.table_stats.num_samples += 1

    def _get_players_per_flop_pct(self):
        showdown_players = len(self.accessor.showdown_players())
        active_players = len(self.accessor.active_players())
        new_sample = showdown_players / active_players
        new_sample = Decimal(new_sample) * 100
        return self._get_rolling_avg(
            num_samples=self.table_stats.num_samples,
            new_sample=new_sample,
            prev_avg=self.table_stats.players_per_flop_pct
        )

    def _get_hands_per_hour(self):
        hands = HandHistory.objects.filter(table=self.accessor.table)
        hands_per_hour = 0
        if hands.exists():
            initial_hand = self._get_initial_hand(hands)
            len_hands = min(hands.count(), HAND_SAMPLING_CAP)
            end_time = timezone.now()
            delta_timestamps = end_time - initial_hand.timestamp
            elapsed_hours = delta_timestamps.total_seconds() / 3600
            try:
                hands_per_hour = len_hands / elapsed_hours
                hands_per_hour = round(hands_per_hour, 2)
            except ZeroDivisionError:
                hands_per_hour = None
        return hands_per_hour

    def _get_initial_hand(self, hands):
        last_hand = hands.latest('hand_number')
        fixed_hand_number = last_hand.hand_number - HAND_SAMPLING_CAP
        hand_number = max(0, fixed_hand_number)
        initial_hand = hands.filter(hand_number=hand_number).first()\
                       or hands.first()
        return initial_hand

    def commit(self):
        self.table_stats.save()

    def updates_for_broadcast(self, player=None, spectator=None):
        table_stats = self.table_stats.__json__() \
            if self.accessor.enough_players_to_play() \
            else None
        return {'table_stats': table_stats}


class TournamentResultsSubscriber(Subscriber):
    def __init__(self, accessor):
        self.tournament = accessor.table.tournament
        self.current_results = TournamentResult.objects.filter(
            tournament=self.tournament
        )
        self.new_results = []
        self.to_broadcast = {}

    def dispatch(self, subj, event, changes=None, **kwargs):
        entrants_count = self.tournament.entrants.count()
        if self.new_results:
            current_placement = self.new_results[-1].placement
        else:
            try:
                current_placement = self.current_results\
                                        .order_by('placement')\
                                        .first()\
                                        .placement
            except Exception:
                current_placement = entrants_count + 1

        # A player was kicked
        if event == Event.LEAVE_SEAT:
            self.new_results.append(TournamentResult(
                user=subj.user,
                placement=current_placement - 1,
                payout_amt=0,
                tournament=self.tournament
            ))
        elif event == Event.FINISH_TOURNAMENT:
            self.new_results.append(TournamentResult(
                user=kwargs['winner'].user,
                placement=1,
                payout_amt=entrants_count * self.tournament.buyin_amt,
                tournament=self.tournament
            ))

    def _result_already_exists(self, user):
        return TournamentResult.objects.filter(
            tournament=self.tournament,
            user=user
        ).exists()

    def commit(self):
        for result in self.new_results:
            if not self._result_already_exists(result.user):
                self.to_broadcast['new_tourney_results'] = [result.__json__()]
                result.save()
        self.new_results = []

    def updates_for_broadcast(self, player=None, spectator=None):
        return self.to_broadcast
