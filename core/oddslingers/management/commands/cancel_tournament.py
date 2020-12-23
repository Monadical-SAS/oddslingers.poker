from django.core.management.base import BaseCommand

from datetime import timedelta
from django.utils import timezone

from poker.models import PokerTournament, TournamentResult
from poker.constants import TOURNAMENT_CANCEL_HOURS, TournamentStatus



class Command(BaseCommand):
    help = 'Cancel a tournament, or all old tournaments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--old', 
            action='store_true', 
            default=False, 
            help='Cancel all old/inactive tournaments'
        )
        parser.add_argument(
            '-t', '--tournament-id',
            dest='tid',
            type=str,
            required=False,
        )

    def handle(self, *args, **options):
        objs_to_save = []
        if options['tid']:
            tournament = PokerTournament.objects.get(
                id__startswith=options['tid']
            )
            if not tournament:
                print(f'No tournament with id {options["tid"]} found')

            else:
                objs_to_save = tournament.on_cancel()

        elif options['old']:
            old = timezone.now() - timedelta(hours=TOURNAMENT_CANCEL_HOURS)
            old_tournaments = PokerTournament.objects.filter(
                created__lt=old, 
                status=TournamentStatus.PENDING.value
            )
            cancel_objs = [
                tournament.on_cancel()
                for tournament in old_tournaments
            ]
            objs_to_save = [obj for objs in cancel_objs for obj in objs]

        else:
            print('No tournament specified!')

        for obj in objs_to_save:
            if isinstance(obj, TournamentResult):
                print(f'Refunded {obj.payout_amt} chips to {obj.user}')
            elif isinstance(obj, PokerTournament):
                print(f'Canceled tournament with id {obj.id}')
            obj.save()
