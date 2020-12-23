from django.http import JsonResponse
from django.db.models import Count
from django.conf import settings

from rewards.mutations import check_xss_swearing

from poker.models import PokerTable, Freezeout
from poker.views.utils import get_view_format_tables, get_visible_tournaments
from poker.tablebeat import start_tablebeat

from poker.game_utils import (
    public_games, make_game, make_tournament,
)

from poker.constants import (
    CASH_GAME_BBS, TOURNEY_BUYIN_AMTS,
    THRESHOLD_BB_FOR_BOTS, THRESHOLD_BB_EMAIL_VERIFIED
)

from oddslingers.mutations import execute_mutations
from oddslingers.tasks import track_analytics_event
from oddslingers.utils import sanitize_html, require_login

from .base_views import PublicReactView


def tables_page_tables():
    return (
        public_games()
            .prefetch_related('stats')
            .annotate(num_players=Count('player'))
            .order_by('-num_players', '-last_human_action_timestamp')
    )


class Tables(PublicReactView):
    title = 'Tables'
    component = 'pages/tables.js'

    def props(self, request):
        tables = list(tables_page_tables())
        return {
            'tables': get_view_format_tables(tables, request.user),
            'tournaments': get_visible_tournaments(request.user),
            'cash_game_bbs': CASH_GAME_BBS,
            'tourney_buyin_amts': TOURNEY_BUYIN_AMTS,
            'threshold_bb_email_verified': THRESHOLD_BB_EMAIL_VERIFIED,
            'games_level_number': request.user.games_level_number if request.user.is_authenticated else 1,
        }

    def get(self, request, *args, **kwargs):
        if not request.GET.get('props_json'):
            execute_mutations(
                check_xss_swearing(request.user, request.GET)
            )
        return super(Tables, self).get(request, *args, **kwargs)

    @require_login
    def post(self, request, autostart_tablebeat=True):
        table_params = validate_table_form(request)
        is_tourney = table_params['is_tournament']
        redirect_path = ''
        zulip_topic = None

        if is_tourney:
            can_create = request.user.can_access_tourney(
                table_params['min_buyin']
            )
            assert can_create, (
                f"{request.user.username} cant create tournaments "
                f"with {table_params['min_buyin']} buyin"
            )
            tournament = make_tournament(
                defaults={
                    **table_params,
                    'created_by': request.user,
                    'tournament_admin': request.user
                },
                user=request.user
            )
            redirect_path = tournament.path
            zulip_topic = tournament.zulip_topic
        else:
            can_create = request.user.can_access_table(table_params['bb'])
            assert can_create, (
                f"{request.user.username} cant create tables "
                f"with {table_params['sb']}/{table_params['bb']} blinds"
            )
            controller = make_game(
                table_params['table_name'],
                defaults={
                    'num_seats': table_params['num_seats'],
                    'sb': table_params['sb'],
                    'bb': table_params['bb'],
                    'table_type': table_params['table_type'],
                    'created_by': request.user,
                    'is_private': table_params['is_private'],
                    'min_buyin': table_params['min_buyin'],
                    'max_buyin': table_params['max_buyin'],
                },
                num_bots=table_params['num_bots'],
                with_user=request.user
            )
            if autostart_tablebeat:
                start_tablebeat(controller.table)

            redirect_path = controller.table.path
            zulip_topic = controller.table.zulip_topic

        created_type = 'tournament' if is_tourney else 'table'
        the_link = f'{settings.DEFAULT_HTTP_PROTOCOL}://{settings.DEFAULT_HOST}{redirect_path}'
        track_analytics_event.send(
            request.user.username,
            f'created new {created_type} [{table_params["table_name"]}]({the_link})',
            topic=zulip_topic,
            stream="Tournaments" if is_tourney else "Tables"
        )
        return JsonResponse({'path': redirect_path})

def validate_table_form(request):
    table_type = request.POST.get('table_type', 'NLHE')
    table_name = request.POST.get('table_name', None)
    sb = int(request.POST.get('sb') or 1)
    bb = int(request.POST.get('bb') or 2)
    num_seats = int(request.POST.get('num_seats') or 6)
    num_bots = int(request.POST.get('num_bots') or 0)
    is_tournament = request.POST.get('is_tournament', False) == 'true'
    is_private = request.POST.get('is_private', False) == 'true'
    default_buyin = TOURNEY_BUYIN_AMTS[0] if is_tournament else 100
    min_buyin = int(request.POST.get('min_buyin', default_buyin))

    assert (not table_name) or (3 <= len(table_name) <= 64)
    assert 0 < sb < 1000000000  # 1_000_000_000
    assert 0 < bb < 2000000000  # 2_000_000_000
    assert 2 <= num_seats <= 6
    assert 0 <= num_bots <= num_seats

    if num_bots > 0:
        assert bb <= THRESHOLD_BB_FOR_BOTS, (
            "Trying to add bots to high stakes table"
        )
    if num_bots and sb > 1 and table_type == 'PLO':
        raise AssertionError(
            "Can't add bots to PLO games with blinds bigger than 1/2"
        )

    if is_tournament:
        assert min_buyin >= TOURNEY_BUYIN_AMTS[0]
    else:
        assert min_buyin >= 0

    if not table_name:
        table_name = generate_table_name(request.user, is_tournament)
    else:
        execute_mutations(
            check_xss_swearing(request.user, dict(request.POST))
        )

        table_name = sanitize_html(
            table_name,
            strip=True,
            allow_safe=False
        )
        table_name = dedupe_table_name(table_name)

    return {
        'table_name': table_name,
        'num_bots': num_bots,
        'num_seats': num_seats,
        'sb': sb,
        'bb': bb,
        'min_buyin': min_buyin,
        'max_buyin': 200*bb,
        'table_type': table_type,
        'created_by': request.user,
        'is_tournament': is_tournament,
        'is_private': is_private,
    }


def generate_table_name(user, is_tournament=False):
    element_label = 'Tournament' if is_tournament else 'Table'
    user_table_str = f"{user.username}'s {element_label} #"

    # get lowest available table number
    num_tables = 1
    table_name = f"{user_table_str}{num_tables}"
    tables = set(
        PokerTable.objects
                  .filter(name__startswith=user_table_str)
                  .values_list('name', flat=True)
    )
    tournaments = set(
        Freezeout.objects
                 .filter(name__startswith=user_table_str)
                 .values_list('name', flat=True)
    )
    elements = tournaments if is_tournament else tables
    while table_name in elements:
        num_tables += 1
        table_name = f'{user_table_str}{num_tables}'
    return table_name


def dedupe_table_name(name):
    table_names = set(
        PokerTable.objects
                  .filter(name__startswith=name)
                  .values_list('name', flat=True)
    )
    tournament_names = set(
        Freezeout.objects
                 .filter(name__startswith=name)
                 .values_list('name', flat=True)
    )
    all_names = table_names | tournament_names

    if all_names:
        return f'{name} #{len(all_names)}'
    return name
