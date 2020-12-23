from uuid import UUID
from typing import List, Mapping
from collections import defaultdict

from django.db.models import Sum, Q, QuerySet, Count
from django.utils import timezone
from django.contrib.auth import get_user_model
# from django.core.cache import cache

from poker.models import PokerTable, Player, Freezeout
from poker.game_utils import featured_table, public_games
from poker.constants import BLINDS_SCHEDULE, TournamentStatus

from banker.utils import winnings


User = get_user_model()


def get_view_format_tables(tables=None, user: User = None,
                           extra: dict=None) -> List[dict]:
    extra = defaultdict(dict, extra or {})

    homepage_game = featured_table(only=('id',))
    tables = tables or public_games()\
                        .prefetch_related('stats')\
                        .order_by('created')

    players = (
        Player.objects
        .filter(table_id__in=tables, seated=True)
        .only('user__username', 'stack', 'position', 'table_id')
    )

    players_by_table: Mapping[UUID, List[Player]] = defaultdict(list)
    for player in players:
        players_by_table[player.table_id].append(player)

    return [
        {
            **extra[str(table.id)],
            'id': str(table.id),
            'path': table.path,
            'players': {
                int(player.position): {
                    'stack': int(player.stack),
                    'username': player.user.username,
                }
                for player in players_by_table[table.id]
            },
            'name': table.name,
            'variant': table.table_type,
            'displayable_variant': table.get_table_type_display(),
            'btn_idx': table.btn_idx,
            'sb_idx': table.sb_idx,
            'bb_idx': table.bb_idx,
            'sb': str(table.sb or 0),
            'bb': str(table.bb or 0),
            'min_buyin': str(table.min_buyin or 0),
            'num_seats': table.num_seats or 6,
            'table_type': table.table_type,
            'hand_number': table.hand_number,
            'stats': table.stats.__json__(),
            'created': table.created,
            'modified': table.modified,
            'stale': table.is_stale,
            'is_archived': table.is_archived,
            'featured': table.id == homepage_game.id,
            'new': table.is_new,
            'hotness_level': table.hotness_level,
            'is_locked': user.is_authenticated\
                         and not user.can_access_table(table.bb),
        }
        for table in tables
    ]


def get_visible_tournaments(user: User) -> List[dict]:
    tournaments = Freezeout.objects\
                           .exclude(status=TournamentStatus.FINISHED.value)\
                           .exclude(status=TournamentStatus.CANCELED.value)\
                           .exclude(is_private=True)\
                           .prefetch_related('entrants')\
                           .annotate(n_entrants=Count('entrants'))\
                           .order_by('-n_entrants')

    return [
        {
            'id': str(tournament.id),
            'is_tournament': True,
            'path': tournament.path,
            'entrants': tournament.get_entrants(),
            'name': tournament.name,
            'buyin_amt': tournament.buyin_amt,
            'sb': BLINDS_SCHEDULE[0][0],
            'bb': BLINDS_SCHEDULE[0][1],
            'max_entrants': tournament.max_entrants,
            'variant': tournament.game_variant,
            'displayable_variant': tournament.get_game_variant_display(),
            'is_locked': user.is_authenticated\
                         and not user.can_access_tourney(tournament.buyin_amt)
        }
        for tournament in tournaments
    ]

def search_tables(query: str) -> QuerySet:
    q_exp = Q(id__startswith=query) | Q(name__icontains=query)
    return PokerTable.objects.filter(q_exp, is_mock=False)

def winnings_this_week(user: User) -> int:
    one_week_ago = timezone.now() - timezone.timedelta(days=7)
    return winnings(user, one_week_ago) or 0

def chips_in_play_this_week(user: User) -> int:
    one_week_ago = timezone.now() - timezone.timedelta(days=7)
    stack_sum = Player.objects\
                       .filter(user=user, seated=True, table__modified__gt=one_week_ago)\
                       .aggregate(Sum('stack'))['stack__sum']
    return stack_sum or 0
