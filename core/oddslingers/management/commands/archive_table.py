from django.core.management.base import BaseCommand

from poker.models import PokerTable
from poker.game_utils import suspend_table
from poker.tablebeat import stop_tablebeat


class Command(BaseCommand):
    help = 'Set a PokerTable to is_archived=True'

    def add_arguments(self, parser):
        parser.add_argument('table_id', type=str)

    def handle(self, table_id):
        table = PokerTable.objects.get(id__startswith=table_id)
        table.is_archived = True
        table.save()
        suspend_table(table)
        stop_tablebeat(table)
