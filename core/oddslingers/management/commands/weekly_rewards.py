from django.db import transaction
from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from poker.constants import SEASONS

from rewards.models import Badge
from ui.views.leaderboard import top_users_by_winnings


class Command(BaseCommand):
    help = 'Award weekly leaderboard badges'

    def handle(self, **kwargs):
        now = timezone.now()
        start = now - timezone.timedelta(days=7)

        season_start = SEASONS[settings.CURRENT_SEASON][0]
        start_of_the_week = max(season_start, start)

        top_users = top_users_by_winnings(
            from_date=start_of_the_week,
            to_date=now
        )
        log = ""

        with transaction.atomic():
            try:
                Badge.objects.create(
                    user=top_users[0],
                    name='golden_week',
                    season=settings.CURRENT_SEASON
                )
                log += f'Badge golden_week created for user {top_users[0]}\n'
                Badge.objects.create(
                    user=top_users[1],
                    name='silver_week',
                    season=settings.CURRENT_SEASON
                )
                log += f'Badge silver_week created for user {top_users[1]}\n'
                Badge.objects.create(
                    user=top_users[2],
                    name='bronze_week',
                    season=settings.CURRENT_SEASON
                )
                log += f'Badge bronze_week created for user {top_users[2]}\n'
            except IndexError:
                pass
        print(log)
