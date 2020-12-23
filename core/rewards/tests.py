import json

from decimal import Decimal

from unittest import skip

from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from banker.utils import balance

from poker.constants import SIDE_EFFECT_SUBJ, Event, NL_BOUNTY
from poker.handhistory import DBLog
from poker.models import HandHistory, HandHistoryEvent, HandHistoryAction
from poker.replayer import ActionReplayer
from poker.subscribers import LogSubscriber
from poker.tests.test_controller import GenericTableTest, FivePlayerTableTest
from poker.level_utils import earned_chips
from poker.controllers import BountyController

from rewards.constants import NEWCOMER_REWARD, REGULAR_BADGE_REWARD
from rewards.models import Badge
from rewards.subscribers import BadgeSubscriber

from ui.test_utils import FrontendTest


class BadgeTest(GenericTableTest):
    # 0: pirate_player          400
    # 1: cuttlefish_player      300
    # 2: ajfenix_player         200
    # 3: cowpig_player          100
    def setUp(self):
        super().setUp()
        acc = self.controller.accessor
        ctrl = self.controller

        ctrl.log = DBLog(acc)
        self.badge_subscriber = BadgeSubscriber(acc, ctrl.log)
        ctrl.subscribers = [
            LogSubscriber(ctrl.log),
            self.badge_subscriber,
        ]

    def tearDown(self):
        HandHistoryEvent.objects.all().delete()
        HandHistoryAction.objects.all().delete()
        HandHistory.objects.all().delete()
        super().tearDown()

class FivePlayerBadgeTest(FivePlayerTableTest):
    # 0: pirate       (400)
    # 1: cuttlefish   (300)
    # 2: ajfenix      (200)
    # 3: cowpig       (100)
    # 4: alexeimartov (400)
    def setUp(self):
        super().setUp()
        acc = self.controller.accessor
        ctrl = self.controller

        ctrl.log = DBLog(acc)
        self.badge_subscriber = BadgeSubscriber(acc, ctrl.log)
        ctrl.subscribers = [
            LogSubscriber(ctrl.log),
            self.badge_subscriber,
        ]

    def tearDown(self):
        HandHistoryEvent.objects.all().delete()
        HandHistoryAction.objects.all().delete()
        HandHistory.objects.all().delete()
        super().tearDown()

class BadgeSubscriberTest(BadgeTest):
    def test_player_winnings_from_history(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '7c,2d',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: 'Kd,Ah',
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)
        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=275)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        # ajfenix and cowpig are all-in
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)

        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']

        # pirate bets, cuttlefish raises, pirate raises, cuttlefish folds
        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=5)
        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=10)
        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=15)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.internal_dispatch(ctrl.return_uncalled_bets())
        ctrl.internal_dispatch([
            (SIDE_EFFECT_SUBJ, Event.NEW_STREET, {}),
            *ctrl.wins_and_losses(),
            (SIDE_EFFECT_SUBJ, Event.SHOWDOWN_COMPLETE, {}),
        ])

        player_wins = self.badge_subscriber.player_winnings_from_history()
        assert len(player_wins.items()) == 1
        pirate_wins = player_wins[self.pirate_player]

        showdown_wins = 100 + 200 + 200 + 200
        other_wins = 75 + 75 + 10 + 10
        assert pirate_wins['showdown'] == showdown_wins
        assert pirate_wins['non-showdown'] == other_wins
        assert pirate_wins['total'] == showdown_wins + other_wins
        assert len(player_wins.keys()) == 1


class TestUserProfileBadges(FrontendTest):
    def setUp(self):
        username = 'test_user'
        self.user = self.setup_user(username=username)
        Badge(user=self.user,
              name='shove',
              season=settings.CURRENT_SEASON).save()

        url = reverse('UserProfile', args=(username,))
        super().setUp(url, setup_user=False)

    def tearDown(self):
        Badge.objects.all().delete()
        super().tearDown()

    def test_badge_props(self):
        response = self.request()
        props = response.context['props']

        assert 'badges' in props
        assert 'shove' in props['badges']
        assert props['badges']['shove']['title'].endswith('x1')
        created = props['badges']['shove']['ts']
        assert (timezone.now() - created).total_seconds() < 30

class ActionReplayerTestWithUsers(TestCase):
    def setUp(self, filename='no_events.json', **kwargs):
        with open(filename, 'r') as f:
            self.hh = json.load(f)

        self.replayer = ActionReplayer(self.hh,
                                       subscriber_types=(BadgeSubscriber,),
                                       **kwargs)
        User = get_user_model()
        for player in self.replayer.controller.accessor.players:
            player.user = User(username=player.username,
                               email=f'{player.username}@example.com',
                               password='banana')

    def tearDown(self):
        Badge.objects.all().delete()
        users = [player.user for player in self.replayer.accessor.players]
        self.replayer.delete()
        for user in users:
            user.delete()


class ShoveTest(BadgeTest):
    # bet or raise all-in
    def test_shove(self):
        self.table.btn_idx = 0
        self.controller.step()
        self.controller.dispatch('raise_to',
                                 player_id=self.cowpig_player.id,
                                 amt=100)

        assert (self.cowpig
                    .badge_set
                    .filter(name='shove')
                    .count())

    def test_two_shoves_count_as_one(self):
        """
        Newcomer badges now are earned just once, so we will use shove to
        represent this
        """
        Badge(user=self.cowpig,
              name='shove',
              season=settings.CURRENT_SEASON).save()
        self.table.btn_idx = 0
        self.controller.step()
        self.controller.dispatch('raise_to',
                                 player_id=self.cowpig_player.id,
                                 amt=100)

        assert (self.cowpig
                    .badge_set
                    .filter(name='shove')
                    .count() == 1)


class BigWinTest(BadgeTest):
    # win a pot over 500bbs
    def test_big_win(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '2s,2d',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: 'Kd,Ah'
        }
        assert self.players[0].user.userbalance().balance == 0

        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)
        self.cowpig_player.stack = Decimal(400)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']
        ctrl.step()
        ctrl.commit()

        big_win = self.players[0].user\
                                 .badge_set\
                                 .filter(name='big_win')
        assert big_win.count() == 1

        true_grit = self.players[0].user\
                                   .badge_set\
                                   .filter(name='true_grit')
        assert not true_grit.count()

        # asserts new balance three badges

        shove = self.players[0].user\
                               .badge_set\
                               .filter(name='shove')
        assert shove.count() == 1

        quads = self.players[0].user\
                               .badge_set\
                               .filter(name='quads')
        assert quads.count() == 1

        expected_bonuses = NEWCOMER_REWARD * 2 + REGULAR_BADGE_REWARD

        winner_user = self.players[0].user
        user_bal = winner_user.userbalance().balance
        cashier_bal = balance(winner_user)
        earned_bal = earned_chips(winner_user)

        assert user_bal == cashier_bal == earned_bal == expected_bonuses


class BountyWinTest(BadgeTest):
    # win a 27 bounty
    def test_bounty_win(self):
        self.table.table_type = NL_BOUNTY
        self.cowpig_player.stack = Decimal(600)
        self.pirate_player.stack = Decimal(600)
        self.controller = BountyController(self.table, players=self.players)
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '2s,7d',
            self.players[1]: '2h,9c',
            self.players[2]: '5c,Ad',
            self.players[3]: '7c,4h'
        }

        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)

        assert self.accessor.table.bounty_flag

        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        # a bounty showdown should not trigger showdown badges
        true_grit = Badge.objects.filter(name='true_grit')
        assert not true_grit

        # winning the bounty awards the bountytown badge
        bountytown = self.players[0].user\
                                    .badge_set\
                                    .filter(name='bountytown')
        assert bountytown


class BigBluffTest(BadgeTest):
    # win a 200bb+ pot without showdown with a bottom 20% hand, and show it
    @skip
    def test_big_bluff(self):
        # TODO
        pass

    # call a 50bb+ bet on the river with a bottom 20% hand, and win
    @skip
    def test_big_call(self):
        # TODO
        pass

    # lose 500bbs or more in a continuous session
    @skip
    def test_run_bad(self):
        # TODO
        pass

    # play 1,000 hands in a continuous session
    @skip
    def test_marathon(self):
        # TODO
        pass

    # play at least 50,000 total hands
    @skip
    def test_adept(self):
        # TODO
        pass


class TheDuckTest(BadgeTest):
    # win a 400bb+ pot with 72o at showdown
    def test_the_duck_awarded(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '7c,2d',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: 'Kd,Ah'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']
        ctrl.step()
        ctrl.commit()

        assert (self.players[0].user
                              .badge_set
                              .filter(name='the_duck')
                              .count())

    def test_the_duck_not_awarded_without_400bbs_at_showdown(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '7c,2d',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: 'Kd,Ah'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=275)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        # ajfenix and cowpig are all-in
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)

        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)

        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=2)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.step()
        ctrl.commit()

        # the showdown sidepot was only worth 350bbs
        assert (not self.players[0].user
                                   .badge_set
                                   .filter(name='the_duck')
                                   .count())


class SpecificHandTest(BadgeTest):
    def test_quads_straight_flush_and_steel_wheel(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Ac,As',
            self.players[1]: '2d,3d',
            self.players[2]: '7d,9d',
            self.players[3]: 'Kd,Qd'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        for player in self.players:
            player.stack = Decimal(200)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['Ad', '4d', '5d', '8d', 'Ah']
        ctrl.step()
        ctrl.commit()

        # did not win with four-of-a-kind
        assert not (self.players[0].user
                                   .badge_set
                                   .filter(name='quads')
                                   .count())
        # did not win with an ace-to-5 straight flush at showdown
        assert (self.players[1].user
                               .badge_set
                               .filter(name='steel_wheel')
                               .count())
        # won with a straight flush at showdown
        assert (self.players[1].user
                               .badge_set
                               .filter(name='straight_flush')
                               .count())

    def test_quads_win(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Ac,As',
            self.players[1]: 'Jd,3d',
            self.players[2]: 'Td,8d',
            self.players[3]: 'Kd,Qd'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['Ad', '4d', '5d', '6d', 'Ah']
        ctrl.step()
        ctrl.commit()

        # won with four-of-a-kind
        assert (self.players[0].user
                              .badge_set
                              .filter(name='quads')
                              .count())

    # win with a royal flush at showdown
    def test_royalty(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Ac,Kc',
            self.players[1]: 'Jd,3d',
            self.players[2]: 'Td,8d',
            self.players[3]: 'Kd,Qd'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['Jc', 'Qc', 'Tc', 'Th', 'Jh']
        ctrl.step()
        ctrl.commit()

        # won with a royal flush
        assert (self.players[0].user
                              .badge_set
                              .filter(name='royalty')
                              .count())


class RoundersHandTest(BadgeTest):
    def test_the_teddy_and_mike_mcd(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Ac,As',
            self.players[1]: 'Ad,5h',
            self.players[2]: '7d,9d',
            self.players[3]: 'Kd,Qd',
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        for player in self.players:
            player.stack = Decimal(200)

        ctrl = self.controller
        acc = self.controller.accessor

        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=200)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch(
            'fold',
            player_id=acc.next_to_act().id,
            sit_out=True,
        )
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)

        acc.table.board = ['Ah', '5d', '6d', '5c', '9d']
        ctrl.step()
        ctrl.commit()

        # win with pocket aces against an Ax full house
        assert (self.players[0].user
                               .badge_set
                               .filter(name='the_teddy')
                               .count())
        # lose with an Ax full house against pocket aces
        assert (self.players[1].user
                               .badge_set
                               .filter(name='mike_mcd')
                               .count())

    def test_the_teddy_and_mike_mcd_doesnt_count(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Ac,As',
            self.players[1]: 'Ad,5h',
            self.players[2]: '7d,9d',
            self.players[3]: 'Kd,Qd',
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        for player in self.players:
            player.stack = Decimal(200)

        ctrl = self.controller
        acc = self.controller.accessor

        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=100)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        ctrl.step()
        acc.table.board = ['Ah', '5d', '6d', '5c', '9d']

        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=100)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)

        # won without showdown--doesn't count
        assert not (self.players[0].user
                                   .badge_set
                                   .filter(name='the_teddy')
                                   .count())
        # lost without showdown--doesn't count
        assert not (self.players[1].user
                                   .badge_set
                                   .filter(name='mike_mcd')
                                   .count())

class ItsATrapTest(BadgeTest):
    # check-raise all-in on the river, get called, and win
    @skip
    def test_its_a_trap(self):
        # TODO
        pass

    # win a 500bb+ pot with a bottom 5% hand
    @skip
    def test_cool_hand_luke(self):
        # TODO
        pass

    # win a 300bb+ pot without ever facing a bet or raise
    @skip
    def test_bombs_away(self):
        # TODO
        pass

class TrueGritTest(BadgeTest):
    # win a 500bb+ pot without ever betting or raising
    def _setup_stuff(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Kd,Ah',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: '2s,2d'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)
        self.cowpig_player.stack = Decimal(400)

    def _earn_true_grit(self):
        ctrl = self.controller
        acc = self.controller.accessor
        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']
        ctrl.step()
        ctrl.commit()

    def test_true_grit(self):
        self._setup_stuff()
        self._earn_true_grit()
        assert (self.players[3].user
                               .badge_set
                               .filter(name='true_grit')
                               .exists())

    def test_true_grit_non_twice(self):
        self._setup_stuff()
        user = self.players[3].user
        Badge(user=user,
              name='true_grit',
              season=settings.CURRENT_SEASON).save()
        self._earn_true_grit()
        assert user.badge_set.filter(name='true_grit').count() == 1


class DoubleCheckRaiseTest(BadgeTest):
    # check-raise twice in the same hand and win the pot
    @skip
    def test_double_check_raise(self):
        # TODO
        pass

    # check-raise, check-raise, check-raise all-in and win
    @skip
    def test_trifecta(self):
        # TODO
        pass

    # limp- or call-reraise, plus a trifecta
    @skip
    def test_quadfecta(self):
        # TODO
        pass

    # call on the river and win a pot with Jx or worse and no pair
    @skip
    def test_soul_reader(self):
        # TODO
        pass


    # === luck or wins/losses badges ===

class PlayChipsTest(BadgeTest):
    # obtain a play-chip balance of 1,000,000 chips or more
    @skip
    def test_so_many_chips(self):
        # TODO: implement this
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Kd,Ah',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: '2s,4d'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)
        for player in self.players:
            player.stack = Decimal(500000)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']
        ctrl.step()
        ctrl.commit()

        assert (self.players[3].user
                               .badge_set
                               .filter(name='so_many_chips')
                               .count())

    # obtain a play-chip balance of 9,999,999 chips or more
    @skip
    def test_play_chip_diety(self):
        #TODO: implement this
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: 'Kd,Ah',
            self.players[1]: 'Kh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: '2s,4d'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)
        for player in self.players:
            player.stack = Decimal(4000000)

        ctrl = self.controller
        acc = self.controller.accessor

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=nxt.stack_available)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']
        ctrl.step()
        ctrl.commit()

        assert (self.players[3].user
                               .badge_set
                               .filter(name='play_chip_diety')
                               .count())

class NiceSessionTest(BadgeTest):
    # win 500bbs or more in a continuous session
    @skip
    def test_nice_session(self):
        # TODO
        pass

    # win at least 1000 bbs in one session
    @skip
    def test_heater(self):
        # TODO
        pass

    # win 1500 bbs in a 24-hour period
    @skip
    def test_sizzler(self):
        # TODO
        pass

    # win at least 2000 bbs in one session
    @skip
    def test_god_mode(self):
        # TODO
        pass

    # lose with aces-full (using both holecards) or better
    @skip
    def test_bad_beat(self):
        # TODO
        pass

    # lose 300bbs or more with top 0.1% hand
    @skip
    def test_cooler(self):
        # TODO
        pass

    # win an all-in with 1% equity
    @skip
    def test_suckout(self):
        # TODO
        pass

    # get all-in and win three times in a row
    @skip
    def test_hes_on_fire(self):
        # TODO
        pass

    # lose 1000bbs or more in a continuous session
    @skip
    def test_this_is_rigged(self):
        # TODO
        pass


    # === grinder badges ===

    # @showdown
    # play 5,000 hands in a continuous session
    @skip
    def test_just_one_more_hand(self):
        # TODO
        pass

    # play 10,000 hands in a continuous session and in at least 500bbs
    @skip
    def test_cant_stop_wont_stop(self):
        # TODO
        pass

    # play 50,000 hands in a month
    @skip
    def test_grinder(self):
        # TODO
        pass

    # play 100,000 hands in a month
    @skip
    def test_true_grinder(self):
        # TODO
        pass

    # play the more hands than any other player in a month
    @skip
    def test_capital_g_grinder(self):
        # TODO
        pass

    # play 500,000 hands in a 1-year period
    @skip
    def test_fiend(self):
        # TODO
        pass

    # play at least 100,000 total hands
    @skip
    def test_veteran(self):
        # TODO
        pass

    # play at least 500,000 total hands
    @skip
    def test_pro(self):
        # TODO
        pass

    # play a total of 1,000,000 hands
    @skip
    def test_seen_it_all(self):
        # TODO
        pass

    # @showdown, but global
    # the biggest winner this week so far in KOTH points
    @skip
    def test_king_of_the_hill(self):
        # TODO
        pass
