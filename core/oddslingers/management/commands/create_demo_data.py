import random

from django.conf import settings
from django.core.management.base import BaseCommand

from poker.constants import TABLE_TYPES
from poker.game_utils import make_game


class Command(BaseCommand):
    help = 'Create demo data for development devices'

    def add_arguments(self, parser):
        parser.add_argument('--num', '-n', type=int, required=False, default=15)

    def handle(self, *args, **options):
        if not settings.DEBUG:
            print('Cannot be run on production! (DEBUG=False)')
            raise SystemExit(1)

        n_games = 25
        num_bots = 5

        print(f'Creating {n_games} games with 1-{num_bots} bots each.')
        for n in range(n_games):
            table_type = random.choice(TABLE_TYPES)

            num_bots = random.choice(range(1, num_bots+1))
            sb = random.choice((1, 2, 5, 50, 100))
            options = {
                'table_type': table_type[0],
                'sb': sb,
                'bb': 2 * sb,
                'num_seats': min(max(random.choice(range(2, 7)), num_bots+1), 6),
            }

            make_game(f"{table_type[1]} #{n+1}",
                      defaults=options,
                      num_bots=num_bots)
