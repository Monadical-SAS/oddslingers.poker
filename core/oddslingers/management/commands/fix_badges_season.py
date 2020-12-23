from django.db import transaction
from django.db.models import Q
from django.conf import settings
from django.core.management.base import BaseCommand

from poker.constants import SEASONS

from rewards.models import Badge

class Command(BaseCommand):
    help = 'Fix Current Badge Season'

    def handle(self, *args, **kwargs):
        season_start = SEASONS[settings.CURRENT_SEASON][0]
        badges_to_fix = Badge.objects\
                             .filter(created__gte=season_start)\
                             .exclude(Q(name__icontains='season')
                                     | Q(name__icontains='week'))

        with transaction.atomic():
            for badge in badges_to_fix:
                badge.season = 1
                badge.save()
                print(
                    f'badge {badge.name} updated '
                    f'to season {settings.CURRENT_SEASON} '
                    f'for user {badge.user}'
                )

        print(f'{badges_to_fix.count()} badges fixed')
