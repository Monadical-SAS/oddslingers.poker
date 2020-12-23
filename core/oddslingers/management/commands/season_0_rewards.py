import math

from django.db import transaction
from django.core.management.base import BaseCommand

from poker.constants import SEASONS
from rewards.models import Badge
from ui.views.leaderboard import top_users_by_winnings


class Command(BaseCommand):
    help = 'Award Season 0 leaderboard badges'

    def handle(self, **kwargs):
        start, end = SEASONS[0]

        top_users = top_users_by_winnings(
            from_date=start,
            to_date=end
        )

        users_amt = len(top_users)
        n_top_one_p = math.floor(users_amt * 0.01) - 10
        n_top_five_p = math.floor(users_amt * 0.05) - 10 - n_top_one_p

        top_badges = [
            'golden_season',
            'silver_season',
            'bronze_season',
            'season_top_5',
            'season_top_5',
            *['season_top_10'] * 5,
            *['season_one_percent'] * n_top_one_p,
            *['season_five_percent'] * n_top_five_p,
        ]

        with transaction.atomic():
            for nth, badge_name in enumerate(top_badges):
                Badge.objects.create(user=top_users[nth], name=badge_name)
                print(f'Badge created: {badge_name} for {top_users[nth]}')

        print('job done')
