from django.core.management.base import BaseCommand

from oddslingers import kill_all_heartbeats


class Command(BaseCommand):
    help = 'Bring all tables to a safe stopping point and kill the heartbeats.'

    def handle(self, *args, **options):
        # 0. Stop heartbeats from accepting new input

        # TODO

        # 1. Make tables finish processing all existing input

        # TODO

        # 2. (Optional) bring tables to an END_HAND state

        # TODO

        # 3. Stop all tablebeat and botbeat processes
        kill_all_heartbeats()

        # 4. Back up all data

        # TODO
