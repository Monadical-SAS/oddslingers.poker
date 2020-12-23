from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from oddslingers import kill_all_heartbeats
from oddslingers.models import UserStats, UserBalance
from oddslingers.settings import SIGNUP_BONUS, VETERAN_BONUS, CURRENT_SEASON

from banker.views import balance, buy_chips, create_transfer

from poker.models import PokerTable, PokerTournament
from poker.controllers import controller_type_for_table
from poker.constants import (
    TournamentStatus, SEASONS, CASH_GAME_BBS, TOURNEY_BUYIN_AMTS,
    N_BB_TO_NEXT_LEVEL, TOURNEY_BUYIN_TIMES
)
from poker.subscribers import BankerSubscriber, LogSubscriber
from poker.handhistory import DBLog

User = get_user_model()

def part_one():
    # PART ONE: archive tournaments and tables
    # RUN WITH PREVIOUS SEASON ACTIVE
    assert CURRENT_SEASON == 0, 'you can update this next year'

    now = timezone.now()
    last_season_end = SEASONS[CURRENT_SEASON][1]
    next_season_start = SEASONS[CURRENT_SEASON + 1][0]

    assert last_season_end >= now and now < next_season_start, \
            'This command must be run during the end of the last season.'

    assert now - last_season_end < timedelta(minutes=120), \
            'This command must be run during the end of the last season.'


    for user in User.objects.all():
        assert user.userbalance()
        assert user.userstats()

    for table in PokerTable.objects.filter(is_mock=False,
                                           is_tutorial=False,
                                           is_archived=False):
        assert table.stats

    with transaction.atomic():
        started_tourneys = PokerTournament.objects.filter(
            status=TournamentStatus.STARTED.value
        ).exists()
        if started_tourneys:
            raise Exception(
                'Let all tournaments finish before running this command!'
            )

        pending_tourneys = PokerTournament.objects.filter(
            status=TournamentStatus.PENDING.value
        )
        for tourney in pending_tourneys:
            print(f'{tourney} was pending; bumping players & closing.')
            for user in tourney.entrants.all():
                tourney.entrants.remove(user)
                xfer_objs = create_transfer(
                    tourney,
                    user,
                    tourney.buyin_amt,
                    "Season end -- forced tournament withdrawal"
                )
                for obj in xfer_objs:
                    obj.save()

            tourney.status = TournamentStatus.FINISHED.value
            tourney.save()

        relevant_tables = PokerTable.objects.filter(
            is_tutorial=False,
            is_archived=False,
            is_mock=False,
        )
        for table in relevant_tables:
            print(f'Checking {table} for players to kick...')
            ctrl = controller_type_for_table(table)(
                table,
                subscribers=[],
                broadcast=False,
                log=None,
            )
            ctrl.log = DBLog(ctrl.accessor)
            ctrl.subscribers = [
                BankerSubscriber(ctrl.accessor),
                LogSubscriber(ctrl.log),
            ]
            ctrl.step()
            kicked = False

            while ctrl.accessor.next_to_act() is not None:
                nxt = ctrl.accessor.next_to_act()
                ctrl.dispatch_player_leave_table(nxt, broadcast=False)
                print(f'{nxt} was kicked')
                kicked = True

            while ctrl.accessor.seated_players():
                nxt = ctrl.accessor.seated_players()[0]
                ctrl.dispatch_player_leave_table(nxt, broadcast=False)
                print(f'{nxt} was kicked')
                kicked = True

            if kicked:
                print('Table final state:')
                ctrl.describe()

            table.is_archived = True
            table.save()

        now = timezone.now()
        print(
            f'set SEASONS[{CURRENT_SEASON}] in poker/constants.py to:\n'
            f'datetime(year={now.year}, month={now.month}, '
            f'day={now.day}, hour={now.hour}, minute={now.minute}, '
            f'second={now.second}, tzinfo=pytz.utc)\n'
            'and then re-run this command.'
        )


def part_two():
    assert CURRENT_SEASON == 1, 'you can update this next year'

    pending_tourneys = PokerTournament.objects.filter(
        status=TournamentStatus.PENDING.value
    )
    started_tourneys = PokerTournament.objects.filter(
        status=TournamentStatus.STARTED.value
    )
    open_tables = PokerTable.objects.filter(
        is_tutorial=False,
        is_archived=False,
        is_mock=False,
    )
    assert not pending_tourneys, 'run part 1 first'
    assert not started_tourneys, 'run part 1 first'
    assert not open_tables, 'run part 1 first'

    # PART TWO: reset balances & issue starting chips
    # RUN WITH NEW SEASON
    with transaction.atomic():
        for user in User.objects.all():
            UserStats.objects.create_for_current_season(user)
            UserBalance.objects.create_for_current_season(user)

            if balance(user) == 0:
                starting_buy = buy_chips(
                    user,
                    SIGNUP_BONUS,
                    f'Season {CURRENT_SEASON} starting chips',
                )
                for obj in starting_buy:
                    obj.save()


                if balance(user, season=CURRENT_SEASON - 1) > VETERAN_BONUS:
                    veteran_bonus_buy = buy_chips(
                        user,
                        VETERAN_BONUS,
                        f'Season {CURRENT_SEASON - 1} veteran bonus'
                    )
                    for obj in veteran_bonus_buy:
                        obj.save()

                    userstats = user.userstats()
                    userstats.games_level = max(
                        CASH_GAME_BBS[1] * N_BB_TO_NEXT_LEVEL,
                        TOURNEY_BUYIN_AMTS[1] * TOURNEY_BUYIN_TIMES,
                    )
                    userstats.save()


    for user in User.objects.all():
        assert user.userbalance()
        assert user.userstats()


class Command(BaseCommand):
    help = (
        'Create database objects necessary to start a new poker season, '
        'use it after you already changed settings.CURRENT_SEASON value. '
        'Set the start datetime of the next season to something in the '
        'future and run this. Any reward scripts should be run after '
        'PART TWO is complete, and before starting services up again.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '-1',
            '--part_1',
            dest='part_1',
            help='part one of the migration. should be run at the '\
                 'end of the ending season.',
        )
        parser.add_argument(
            '-2',
            '--part_2',
            dest='part_2',
            help='part two of the migration. should be run at the '\
                 'beginning of the starting season.',
        )

    def handle(self, *args, **options):
        if options['part_1']:
            kill_all_heartbeats()
            part_one()

        if options['part_2']:
            kill_all_heartbeats()
            part_two()

        self.stdout.write(self.style.SUCCESS(
            'Command successfully executed'
        ))
