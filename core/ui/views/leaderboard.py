import os
import json
import logging
from typing import List, Dict, Any

from django.db.models import Q, Sum, QuerySet, Prefetch
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.conf import settings

from oddslingers.utils import ExtendedEncoder, sanitize_html
from oddslingers.models import User
from oddslingers.mutations import execute_mutations

from rewards.models import Badge
from banker.utils import get_timing_kwargs
from banker.models import BalanceTransfer

from poker.models import PokerTable, Freezeout
from poker.constants import SEASONS

from rewards.mutations import check_xss_swearing

from .base_views import PublicReactView

logger = logging.getLogger('poker')


class Leaderboard(PublicReactView):
    title = 'Leaderboard'
    component = 'pages/leaderboard.js'
    custom_stylesheet = 'leaderboard.css'

    def get(self, request, *args, **kwargs):
        if not request.GET.get('props_json'):
            execute_mutations(
                check_xss_swearing(request.user, request.GET)
            )
        return super(Leaderboard, self).get(request, *args, **kwargs)

    def props(self, request):
        query = sanitize_html(request.GET.get('search', '').strip())
        base_response = {
            'total_users': User.objects.filter(is_robot=False).count(),
        }

        # When searching we send only simple profiles without collecting stats
        if query:
            users = users_matching_search(query)
            return {
                **base_response,
                'current_top': [
                    {
                        'id': user.id,
                        'username': user.username,
                        'profile_image': user.profile_image,
                        'badge_count': user.badge_count(),
                    }
                    for user in users
                ],
            }

        # Full Version, commenteded until optimized to be faster
        # top_users_tw = top_users_this_week()
        # top_users_lw = top_users_last_week()
        # full_leaderboard = {
        #     **base_response,
        #     'current_top': [
        #         leaderboard_user_json(user, ranking)
        #         for ranking, user in enumerate(top_users_tw)
        #     ],
        #     'past_top': [
        #         leaderboard_user_json(user, ranking)
        #         for ranking, user in enumerate(top_users_lw)
        #     ],
        #     'seasons': [
        #         [
        #             leaderboard_user_json(user, ranking)
        #             for ranking, user in enumerate(season)
        #         ] for season in top_users_all_seasons()
        #     ],
        # }

        cached_info = load_leaderboard_cache()
        return {
            **base_response,
            **cached_info,
            'last_top': [],
        }


def save_leaderboard_cache():
    """
    Save the cached leaderboard data so we don't have to do a query every time.

    Generate the cache file in advance using ./manage.py save_leaderboard_cache
    """
    badge_counts = [
        {
            str(user.id): user.badge_count(season=season)
            for user in User.objects.all()
        }
        for season in range(settings.CURRENT_SEASON + 1)
    ]
    leaderboard_props = {
        'seasons': [
            [
                leaderboard_user_json(
                    user,
                    ranking,
                    badge_counts[0],
                    include_tables=False
                )
                for ranking, user in enumerate(top_users_in_season(0))
            ],
            [
                leaderboard_user_json(user, ranking, badge_counts[settings.CURRENT_SEASON])
                for ranking, user in enumerate(top_users_in_season())
            ],
        ],
        'current_top': [
            leaderboard_user_json(user, ranking, badge_counts[settings.CURRENT_SEASON])
            for ranking, user in enumerate(top_users_this_week())
        ],
    }

    cache_path = os.path.join(settings.CACHES_DIR,
                              settings.LEADERBOARD_CACHE_PATH)
    with open(cache_path, 'w+') as f:
        json.dump(leaderboard_props, f, cls=ExtendedEncoder)


def load_leaderboard_cache() -> dict:
    """
    Load the cached leaderboard data so we don't have to do a query every time.
    """

    leaderboard_cache: dict = {}
    cache_path = os.path.join(settings.CACHES_DIR,
                              settings.LEADERBOARD_CACHE_PATH)
    try:
        with open(cache_path, 'r') as f:
            leaderboard_cache = json.load(f)
    except Exception as e:
        logger.warning(
            'Past seasons data from data/caches was missing, had to recreate',
            extra={
                'exception': f'{e.__class__.__name__}: {e}',
                'leaderboard_cache_file': cache_path,
            },
        )
        save_leaderboard_cache()
        with open(cache_path, 'r') as f:
            leaderboard_cache = json.load(f)

    return leaderboard_cache


def leaderboard_user_json(user: User,
                          ranking: int,
                          badge_counts: Dict,
                          include_tables: bool=True) -> Dict[str, Any]:
    recent_winnings = getattr(user, 'recent_winnings', 0)
    return {
        'id': user.id,
        'username': user.username,
        'ranking': ranking if recent_winnings else 9999999999,
        'winnings': recent_winnings,
        'profile_image': user.profile_image,
        'badge_count': badge_counts.get(str(user.id), 0),
        'tables': (
            leaderboard_tables_json(user)
            if ranking < 10 and include_tables
            else None
        ),
    }


def leaderboard_tables_json(user: User) -> List[Dict[str, Any]]:
    leaderboard_expiry = timezone.timedelta(
        days=settings.LEADERBOARD_PAGE_TIME_RANGE
    )
    days_ago = timezone.now() - leaderboard_expiry
    return [
        {
            'id': table.id,
            'path': table.path,
            'name': table.name,
        }
        for table in PokerTable.objects
            .filter(
                player__user_id=user.id,
                modified__gt=days_ago,
                is_archived=False,
                is_mock=False,
                is_tutorial=False,
                is_private=False,
            )
            .only('name')[:4]
    ]


def users_matching_search(query: str) -> QuerySet:
    return (
        User.objects.filter(
            Q(id__startswith=query)
            | Q(username__icontains=query)
        )
        .order_by('username')
        .prefetch_related(
            Prefetch(
                'badge_set',
                queryset=Badge.objects.all().only('user_id', 'id'),
            ),
        )
    )


def top_users_all_seasons() -> dict:
    """
    Returns a list of the top users of all seasons
    """
    seasons_amt = settings.CURRENT_SEASON + 1

    tops = []
    for season in range(seasons_amt):  # Season 0 counts
        tops.append(top_users_in_season(season))
    return tops


def top_users_in_season(season_number=settings.CURRENT_SEASON) -> dict:
    """
    Returns the top users of the given season_number
    """
    season_range = SEASONS[season_number]
    season_start, season_end = season_range

    return top_users_by_winnings(from_date=season_start, to_date=season_end)


def top_users_this_week() -> dict:
    """
    Returns the top users of the current week starting last
    sunday 00:00
    """
    today = timezone.now()
    sunday_idx = (today.weekday() + 1) % 7 # weekday returns 0 for monday
    sunday = today - timezone.timedelta(days=sunday_idx)
    sunday = sunday.replace(hour=0, minute=0, second=0, microsecond=0)

    season_start = SEASONS[settings.CURRENT_SEASON][0]
    start_of_the_week = max(season_start, sunday)

    return top_users_by_winnings(from_date=start_of_the_week)

def top_users_last_week() -> dict:
    """
    Returns the top users of the last week starting past
    sunday 00:00
    """
    today = timezone.now().date()  # 0 seconds, 0 ms, etc
    sunday_idx = (today.weekday() + 1) % 7 # weekday returns 0 for monday
    sunday = today - timezone.timedelta(days=sunday_idx)
    past_sunday = sunday - timezone.timedelta(days=7)

    return top_users_by_winnings(from_date=past_sunday, to_date=sunday)


def top_users_by_winnings(last_days=None,
                          from_date=None,
                          to_date=None,
                          max_users=100) -> dict:
    tabletype = ContentType.objects.get_for_model(PokerTable)
    freezeouttype = ContentType.objects.get_for_model(Freezeout)
    usertype = ContentType.objects.get_for_model(User)

    if last_days is None and from_date is None and to_date is None:
        timing_kwargs = {}
    else:
        now = timezone.now()
        if from_date is None:
            from_date = now - timezone.timedelta(days=last_days)

        if to_date is None:
            to_date = now

        timing_kwargs = get_timing_kwargs(from_date, to_date)

    # collect all balance transfers for the week, group and sum by dest/src
    debits_by_user = {
        debits['source_id']: debits['total']
        for debits in BalanceTransfer.objects
                                     .filter(Q(dest_type=tabletype)
                                             | Q(dest_type=freezeouttype),
                                             source_type=usertype,
                                             **timing_kwargs)
                                     .values('source_id')
                                     .annotate(total=Sum('amt'))
    }
    credits_by_user = {
        credits['dest_id']: credits['total']
        for credits in BalanceTransfer.objects
                                      .filter(Q(source_type=tabletype)
                                              | Q(source_type=freezeouttype),
                                              dest_type=usertype,
                                              **timing_kwargs)
                                      .values('dest_id')
                                      .annotate(total=Sum('amt'))
    }

    user_nets = users_current_net(credits_by_user, debits_by_user)

    top_users = []
    sorted_by_winnings = sorted(
        user_nets.items(),
        key=lambda u: -u[1]
    )[:max_users]
    user_objs = {
        u.id: u
        for u in User.objects
            .filter(id__in=[uid for uid, _ in sorted_by_winnings])
            .only('username', 'profile_picture')
    }
    for user_id, winnings in sorted_by_winnings:
        user_obj = user_objs[user_id]
        # this is to temporarily remove Fredlocks from leaderboards
        # (except season 0)
        #   until we deal with the bug where he got a bunch of chips
        if user_obj.username == 'Fredlocks' and from_date != SEASONS[0][0]:
            continue
        user_obj.recent_winnings = winnings
        top_users.append(user_obj)

    return top_users


def users_current_net(credits: dict, debits: dict) -> dict:
    """
    Return an object with the current net of users
    """
    user_nets = {}
    for user_id in credits.keys():
        user = User.objects.get(id=user_id)
        if user.is_robot:
            continue

        user_credits = credits.get(user_id, 0)
        user_debits = debits.get(user_id, 0)

        current_winnings = user.player_set\
                               .filter(seated=True)\
                               .aggregate(Sum('stack'))['stack__sum'] or 0

        user_credits += current_winnings
        net = user_credits - user_debits

        if net > 0:
            user_nets[user_id] = net

    return user_nets
