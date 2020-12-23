import os
import logging

from time import sleep

from django.shortcuts import redirect, Http404
from django.utils import timezone
from django.conf import settings
from django.shortcuts import render
from django.views.decorators.clickjacking import xframe_options_exempt

from oddslingers.tasks import (
    track_analytics_event, async_start_tablebeat,
)
from oddslingers.utils import sanitize_html, ExtendedEncoder
from oddslingers.mutations import execute_mutations

from sidebets.views import get_sidebets

from sockets.router import SocketRouter
from sockets.handlers import RoutedSocketHandler

from rewards.mutations import reward_attempted_xss, reward_swearing

from support.views import support_tickets_for_user
from support.incidents import ticket_from_support_page

from poker.models import PokerTable, Freezeout
from poker.views.handlers import (
    PokerWithChatSocketHandler, TournamentSocketHandler,
)
from poker.game_utils import (
    featured_game, make_game, fuzzy_get_table, fuzzy_get_game,
)
from poker.subscribers import json_for_chatline
from poker.tablebeat import (
    queue_tablebeat_dispatch, peek_tablebeat_dispatch,
    start_tablebeat, stop_tablebeat,
)
from poker.megaphone import gamestate_json
from poker.constants import TournamentStatus, HIDE_TABLES_AFTER_N_HANDS

from ui.views.base_views import BaseView, PublicReactView

logger = logging.getLogger('root')


def subscribe_to_newsletter(name, email):
    assert email and '@' in email and '.' in email, 'Invalid email'
    assert name in ('main'), ('Not a valid newsletter name.')

    with open(os.path.join(settings.EMAIL_LIST_DIR, f'{name}.txt'), 'a+') as f:
        f.write(f'{email}\n')

    track_analytics_event.send(email, f'subscribed to newsletter {name}')


def autostart_tablebeat_if_needed(table: PokerTable) -> None:
    if settings.ASYNC_TABLEBEAT_START:
        async_start_tablebeat.send(str(table.id))
    else:
        start_tablebeat(table)

class About(BaseView):
    title = 'About'
    template = 'ui/about.html'

    def post(self, request):
        email = request.POST.get('email').strip() or getattr(request.user,
                                                             'email',
                                                             None)
        subscribe_to_newsletter('main', email)

        return render(request, self.template, {
            'submitted': True,
            'email': email,
        })

class Learn(BaseView):
    title = 'Learn'
    template = 'ui/learn.html'

    STARTING_TUTORIAL_VERSION = 1

    def generate_tutorial_name(self, user):
        '''
        Versions the tutorial table so that it doesn't accumulate
        a HH > 500 hands
        '''

        basename = f'Tutorial: {user.username}'
        name = basename

        # Get all tutorials of a user
        regex = f'{basename}(\\s\\d+$|$)'
        latest_qs = PokerTable.objects.filter(
            name__regex=regex,
        )
        latest_table = latest_qs.latest('created') if latest_qs else None

        if latest_table:
            if latest_table.hand_number > HIDE_TABLES_AFTER_N_HANDS or \
                latest_table.is_archived:
                table_number = latest_table.name.replace(basename, '').strip()

                if table_number:
                    next_number = str(int(table_number) + 1)
                    name = f'{basename} {next_number}'
                else:
                    name = f'{basename} {Learn.STARTING_TUTORIAL_VERSION}'

            else:
                name = latest_table.name

        return name

    def context(self, request):
        table_params = {
            'num_seats': 6,
            'sb': 1,
            'bb': 2,
            'is_tutorial': True,
            'table_type': 'NLHE',
        }
        user = request.user
        table_path = None

        if user.is_authenticated:
            controller = make_game(
                name=self.generate_tutorial_name(user),
                defaults=table_params,
                num_bots=3,
            )
            table = controller.table
            autostart_tablebeat_if_needed(table)
            table_players = table.player_set
            if not table_players.filter(user_id=user.id).exists():
                join_table_event = {
                    'type': 'JOIN_TABLE',
                    'user_id': user.id,
                }
                queue_tablebeat_dispatch(table.id, join_table_event)

            # track_analytics_event.send(user.username, 'opened learn page')

            table_path = table.path.replace('/table/', '/embed/')

        return { 'table_path': table_path }


class Support(BaseView):
    title = 'Support'
    template = 'ui/support.html'

    def get(self, request, *args, **kwargs):
        message = request.GET.get('message', '').strip()
        subject = request.GET.get('subject', '').strip()

        if request.user.is_authenticated:
            track_analytics_event.send(
                request.user.username,
                'opened support page'
            )

        context = self.get_context(request, *args, **kwargs)
        return render(request, self.template, {
            **context,
            'subject': subject,
            'message': message,
            'tickets': support_tickets_for_user(request.user),
        })

    def post(self, request):
        if not request.user.is_authenticated:
            return super().get(request)

        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()

        if (not subject) and (len(message) > 5):
            subject = message[:64].replace('\n', ' ')

        if len(subject) < 5 or len(message) < 5:
            return render(request, self.template, {
                'submitted': False,
                'error': ('Message or subject too short, '
                          'please be more descriptive.'),
                'subject': subject,
                'message': message,
            })

        ticket = ticket_from_support_page(subject, message, request.user)

        execute_mutations([
            *reward_swearing(request.user, subject + message),
            *reward_attempted_xss(request.user, subject + message)
        ])

        return render(request, self.template, {
            'submitted': True,
            'email': getattr(request.user, 'email', None),
            'subject': subject,
            'message': message,
            'ticket_id': ticket.short_id,
            'tickets': support_tickets_for_user(request.user),
        })


class Speedtest(BaseView):
    title = 'Speedtest'
    template = 'ui/speedtest.html'

    socket = SocketRouter()

    @socket.route('ECHO')
    def on_echo(self, content=None):
        self.send_action('ECHO', start_time=content['start_time'])

    @socket.route('SERVER_LATENCY_TEST')
    def on_server_test(self, content=None):
        self.setup_session()
        controller = featured_game()
        start_tablebeat(controller.table)
        table = controller.table

        # warm up the heartbeat process
        queue_tablebeat_dispatch(table.id, {'type': 'NOOP'})
        queue_tablebeat_dispatch(table.id, {'type': 'NOOP'})
        queue_tablebeat_dispatch(table.id, {'type': 'NOOP'})
        start_tablebeat(table)
        while peek_tablebeat_dispatch(table.id):
            sleep(0.1)

        # tests latency from here until controller.commit() is finished
        test_event = {
            'type': 'LATENCY_TEST',
            'socket_id': self.socket.id,
            'RECV_TIMESTAMP': timezone.now().timestamp(),
        }
        queue_tablebeat_dispatch(table.id, test_event)


class Home(PublicReactView):
    title = 'Home'
    component = 'pages/table.js'
    template = 'ui/table.html'
    socket = SocketRouter(handler=PokerWithChatSocketHandler)

    def props(self, request=None, autostart_tablebeat=True, **kwargs):
        user = request.user
        self.autostart_tablebeat = autostart_tablebeat
        self.controller = featured_game()
        accessor = self.controller.accessor
        table = self.controller.table

        logged_in_player = None
        if user.id and table.player_set.filter(user=user).exists():
            logged_in_player = accessor.player_by_user_id(user.id)

        gamestate = gamestate_json(self.controller.accessor,
                                   logged_in_player,
                                   self.controller.subscribers)

        target = table.tournament or table
        chat = [
            json_for_chatline(line, accessor=accessor)
            for line in target.chat_history.get_last_100()
        ] if target.chat_history is not None else []

        return {
            'gamestate': {
                'table': gamestate['table'],
                'players': gamestate['players'],
                'chat': chat,
                'timestamp': timezone.now().timestamp(),
            },
            'viewers': table.sockets.filter(active=True).count() or 1,
            'DEBUG': settings.DEBUG or user.is_staff,
        }

    def after_response(self, request=None, response=None):
        super().after_response(request=request, response=response)

        if self.autostart_tablebeat:
            start_tablebeat(self.controller.table)

class Table(PublicReactView):
    title = 'Table'
    component = 'pages/table.js'
    template = 'ui/table.html'
    socket = SocketRouter(handler=PokerWithChatSocketHandler)
    controller = None

    def get(self, request, id=None, name=None, autostart_tablebeat=True):
        # redirect to proper short game id if they used a shorter or
        #   longer version
        if not id:
            return redirect('Tables')

        try:
            self.controller = fuzzy_get_game(id)
        except (KeyError, ValueError):
            safe_id = sanitize_html(id, strip=True, allow_safe=False)
            return redirect(f'/tables/?search={safe_id}')

        if self.controller.table.is_archived:
            return redirect('Tables')

        self.autostart_tablebeat = autostart_tablebeat and not self.controller.table.tournament
        short_id = self.controller.table.short_id

        if id != short_id:
            return redirect('Table', id=short_id)

        toggle_sidebet = request.GET.get('sidebetting', None)
        if toggle_sidebet is not None and request.user.is_staff:
            stop_tablebeat(self.controller.table)
            PokerTable.objects.filter(id=self.controller.table.id)\
                              .update(sidebets_enabled=bool(toggle_sidebet))
            start_tablebeat(self.controller.table)

        return super().get(request, id)

    def props(self, request, id=None, **kwargs):
        user = request.user
        self.controller = self.controller or fuzzy_get_game(id)
        accessor = self.controller.accessor
        table = accessor.table
        player = None
        logged_in_player = None

        if user.id and any(p.user.id == user.id for p in table.player_set.all()):
            player = accessor.player_by_user_id(user.id)
            if player in accessor.seated_players():
                logged_in_player = player

        spectator = user if not logged_in_player else None

        gamestate = gamestate_json(accessor,
                                   logged_in_player,
                                   self.controller.subscribers,
                                   spectator)

        target = table.tournament or table
        chat = [
            json_for_chatline(line, accessor=accessor)
            for line in target.chat_history.get_last_100()
        ] if target.chat_history is not None else []

        has_access = (
            user.can_access_table(table.bb)
            if user.is_authenticated else
            (not table.tournament)
        )

        return {
            'gamestate': {
                'table': gamestate['table'],
                'players': gamestate['players'],
                'sidebets': gamestate.get('sidebets', []),
                'chat': chat,
                'timestamp': timezone.now().timestamp(),
                'last_stack_at_table': player.stack if player else None,
                'table_locked': not has_access,
            },
            'viewers': table.sockets.filter(active=True).count() or 1,
            'DEBUG': settings.DEBUG or user.is_staff,
        }

    def after_response(self, request=None, response=None):
        super().after_response(request=request, response=response)

        if self.autostart_tablebeat:
            start_tablebeat(self.controller.table)


class TableEmbed(Table):
    title = 'Table Embed'
    template = 'ui/react_base_bare.html'
    component = 'pages/table.js'
    socket = SocketRouter(handler=PokerWithChatSocketHandler)

    @xframe_options_exempt
    def get(self, request, id=None):
        try:
            table = fuzzy_get_table(id, only=('id',))
        except Exception:
            safe_id = sanitize_html(id, strip=True, allow_safe=False)
            msg = f'Table "{safe_id}" does not exist or is not embeddable.'
            raise Http404(msg)

        if id != table.short_id:
            return redirect('TableEmbed', id=table.short_id)
        return super().get(request, table.short_id)


class Sidebet(PublicReactView):
    title = 'Sidebet'
    component = 'pages/sidebet.js'
    socket = SocketRouter(handler=RoutedSocketHandler)

    @socket.route('UPDATE_SIDEBET')
    def on_update_sidebet(self, content=None):
        self.send_action('UPDATE_SIDEBET', **sidebets_dict(self.user))

    def get(self, request, search=''):
        return super().get(request)

    def props(self, request):
        return sidebets_dict(request.user)


def sidebets_dict(user):
    sidebets = list(get_sidebets(user).prefetch_related('table',
                                                        'player'))
    bets = []
    total = 0
    for sidebet in sidebets:
        total += sidebet.current_value() - sidebet.amt
        bets.append(sidebet.__json__())
    return {
        'bets': bets,
        'total': total,
        'tables': [
            {
                'name': 'Bounty Hold`em Omaha',
                'player': {
                    'username': 'YamiPoker',
                    'stack': 100
                },
                'amt': '1000',
                'odds': '1'
            }
        ]
    }


class TournamentSummary(PublicReactView):
    title = 'Tournament Summary'
    component = 'pages/tournament-summary.js'
    socket = SocketRouter(handler=TournamentSocketHandler)

    def get(self, request, id=None):
        # redirect to proper short game id if they used a shorter or
        #   longer version
        if not id:
            return redirect('Tables')

        try:
            self.tournament = Freezeout.objects.get(id__startswith=id)
        except Freezeout.DoesNotExist:
            return self._redirect_to_search(id)

        short_id = self.tournament.short_id

        if id != short_id:
            return redirect('TournamentSummary', id=short_id)

        return super().get(request, id)

    def _redirect_to_search(self, id):
        safe_id = sanitize_html(id, strip=True, allow_safe=False)
        return redirect(f'/tables/?search={safe_id}')

    def props(self, request, id=None, **kwargs):
        tournament = self.tournament
        entrants = tournament.get_entrants()

        chat = [
            json_for_chatline(
                line,
                tourney_entrants=[e['username']for e in entrants]
            )
            for line in tournament.chat_history.get_last_100()
        ] if tournament.chat_history else []

        players = dict()
        if self.tournament.status == TournamentStatus.STARTED.value:
            table = PokerTable.objects.get(tournament=self.tournament)
            controller = fuzzy_get_game(table.id)
            accessor = controller.accessor
            players = accessor.players_json()
        admin = tournament.tournament_admin
        return {
            'id': str(tournament.id),
            'name': tournament.name,
            'tourney_path': tournament.path,
            'table_path': tournament.table_path,
            'tournament_status': tournament.get_status_display(),
            'game_variant': tournament.variant,
            'max_entrants': tournament.max_entrants,
            'buyin_amt': tournament.buyin_amt,
            'entrants': entrants,
            'results': tournament.get_results(),
            'user_funds': request.user.userbalance().balance
                          if request.user.is_authenticated
                          else None,
            'tournament_admin': admin and admin.attrs('username'),
            'chat': chat,
            'players': ExtendedEncoder.convert_for_json(players),
            'is_private': tournament.is_private,
            'is_locked': not request.user.can_access_tourney(
                tournament.buyin_amt
            ) if request.user.is_authenticated else False,
        }


class FAQ(BaseView):
    title = 'FAQ'
    template = 'ui/faq.html'
