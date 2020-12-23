from datetime import timedelta
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from poker.models import PokerTable
from poker.controllers import controller_for_table
from poker.tablebeat import tablebeat_pid

logger = logging.getLogger('command')


def bump_all_inactives():
    recent = timezone.now() - timedelta(minutes=30)
    old_tbls = PokerTable.objects\
                         .filter(is_mock=False,
                                 last_action_timestamp__lt=recent)\
                         .exclude(name__icontains='tutorial')

    for old_tbl in old_tbls:
        logger.info(f'Checking table {old_tbl.short_id} for inactivity...')
        ctrl = controller_for_table(old_tbl)
        if tablebeat_pid(old_tbl) is None:
            plyrs = ctrl.bump_inactive_humans()
            ctrl.commit(broadcast=True)
            for plyr in plyrs:
                logger.info(f'\tbumped {plyr} due to inactivity')

class Command(BaseCommand):
    help = 'Boot players from tables if they have been inactive for 1hr'

    def handle(self, *args, **kwargs):
        bump_all_inactives()
