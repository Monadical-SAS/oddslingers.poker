# from datetime import timedelta

# from django.utils import timezone
from django.contrib.auth import get_user_model

# from oddslingers.tests.test_utils import TimezoneMocker

from oddslingers.mutations import execute_mutations

from banker.mutations import buy_chips

from poker.tests.test_controller import TableWithChipsTest

from sidebets.subscribers import SidebetSubscriber
from sidebets.views import make_sidebet, get_sidebets
from sidebets.models import Sidebet

User = get_user_model()

class SidebetTest(TableWithChipsTest):
    # 0: pirate_player          400
    # 1: cuttlefish_player      300
    # 2: ajfenix_player         200
    # 3: cowpig_player          100
    def setUp(self):
        super().setUp()
        acc = self.controller.accessor
        ctrl = self.controller

        self.sidebet_subscriber = SidebetSubscriber(acc)
        ctrl.subscribers = [
            self.sidebet_subscriber,
        ]

        self.railplover = User.objects.create_user(
            username='railplover',
            email='railplover@hello.com',
            password='banana'
        )
        self.railpigeon = User.objects.create_user(
            username='railpigeon',
            email='railpigeon@hello.com',
            password='banana'
        )
        self.railostrich = User.objects.create_user(
            username='prailostrich',
            email='railostrich@hello.com',
            password='banana'
        )

        mutations = [
            *buy_chips(self.railplover, 500),
            *buy_chips(self.railpigeon, 500),
            *buy_chips(self.railostrich, 500),
        ]
        execute_mutations(mutations)

    def tearDown(self):
        Sidebet.objects.all().delete()
        super().tearDown()


class SidebetWinAndLossTest(SidebetTest):
    def setUp(self):
        super().setUp()
        sidebet_a, _ = make_sidebet(self.railpigeon,
                                 self.cuttlefish_player,
                                 amt=10,
                                 delay=None)
        sidebet_a.starting_stack = self.cuttlefish_player.stack
        sidebet_a.save()

        sidebet_b, _ = make_sidebet(self.railostrich,
                                 self.ajfenix_player,
                                 amt=10,
                                 delay=None)
        sidebet_b.starting_stack = self.ajfenix_player.stack
        sidebet_b.save()

    def test_sidebet_win_and_loss(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: 'Ac,Kc',
                self.ajfenix_player: 'Qc,Qd',
                self.cowpig_player: '3c,2d',
            },
            add_log=True,
            board_str='5d,Qh,Qs',
        )

        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=300)
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        # ajfenix doubles up; cuttlefish loses 2/3 of stack

        cuttelfish_sidebet = get_sidebets(self.railpigeon, ctrl.table)[0]
        assert float(cuttelfish_sidebet.current_value()) - 3.33 < 0.01
        ajfenix_sidebet = get_sidebets(self.railostrich, ctrl.table)[0]
        assert ajfenix_sidebet.current_value() - 20 < 0.01


class SidebetWithOddsTest(SidebetTest):
    def setUp(self):
        super().setUp()

        sidebet_a, _ = make_sidebet(self.railpigeon,
                                 self.cuttlefish_player,
                                 amt=10,
                                 delay=None,
                                 odds=0.5,)
        sidebet_a.starting_stack = self.cuttlefish_player.stack
        sidebet_a.save()

        self.aj_odds = 1.5
        sidebet_b, _ = make_sidebet(self.railostrich,
                                 self.ajfenix_player,
                                 amt=10,
                                 delay=None,
                                 odds=self.aj_odds,)
        sidebet_b.starting_stack = self.ajfenix_player.stack
        sidebet_b.save()

    def test_sidebet_with_odds(self):

        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: 'Ac,Kc',
                self.ajfenix_player: 'Qc,Qd',
                self.cowpig_player: '3c,2d',
            },
            add_log=True,
            board_str='5d,Qh,Qs',
        )

        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=300)
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        # ajfenix doubles up; cuttlefish loses 2/3 of stack

        # odds don't affect losses
        cuttelfish_sidebet = get_sidebets(self.railpigeon, ctrl.table)[0]
        assert float(cuttelfish_sidebet.current_value()) - 3.33 < 0.01

        # odds do affect winnings
        ajfenix_sidebet = get_sidebets(self.railostrich, ctrl.table)[0]
        expected = (10 + 10 * self.aj_odds)
        assert float(ajfenix_sidebet.current_value()) - expected < 0.01


class SidebetClosesPlayerGetsStackedTest(SidebetTest):
    def setUp(self):
        super().setUp()
        sidebet_a, _ = make_sidebet(self.railpigeon,
                                    self.ajfenix_player,
                                    amt=10,
                                    delay=None)
        sidebet_a.starting_stack = self.ajfenix_player.stack
        sidebet_a.save()

        sidebet_b, _ = make_sidebet(self.railostrich,
                                    self.cuttlefish_player,
                                    amt=10,
                                    delay=None)
        sidebet_b.starting_stack = self.cuttlefish_player.stack
        sidebet_b.save()

    def test_sidebet_closes_player_gets_stacked(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: 'Ac,Kc',
                self.cowpig_player: '3c,2d',
            },
            add_log=True,
            board_str='5d,Qh,Qs',
        )
        ctrl.dispatch('SET_AUTO_REBUY',
                      player_id=self.ajfenix_player.id,
                      amt=200)
        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=300)
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        # ajfenix gets stacked

        ajfenix_sidebet = get_sidebets(self.railpigeon, ctrl.table)[0]
        assert ajfenix_sidebet.status == 'closed'
        assert ajfenix_sidebet.current_value() == 0

        cuttlefish_sidebet = get_sidebets(self.railostrich, ctrl.table)[0]
        assert cuttlefish_sidebet.status == 'active'


class NewSidebetRebuyTest(SidebetTest):
    def setUp(self):
        super().setUp()
        sidebet, _ = make_sidebet(self.railostrich,
                                  self.ajfenix_player,
                                  amt=10,
                                  delay=None)
        sidebet.starting_stack = self.ajfenix_player.stack
        sidebet.save()

    def test_new_sidebet_on_rebuy(self):
        ctrl = self.controller

        ajfenix_sidebets = get_sidebets(self.railostrich, ctrl.table)
        assert ajfenix_sidebets.count() == 1

        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            add_log=True,
        )
        ctrl.dispatch('SET_AUTO_REBUY',
                      player_id=self.ajfenix_player.id,
                      amt=300)

        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=5)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.ajfenix_player.id,
                      amt=100)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=200)
        ctrl.dispatch('FOLD', player_id=self.ajfenix_player.id)

        ajfenix_sidebets = get_sidebets(self.railostrich, ctrl.table)
        assert ajfenix_sidebets.count() == 2

        ajfenix_closed_sidebets = ajfenix_sidebets.filter(status='closed')
        assert ajfenix_closed_sidebets.count() == 1
        ajfenix_closed_sidebet = ajfenix_closed_sidebets.get()
        assert ajfenix_closed_sidebet.current_value() == 5

        ajfenix_active_sidebets = ajfenix_sidebets.filter(status='active')
        assert ajfenix_active_sidebets.count() == 1
        ajfenix_active_sidebet = ajfenix_active_sidebets.get()
        assert ajfenix_active_sidebet.amt == 5
        assert ajfenix_active_sidebet.starting_stack == 300


class CloseSidebetTest(SidebetTest):
    def setUp(self):
        super().setUp()
        sidebet_a, _ = make_sidebet(self.railpigeon,
                                    self.cuttlefish_player,
                                    amt=10,
                                    delay=None)
        sidebet_a.starting_stack = self.cuttlefish_player.stack
        sidebet_a.save()
        sidebet_b, _ = make_sidebet(self.railpigeon,
                                    self.cuttlefish_player,
                                    amt=20,
                                    delay=None)
        sidebet_b.starting_stack = self.cuttlefish_player.stack
        sidebet_b.save()
        sidebet_c, _ = make_sidebet(self.railostrich,
                                    self.cuttlefish_player,
                                    amt=20,
                                    delay=None)
        sidebet_c.starting_stack = self.cuttlefish_player.stack
        sidebet_c.save()

    def test_close_sidebet(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: 'Ac,Kc',
                self.cowpig_player: '3c,2d',
            },
            add_log=True,
            board_str='5d,Qh,Qs',
        )
        ctrl.dispatch('CLOSE_SIDEBET',
                      player_id=self.cuttlefish_player.id,
                      user_id=self.railpigeon.id)
        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cuttlefish_player.id,
                      amt=200)
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)

        sidebets = get_sidebets(self.railpigeon, ctrl.table)
        cuttlefish_sidebet = sidebets[0]
        assert cuttlefish_sidebet.status == 'closed'
        assert float(cuttlefish_sidebet.current_value()) - 33.33 < 0.01

        cuttlefish_sidebet = sidebets[1]
        assert cuttlefish_sidebet.status == 'closed'
        assert float(cuttlefish_sidebet.current_value()) - 26.66 < 0.01

        cuttlefish_sidebet = get_sidebets(self.railostrich, ctrl.table)[0]
        assert cuttlefish_sidebet.status == 'active'


class SidebetClosesPlayerLeaveSeatTest(SidebetTest):
    def setUp(self):
        super().setUp()
        sidebet, _ = make_sidebet(self.railpigeon,
                                  self.ajfenix_player,
                                  amt=10,
                                  delay=None)
        sidebet.starting_stack = self.ajfenix_player.stack
        sidebet.save()

    def test_sidebet_closes_player_gets_stacked(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: 'Ac,Kc',
                self.cowpig_player: '3c,2d',
            },
            add_log=True,
            board_str='5d,Qh,Qs',
        )
        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('CALL',
                      player_id=self.cuttlefish_player.id,
                      amt=2)
        ctrl.dispatch('LEAVE_SEAT', player_id=self.ajfenix_player.id)

        ajfenix_sidebet = get_sidebets(self.railpigeon, ctrl.table)[0]
        assert ajfenix_sidebet.status == 'closed'
        assert float(ajfenix_sidebet.current_value()) - 10 < 0.01


# class SidebetCloseTimeTest(SidebetTest):
#     def test_sidebet_close_time(self):
#         now = timezone.now()
#         few_mins = timedelta(minutes=5)

#         make_sidebet(self.railpigeon,
#                      self.cuttlefish_player,
#                      amt=10,
#                      delay=None,
#                      endtime=now + few_mins)
#         make_sidebet(self.railostrich,
#                      self.ajfenix_player,
#                      amt=10,
#                      delay=None,
#                      end_time=now + few_mins)

#         ctrl = self.controller
#         self.setup_hand(
#             blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
#             player_hole_cards={
#                 self.pirate_player: '2s,3h',
#                 self.cuttlefish_player: 'Ac,Kc',
#                 self.ajfenix_player: 'Qc,Qd',
#                 self.cowpig_player: '3c,2d',
#             },
#             add_log=True,
#             board_str='5d,Qh,Qs',
#         )

#         ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
#         ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
#         ctrl.dispatch('RAISE_TO',
#                       player_id=self.cuttlefish_player.id,
#                       amt=300)

#         # next hand will start after the timedelta
#         with TimezoneMocker(now + few_mins + timedelta(seconds=1)):
#             ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)

#             # next hand
#             ctrl.dispatch('RAISE_TO', player_id=self.pirate_player.id,
#                           amt=50)
#             ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
#             ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
#             ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)

#             ctrl.dispatch('FOLD', player_id=ctrl.accessor.next_to_act().id)
#             ctrl.dispatch('FOLD', player_id=ctrl.accessor.next_to_act().id)


#         cuttelfish_sidebet = get_sidebets(self.railpigeon, ctrl.table)[0]
#         assert float(cuttelfish_sidebet.current_value()) - 3.33 < 0.01
#         ajfenix_sidebet = get_sidebets(self.railostrich, ctrl.table)[0]
#         assert ajfenix_sidebet.current_value() - 20 < 0.01
