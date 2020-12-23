import random

from decimal import Decimal
from random import randint
from datetime import timedelta

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone

from oddslingers.utils import DoesNothing, fnv_hash
from oddslingers.tests.test_utils import TimezoneMocker
from oddslingers.mutations import execute_mutations

from poker.models import PokerTable, Player, ChatLine, ChatHistory
from poker.cards import Card, Deck, INDICES
from poker.constants import (
    Event, Action, MAX_ORBITS_SITTING_OUT, NL_BOUNTY, PlayingState,
    NUM_HOLECARDS, BUMP_AFTER_INACTIVE_MINS
)
from poker.controllers import (
    HoldemController, BountyController, InvalidAction
)
from poker.subscribers import (
    InMemoryLogSubscriber, BankerSubscriber, NotificationSubscriber,
    LogSubscriber
)
from poker.handhistory import DBLog
from poker.bots import get_robot_move
from poker.game_utils import fuzzy_get_table, has_recent_human_activity

from banker.mutations import buy_chips, create_transfer
from banker.utils import transfer_history
from banker.models import BalanceTransfer, Cashier

from rewards.models import Badge


class GenericTableTest(TestCase):
    # 0: pirate_player          400
    # 1: cuttlefish_player      300
    # 2: ajfenix_player         200
    # 3: cowpig_player          100
    def setUp(self):
        User = get_user_model()
        self.table = PokerTable.objects.create_table(
            name="test_table",
            num_seats=6,
            sb=Decimal(1),
            bb=Decimal(2),
            min_buyin=120,
            max_buyin=300,
        )
        self.pirate = User.objects.create_user(
            username='pirate',
            email='nick@hello.com',
            password='banana'
        )
        self.cuttlefish = User.objects.create_user(
            username='cuttlefish',
            email='sam@hello.com',
            password='banana'
        )
        self.cowpig = User.objects.create_user(
            username='cowpig',
            email='maxy@hello.com',
            password='banana'
        )
        self.ajfenix = User.objects.create_user(
            username='ajfenix',
            email='aj@hello.com',
            password='banana'
        )
        self.pirate_player = Player.objects.create(
            user=self.pirate,
            stack=Decimal('400.00'),
            table=self.table,
            position=0,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )
        self.cuttlefish_player = Player.objects.create(
            user=self.cuttlefish,
            stack=Decimal('300.00'),
            table=self.table,
            position=1,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )
        self.ajfenix_player = Player.objects.create(
            user=self.ajfenix,
            stack=Decimal('200.00'),
            table=self.table,
            position=2,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )
        self.cowpig_player = Player.objects.create(
            user=self.cowpig,
            stack=Decimal('100.00'),
            table=self.table,
            position=3,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )

        self.players = [
            self.pirate_player,
            self.cuttlefish_player,
            self.ajfenix_player,
            self.cowpig_player
        ]
        self.log = DoesNothing()
        self.controller = HoldemController(self.table,
                                           self.players,
                                           log=self.log,
                                           subscribers=[])
        self.controller.commit()
        # mock out the timing events and logging system
        # self.controller.timing_events = lambda _, __: []

        self.accessor = self.controller.accessor

    def setup_hand(self, sit_out=None,
                         blinds_positions=None,
                         player_hole_cards=None,
                         board_str=None,
                         add_log=False):
        '''
        args:
            sit_out: list of players
            blinds_positions: {bb_pos: <bb_idx>, sb_pos: <sb_idx>, ...}
            player_hole_cards: {<player>: '2c,2s', ...}
            board_str: '2c,3s,4h ...'
            add_log: bool

        note: player_hole_cards can only be defined if
                 positions are also defined.
        '''

        if add_log:
            self.controller.log = DBLog(self.controller.accessor)
            log_subscriber = LogSubscriber(self.controller.log)
            self.controller.subscribers.append(log_subscriber)

        sit_out = sit_out or []
        for player in sit_out:
            player.playing_state = PlayingState.SITTING_OUT

        deck = []
        cards_left = set(Deck().cards)
        cards_per_player = NUM_HOLECARDS[self.accessor.table.table_type]
        if player_hole_cards:
            if blinds_positions['sb_pos'] == blinds_positions['btn_pos']:
                first_card = blinds_positions['bb_pos']
            else:
                first_card = blinds_positions['sb_pos']

            players = self.controller.accessor.active_players(
                rotate=first_card
            )
            player_hands = {
                player: [
                    Card(card)
                    for card in player_hole_cards[player].split(',')
                ]
                for player in player_hole_cards
            }
            for i in range(cards_per_player):
                for player in players:
                    card = player_hands[player][i]
                    deck.append(card)
                    cards_left.remove(card)

        if board_str:
            if not player_hole_cards:
                n_plyrs = len(self.controller.accessor.active_players())
                board_cards = {Card(card) for card in board_str.split(',')}
                nonboard_cards = cards_left - board_cards
                deck = random.sample(
                    nonboard_cards,
                    n_plyrs * cards_per_player
                )
                for card in deck:
                    cards_left.remove(card)

            for card_str in board_str.split(','):
                card = Card(card_str)
                deck.append(card)
                cards_left.remove(card)

        deck += random.sample(cards_left, len(cards_left))

        self.controller.setup_hand(
            mocked_deck_str=','.join(str(card) for card in deck),
            mocked_blinds=blinds_positions
        )

    def dispatch_random_actions(self, num_actions):
        for _ in range(num_actions):
            if self.controller.accessor.next_to_act() is not None:
                action, kwargs = get_robot_move(self.controller.accessor,
                                             self.controller.log,
                                             delay=False,
                                             warnings=False,
                                             stupid=True)
                self.controller.dispatch(action, **kwargs)

    def tearDown(self):
        ChatLine.objects.all().delete()
        ChatHistory.objects.all().delete()
        Player.objects.all().delete()
        Badge.objects.all().delete()
        get_user_model().objects.all().delete()
        PokerTable.objects.all().delete()


class TableWithCardsTest(GenericTableTest):
    def setUp(self):
        super(TableWithCardsTest, self).setUp()
        card_strs = ['2h', '2s', '3h', '3s', '4h', '4s', '4c', '4d']
        cards_to_deal = [Card(c) for c in card_strs]
        self.pirate_player.dispatch('deal', card=cards_to_deal[0])
        self.pirate_player.dispatch('deal', card=cards_to_deal[1])
        self.cuttlefish_player.dispatch('deal', card=cards_to_deal[2])
        self.cuttlefish_player.dispatch('deal', card=cards_to_deal[3])
        self.ajfenix_player.dispatch('deal', card=cards_to_deal[4])
        self.ajfenix_player.dispatch('deal', card=cards_to_deal[5])
        self.cowpig_player.dispatch('deal', card=cards_to_deal[6])
        self.cowpig_player.dispatch('deal', card=cards_to_deal[7])
        cards_for_table = [
            Card(c) for c in list(set(INDICES) - set(card_strs))
        ]
        self.table.deck = Deck(cards_for_table)

    def test_cards_per_actor(self):
        self.assertEqual(52 - 8, len(self.table.deck.to_num()))
        self.assertEqual(2, len(self.pirate_player.cards))
        self.assertEqual(
            ['2h', '2s'],
            sorted([str(c) for c in self.pirate_player.cards])
        )
        self.assertEqual(2, len(self.cuttlefish_player.cards))
        self.assertEqual(2, len(self.ajfenix_player.cards))
        self.assertEqual(2, len(self.cowpig_player.cards))


class TableWithChipsTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        execute_mutations([
            *buy_chips(self.pirate, 1000),
            *buy_chips(self.ajfenix, 1000),
            *buy_chips(self.cowpig, 1000),
            *buy_chips(self.cuttlefish, 1000)
        ])
        self.pirate.userbalance().refresh_from_db()
        self.ajfenix.userbalance().refresh_from_db()
        self.cowpig.userbalance().refresh_from_db()
        self.cuttlefish.userbalance().refresh_from_db()
        self.controller.subscribers.append(BankerSubscriber(self.accessor))

    def tearDown(self):
        BalanceTransfer.objects.all().delete()
        super().tearDown()


class MoveBlindsNewTableTest(GenericTableTest):
    def test_move_blinds(self):
        for _ in range(100):
            sitting_out_player = random.choice(self.players)
            sitting_out_player.playing_state = PlayingState.SITTING_OUT

            _, _, positions = self.controller\
                                  .sit_in_pending_and_move_blinds()\
                                  .pop()

            btn_plyr = self.accessor.players_at_position(positions['btn_pos'])
            sb_plyr = self.accessor.players_at_position(positions['sb_pos'])
            bb_plyr = self.accessor.players_at_position(positions['bb_pos'])

            self.assertEqual(btn_plyr.is_sitting_out(), False)
            self.assertEqual(type(sb_plyr), Player)
            self.assertEqual(bb_plyr.is_sitting_out(), False)

            sitting_out_player.playing_state = PlayingState.SITTING_OUT

            sitting_out_player.playing_state = PlayingState.SITTING_IN

            # TODO: wtf is going on here? this looks like an incomplete test


class LockedBTNOnePlayerTest(GenericTableTest):
    def test_locked_bb_for_one_player(self):
        acc = self.controller.accessor
        self.controller.internal_dispatch([
            (self.pirate_player, Event.LEAVE_SEAT, {'immediate': True})])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True})])
        self.controller.internal_dispatch([
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True})])

        self.controller.step()
        assert acc.btn_is_locked()
        assert acc.table.btn_idx == self.cuttlefish_player.position


class MoveBlindsHeadsUpWithSitInBetweenTest(GenericTableTest):
    def test_move_blinds_special_case(self):
        self.ajfenix_player.seated = False
        self.cuttlefish_player.playing_state = PlayingState.SITTING_OUT
        self.cuttlefish_player.sit_in_at_blinds = False
        self.table.btn_idx = 0
        self.table.sb_idx = 0
        self.table.bb_idx = 3
        self.controller.step()

        self.controller.dispatch('sit_in_at_blinds',
                                 player_id=self.cuttlefish_player.id,
                                 set_to=True)

        self.controller.dispatch('fold', player_id=self.cowpig_player.id)

        assert self.cowpig_player == self.accessor.btn_player()
        assert self.pirate_player == self.accessor.sb_player()
        assert self.cuttlefish_player == self.accessor.bb_player()


class WaitToSitInTest(GenericTableTest):
    def test_wait_to_sit_in(self):
        '''
            this tests an edgecase, in which a player sits in between
            the btn and bb at a hu table, and must wait an extra hand to
            get the bb
        '''
        acc = self.accessor

        self.table.btn_idx = 0
        self.table.sb_idx = 0
        self.table.bb_idx = 1

        self.ajfenix_player.playing_state = PlayingState.SITTING_OUT
        self.cowpig_player.playing_state = PlayingState.SITTING_OUT

        self.controller.step()

        self.controller.dispatch('sit_in',
                                 player_id=self.cowpig_player.id)

        next_to_act = self.accessor.next_to_act()
        self.controller.dispatch('fold',
                                 player_id=next_to_act.id)

        assert self.cowpig_player.playing_state == PlayingState.SIT_IN_PENDING

        avail_acts = acc.available_actions(self.cowpig_player)
        assert Action.SIT_OUT in avail_acts
        assert Action.SIT_IN not in avail_acts

        next_to_act = self.accessor.next_to_act()
        self.controller.dispatch('fold',
                                 player_id=next_to_act.id)

        assert self.cowpig_player.last_action == Event.POST

    def test_wait_to_sit_in_with_two_players(self):
        """
        When there is one player in the table and the second one sits in,
        the wait to sit in notification should not be displayed
        """
        self.controller.commit()
        acc = self.controller.accessor
        notification_sub = NotificationSubscriber(acc)
        self.controller.subscribers = [notification_sub]

        self.table.btn_idx = 0
        self.table.sb_idx = 0
        self.table.bb_idx = 1

        self.pirate_player.playing_state = PlayingState.SITTING_OUT
        self.cuttlefish_player.playing_state = PlayingState.SITTING_OUT
        self.cowpig_player.playing_state = PlayingState.SITTING_OUT

        self.ajfenix_player.playing_state = PlayingState.SITTING_IN
        self.controller.step()

        self.controller.dispatch(
            'sit_in',
            player_id=self.cowpig_player.id
        )
        notification_types = [
            notification['type']
            for notification in
                notification_sub.to_broadcast[self.cowpig_player]
        ]
        assert 'wait_to_sit_in' not in notification_types


class PlayingStateActionsWhenAloneTest(GenericTableTest):
    def test_can_sit_in_out_and_leave_when_sitting_alone(self):
        acc = self.controller.accessor
        self.controller.internal_dispatch([
            (self.pirate_player, Event.LEAVE_SEAT, {'immediate': True})])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True})])
        self.controller.internal_dispatch([
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True})])

        self.controller.step()
        assert self.cuttlefish_player.is_sitting_out() == False

        cuttlefish_acts = acc.available_actions(self.cuttlefish_player)
        assert Action.SIT_OUT in cuttlefish_acts
        assert Action.LEAVE_SEAT in cuttlefish_acts

        self.controller.dispatch('sit_out',
                                 player_id=self.cuttlefish_player.id)
        assert self.cuttlefish_player.is_sitting_out() == True

        self.controller.dispatch('sit_in',
                                 player_id=self.cuttlefish_player.id)
        assert self.cuttlefish_player.is_sitting_out() == False

        self.controller.dispatch('leave_seat',
                                 player_id=self.cuttlefish_player.id)
        assert self.cuttlefish_player.seated == False


class FivePlayerTableTest(GenericTableTest):
    def setUp(self):
        ''' seats are:
            0: pirate       (400)
            1: cuttlefish   (300)
            2: ajfenix      (200)
            3: cowpig       (100)
            4: alexeimartov (400)
        '''
        super(FivePlayerTableTest, self).setUp()

        self.alexeimartov = get_user_model().objects.create_user(
            username='alexeimartov',
            email='marty@hello.com',
            password='banana'
        )
        self.alexeimartov_player = Player.objects.create(
            user=self.alexeimartov,
            stack=400,
            table=self.table,
            position=4,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )

        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.table.save()
        self.players = [
            self.pirate_player,
            self.cuttlefish_player,
            self.ajfenix_player,
            self.cowpig_player,
            self.alexeimartov_player
        ]
        self.controller = HoldemController(self.table, self.players,
                                           self.log, subscribers=[])
        self.controller.timing_events = lambda _, __: []

        self.accessor = self.controller.accessor


class SixPlayerTableTest(FivePlayerTableTest):
    def setUp(self):
        ''' seats are:
            0: pirate       (400)
            1: cuttlefish   (300)
            2: ajfenix      (200)
            3: cowpig       (100)
            4: alexeimartov (400)
            5: ahnuld       (200)
            # 6: skier_5      (300) oops that's 7
        '''

        super().setUp()

        self.ahnuld = get_user_model().objects.create_user(
            username='ahnuld',
            email='jordan@hello.com',
            password='banana'
        )
        self.ahnuld_player = Player.objects.create(
            user=self.ahnuld,
            stack=200,
            table=self.table,
            position=5,
            seated=True,
            playing_state=PlayingState.SITTING_IN,
        )

        # self.skier_5 = get_user_model().objects.create_user(
        #     username='skier_5',
        #     email='tommy@hello.com',
        #     password='banana'
        # )
        # self.skier_5_player = Player.objects.create(
        #     user=self.skier_5,
        #     stack=300,
        #     table=self.table,
        #     position=6,
        #     seated=True,
        #     playing_state=PlayingState.SITTING_IN,
        # )

        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.table.save()
        self.players = [
            self.pirate_player,
            self.cuttlefish_player,
            self.ajfenix_player,
            self.cowpig_player,
            self.alexeimartov_player,
            self.ahnuld_player,
            # self.skier_5_player,
        ]
        self.controller = HoldemController(self.table, self.players,
                                           self.log, subscribers=[])
        self.controller.timing_events = lambda _, __: []

        self.accessor = self.controller.accessor


class RaiseTest(FivePlayerTableTest):
    def test_raise(self):
        self.controller.step()
        alexeimartov = self.accessor.player_by_username('alexeimartov')
        alexeimartov.dispatch('call', amt=2)
        self.accessor.player_by_username('pirate').dispatch('call', amt=2)
        self.accessor.player_by_username('cuttlefish').dispatch('call', amt=2)
        self.accessor.player_by_username('ajfenix').dispatch('call', amt=2)
        cowpig = self.accessor.player_by_username('cowpig')
        cowpig.dispatch('raise_to', amt=5)

        self.assertEqual(5, cowpig.wagers)
        self.assertEqual(5, cowpig.uncollected_bets)

        self.assertEqual(13, self.accessor.current_pot())

        alexeimartov.dispatch('raise_to', amt=15)
        self.assertEqual(15, alexeimartov.wagers)
        self.assertEqual(15, alexeimartov.uncollected_bets)

        self.assertEqual(26, self.accessor.current_pot())


class MoveBlindsNewFivePlayerTableTest(FivePlayerTableTest):
    def test_move_blinds(self):
        acc = self.accessor
        self.table.btn_idx = None
        self.table.sb_idx = None
        self.table.bb_idx = None

        for _ in range(100):

            sitting_out_player = random.choice(self.players)
            sitting_out_player.dispatch('sit_out', immediate=True)

            _, _, positions = self.controller\
                                  .sit_in_pending_and_move_blinds()\
                                  .pop()

            btn_player = acc.players_at_position(positions['btn_pos'])
            sb_player = acc.players_at_position(positions['sb_pos'])
            bb_player = acc.players_at_position(positions['bb_pos'])

            self.assertEqual(btn_player.is_sitting_out(), False)
            self.assertEqual(sb_player.is_sitting_out(), False)
            self.assertEqual(bb_player.is_sitting_out(), False)

            sitting_out_player.playing_state = PlayingState.SITTING_OUT

            sitting_out_player.playing_state = PlayingState.SITTING_IN


class MoveBlindsPresetTableTest(FivePlayerTableTest):
    def test_move_blinds(self):
        acc = self.accessor
        for _ in range(100):
            self.table.btn_idx = randint(0, self.table.num_seats - 1)
            self.table.sb_idx = (self.table.btn_idx + 1) % self.table.num_seats
            self.table.bb_idx = (self.table.sb_idx + 1) % self.table.num_seats

            sitting_out_player = random.choice(self.players)
            sitting_out_player.dispatch('sit_out')

            _, _, positions = self.controller\
                                  .sit_in_pending_and_move_blinds()\
                                  .pop()

            btn_player = acc.players_at_position(positions['btn_pos'])
            sb_player = acc.players_at_position(positions['sb_pos'])
            bb_player = acc.players_at_position(positions['bb_pos'])

            self.assertEqual(btn_player.is_sitting_out(), False)
            if sb_player is None:
                self.assertEqual(positions['bb_pos'], 0)
            self.assertEqual(bb_player.is_sitting_out(), False)

            sitting_out_player.playing_state = PlayingState.SITTING_OUT

            sitting_out_player.playing_state = PlayingState.SITTING_IN


class SetupHandTest(FivePlayerTableTest):
    def test_setup_hand(self):
        self.controller.setup_hand()
        expected_cards_left = 52 - (2 * len(self.players))
        cards_left = len(self.controller.table.deck.to_list())
        self.assertEqual(expected_cards_left, cards_left)


class DealFlopTest(FivePlayerTableTest):
    def test_deal_flop(self):
        self.controller.setup_hand()
        self.controller.deal_flop()
        self.assertEqual(3, len(self.controller.table.board))


class DealFlopTurnTest(FivePlayerTableTest):
    def test_deal_flop_turn(self):
        self.controller.setup_hand()
        self.controller.deal_flop()
        self.controller.deal_turn()
        self.assertEqual(4, len(self.controller.table.board))


class DealFlopTurnRiverTest(FivePlayerTableTest):
    def test_deal_flop_turn_river(self):
        self.controller.setup_hand()
        self.controller.deal_flop()
        self.controller.deal_turn()
        self.controller.deal_river()
        self.assertEqual(5, len(self.controller.table.board))


class DealCardsTest(FivePlayerTableTest):
    def test_deal_cards(self):
        self.controller.table.dispatch('shuffle')

        orig_cards = self.controller.table.deck.cards

        events = self.controller.deal_to_board(3)
        pop_event = events[-1]
        deal_events = events[:-1]

        cards = [args['card'] for _, _, args in deal_events]

        table, pop_event, num_cards = pop_event

        _, new_deck = table.dispatch('pop_cards', **num_cards)[0]
        new_cards = new_deck.cards
        popped_cards = [card for card in orig_cards if card not in new_cards]

        self.assertEqual(cards, popped_cards)


class BlindRotationTest(FivePlayerTableTest):
    def test_standard_rotation(self):
        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(3, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[4], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(2, self.table.btn_idx)
        self.assertEqual(3, self.table.sb_idx)
        self.assertEqual(4, self.table.bb_idx)

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(3, self.table.btn_idx)
        self.assertEqual(4, self.table.sb_idx)
        self.assertEqual(0, self.table.bb_idx)

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(4, self.table.btn_idx)
        self.assertEqual(0, self.table.sb_idx)
        self.assertEqual(1, self.table.bb_idx)

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(1, self.table.sb_idx)
        self.assertEqual(2, self.table.bb_idx)


class BlindRotationSBStandTest(FivePlayerTableTest):
    def test_sb_standup(self):
        """leaves [0, 2, 3, 4] sitting"""
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(3, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[4], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(2, self.table.btn_idx)
        self.assertEqual(3, self.table.sb_idx)
        self.assertEqual(4, self.table.bb_idx)
        self.assertEqual(self.players[0], self.accessor.next_to_act())


class BlindRotationBBStandTest(FivePlayerTableTest):
    def test_bb_standup(self):
        """leaves [0, 1, 3, 4] sitting"""
        self.controller.internal_dispatch([
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(3, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[4], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(3, self.table.sb_idx)
        self.assertEqual(4, self.table.bb_idx)
        self.assertEqual(self.players[0], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(3, self.table.btn_idx)
        self.assertEqual(4, self.table.sb_idx)
        self.assertEqual(0, self.table.bb_idx)
        self.assertEqual(self.players[1], self.accessor.next_to_act())


class BlindRotationSBBBStandTest(FivePlayerTableTest):
    def test_sb_bb_standup(self):
        """leaves [0, 3, 4] sitting"""
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(3, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[4], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(3, self.table.sb_idx)
        self.assertEqual(4, self.table.bb_idx)
        self.assertEqual(self.players[0], self.accessor.next_to_act())


class BlindRotationBBUTGStandTest(FivePlayerTableTest):
    def test_bb_utg_standup(self):
        """leaves [0, 1, 4] sitting"""
        self.controller.internal_dispatch([
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(3, self.table.sb_idx)
        self.assertEqual(4, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[0], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(4, self.table.sb_idx)
        self.assertEqual(0, self.table.bb_idx)
        self.assertEqual(self.players[1], self.accessor.next_to_act())


class BlindRotationSBUTGStandTest(FivePlayerTableTest):
    def test_sb_utg_standup(self):
        """leaves [0, 2, 4] sitting"""
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(4, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[0], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(2, self.table.btn_idx)
        self.assertEqual(4, self.table.sb_idx)
        self.assertEqual(0, self.table.bb_idx)
        self.assertEqual(self.players[2], self.accessor.next_to_act())


class BlindRotationSBBBHUTest(FivePlayerTableTest):
    def test_sb_bb_to_hu_standup(self):
        """leaves [1, 2] sitting"""
        self.controller.internal_dispatch([
            (self.pirate_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.alexeimartov_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(2, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(1, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[2], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(1, self.table.sb_idx)
        self.assertEqual(2, self.table.bb_idx)
        self.assertEqual(self.players[1], self.accessor.next_to_act())


class BlindRotationBTNSBHUTest(FivePlayerTableTest):
    def test_btn_sb_to_hu_standup(self):
        """leaves [0, 1] sitting"""
        self.controller.internal_dispatch([
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.alexeimartov_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(1, self.table.btn_idx)
        self.assertEqual(1, self.table.sb_idx)
        self.assertEqual(0, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[1], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(0, self.table.sb_idx)
        self.assertEqual(1, self.table.bb_idx)
        self.assertEqual(self.players[0], self.accessor.next_to_act())


class BlindRotationBTNBBHUTest(FivePlayerTableTest):
    def test_btn_bb_to_hu_standup(self):
        """leaves [0, 2] sitting"""
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        self.controller.internal_dispatch([
            (self.alexeimartov_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(2, self.table.btn_idx)
        self.assertEqual(2, self.table.sb_idx)
        self.assertEqual(0, self.table.bb_idx)

        self.table.dispatch('shuffle')
        self.controller.internal_dispatch(
            self.controller.deal_starting_hands()
        )
        self.assertEqual(self.players[2], self.accessor.next_to_act())

        events = self.controller.sit_in_pending_and_move_blinds()
        self.controller.internal_dispatch(events)
        self.assertEqual(0, self.table.btn_idx)
        self.assertEqual(0, self.table.sb_idx)
        self.assertEqual(2, self.table.bb_idx)
        self.assertEqual(self.players[0], self.accessor.next_to_act())


class BlindsHeadsUpNewPlayerSitsInTest(FivePlayerTableTest):
    def test_blinds_after_sit_back_in(self):
        recorder = InMemoryLogSubscriber()
        self.controller.subscribers.append(recorder)

        '''
            This test is for a special edgecase, where the player who just sat
            in must wait another hand to play, even if they want to post dead
        '''

        # leaves [3, 4] sitting
        self.controller.internal_dispatch([
            (self.pirate_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        assert len(self.accessor.seated_players()) == 2

        self.table.btn_idx = 4
        self.table.sb_idx = 4
        self.table.bb_idx = 3

        execute_mutations(
            buy_chips(self.pirate, 500)
        )
        self.controller.internal_dispatch(
                [(self.pirate_player, Event.TAKE_SEAT, {'position': 1})])
        self.controller.internal_dispatch(
                [(self.pirate_player, Event.SIT_IN, {})])

        self.controller.step()

        assert self.table.btn_idx == 3
        assert self.table.sb_idx == 3
        assert self.table.bb_idx == 4

        assert self.pirate_player.is_sitting_out()
        alert = [
            event for event in recorder.log
            if event[1] == Event.NOTIFICATION
        ].pop()
        assert alert[2]['player'] == self.pirate_player
        assert alert[2]['notification_type'] == 'wait_to_sit_in'

        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        assert self.pirate_player.playing_state == PlayingState.SITTING_IN
        assert self.table.btn_idx == 3
        assert self.table.sb_idx == 4
        assert self.table.bb_idx == 1


class NewPlayerCannotSitInOnSBTest(FivePlayerTableTest):
    def test_sitting_in_at_sb(self):
        recorder = InMemoryLogSubscriber()
        self.controller.subscribers.append(recorder)

        # 0: pirate
        # 1: cuttlefish
        # 2: ajfenix
        # 3: cowpig
        # 4: alexeimartov
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        assert len(self.accessor.seated_players()) == 3

        self.table.btn_idx = 0
        self.table.sb_idx = 2
        self.table.bb_idx = 4

        execute_mutations(
            buy_chips(self.cowpig, 500)
        )
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.TAKE_SEAT, {'position': 3}),
        ])
        self.controller.internal_dispatch([
            (self.cowpig_player, Event.SIT_IN, {}),
        ])

        self.controller.step()
        assert self.table.btn_idx == 2
        assert self.table.sb_idx == 4
        assert self.table.bb_idx == 0

        assert self.cowpig_player.is_sitting_out()
        alert = [
            event for event in recorder.log
            if event[1] == Event.NOTIFICATION
        ].pop()
        assert alert[2]['player'] == self.cowpig_player
        assert alert[2]['notification_type'] == 'wait_to_sit_in'

        self.controller.dispatch('FOLD',
                                 player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.alexeimartov_player.id)

        assert self.table.btn_idx == 4
        assert self.table.sb_idx == 0
        assert self.table.bb_idx == 2
        assert not self.cowpig_player.is_sitting_out()
        assert self.cowpig_player.last_action == Event.POST


class NewPlayerSitsInBetweenBTNAndSBTest(FivePlayerTableTest):
    def test_sitting_in_between_btn_and_sb(self):
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        assert len(self.accessor.seated_players()) == 3

        self.table.btn_idx = 2
        self.table.sb_idx = 4
        self.table.bb_idx = 0

        execute_mutations(
            buy_chips(self.cowpig, 500)
        )
        self.controller.internal_dispatch(
                [(self.cowpig_player, Event.TAKE_SEAT, {'position': 3})])
        self.controller.internal_dispatch(
                [(self.cowpig_player, Event.SIT_IN, {})])

        self.controller.step()
        assert self.table.btn_idx == 4
        assert self.table.sb_idx == 0
        assert self.table.bb_idx == 2

        assert not self.cowpig_player.is_sitting_out()
        assert self.cowpig_player.last_action == Event.POST


class BlindsAfterSitBackInTest(GenericTableTest):

    def test_blinds_after_sit_back_in(self):
        self.controller.internal_dispatch([
            (self.pirate_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.cuttlefish_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.ajfenix_player, Event.LEAVE_SEAT, {'immediate': True}),
            (self.cowpig_player, Event.LEAVE_SEAT, {'immediate': True}),
        ])
        assert len(self.accessor.seated_players()) == 0

        self.controller.step()
        execute_mutations([
            *buy_chips(self.pirate, 500),
            *buy_chips(self.cuttlefish, 500),
        ])
        self.controller.dispatch('take_seat',
                                 player_id=self.cuttlefish_player.id,
                                 position=4)
        self.controller.dispatch('sit_in', player_id=self.cuttlefish_player.id)
        # button gets 'locked' to the only active player if nobody else is
        #   sitting in. this means table.bb_idx, table.sb_idx are both None
        #   while table.btn_idx is set to 4
        assert self.accessor.btn_is_locked()
        self.controller.dispatch('take_seat',
                                 player_id=self.pirate_player.id,
                                 position=1)
        self.controller.dispatch('sit_in', player_id=self.pirate_player.id)

        # player who sat in first should get the sb
        assert self.table.sb_idx == 4
        assert self.accessor.current_pot() == 3


class PassiveSittingStatesAreExclusiveTest(TableWithChipsTest):
    def test_passive_sitting_states_are_exclusive(self):
        self.controller.step()

        assert self.pirate_player.playing_state == PlayingState.SITTING_IN
        assert not self.pirate_player.sit_out_at_blinds

        self.controller.dispatch('sit_out_at_blinds',
                                 player_id=self.pirate_player.id,
                                 set_to=True)
        assert self.pirate_player.playing_state == PlayingState.SITTING_IN
        assert self.pirate_player.sit_out_at_blinds == True

        # sit_out_at_blinds, sit_out_pending, and leave_seat are all
        #   mutually exclusive
        self.controller.dispatch('sit_out',
                                 player_id=self.pirate_player.id)
        assert self.pirate_player.playing_state == PlayingState.SIT_OUT_PENDING
        assert not self.pirate_player.sit_out_at_blinds

        self.controller.dispatch('sit_out_at_blinds',
                                 player_id=self.pirate_player.id,
                                 set_to=True)
        assert self.pirate_player.playing_state == PlayingState.SITTING_IN
        assert self.pirate_player.sit_out_at_blinds == True

        self.controller.dispatch('leave_seat',
                                 player_id=self.pirate_player.id)
        assert self.pirate_player\
                   .playing_state == PlayingState.LEAVE_SEAT_PENDING
        assert not self.pirate_player.sit_out_at_blinds

        # .. NEXT HAND ..
        for _ in range(3):
            self.controller.dispatch('fold',
                                     player_id=self.accessor.next_to_act().id)

        self.controller.join_table(self.pirate.id)
        assert self.pirate_player.seated
        # new player defaults to sitting out
        assert self.pirate_player\
                   .playing_state == PlayingState.SITTING_OUT

        # sit_in_at_blinds and sit_in_next_hand are mutually exclusive
        self.controller.dispatch('sit_in',
                                 player_id=self.pirate_player.id)
        assert self.pirate_player.playing_state == PlayingState.SIT_IN_PENDING
        assert not self.pirate_player.sit_out_at_blinds

        self.controller.dispatch('sit_in_at_blinds',
                                 player_id=self.pirate_player.id,
                                 set_to=True)
        assert self.pirate_player\
                   .playing_state == PlayingState.SIT_IN_AT_BLINDS_PENDING
        assert not self.pirate_player.sit_out_at_blinds
        self.controller.dispatch('sit_in',
                                 player_id=self.pirate_player.id)
        assert self.pirate_player.playing_state == PlayingState.SIT_IN_PENDING
        assert not self.pirate_player.sit_out_at_blinds

        self.controller.dispatch('sit_in_at_blinds',
                                 player_id=self.pirate_player.id,
                                 set_to=True)
        assert self.pirate_player\
                   .playing_state == PlayingState.SIT_IN_AT_BLINDS_PENDING
        assert not self.pirate_player.sit_out_at_blinds


class BlindsNewTableTest(GenericTableTest):
    def test_blinds_new_table(self):
        execute_mutations([
            *buy_chips(self.pirate, 500),
            *buy_chips(self.cowpig, 500),
        ])

        table = PokerTable(name=f"{'TEST'}'s Table")
        table.num_seats = 6
        table.sb = 1
        table.bb = 2
        controller = HoldemController(table,
                                      log=DoesNothing(),
                                      subscribers=[])
        controller.dispatch('join_table', user_id=self.pirate.id)

        accessor = controller.accessor

        controller.dispatch('join_table', user_id=self.cowpig.id)

        pirate = accessor.player_by_user_id(self.pirate.id)
        cowpig = accessor.player_by_user_id(self.cowpig.id)

        controller.dispatch('SIT_IN', player_id=pirate.id)
        controller.dispatch('SIT_IN', player_id=cowpig.id)

        # player who is sitting first always gets the sb
        assert accessor.players_at_position(table.sb_idx) == pirate
        assert controller.accessor.current_pot() == 3

        controller.dispatch('fold', player_id=pirate.id)
        controller.dispatch('fold', player_id=cowpig.id)

        assert controller.accessor.current_pot() == 3


class OweBBRemovedAfterPayingTest(FivePlayerTableTest):
    def test_owe_bb_removed_after_paying(self):
        self.table.sb_idx = 2
        self.table.bb_idx = 3
        self.controller.internal_dispatch([
            (self.cuttlefish_player, Event.OWE_BB, {"owes": True}),
        ])
        self.controller.step()

        # includes cuttlefish's owed bb
        assert self.accessor.current_pot() == 5

        # fold around to alexeimartov to get to the next hand
        for player in self.accessor.active_players()[:-1]:
            self.controller.dispatch('fold', player_id=player.id)

        # it's a new hand now, and the blinds are back to normal
        assert self.accessor.current_pot() == 3


class ShowdownTest(GenericTableTest):
    def test_wins_and_losses_equal_split(self):
        controller = self.controller
        self.cowpig_player.playing_state = PlayingState.SITTING_OUT

        self.table.bb_idx = 0

        controller.internal_dispatch([
            (p, Event.RESET, {})
            for p in controller.accessor.active_players()
        ])
        controller.internal_dispatch([(self.table, Event.RESET, {})])
        controller.internal_dispatch([
            (self.pirate_player, Event.DEAL, {'card': Card("Ts")}),
            (self.pirate_player, Event.DEAL, {'card': Card("Th")}),
            (self.cuttlefish_player, Event.DEAL, {'card': Card("9s")}),
            (self.cuttlefish_player, Event.DEAL, {'card': Card("9h")}),
            (self.ajfenix_player, Event.DEAL, {'card': Card("8s")}),
            (self.ajfenix_player, Event.DEAL, {'card': Card("8h")})])

        controller.internal_dispatch([
            (self.pirate_player, Event.RAISE_TO, {'amt': 400}),
            (self.cuttlefish_player, Event.CALL, {'amt': 300}),
            (self.ajfenix_player, Event.CALL, {'amt': 200})])

        self.table.board = [
            Card("6c"), Card("7c"), Card("8c"), Card("9c"), Card("Tc")
        ]

        controller.internal_dispatch(controller.wins_and_losses())
        self.controller.step()

        assert(self.pirate_player.stack == 400)
        assert(self.cuttlefish_player.stack == 300)
        assert(self.ajfenix_player.stack == 200)


class TwoHandsWithSplitPotTest(GenericTableTest):
    def test_wins_and_losses_three_way_split(self):
        self.cowpig_player.stack = 400

        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,  # cuttlefish
                'sb_pos': 2,  # ajfenix
                'bb_pos': 3,  # cowpig
            },
            player_hole_cards={
                self.pirate_player:     'Ts,Qh',
                self.cuttlefish_player: 'Tc,9h',
                self.ajfenix_player:    'Th,8h',
                self.cowpig_player:     'Ac,3h',
            },
            board_str='6d,7c,8c,9c,Ah'
        )

        self.controller.dispatch('RAISE_TO',
                                 player_id=self.pirate_player.id, amt=400)
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('CALL', player_id=self.ajfenix_player.id)
        self.controller.dispatch('CALL', player_id=self.cowpig_player.id)

        assert(self.pirate_player.stack_available == 617)
        assert(self.cuttlefish_player.stack_available == 416)
        assert(self.ajfenix_player.stack_available == 267)
        assert(self.cowpig_player.stack_available == 0)

        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('RAISE_TO',
                                 player_id=self.pirate_player.id, amt=50)
        self.controller.dispatch('RAISE_TO',
                                 player_id=self.cuttlefish_player.id, amt=100)
        self.controller.dispatch('FOLD', player_id=self.pirate_player.id)

        assert(self.pirate_player.stack_available == 567)
        assert(self.cuttlefish_player.stack_available == 466)
        assert(self.ajfenix_player.stack_available == 267)
        assert(self.cowpig_player.stack_available == 0)


class ShowdownWinAnnotationTest(GenericTableTest):
    def test_showdown_win_annotation(self):
        # 0: pirate_player          400
        # 1: cuttlefish_player      300
        # 2: ajfenix_player         200
        # 3: cowpig_player          100
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        player_hole_cards = {
            self.players[0]: '2s,3s',
            self.players[1]: 'Qh,Ac',
            self.players[2]: 'Kc,Ad',
            self.players[3]: 'Kd,Kh'
        }
        self.setup_hand(blinds_positions=blind_pos,
                        player_hole_cards=player_hole_cards)

        ctrl = self.controller
        acc = self.controller.accessor

        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=150)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        acc.table.board = ['2h', '2c', '4h', '5h', 'Kd']


        ctrl.player_dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=150)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)

        ctrl.internal_dispatch(ctrl.return_uncalled_bets())

        # pirate should win a $150 pot without showdown
        # cowpig should win a $400 pot with showdown
        win_events = [
            event for event in ctrl.wins_and_losses()
            if event[1] == Event.WIN
        ]

        assert len(win_events) == 2

        plyr, _, kwargs = win_events[1]
        assert plyr == self.pirate_player
        assert kwargs['showdown'] == False

        plyr, _, kwargs = win_events[0]
        assert plyr == self.cowpig_player
        assert kwargs['showdown'] == True

    def test_showdown_win_annotation_everyone_folds(self):
        ctrl = self.controller
        acc = self.controller.accessor
        ctrl.step()

        ctrl.dispatch('fold', player_id=acc.next_to_act().id, amt=150)
        ctrl.dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.internal_dispatch(ctrl.return_uncalled_bets())

        win_events = [
            event for event in ctrl.wins_and_losses()
            if event[1] == Event.WIN
        ]

        assert len(win_events) == 1

        plyr, _, kwargs = win_events[0]
        assert kwargs['showdown'] == False




class BuyTest(GenericTableTest):
    """
    BUYIN TESTS
    starting player stacks:
        0: pirate_player          400
        1: cuttlefish_player      300
        2: ajfenix_player         200
        3: cowpig_player          100
    table has min 120, max 300
    """
    def setUp(self):
        super().setUp()
        self.controller.subscribers.append(BankerSubscriber(self.accessor))

    def tearDown(self):
        super().tearDown()
        BalanceTransfer.objects.all().delete()

    def test_illegal_buyin(self):
        execute_mutations(
            buy_chips(self.cowpig, 200)
        )
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == 200

        # must be at least 20
        prev_pending_rebuy = self.cowpig_player.pending_rebuy
        self.controller.step()
        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=19
        )
        assert prev_pending_rebuy == self.cowpig_player.pending_rebuy

        # cannot be negative
        prev_pending_rebuy = self.cowpig_player.pending_rebuy
        self.controller.step()
        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=-10
        )
        assert prev_pending_rebuy == self.cowpig_player.pending_rebuy

        # must be 200 or less
        prev_pending_rebuy = self.cowpig_player.pending_rebuy
        self.controller.step()
        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=201
        )
        assert prev_pending_rebuy == self.cowpig_player.pending_rebuy

    def test_illegal_buyin_no_balance(self):
        execute_mutations(
            buy_chips(self.cowpig, 200)
        )
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == 200
        prev_pending_rebuy = self.cowpig_player.pending_rebuy
        self.controller.step()
        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=201
        )
        assert prev_pending_rebuy == self.cowpig_player.pending_rebuy

    def test_buyin_with_a_pending_buy(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.controller.step()

        execute_mutations(
            buy_chips(self.cowpig, 500)
        )

        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=100
        )
        assert self.cowpig_player.pending_rebuy == 100

        prev_pending_rebuy = self.cowpig_player.pending_rebuy
        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=200
        )
        assert prev_pending_rebuy == self.cowpig_player.pending_rebuy

    def test_buyin_in_stack(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.controller.step()
        STARTING_BALANCE = 500
        BUYIN_AMT = 150

        execute_mutations(
            buy_chips(self.cowpig, STARTING_BALANCE)
        )
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == STARTING_BALANCE

        self.controller.dispatch(
            'BUY',
            player_id=self.cowpig_player.id,
            amt=BUYIN_AMT
        )
        assert self.cowpig_player.pending_rebuy == BUYIN_AMT

        # Cowpig has the big blind
        assert self.cowpig_player.stack == 98
        prev_cowpig_stack = self.cowpig_player.stack

        # Play the hand
        self.controller.dispatch('RAISE_TO', amt=50,
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cowpig_player.id)

        # Rebuy and small blind minus 2 lost chips on previous hand
        assert self.cowpig_player.stack == BUYIN_AMT + prev_cowpig_stack - 1
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == STARTING_BALANCE - BUYIN_AMT


class AutoRebuyTest(TableWithChipsTest):
    def test_illegal_auto_rebuys(self):
        def illegal_auto_rebuy1():
            # must be >= 120
            self.controller.set_auto_rebuy(self.cowpig_player.id, 100)

        def illegal_auto_rebuy2():
            # must be <= 300
            self.controller.set_auto_rebuy(self.cowpig_player.id, 400)

        self.assertRaises(ValueError, illegal_auto_rebuy1)
        self.assertRaises(ValueError, illegal_auto_rebuy2)

    def test_rebuys_and_banking_work(self):
        # cuttlefish is broke
        execute_mutations(create_transfer(
            self.cuttlefish,
            Cashier.load(),
            self.cuttlefish.userbalance().balance
        ))
        self.cuttlefish.userbalance().refresh_from_db()
        assert self.cuttlefish.userbalance().balance == 0

        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2
        self.controller.step()

        set_auto_rebuys = [
            *self.controller.set_auto_rebuy(self.pirate_player.id, 300),
            *self.controller.set_auto_rebuy(self.cuttlefish_player.id, 300),
            *self.controller.set_auto_rebuy(self.ajfenix_player.id, 300),
            *self.controller.set_auto_rebuy(self.cowpig_player.id, 120),
        ]
        self.controller.internal_dispatch(set_auto_rebuys)

        self.controller.dispatch('RAISE_TO', amt=50,
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('CALL',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('CALL',
                                 player_id=self.ajfenix_player.id)
        self.controller.dispatch('RAISE_TO', amt=100,
                                 player_id=self.cowpig_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.ajfenix_player.id)

        assert self.pirate_player.stack_available == 350
        # cuttlefish doesn't have chips in the bank
        assert self.cuttlefish_player.stack_available == 250
        assert self.ajfenix_player.stack_available == 300
        assert self.cowpig_player.stack_available == 250

        self.pirate.userbalance().refresh_from_db()
        assert self.pirate.userbalance().balance == 1000
        self.ajfenix.userbalance().refresh_from_db()
        assert self.ajfenix.userbalance().balance == 1000 - 150

        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD',
                                 player_id=self.cowpig_player.id)

        self.ajfenix.userbalance().refresh_from_db()
        assert self.ajfenix.userbalance().balance == 1000 - 150 + 300

        # getting booted for inactivity chips should be refunded
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == 1000


        self.controller.dispatch('SIT_OUT', player_id=self.cowpig_player.id)

        cowpig_stack = self.cowpig_player.stack

        for _ in range(10):
            plyr = self.accessor.next_to_act()
            self.controller.dispatch('FOLD', player_id=plyr.id)

        assert not self.cowpig_player.seated

        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == 1000 + cowpig_stack



class BalanceUpdatesTest(TableWithChipsTest):
    def test_balance_updates(self):
        new_user = get_user_model().objects.create_user(
            username='new_user',
            email='new_user@hello.com',
            password='banana'
        )
        new_user.save()
        execute_mutations(
            buy_chips(new_user, 5000)
        )
        new_user.userbalance().refresh_from_db()

        assert new_user.userbalance().balance == 5000
        self.controller.dispatch('join_table', user_id=new_user.id, buyin_amt=200)
        new_plyr = self.accessor.player_by_user_id(new_user.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000 - 200
        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000
        self.controller.dispatch('join_table', user_id=new_user.id, buyin_amt=200)
        new_plyr = self.accessor.player_by_user_id(new_user.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000 - 200
        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)

        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 5000


class JoinTableBalanceTest(TableWithChipsTest):
    def test_join_table_balance(self):
        # table.min_buyin is 120
        new_user = get_user_model().objects.create_user(
            username='new_user',
            email='new_user@hello.com',
            password='banana'
        )
        new_user.save()
        execute_mutations(
            buy_chips(new_user, 50)
        )

        with self.assertRaises(InvalidAction):
            self.controller.dispatch('join_table', user_id=new_user.id)

        new_user = self.accessor.user_by_id(new_user.id)

        execute_mutations(
            buy_chips(new_user, 70)
        )

        self.controller.dispatch('join_table', user_id=new_user.id)
        new_plyr = self.accessor.player_by_user_id(new_user.id)
        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)

        execute_mutations(
            buy_chips(new_user, 200)
        )
        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 320

        self.controller.dispatch(
            'join_table',
            user_id=new_user.id,
            buyin_amt=300
        )
        self.controller.commit()
        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 20

        new_plyr = self.accessor.player_by_user_id(new_user.id)
        self.controller.dispatch('LEAVE_SEAT', player_id=new_plyr.id)
        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 320

        execute_mutations(
            create_transfer(new_user, Cashier.load(), 100)
        )
        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 220

        # player doesn't have enough to join with old balance
        self.assertRaises(InvalidAction,
                          self.controller.join_table,
                          new_user.id)


class BuyBalanceTest(TableWithChipsTest):
    def test_buy_balance(self):
        assert self.cowpig.userbalance().balance == 1000

        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,7d',
                self.cuttlefish_player: '2d,7h',
                self.ajfenix_player: '2h,7c',
                self.cowpig_player: '2c,7s',
            },
        )
        # preflop
        self.controller.dispatch(player_id=self.cowpig_player.id,
                                 amt=150, action_name='BUY')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='RAISE_TO', amt=50)
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='FOLD')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='FOLD')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='FOLD')
        self.cowpig.userbalance().refresh_from_db()
        assert self.cowpig.userbalance().balance == 850
        assert self.cowpig_player.stack == 251


class TutorialsIgnoreCashTest(TableWithChipsTest):
    def setUp(self):
        super().setUp()
        self.table.is_tutorial = True
        self.table.max_buyin = 400
        self.cowpig.is_robot = True

    def test_tutorials_ignore_cash(self):
        # import ipdb; ipdb.set_trace()
        userbalances = {
            plyr: plyr.user.userbalance().balance
            for plyr in self.players
        }
        n_transactions = {
            plyr: len(transfer_history(plyr.user))
            for plyr in self.players
        }
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2}
        )
        self.controller.dispatch(player_id=self.cowpig_player.id,
                                 amt=150, action_name='BUY')
        self.controller.internal_dispatch([
            *self.controller.set_auto_rebuy(self.pirate_player.id, 400),
            *self.controller.set_auto_rebuy(self.cuttlefish_player.id, 400),
        ])

        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.cowpig_player.id,
            amt=10
        )
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.pirate_player.id,
            amt=50
        )
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.cuttlefish_player.id,
            amt=120
        )
        self.controller.dispatch(
            'RAISE_TO',
            player_id=self.ajfenix_player.id,
            amt=190
        )
        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.cowpig_player.id)
        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.pirate_player.id)
        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.cuttlefish_player.id)

        self.controller.join_table(self.pirate.id)
        self.controller.join_table(self.cuttlefish.id)

        assert self.pirate_player.stack == 400
        assert self.cuttlefish_player.stack == 400

        for plyr in self.players:
            n_xfers = len(transfer_history(plyr.user))
            assert n_transactions[plyr] == n_xfers
            assert plyr.user.userbalance().balance == userbalances[plyr]


class RobotsHaveInfiniteMoneyTest(TableWithChipsTest):
    # TODO: if a player is a robot, their balance never goes down
    pass


# class PlayerDisconnectTest(GenericTableTest):
#     def test_leaving_table(self):
#         self.table.btn_idx = 0
#         self.table.sb_idx = 1
#         self.table.bb_idx = 2

#         self.controller.step()
#         cuttlefish = self.cuttlefish_player
#         self.controller.player_disconnect(cuttlefish)

#         raise_action = {
#             'player_id': self.pirate_player.id,
#             'action_name': 'RAISE_TO',
#             'amt': 7
#         }
#         self.controller.dispatch(**raise_action)

#         assert cuttlefish.playing_state == PlayingState.SIT_OUT_PENDING

#         self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
#         self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

#         assert cuttlefish.is_sitting_out()


class PlayerCloseTableTest(GenericTableTest):
    def test_leaving_table(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()
        cuttlefish = self.cuttlefish_player
        self.controller.player_close_table(cuttlefish)

        raise_action = {
            'player_id': self.pirate_player.id,
            'action_name': 'RAISE_TO',
            'amt': 7
        }
        self.controller.dispatch(**raise_action)

        assert cuttlefish.playing_state == PlayingState.LEAVE_SEAT_PENDING

        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        assert cuttlefish.seated == False

class BumpAfterOrbitsTest(TableWithChipsTest):
    def init_bump(self):
        self.table.btn_idx = 1
        self.table.sb_idx = 2
        self.table.bb_idx = 3
        # after blinds move, cuttlefish will be UTG
        self.cuttlefish_player.playing_state = PlayingState.SITTING_OUT
        self.controller.step()

    def play_orbits(self, num_orbits):
        n_actives = len(self.accessor.active_players())
        upper_bound = self.table.hand_number + num_orbits * n_actives
        while self.table.hand_number < upper_bound:
            self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                action_name='FOLD')

    def test_orbit_bump(self):
        self.init_bump()
        self.play_orbits(MAX_ORBITS_SITTING_OUT + 2)
        cuttlefish_orbits_out = self.cuttlefish_player.orbits_sitting_out
        assert cuttlefish_orbits_out == MAX_ORBITS_SITTING_OUT
        assert self.cuttlefish_player.seated == False

    def test_resets_orbit_bump_on_deal(self):
        self.init_bump()
        self.play_orbits(MAX_ORBITS_SITTING_OUT)
        cuttlefish_orbits_out = self.cuttlefish_player.orbits_sitting_out
        assert cuttlefish_orbits_out == MAX_ORBITS_SITTING_OUT
        assert self.cuttlefish_player.seated == True

        self.controller.dispatch(player_id=self.cuttlefish_player.id,
                action_name='SIT_IN')

        self.play_orbits(1) #play an orbit to ensure cuttlefish is dealt in
        assert self.cuttlefish_player.orbits_sitting_out == 0
        assert self.cuttlefish_player.seated == True

    def test_resets_orbit_bump_on_join_table(self):
        self.init_bump()
        self.play_orbits(MAX_ORBITS_SITTING_OUT + 2)

        #player should have been booted so sit down and ensure that
        #   the player's orbits have been resert
        self.controller.dispatch(user_id=self.cuttlefish.id,
                action_name='JOIN_TABLE')
        assert self.cuttlefish_player.orbits_sitting_out == 0
        assert self.cuttlefish_player.seated == True


class PostDeadTest(GenericTableTest):
    def test_post_dead(self):
        self.table.btn_idx = 1
        self.table.sb_idx = 2
        self.table.bb_idx = 3

        self.cuttlefish_player.owes_bb = True
        self.cuttlefish_player.owes_sb = True
        self.cuttlefish_player.sit_in_at_blinds = False

        self.controller.step()

        # cuttlefish should post dead sb, and post bb, and be first to act
        assert self.accessor.current_pot() == 1 + 2 + 1 + 2
        assert self.accessor.next_to_act() == self.cuttlefish_player

        # contributing 11 to pot w/dead blind
        self.cuttlefish_player.dispatch('raise_to', amt=10)
        self.ajfenix_player.dispatch('raise_to', amt=30)

        assert self.accessor.current_pot() == 1 + 2 + 11 + 30

        self.cowpig_player.dispatch('fold')
        self.pirate_player.dispatch('fold')
        self.cuttlefish_player.dispatch('fold')
        self.controller.step()

        assert self.ajfenix_player.stack == 200 + 1 + 2 + 11


class HandRevealTest(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.setup_hand(
            blinds_positions={
                'btn_pos': 1,  # cuttlefish
                'sb_pos': 2,  # ajfenix
                'bb_pos': 3,  # cowpig
            },
            player_hole_cards={
                self.ajfenix_player:    'Ks,3h',
                self.cowpig_player:     'As,2h',
                self.pirate_player:     'Ah,8h',
                self.cuttlefish_player: 'Qs,4h',
            },
            board_str='Tc,Jc,Qd,Kh,9h'
        )
        self.table.board = ['Tc', 'Jc', 'Qd', 'Kh', '9h']

    def winning_players_api(self, ctrl, acc):
        # step -> end_hand
        ctrl.internal_dispatch(ctrl.return_uncalled_bets())

        # win_and_loses
        all_pots = acc.sidepot_summary()

        showdown_winnings = [
            acc.showdown_winnings_for_pot(pot_summary, i)
            for i, pot_summary in enumerate(all_pots)
        ]

        showdown_win_events_nested = [
            ctrl.showdown_win_events(showdown_winnings_for_pot)
            for showdown_winnings_for_pot in showdown_winnings
        ]
        # flattens the list of lists of win events
        showdown_win_events = [
            win_event
            for win_events in showdown_win_events_nested
            for win_event in win_events
        ]

        winning_players = {p for p, _, _ in showdown_win_events}
        return winning_players

    def test_hand_reveals(self):
        ctrl = self.controller
        acc = self.controller.accessor
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        ctrl.dispatch('CHECK', player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        ctrl.player_dispatch('CALL', player_id=self.cuttlefish_player.id)

        winning_players = self.winning_players_api(ctrl, acc)
        reveal_events = ctrl.reveal_hands(winning_players)
        expected_reveal_event_players = [
            (self.ajfenix_player, Event.REVEAL_HAND),
            (self.ajfenix_player, Event.CHAT),
            (self.cowpig_player, Event.REVEAL_HAND),
            (self.cowpig_player, Event.CHAT),
            (self.pirate_player, Event.REVEAL_HAND),
            (self.pirate_player, Event.CHAT),
            (self.cuttlefish_player, Event.MUCK),
            (self.cuttlefish_player, Event.CHAT),
        ]

        for event, expected in zip(reveal_events,
                                   expected_reveal_event_players):
            subj, event_type, args = event
            player, expected_type = expected
            assert event_type == expected_type

            if event_type == Event.REVEAL_HAND:
                assert args['cards'] == player.cards
            elif event_type == Event.MUCK:
                assert player.id == subj.id
            else:
                assert player.username in event[2]['msg']

    def test_hand_raise_reveals(self):
        ctrl = self.controller
        acc = self.controller.accessor
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        ctrl.dispatch('CHECK', player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        ctrl.dispatch('RAISE_TO', player_id=self.cuttlefish_player.id, amt=10)
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        ctrl.player_dispatch('CALL', player_id=self.pirate_player.id)

        winning_players = self.winning_players_api(ctrl, acc)
        reveal_events = self.controller.reveal_hands(winning_players)
        expected_reveal_event_players = [
            (self.cuttlefish_player, Event.REVEAL_HAND),
            (self.cuttlefish_player, Event.CHAT),
            (self.ajfenix_player, Event.REVEAL_HAND),
            (self.ajfenix_player, Event.CHAT),
            (self.cowpig_player, Event.REVEAL_HAND),
            (self.cowpig_player, Event.CHAT),
            (self.pirate_player, Event.REVEAL_HAND),
            (self.pirate_player, Event.CHAT),
        ]

        for event, expected in zip(reveal_events,
                                   expected_reveal_event_players):
            subj, event_type, args = event
            player, expected_type = expected
            assert event_type == expected_type

            if event_type == Event.REVEAL_HAND:
                assert args['cards'] == player.cards
            else:
                assert player.username in event[2]['msg']

    def test_hand_bet_reveals(self):
        self.table.board = ['Tc', 'Jc', 'Qd', 'Kh']
        ctrl = self.controller
        acc = self.controller.accessor
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        ctrl.dispatch('CHECK', player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)

        # Last round
        ctrl.dispatch('CHECK', player_id=self.ajfenix_player.id)
        ctrl.dispatch('CHECK', player_id=self.cowpig_player.id)
        ctrl.dispatch('BET', player_id=self.pirate_player.id, amt=10)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
        ctrl.dispatch('CALL', player_id=self.ajfenix_player.id)
        ctrl.player_dispatch('CALL', player_id=self.cowpig_player.id)

        winning_players = self.winning_players_api(ctrl, acc)
        reveal_events = self.controller.reveal_hands(winning_players)
        expected_reveal_event_players = [
            (self.pirate_player, Event.REVEAL_HAND),
            (self.pirate_player, Event.CHAT),
            (self.cuttlefish_player, Event.MUCK),
            (self.cuttlefish_player, Event.CHAT),
            (self.ajfenix_player, Event.MUCK),
            (self.ajfenix_player, Event.CHAT),
            (self.cowpig_player, Event.REVEAL_HAND),
            (self.cowpig_player, Event.CHAT),
        ]

        for event, expected in zip(reveal_events,
                                   expected_reveal_event_players):
            subj, event_type, args = event
            player, expected_type = expected
            assert event_type == expected_type

            if event_type == Event.REVEAL_HAND:
                assert args['cards'] == player.cards
            elif event_type == Event.MUCK:
                assert player.id == subj.id
            else:
                assert player.username in event[2]['msg']



class SittingGivenBlindsTest(GenericTableTest):
    def test_sitting_given_blinds(self):
        self.table.btn_idx = 1
        self.table.sb_idx = 2
        self.table.bb_idx = 3

        self.pirate_player.sit_out_at_blinds = True
        self.cuttlefish_player.sit_out_at_blinds = True

        sitting_blinds_events = self.controller.set_sitting_given_blinds()

        sitout_plyrs = {
            plyr for plyr, event, _ in sitting_blinds_events
            if event == Event.SIT_OUT
        }
        assert sitout_plyrs == {self.pirate_player, self.cuttlefish_player}

        self.pirate_player.sit_out_at_blinds = False
        self.pirate_player.playing_state = PlayingState.SITTING_OUT
        self.controller.player_dispatch('sit_in_at_blinds',
                                        player_id=self.pirate_player.id,
                                        set_to=True)

        sitting_in = {
            plyr for plyr, event, _ in
            self.controller.set_sitting_given_blinds()
            if event == Event.SIT_IN
        }
        assert sitting_in == {self.pirate_player}


class TimebankTest(GenericTableTest):
    def test_time_runs_out(self):
        self.table.seconds_per_action_base = 0
        self.table.min_timebank = 0
        self.table.max_timebank = 1
        self.table.save()

        self.table.player_set.update(timebank_remaining=1)

        self.controller.step()
        self.controller.commit()

        for player in self.accessor.players:
            player.refresh_from_db()

        next_to_act = self.accessor.next_to_act()
        next_to_act.n_hands_played = 10000

        # wait for player's time to run out
        now = timezone.now()
        in_2_seconds = now + timedelta(seconds=2)

        with TimezoneMocker(in_2_seconds):
            assert self.accessor.is_out_of_time(next_to_act)
            self.controller.dispatch('FOLD', player_id=next_to_act.id)
            new_next = self.accessor.next_to_act()
            new_next.n_hands_played = 10000

            # even though we're 2s in the future, last_action_timestamp
            #   resets so that this player has a new 1s to act
            last_timestamp = self.table.last_action_timestamp
            # to_act = self.accessor.seconds_to_act()
            # delay = to_act + new_next.timebank_remaining
            # should_by = last_timestamp + timedelta(seconds=delay)
            # print(
            #     f'now={now}\n'
            #     f'in_2_seconds={in_2_seconds}\n'
            #     f'last_timestamp={last_timestamp}\n'
            #     f'autofold_delay={delay}\n'
            #     f'should_by={should_by}\n'
            #     f'out_of_time={self.accessor.is_out_of_time(new_next)}'
            # )
            assert last_timestamp == in_2_seconds == timezone.now()
            assert not self.accessor.is_out_of_time(new_next)

    def test_countdown_delay_for_showdown(self):
        self.table.seconds_per_action_base = 0
        self.table.min_timebank = 0
        self.table.max_timebank = 1
        self.table.save()

        self.table.player_set.update(timebank_remaining=0)

        self.controller.step()
        self.controller.commit()

        for _ in range(len(self.players) - 1): # fold around to bb
            p = self.accessor.next_to_act()
            self.controller.dispatch('fold', player_id=p.id)

        for player in self.accessor.players:
            player.refresh_from_db()

        next_to_act = self.accessor.next_to_act()
        next_to_act.n_hands_played = 10000

        assert not self.accessor.is_out_of_time(next_to_act)


class TimebankUpdateTest(GenericTableTest):
    def test_timebank_updates(self):
        self.controller = HoldemController(self.table,
                                           self.players,
                                           self.log,
                                           subscribers=[])
        self.table.seconds_per_action_base = 2
        self.table.seconds_per_action_increment = 1
        self.table.min_timebank = 2
        self.table.max_timebank = 8
        self.table.save()
        self.cuttlefish_player.timebank_remaining = 0
        self.cuttlefish_player.save()
        self.controller.step()

        assert self.accessor.next_to_act(), \
                'No player is next to act on a fresh game.'

        # rapidly play 21 actions, should not deplete anyone's timbank
        #   since it's instantaneous
        while self.table.hand_number < 21:
            self.controller.dispatch('FOLD',
                                     player_id=self.accessor.next_to_act().id)
            self.controller.timed_dispatch()

        assert self.cuttlefish_player.timebank_remaining > 0, \
            "Player's timebank was depleted, even though actions "\
            "were made in time."


class BuyinRestartPlayTest(GenericTableTest):
    def test_buyin_restart_play(self):
        self.pirate_player.stack = 0
        self.cuttlefish_player.stack = 0
        self.ajfenix_player.stack = 0
        execute_mutations(
            buy_chips(self.cuttlefish, 1000)
        )
        self.cuttlefish_player.playing_state = PlayingState.SITTING_IN

        # not enough chips to play
        self.controller.step()
        self.controller.commit()

        # adds more
        self.controller.dispatch(player_id=self.cuttlefish_player.id,
                                action_name='BUY',
                                amt=120)
        acc = self.controller.accessor
        acc_plry = acc.player_by_player_id(self.cuttlefish_player.id)
        self.controller.internal_dispatch(
            self.controller.rebuy_updates_for_player(acc_plry))

        # cuttlefish has to manually sit back in before the game restarts
        assert self.accessor.enough_players_to_play() == False

        self.controller.dispatch(player_id=self.cuttlefish_player.id,
                                action_name='SIT_IN')

        # new heads-up hands should start, with cowpig on the button
        assert len(self.accessor.active_players()) == 2
        assert self.accessor.next_to_act() == self.cowpig_player


class CannotSitInWithoutEnoughChipsTest(GenericTableTest):
    def test_cannot_sit_in_without_enough_chips(self):
        self.pirate_player.stack = 0
        self.cuttlefish_player.stack = 0
        self.ajfenix_player.stack = 0
        execute_mutations(
            buy_chips(self.cuttlefish, 1000)
        )
        self.controller.step()

        avail_acts = self.accessor.available_actions(self.cuttlefish_player)
        assert Action.SIT_IN not in avail_acts
        assert Action.SIT_IN_AT_BLINDS not in avail_acts


class SitOutNextHandHeadsUpTest(GenericTableTest):
    def test_sit_out_next_hand(self):
        self.pirate_player.seated = False
        self.cuttlefish_player.seated = False

        self.table.btn_idx = 3 # cowpig

        self.controller.step()

        self.controller.dispatch('sit_out',
                                 player_id=self.cowpig_player.id,
                                 set_to=True)

        self.controller.dispatch('fold',
                                 player_id=self.cowpig_player.id)

        assert len(self.accessor.players_who_can_play()) == 1

class SitOutAtBlindsHeadsUpTest(GenericTableTest):
    def test_sit_out_at_blinds(self):
        self.pirate_player.seated = False
        self.cuttlefish_player.seated = False

        self.table.btn_idx = 3 # cowpig

        self.controller.step()

        self.controller.dispatch('sit_out_at_blinds',
                                 player_id=self.cowpig_player.id,
                                 set_to=True)
        self.controller.dispatch('fold',
                                 player_id=self.cowpig_player.id)

        assert len(self.accessor.players_who_can_play()) == 1


# 0: pirate_player          400
# 1: cuttlefish_player      300
# 2: ajfenix_player         200
# 3: cowpig_player          100
class ReturnUncalledBetsTest(GenericTableTest):
    def test_return_because_folds(self):
        recorder = InMemoryLogSubscriber()
        self.controller.subscribers.append(recorder)

        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()

        self.controller.dispatch('RAISE_TO',
                                 player_id=self.pirate_player.id,
                                 amt=7)
        self.controller.dispatch('FOLD', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        self.controller.dispatch('FOLD', player_id=self.cowpig_player.id)

        uncalled_bet_returns = [
            event for event in recorder.log
            if event[1] == Event.RETURN_CHIPS
        ]

        assert len(uncalled_bet_returns) == 1, \
                'should be one event where bets are returned'
        assert uncalled_bet_returns.pop()[2]['amt'] == 5, \
                'should have returned 5 chips to pirate'
        expected_sum = 400 + 300 + 200 + 100
        assert sum(p.stack_available for p in self.players) == expected_sum

    def test_return_because_allins(self):
        recorder = InMemoryLogSubscriber()
        self.controller.subscribers.append(recorder)

        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()

        self.controller.dispatch('RAISE_TO',
                                 player_id=self.pirate_player.id,
                                 amt=400)
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('CALL', player_id=self.ajfenix_player.id)
        self.controller.dispatch('CALL', player_id=self.cowpig_player.id)

        uncalled_bet_returns = [
            event for event in recorder.log
            if event[1] == Event.RETURN_CHIPS
        ]

        assert len(uncalled_bet_returns) == 1, \
                'should be one event where bets are returned'
        assert uncalled_bet_returns.pop()[2]['amt'] == 100, \
                'should have returned 5 chips to pirate'
        expected_sum = 400 + 300 + 200 + 100
        assert sum(p.stack_available for p in self.players) == expected_sum

    def test_no_return_with_all_ins(self):
        recorder = InMemoryLogSubscriber()
        self.controller.subscribers.append(recorder)

        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()

        self.controller.dispatch('RAISE_TO',
                                 player_id=self.pirate_player.id,
                                 amt=300)
        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('CALL', player_id=self.ajfenix_player.id)
        self.controller.dispatch('CALL', player_id=self.cowpig_player.id)

        uncalled_bet = lambda event: event[1] == Event.RETURN_CHIPS

        uncalled_bet_returns = [e for e in recorder.log if uncalled_bet(e)]

        assert len(uncalled_bet_returns) == 0, \
                'nothing to return; pirate bet 300'
        expected_sum = 400 + 300 + 200 + 100
        assert sum(p.stack_available for p in self.players) == expected_sum

    def test_return_with_sidepot_bet_fold_on_river(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        self.setup_hand(blinds_positions=blind_pos)

        ctrl = self.controller
        acc = self.controller.accessor

        recorder = InMemoryLogSubscriber(acc)
        ctrl.subscribers.append(recorder)

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

        # pirate bets, cuttlefish folds
        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=5)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.end_hand()

        returned_chip_events = [
            event for event in recorder.log
            if event[1] == Event.RETURN_CHIPS
        ]
        assert len(returned_chip_events) == 1
        assert returned_chip_events.pop()[2]['amt'] == 5

    def test_return_with_sidepot_check_fold_on_river(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        self.setup_hand(blinds_positions=blind_pos)

        ctrl = self.controller
        acc = self.controller.accessor

        recorder = InMemoryLogSubscriber(acc)
        ctrl.subscribers.append(recorder)

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=275)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        # ajfenix and cowpig are all-in
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)

        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=5)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        # pirate checks, cuttlefish folds
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.end_hand()

        returned_chip_events = [
            event for event in recorder.log
            if event[1] == Event.RETURN_CHIPS
        ]
        assert len(returned_chip_events) == 0


# 0: pirate       (400)
# 1: cuttlefish   (300)
# 2: ajfenix      (200)
# 3: cowpig       (100)
# 4: alexeimartov (400)
class ComplicatedReturnUncalledBetsTest(FivePlayerTableTest):
    def test_complicated_return_uncalled_bets(self):
        blind_pos = {'btn_pos': 1, 'sb_pos': 2, 'bb_pos': 3}
        self.setup_hand(blinds_positions=blind_pos)

        ctrl = self.controller
        acc = self.controller.accessor

        recorder = InMemoryLogSubscriber(acc)
        ctrl.subscribers.append(recorder)

        nxt = acc.next_to_act()
        ctrl.dispatch('raise_to', player_id=nxt.id, amt=275)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)
        ctrl.dispatch('call', player_id=acc.next_to_act().id)

        # ajfenix and cowpig are all-in
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)

        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)
        ctrl.dispatch('check', player_id=acc.next_to_act().id)

        # alexeimartov bets, pirate raises, cuttlefish raises, fold, fold
        ctrl.dispatch('bet', player_id=acc.next_to_act().id, amt=5)
        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=10)
        ctrl.dispatch('raise_to', player_id=acc.next_to_act().id, amt=25)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.player_dispatch('fold', player_id=acc.next_to_act().id)
        ctrl.end_hand()

        returned_chip_events = [
            event for event in recorder.log
            if event[1] == Event.RETURN_CHIPS
        ]
        assert len(returned_chip_events) == 1
        assert returned_chip_events.pop()[2]['amt'] == 15

class PlayerToggleEventsTest(GenericTableTest):
    def test_sit_in_and_out(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()

        self.controller.dispatch('SIT_OUT',
                                 player_id=self.pirate_player.id)
        assert self.pirate_player.playing_state == PlayingState.SIT_OUT_PENDING
        self.controller.dispatch('FOLD', player_id=self.pirate_player.id)

        # should be sat out at the beginning of next hand
        assert not self.pirate_player.is_sitting_out()

        # pirate can cancel this and return to a folded state
        self.controller.dispatch('SIT_IN', player_id=self.pirate_player.id)
        assert self.pirate_player.playing_state == PlayingState.SITTING_IN


        self.controller.dispatch('FOLD', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('SIT_OUT', player_id=self.cuttlefish_player.id)

        # import ipdb; ipdb.set_trace()
        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        # this ends the hand, and cuttlefish's pending sit_out should fire
        assert self.cuttlefish_player.is_sitting_out()
        # pirate cancelled it, should be still active
        assert self.pirate_player.is_active()

        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.cuttlefish_player.id)
        # this should take effect immediately, since cuttlefish is
        #   already sitting out
        assert len(self.accessor.seated_players()) == 3

    def test_leave_seat(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()
        pirate = self.pirate_player
        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=pirate.id)

        assert pirate.last_action == Event.FOLD
        assert pirate.playing_state == PlayingState.LEAVE_SEAT_PENDING

        # should leave table at the beginning of next hand
        assert pirate.seated == True

        # pirate can cancel this and return to a folded state
        self.controller.dispatch('TAKE_SEAT',
                                 player_id=pirate.id,
                                 position=pirate.position)
        assert pirate.playing_state == PlayingState.SITTING_IN

        self.controller.dispatch('FOLD', player_id=self.cuttlefish_player.id)
        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.cuttlefish_player.id)

        self.controller.dispatch('FOLD', player_id=self.ajfenix_player.id)
        # this ends the hand, and cuttlefish's pending sit_out should fire
        assert self.cuttlefish_player.seated == False
        # pirate cancelled it, should be still active
        assert pirate.is_active()


class BountyHandWhenPlayerSitsOutTest(GenericTableTest):
    def test_bounty_with_sit_out(self):
        self.table.table_type = NL_BOUNTY
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        controller = BountyController(self.table, players=self.players)
        accessor = controller.accessor

        controller.step()
        self.cowpig_player.cards = ['7s', '2d']

        controller.dispatch('FOLD', player_id=self.pirate_player.id)
        controller.dispatch('LEAVE_SEAT', player_id=self.pirate_player.id)
        controller.dispatch('FOLD', player_id=self.cuttlefish_player.id)
        controller.dispatch('SIT_OUT', player_id=self.cuttlefish_player.id)
        controller.dispatch('FOLD', player_id=self.ajfenix_player.id)

        # pirate is on the hook for bounty despite leaving seat
        # cuttlefish is on the hook for bounty despite sitting out
        assert accessor.current_pot() == self.cowpig_player.stack * 3


class PresetActionsTest(GenericTableTest):
    def test_sit_in_and_out(self):
        self.table.btn_idx = 0
        self.table.sb_idx = 1
        self.table.bb_idx = 2

        self.controller.step()

        try:
            self.controller.dispatch('SET_PRESET_CHECKFOLD',
                                     player_id=self.pirate_player.id,
                                     set_to=True)
            assert False, \
                    'should not be able to set a preset condition '\
                    ' when it is your turn to act'
        except ValueError:
            pass

        try:
            self.controller.dispatch('SET_PRESET_CALL',
                                     player_id=self.cuttlefish_player.id,
                                     set_to=10)
            assert False, 'preset call should only work for current call_amt'
        except ValueError:
            pass

        # import ipdb; ipdb.set_trace()
        self.controller.dispatch('SET_PRESET_CALL',
                                 player_id=self.cuttlefish_player.id,
                                 set_to=2)
        assert self.cuttlefish_player.preset_call == Decimal(2)

        self.controller.dispatch('SET_PRESET_CALL',
                                 player_id=self.ajfenix_player.id,
                                 set_to=2)
        self.controller.dispatch('SET_PRESET_CHECKFOLD',
                                 player_id=self.ajfenix_player.id,
                                 set_to=True)
        assert not self.ajfenix_player.preset_call
        assert self.ajfenix_player.preset_checkfold == True

        self.controller.dispatch('SET_PRESET_CHECK',
                                 player_id=self.cowpig_player.id,
                                 set_to=True)

        self.controller.dispatch('RAISE_TO',
                                 player_id=self.pirate_player.id,
                                 amt=6)

        next_to_act = self.controller.accessor.next_to_act()
        assert next_to_act == self.cuttlefish_player, \
                'preset call of 2 no longer applies when wager amt is 6'

        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)

        assert self.ajfenix_player.last_action == Event.FOLD

        self.controller.dispatch('CALL', player_id=self.cowpig_player.id)

        presets = ['preset_call', 'preset_checkfold', 'preset_check']
        for player in self.accessor.active_players():
            for preset in presets:
                assert not getattr(player, preset), \
                        'all presets should be cleared on new street'

        self.controller.dispatch('BET',
                                 player_id=self.cowpig_player.id,
                                 amt=15)
        self.controller.dispatch('SET_PRESET_CALL',
                                 player_id=self.cuttlefish_player.id,
                                 set_to=15)
        self.controller.dispatch('SET_PRESET_CALL',
                                 player_id=self.cuttlefish_player.id,
                                 set_to=0)

        assert not self.cuttlefish_player.preset_call

        self.controller.dispatch('CALL', player_id=self.pirate_player.id)

        next_to_act = self.controller.accessor.next_to_act()
        assert next_to_act == self.cuttlefish_player, \
                'preset call should be cleared'

        self.controller.dispatch('CALL', player_id=self.cuttlefish_player.id)

        assert self.controller.accessor.is_turn(), \
                'call should have brought us to the next street'

        self.controller.dispatch('BET',
                                 player_id=self.cowpig_player.id,
                                 amt=15)
        self.controller.dispatch('SET_PRESET_CALL',
                                 player_id=self.cuttlefish_player.id,
                                 set_to=15)
        self.controller.dispatch('FOLD', player_id=self.pirate_player.id)

        assert self.controller.accessor.is_river(), \
                'preset-call should have brought us to the next street'


class PlayerNHandsIncrementTest(GenericTableTest):
    def test_player_n_hands_incremented(self):
        cont = self.controller
        acc = cont.accessor

        cont.step()

        assert self.cuttlefish_player.n_hands_played == 0

        # plays 5 hands; cuttlefish_player sit out afterwards
        for _ in range(3 * 5 - 1):
            cont.dispatch('FOLD', player_id=acc.next_to_act().id)
        cont.dispatch('SIT_OUT', player_id=self.cuttlefish_player.id)
        cont.dispatch('FOLD', player_id=acc.next_to_act().id)

        assert self.cuttlefish_player.n_hands_played == 5

        # 5 more hands
        for _ in range(2 * 5):
            cont.dispatch('FOLD', player_id=acc.next_to_act().id)

        assert self.cuttlefish_player.n_hands_played == 5
        assert self.pirate_player.n_hands_played == 10


class GamestateIsClearedAtEndOfHandTest(GenericTableTest):
    def test_gamestate_is_cleared(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,
            'sb_pos': 1,
            'bb_pos': 2,
        })

        cont = self.controller
        acc = cont.accessor

        while not acc.is_river():
            player = acc.next_to_act()
            if acc.call_amt() < 7:
                if Action.BET in acc.available_actions(player):
                    cont.dispatch('BET', player_id=player.id, amt=7)
                else:
                    cont.dispatch('RAISE_TO', player_id=player.id, amt=7)
            else:
                cont.dispatch('CALL', player_id=player.id)

        player = acc.next_to_act()
        cont.dispatch('BET', player_id=player.id, amt=5)

        for _ in range(3):
            player = acc.next_to_act()
            cont.dispatch('FOLD', player_id=player.id, sit_out=True)

        assert not acc.enough_players_to_play()
        assert acc.table.board == []
        uncollected = sum(
            plyr.uncollected_bets
            for plyr in acc.seated_players()
        )
        assert uncollected == 0


class NoDispatchLoopIfNotEnoughPlayersTest(GenericTableTest):
    def test_no_dipatch_loop(self):
        for player in self.players[:3]:
            self.controller.internal_dispatch(
                [(player, Event.LEAVE_SEAT, {'immediate': True})]
            )

        self.controller.step()

        assert self.controller.accessor.btn_is_locked()

        def log_instead(events):
            log_instead.new_events += events
        log_instead.new_events = []

        self.controller.internal_dispatch = log_instead

        self.controller.step()
        assert not log_instead.new_events


class SplitPotShowdownTest(GenericTableTest):
    def test_split_pot_showdown(self):
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,7d',
                self.cuttlefish_player: '2d,7h',
                self.ajfenix_player: '2h,7c',
                self.cowpig_player: '2c,7s',
            },
        )

        self.controller.subscribers = [InMemoryLogSubscriber(self.accessor)]

        # preflop
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='RAISE_TO', amt=50)
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CALL')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CALL')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CALL')

        self.table.board = ['3h', '3c', '4h', '5h', 'Kd']
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')
        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')

        self.controller.dispatch(player_id=self.accessor.next_to_act().id,
                                 action_name='CHECK')

        # test the chat summary
        chats = [
            kwargs['msg']
            for _, event, kwargs, _ in self.controller.subscribers[0].log
            if event == Event.CHAT
        ]

        for chat in chats:
            if 'chips' in chat:
                assert 'split' in chat, 'should be a split pot msg'

        # make sure player cards are in the win_events
        win_event_kwargs = [
            kwargs
            for _, event, kwargs, _ in self.controller.subscribers[0].log
            if event == Event.WIN
        ]

        for kwargs in win_event_kwargs:
            assert 'winning_hand' in kwargs, 'Need winning_hand for frontend'
            assert len(kwargs['winning_hand']) == 5


class BotsSitInTest(GenericTableTest):
    def test_bots_sit_in(self):
        self.controller.step()

        robots = (self.pirate_player, self.cowpig_player, self.ajfenix_player)
        # make them robots and time them out
        for plyr in robots:
            plyr.user.is_robot = True
            self.controller.dispatch('SIT_OUT', player_id=plyr.id)

        for _ in range(3):
            next_to_act = self.accessor.next_to_act()
            self.controller.dispatch('FOLD', player_id=next_to_act.id)

        assert self.accessor.is_predeal()
        assert not self.accessor.enough_players_to_play()

        # they should sit themselves back in here
        self.controller.dispatch_sit_in_for_bots()

        assert not self.accessor.is_predeal()
        assert self.accessor.is_preflop()

        assert len(self.accessor.active_players()) == 4


class SimultaneousSitInSitOutEdgecaseTest(GenericTableTest):
    def test_simultaneous_sit_in_sit_out_edgecase(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,
            'sb_pos': 1,
            'bb_pos': 2,
        })
        pirate = self.pirate_player             # 0
        cuttlefish = self.cuttlefish_player     # 1
        ajfenix = self.ajfenix_player           # 2
        cowpig = self.cowpig_player             # 3

        self.controller.dispatch('fold', player_id=cowpig.id, sit_out=True)
        self.controller.dispatch('fold', player_id=pirate.id, sit_out=True)
        self.controller.dispatch('fold', player_id=cuttlefish.id)

        self.controller.dispatch('fold', player_id=ajfenix.id)

        self.controller.dispatch('sit_in', player_id=pirate.id)
        self.controller.dispatch('sit_in', player_id=cowpig.id)
        self.controller.dispatch('sit_out', player_id=ajfenix.id)
        self.controller.dispatch('fold', player_id=cuttlefish.id, sit_out=True)

        assert ajfenix.is_sitting_out()
        assert cuttlefish.is_sitting_out()

        assert not cowpig.is_sitting_out()
        assert not pirate.is_sitting_out()

        assert self.table.btn_idx in (0, 3)
        assert self.table.bb_idx in (0, 3)
        assert self.table.sb_idx in (0, 3)


class KickInactivePlayersTest(GenericTableTest):
    def test_kick_inactive_players(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,
            'sb_pos': 1,
            'bb_pos': 2,
        })
        pirate = self.pirate_player             # 0
        cuttlefish = self.cuttlefish_player     # 1
        ajfenix = self.ajfenix_player           # 2
        cowpig = self.cowpig_player             # 3

        assert not ajfenix.is_sitting_out()
        assert not cuttlefish.is_sitting_out()

        self.controller.dispatch('fold', player_id=cowpig.id, sit_out=True)
        self.controller.dispatch('fold', player_id=pirate.id, sit_out=True)
        self.controller.dispatch('fold', player_id=cuttlefish.id)
        self.controller.dispatch('fold', player_id=ajfenix.id)
        self.controller.dispatch('sit_in', player_id=pirate.id)
        self.controller.dispatch('sit_in', player_id=cowpig.id)
        self.controller.dispatch('sit_out', player_id=ajfenix.id)
        self.controller.dispatch('fold', player_id=cuttlefish.id, sit_out=True)

        assert ajfenix.is_sitting_out()
        assert cuttlefish.is_sitting_out()
        assert cuttlefish.seated
        assert ajfenix.seated

        inactivity_bump = timedelta(minutes=BUMP_AFTER_INACTIVE_MINS)
        with TimezoneMocker(timezone.now() + inactivity_bump):
            self.controller.dispatch_kick_inactive_players()

        assert not cuttlefish.seated
        assert not ajfenix.seated


class LeaveSeatFoldTest(GenericTableTest):
    def test_leave_seat_fold(self):
        self.ajfenix_player.seated = False
        self.cowpig_player.seated = False
        self.setup_hand(blinds_positions={
            'btn_pos': 0,
            'sb_pos': 0,
            'bb_pos': 1,
        })
        nxt = self.accessor.next_to_act()
        self.controller.dispatch('LEAVE_SEAT', player_id=nxt.id)
        assert self.accessor.current_pot() == 0
        assert not self.accessor.enough_players_to_play()


class KickBoredRobotsTest(GenericTableTest):
    def test_kick_bored_robots(self):
        self.pirate.is_robot = True
        self.pirate.save()
        self.cuttlefish.is_robot = True
        self.cuttlefish.save()
        self.table.hand_number = 501
        self.table.save()
        # see PokerAccessor.is_bored for how fnv_hash is
        #   used to determine boredom
        assert fnv_hash('pirate') % 40 == 514 % 40
        assert fnv_hash('cuttlefish') % 40 == 502 % 40

        inactivity_bump = timedelta(minutes=BUMP_AFTER_INACTIVE_MINS)
        now = timezone.now()
        bumptime1 = now + inactivity_bump
        bumptime2 = bumptime1 + inactivity_bump
        # bumptime3 = bumptime2 + inactivity_bump

        self.controller.step()

        assert len(self.accessor.seated_players()) == 4

        self.controller.dispatch('LEAVE_SEAT',
                                 player_id=self.cowpig_player.id)

        while self.table.hand_number < 502:
            self.controller.dispatch(
                'FOLD',
                player_id=self.accessor.next_to_act().id,
                sit_out=True
            )

        sit_in_plyrs = [
            plyr for plyr in self.accessor.seated_players()
            if plyr.playing_state == PlayingState.SITTING_IN
        ]
        if sit_in_plyrs:
            self.controller.dispatch(
                'SIT_OUT',
                sit_to=True,
                player_id=sit_in_plyrs[0].id
            )

        with TimezoneMocker(bumptime1):
            self.controller.dispatch_kick_inactive_players()

            assert self.accessor.is_bored(self.cuttlefish_player), (
                "cuttlefish's boredom hand is 502"
            )
            assert len(self.accessor.seated_players()) == 3, (
                "but wasn't booted because robots never get bored "
                "around human players"
            )

            self.controller.dispatch_sit_in_for_bots()
            while self.table.hand_number < 514:
                self.controller.dispatch(
                    'FOLD',
                    player_id=self.accessor.next_to_act().id
                )

        assert len(self.accessor.seated_players()) == 2, (
            "By now, ajfenix (the last remaining human player) "
            "has been booted for sitting out 3+ orbits"
        )

        with TimezoneMocker(bumptime2):
            self.controller.dispatch_kick_inactive_players()
            if len(self.accessor.seated_players()) == 2:
                bb_state = self.accessor.bb_player().playing_state
                assert bb_state == PlayingState.LEAVE_SEAT_PENDING
                self.controller.dispatch(
                    'FOLD',
                    player_id=self.accessor.next_to_act().id
                )
            self.controller.dispatch_kick_inactive_players()

        # assert len(self.accessor.seated_players()) == 1, (
        #     "pirate left, but cuttlefish will wait a "
        #     "minute before also leaving out of loneliness"
        # )

        # with TimezoneMocker(bumptime3):
        #     self.controller.dispatch_kick_inactive_players()

        assert len(self.accessor.seated_players()) == 0


class JoinTableBuyinAmt(TableWithChipsTest):
    def test_join_table_no_rebuy(self):
        # table.min_buyin is 120
        new_user = get_user_model().objects.create_user(
            username='new_user',
            email='new_user@hello.com',
            password='banana'
        )
        new_user.save()
        execute_mutations(
            buy_chips(new_user, 200)
        )
        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 200

        new_plyr = self.controller.join_table(new_user.id)
        assert new_plyr.stack == 120

    def test_join_table_autorebuy(self):
        # player.user.auto_rebuy_in_bbs is 100
        new_user = get_user_model().objects.create_user(
            username='new_user',
            email='new_user@hello.com',
            password='banana',
            auto_rebuy_in_bbs=100
        )
        new_user.save()

        execute_mutations(
            buy_chips(new_user, 200)
        )
        new_user.userbalance().refresh_from_db()
        assert new_user.userbalance().balance == 200

        self.controller.dispatch('join_table', user_id=new_user.id)
        new_plyr = self.controller.accessor.player_by_user_id(new_user.id)
        assert new_plyr.stack == 200


class TestGameUtilsPerformance(GenericTableTest):
    def test_fuzzy_get_table(self):
        table_id = self.accessor.table.id

        with self.assertNumQueries(1):
            table = fuzzy_get_table(table_id, only=('id', 'name'))

        with self.assertNumQueries(0):
            assert table.name == self.accessor.table.name

        with self.assertNumQueries(5):
            # 1 for table
            # 1 for players
            # 1 for user.username and user.is_robot
            # 1 for stats
            # 1 for chathistory
            table = fuzzy_get_table(table_id)

        with self.assertNumQueries(0):
            table.player_set.all()[0].username


class TestLastHumanActionTimestamp(GenericTableTest):
    def test_last_human_action_timestamp(self):
        self.controller.step()

        time1 = timezone.now() + timedelta(minutes=11)
        time2 = time1 + timedelta(seconds=15)
        time3 = time2 + timedelta(seconds=10)

        start_time = self.table.last_human_action_timestamp

        next_plyr = self.accessor.next_to_act()
        next_plyr.user.is_robot = True

        with TimezoneMocker(time1):
            self.controller.dispatch('FOLD', player_id=next_plyr.id)
            assert not has_recent_human_activity(self.table, minutes=10)

        # unchanged because robot acted
        assert self.table.last_human_action_timestamp == start_time

        next_plyr = self.accessor.next_to_act()
        next_plyr.user.is_robot = False

        with TimezoneMocker(time2):
            self.controller.dispatch('FOLD', player_id=next_plyr.id)
            assert has_recent_human_activity(self.table, minutes=10)

        assert self.table.last_action_timestamp == time2
        assert self.table.last_human_action_timestamp == time2

        next_plyr = self.accessor.next_to_act()
        next_plyr.user.is_robot = True

        with TimezoneMocker(time3):
            self.controller.dispatch('FOLD', player_id=next_plyr.id)

        # greater than because 3 folds starts a new hand and therefore
        #   table-specific events move the last_action_timestamp forward
        assert self.table.last_action_timestamp > time3
        # unchanged because robot acted
        assert self.table.last_human_action_timestamp == time2


class TestPresetCall(TableWithChipsTest):
    def test_no_preset_call_on_call_zero(self):
        self.setup_hand(blinds_positions={
            'btn_pos': 0,
            'sb_pos': 1,
            'bb_pos': 2,
        })
        pirate = self.pirate_player             # 0
        cuttlefish = self.cuttlefish_player     # 1
        ajfenix = self.ajfenix_player           # 2
        cowpig = self.cowpig_player             # 3

        assert not ajfenix.is_sitting_out()
        assert not cuttlefish.is_sitting_out()

        self.controller.dispatch('fold', player_id=cowpig.id, sit_out=True)
        self.controller.dispatch('raise_to', player_id=pirate.id, amt=10)

        #setting preset to 0, simulating frontend checks
        self.controller.dispatch('SET_PRESET_CALL',
                                  player_id=ajfenix.id,
                                  set_to=10)
        self.controller.dispatch('SET_PRESET_CALL',
                                  player_id=ajfenix.id,
                                  set_to=0)
        assert ajfenix.preset_call == Decimal(0)
        self.controller.dispatch('fold', player_id=cuttlefish.id, sit_out=True)
        self.controller.dispatch('call', player_id=ajfenix.id, amt=10)

        assert ajfenix.preset_call == Decimal(0)
