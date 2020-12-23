from django.core.management.base import BaseCommand

from poker.tablebeat import tablebeat_entrypoint


class Command(BaseCommand):
    help = 'Start a heartbeat process for the specified table'

    def add_arguments(self, parser):
        parser.add_argument('table_id', type=str)
        parser.add_argument(
            '--daemonize',
            action='store_true',
            dest='daemonize',
            default=False,
            help='Double fork to daemonize the heartbeat'
        )

    def handle(self, *args, **kwargs):
        tablebeat_entrypoint(*args, **kwargs)
