from django.core.management.base import BaseCommand

from oddslingers.tasks import track_analytics_event

class Command(BaseCommand):
    help = 'Send an analytics event.'

    def add_arguments(self, parser):
        parser.add_argument('event', type=str, default=None)
        parser.add_argument('-u', '--username', type=str, required=False, default=None)
        parser.add_argument('-t', '--topic', type=str, required=False, default='Admin Commands')
        parser.add_argument('-s', '--stream', type=str, required=False, default='logs')

    def handle(self, *args, **options):
        track_analytics_event(options['username'],
                              options['event'],
                              options['topic'],
                              options['stream'])
