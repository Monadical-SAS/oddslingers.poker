from django.utils import timezone
from django.core.management.base import BaseCommand

from oddslingers.tasks import check_server_load


class Command(BaseCommand):
    help = 'Make sure the server is not overloaded, restarts procs if needed.'

    def handle(self, *args, **kwargs):
        warnings, curent_stats = check_server_load(warn_zulip=True,
                                                   restart_heartbeats=True)

        timestamp = timezone.now().strftime('%Y-%m-%d.%H-%M-%S')
        stats_str = ', '.join(
            f'{desc}: {val}% capacity'
            for desc, val in curent_stats.items()
        )

        if warnings:
            warnings_str = ' '.join(warnings)
            print(f'[{timestamp}]: {stats_str}. {warnings_str} ')
        else:
            print(f'[{timestamp}]: {stats_str}. Load is healthy.')
