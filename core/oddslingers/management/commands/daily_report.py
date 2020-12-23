from django.core.management.base import BaseCommand

from oddslingers.tasks import daily_report

class Command(BaseCommand):
    help = 'Run the daily analytics report.'

    def handle(self, *args, **kwargs):
        print(daily_report(send_zulip=True))
