from django.core.management.base import BaseCommand

from poker.botbeat import botbeat_entrypoint


class Command(BaseCommand):
    help = 'Start a heartbeat process to process bot (AI) moves'

    def add_arguments(self, parser):
        parser.add_argument('--daemonize', action='store_true', dest='daemonize', default=False, help='Double fork to daemonize the heartbeat')
        parser.add_argument('--stupid', action='store_true', dest='stupid', default=False, help='Use stupid AI')

    def handle(self, *args, **kwargs):
        botbeat_entrypoint(*args, **kwargs)
