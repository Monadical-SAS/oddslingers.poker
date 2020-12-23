from datetime import datetime
from decimal import Decimal
import pytz

from django.conf import settings
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from oddslingers.tests.test_utils import TimezoneMocker
from oddslingers.models import UserStats, UserBalance
from oddslingers.subscribers import UserStatsSubscriber
from oddslingers.mutations import execute_mutations

from banker.models import BalanceTransfer
from banker.mutations import buy_chips

from poker.tests.test_controller import TableWithChipsTest, GenericTableTest


User = get_user_model()
utc = pytz.utc


class TestSeasonManager(TestCase):
    def setUp(self):
        super().setUp()
        self.user1 = User.objects.create_user(
            username='user1',
            email='user1@example.com',
            password='user1'
        )
        self.user2 = User.objects.create_user(
            username='user2',
            email='user2@example.com',
            password='user2'
        )

    def test_seasons_on_balance_transfers(self):
        # Random date in 2019 (Season 1)
        with TimezoneMocker(datetime(year=2019, month=7, day=25, tzinfo=utc)):
            xfer_1 = BalanceTransfer.objects.create(
                source=self.user1,
                dest=self.user2,
                amt=Decimal(1000),
                notes='test xfer'
            )
            xfer_2 = BalanceTransfer.objects.create(
                source=self.user1,
                dest=self.user2,
                amt=Decimal(1000),
                notes='test xfer'
            )

        # Random date in 2018 (Season 0)
        with TimezoneMocker(datetime(year=2017, month=4, day=25, tzinfo=utc)):
            xfer_3 = BalanceTransfer.objects.create(
                source=self.user1,
                dest=self.user2,
                amt=Decimal(1000),
                notes='test xfer'
            )

        # Random date in 2016 (Season 0)
        with TimezoneMocker(datetime(year=2016, month=5, day=2, tzinfo=utc)):
            xfer_4 = BalanceTransfer.objects.create(
                source=self.user1,
                dest=self.user2,
                amt=Decimal(1000),
                notes='test xfer'
            )

        # Season 1 asserts
        assert xfer_1 in BalanceTransfer.objects.season(1)
        assert xfer_2 in BalanceTransfer.objects.season(1)
        assert xfer_3 not in BalanceTransfer.objects.season(1)
        assert xfer_4 not in BalanceTransfer.objects.season(1)

        # Season 0 asserts
        assert xfer_1 not in BalanceTransfer.objects.season(0)
        assert xfer_2 not in BalanceTransfer.objects.season(0)
        assert xfer_3 in BalanceTransfer.objects.season(0)
        assert xfer_4 in BalanceTransfer.objects.season(0)

    def tearDown(self):
        super().tearDown()
        User.objects.all().delete()
        BalanceTransfer.objects.all().delete()


class TestSeasonRegularManager(TestCase):
    def setUp(self):
        super().setUp()
        self.user = User.objects.create(
            username='user1',
            email='user1@example.com',
            password='user1'
        )

    def test_user_stats_per_season(self):
        SEASON_HANDS = {
            0: 100,
            1: 300
        }
        season_0_stats, _ = UserStats.objects.create_for_season(0, self.user)
        season_0_stats.hands_played = SEASON_HANDS[0]
        season_0_stats.save()
        season_1_stats, _ = UserStats.objects.create_for_season(1, self.user)
        season_1_stats.hands_played = SEASON_HANDS[1]
        season_1_stats.save()

        # Make sure season methods work as expected
        season_0 = UserStats.objects.season(0)
        assert season_0.count() == 1
        assert season_0.first().hands_played == 100

        season_1 = UserStats.objects.season(1)
        assert season_1.count() == 1
        assert season_1.first().hands_played == 300

        # Make sure userstats property from User model works by default with
        # current season
        assert self.user.userstats().hands_played\
               == SEASON_HANDS[settings.CURRENT_SEASON]


    def test_user_balance_per_season(self):
        SEASON_BALANCE = {
            0: Decimal(1000),
            1: Decimal(2000)
        }
        season_0_balance, _ = UserBalance.objects.create_for_season(
            0,
            self.user
        )
        season_0_balance.balance = SEASON_BALANCE[0]
        season_0_balance.save()
        season_1_balance, _ = UserBalance.objects.create_for_season(
            1,
            self.user
        )
        season_1_balance.balance = SEASON_BALANCE[1]
        season_1_balance.save()

        # Make sure season methods work as expected
        season_0 = UserBalance.objects.season(0)
        assert season_0.count() == 1
        assert season_0.first().balance == SEASON_BALANCE[0]

        season_1 = UserBalance.objects.season(1)
        assert season_1.count() == 1
        assert season_1.first().balance == SEASON_BALANCE[1]

        # Make sure balance property from User model works by default with
        # current season
        assert self.user.userbalance().balance\
               == SEASON_BALANCE[settings.CURRENT_SEASON]


@override_settings(CURRENT_SEASON=1)
class SeasonedBalanceUpdatesTest(TableWithChipsTest):
    def test_balance_updates(self):
        new_user = get_user_model().objects.create_user(
            username='new_user',
            email='new_user@hello.com',
            password='banana'
        )
        # Season 0 UserBalance object
        UserBalance.objects.create_for_season(0, new_user)

        execute_mutations(
            buy_chips(new_user, 5000)
        )

        assert new_user.userbalance().balance == 5000
        self.controller.dispatch(
            'join_table',
            user_id=new_user.id,
            buyin_amt=200
        )
        new_plyr = self.accessor.player_by_user_id(new_user.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000 - 200
        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000
        self.controller.dispatch(
            'join_table',
            user_id=new_user.id,
            buyin_amt=200
        )
        new_plyr = self.accessor.player_by_user_id(new_user.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000 - 200
        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000

        # Season checks
        assert new_user.userbalance().season == 1
        season_0_balance = UserBalance.objects.season(0)\
                                              .filter(user=new_user)\
                                              .first()
        assert season_0_balance.balance == 0
        # Emulate the moment when the admin manually changes the season
        with self.settings(CURRENT_SEASON=0):
            assert new_user.userbalance().season == 0
            assert new_user.userbalance().balance == 0


@override_settings(CURRENT_SEASON=1)
class SeasonedTestUserStatsSubscriber(GenericTableTest):
    def test_hands_played(self):
        """Test if each hand is correctly counted in the specific season"""

        # Create UserStats object for season 0
        for player in self.players:
            UserStats.objects.create_for_season(0, player.user)

        self.user_stats_sub = UserStatsSubscriber(self.accessor)
        self.controller.subscribers.append(self.user_stats_sub)
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()
        self.controller.commit()

        #import ipdb; ipdb.set_trace()
        for _ in range(30):
            self.controller.dispatch(
                'FOLD', player_id=self.accessor.next_to_act().id)
        for player in self.accessor.active_players():
            player.user.refresh_from_db()
            # In 30 folds for a 4 players table we will have 10 hands played
            assert player.user.userstats().hands_played == 10
            assert player.user.userstats().season == 1
            season_0_stats = UserStats.objects.season(0)\
                                              .filter(user=player.user)\
                                              .first()
            assert season_0_stats.hands_played == 0
            # Emulate the moment when the admin manually changes the season
            with self.settings(CURRENT_SEASON=0):
                assert player.user.userstats().season == 0
                assert player.user.userstats().hands_played == 0
