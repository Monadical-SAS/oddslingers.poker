import json

import os

from django.test import TestCase

from poker.constants import HH_TEST_PATH
from poker.replayer import ActionReplayer
from poker.controllers import InvalidAction, BountyController

from poker.tests.test_controller import GenericTableTest
from poker.tests.test_replayer import ActionReplayerTest, EventReplayerTest

from poker.tests.test_log import assert_equivalent_game_states  # noqa


class RaiseAmountTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'raise_amount.json')
        super(RaiseAmountTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()

        def bad_raise_size(replayer):
            bad_event = {
                "ts": "18:54:14",
                "args": "3",
                "event": "RAISE_TO",
                "subj": "ajfenix"
            }
            self.replayer.dispatch_event(bad_event)

        self.assertRaises(Exception, bad_raise_size, self.replayer)


class RaiseAmount2Test(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'raise_amount2.json')
        super(RaiseAmount2Test, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()

        try:
            good_event = {
                "event": "RAISE_TO",
                "args": {
                    "amt": "400"
                },
                "subj": "max"
            }
            self.replayer.dispatch_event(good_event)
        except:
            self.fail("Valid raise size considered invalid!")


class RaiseAmount3Test(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'raise_amount3.json')
        super(RaiseAmount3Test, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()

        try:
            good_event = {
                "event": "RAISE_TO",
                "args": {
                    "amt": "200"
                },
                "subj": "max"
            }
            self.replayer.dispatch_event(good_event)
        except:
            self.fail("Valid raise size considered invalid!")


class BetAmountTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'bet_amount.json')
        super(BetAmountTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()

        try:
            good_event = {
                "event": "BET",
                "args": {
                    "amt": "1"
                },
                "subj": "cuttlefish"
            }
            self.replayer.dispatch_event(good_event)
        except:
            self.fail("Valid raise size considered invalid!")


class CallSameSizeTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'call_same_size.json')
        super(CallSameSizeTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor
        p_max = accessor.player_by_username("max")
        p_fenix = accessor.player_by_username("ajfenix")

        self.assertEqual(p_max.uncollected_bets, p_fenix.uncollected_bets)
        self.assertEqual(p_max.wagers, p_fenix.wagers)


class BrokenShowdownTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'broken_showdown.json')
        super(BrokenShowdownTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        self.replayer.controller.end_hand()

        players = self.replayer.controller.accessor.active_players()
        self.assertEqual(sum([p.stack_available for p in players]), 200*5)


class FirstToActTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'first_to_act_after_allin.json')
        super(FirstToActTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor
        p_cuttlefish = accessor.player_by_username("cuttlefish")
        self.assertEqual(accessor.next_to_act(), p_cuttlefish)


class FirstToAct2Test(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'first_to_act2.json')
        super(FirstToAct2Test, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()

        accessor = self.replayer.controller.accessor
        p_cuttlefish = accessor.player_by_username("cuttlefish")

        next_to_act = accessor.next_to_act()
        self.assertEqual(next_to_act, p_cuttlefish)


class HandEndWithOneAllinTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'hand_should_end.json')
        super(HandEndWithOneAllinTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        event = {
            "subj": "ajfenix",
            "ts": "00:14:08",
            "event": "CALL",
            "args": {
                "amt": "50"
            }
        }

        hand_number = self.replayer.table.hand_number
        self.replayer.dispatch_event(event)
        self.replayer.controller.step()

        self.assertEqual(hand_number + 1, self.replayer.table.hand_number)


class NextToActTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'next_to_act.json')
        super(NextToActTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor

        p_ajfenix = accessor.player_by_username("ajfenix")
        next_to_act = accessor.next_to_act()
        self.assertEqual(next_to_act, p_ajfenix)


class NextToAct2Test(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'next_to_act2.json')
        super(NextToAct2Test, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor

        p_max = accessor.player_by_username("max")
        next_to_act = accessor.next_to_act()
        self.assertEqual(next_to_act, p_max)


class NextToAct3Test(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'next_to_act3.json')
        super(NextToAct3Test, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor

        self.assertEqual(accessor.next_to_act(), None)


class NextToAct4Test(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'next_to_act4.json')
        super(NextToAct4Test, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor
        # import ipdb; ipdb.set_trace()
        self.assertEqual(accessor.next_to_act(), None)


class BrokenPostTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'broken_post.json')
        super(BrokenPostTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()

        try:
            self.replayer.controller.step()
        except Exception as e:
            self.fail(f"Got exception when trying to POST:\n{e}")


class FaultyRaiseTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'faulty_raise.json')
        super(FaultyRaiseTest, self).setUp(filename=filename)

    def test_stuff(self):
        self.replayer.skip_to_end_of_hand()
        accessor = self.replayer.controller.accessor
        faulty_raise = {
            "args": {
                "amt": "4"
            },
            "event": "RAISE_TO",
            "subj": "pirate"
        }
        self.replayer.dispatch_event(faulty_raise)

        pirate = accessor.player_by_username('pirate')
        self.assertEqual(pirate.stack, 0)
        self.assertEqual(pirate.wagers, 4)


class HandEndsTest(EventReplayerTest):
    def setUp(self):
        filename = os.path.join(HH_TEST_PATH, 'end_hand.json')
        super(HandEndsTest, self).setUp(filename=filename)

    def test_stuff(self):
        accessor = self.replayer.controller.accessor
        chips_before = sum(p.stack + p.wagers for p in accessor.players)

        self.replayer.skip_to_end_of_hand()
        all_chips = sum(p.stack + p.wagers for p in accessor.players)

        self.replayer.controller.step()
        new_chip_count = sum(p.stack + p.wagers for p in accessor.players)

        self.assertEqual(all_chips, chips_before)
        self.assertEqual(all_chips, new_chip_count)


class BlindsWrongTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'blinds_wrong.json')
        super().setUp(self.filename, hand_idx=0)

    def test_blinds_are_correct(self):
        rep = self.replayer

        # step forward to next hand
        while True:
            try:
                rep.step_forward()
            except StopIteration:
                break

        rep.controller.step()

        assert rep.table.bb_idx == 2
        assert rep.accessor.player_by_username('max').is_sitting_out() == False


class EffectiveHeadsUpBlindsTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'effective_hu_blinds_move.json')
        super().setUp(self.filename, hand_idx=0)

    def test_blinds_are_correct(self):
        rep = self.replayer

        # step forward to next hand
        for _ in range(len(rep.current_hand()['actions']) - 2):
            rep.step_forward()
        # import ipdb; ipdb.set_trace()
        rep.step_forward()
        rep.step_forward()

        assert rep.table.btn_idx == 2
        assert rep.table.sb_idx == 2
        assert rep.table.bb_idx == 4
        assert rep.accessor\
                  .player_by_username('cowpig')\
                  .is_sitting_out() == True


class CrazyBlindsEdgecaseTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'crazy_blinds_edgecase.json')
        super().setUp(self.filename)

    def test_stuff(self):
        '''
        This is a crazy edgecase that looks like this:
        pos #: name         cards  stack   - last_action
         bb 0: pirate      [ out ] 0.00    -    none
        btn 2: ajfenix     [     ] 1223.00 -    none
            3: cowpig      [     ] 165.00  -   SIT_IN
         sb 4: alexeimart  [ out ] 0.00    -    none
            5: cuttlefish  [     ] 12.00   -   SIT_IN
        '''
        rep = self.replayer
        # rep.verbose = True
        acc = rep.controller.accessor
        rep.skip_to_end_of_hand()
        rep.controller.step()

        ajfenix = acc.player_by_username('ajfenix')
        cowpig = acc.player_by_username('cowpig')
        cuttlefish = acc.player_by_username('cuttlefish')

        assert acc.table.btn_idx == ajfenix.position
        assert acc.table.sb_idx == cowpig.position
        assert acc.table.bb_idx == cuttlefish.position


class MinBetTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(HH_TEST_PATH, 'min_bet.json')
        super().setUp(self.filename)

    def test_min_bet(self):
        rep = self.replayer

        # rep.verbose = True
        rep.skip_to_last_hand()
        for _ in range(3):
            rep.step_forward()

        next_player = rep.accessor.next_to_act()
        try:
            rep.controller.dispatch(
                'raise_to',
                player_id=next_player.id,
                amt=7
            )
        except InvalidAction:
            return

        self.fail('Should raise ValueError')


class HHIntegrityTest(TestCase):
    '''
        checks the integrity of hh files saved in the hh files folder
    '''

    def test_hh_integrity(self):
        path = HH_TEST_PATH
        hh_files = [
            os.path.join(path, fn)
            for fn in os.listdir(path)
            if os.path.isfile(os.path.join(path, fn)) and '.json' in fn
        ]
        for filename in hh_files:
            self.check_deal_integrity(filename)
            # self.check_action_event_integrity(filename)

    # TODO: uncomment this when issue #347 (update EventReplayer) is done
    # def test_action_event_integrity(self, filename):
    #     data = json.load(open(filename))
    #     action_replayer = ActionReplayer(data, hand_idx=0)
    #     action_replayer.describe()
    #     event_replayer = EventReplayer(data, hand_idx=0)
    #     event_replayer.describe()

    #     while True:
    #         for _ in action_replayer.current_hand()['actions']:
    #             # print('...')
    #             # print(f'dispatching {action_replayer.current_action()}')
    #             action_replayer.step_forward(multi_hand=False)
    #         action_replayer.controller.end_hand()

    #         while True:
    #             try:
    #                 # print('...')
    #                 # print(f'dispatching {event_replayer.current_event()}')
    #                 event_replayer.step_forward()
    #                 event_replayer.describe()
    #             except StopIteration:
    #                 break
    #         event_replayer.controller.end_hand()

    #         assert_equivalent_game_states(
    #             event_replayer.controller.accessor,
    #             action_replayer.controller.accessor
    #         )

    #         try:
    #             event_replayer.next_hand()
    #             action_replayer.next_hand()
    #         except StopIteration:
    #             break

    def check_deal_integrity(self, filename):
        with open(filename) as file:
            data = json.load(file)
        if 'replayer' not in data['hands'][0].keys():
            return

        replayer = ActionReplayer(data, hand_idx=0)
        # replayer.verbose = True

        def get_all_cards(replayer):
            output = [
                card
                for player in replayer.accessor.players
                    for card in player.cards or []
            ]
            for card in replayer.table.board or []:
                output.append(card)

        all_cards = []

        while True:
            try:
                replayer.step_forward()
            except StopIteration:
                break

            all_cards.append(get_all_cards(replayer))

        replayer.skip_to_hand_idx(0)

        for cards_list in all_cards:
            replayer.step_forward()
            self.assertEqual(cards_list, get_all_cards(replayer))


class ActionReplayerBountyFlipTest(GenericTableTest):
    def test_action_replayer_bounty_flip(self):
        self.table.table_type = 'BNTY'
        self.controller = BountyController(
            self.table,
            players=self.players,
            subscribers=[],
        )
        # self.controller.verbose = True
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,7d',
                self.cuttlefish_player: '2d,7h',
                self.ajfenix_player: '2h,7c',
                self.cowpig_player: '2c,7s',
            },
            add_log=True,
        )
        acc = self.controller.accessor
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)
        # we're at the bounty flip
        assert acc.current_pot() > 400
        bounty_flip_hands = {
            plyr.username: plyr.cards_str for plyr in acc.players
        }
        bounty_deck = acc.table.deck_str
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)
        self.controller.dispatch('call', player_id=acc.next_to_act().id)
        json_log = self.controller.log.get_log('all')
        assert len(json_log['hands']) == 2

        rep = ActionReplayer(json_log, hand_idx=0)

        # start at hand 0
        assert rep.accessor.table.hand_number == 0
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)
        # should fold around and trigger a bounty flip; still in 1st hand
        assert rep.accessor.table.hand_number == 0
        assert rep.accessor.current_pot() > 400

        for player in rep.accessor.players:
            assert player.cards_str == bounty_flip_hands[player.username]
        assert bounty_deck.startswith(rep.accessor.table.deck_str)
        rep.step_forward(multi_hand=True)
        # now we're onto the next hand
        assert rep.accessor.table.hand_number == 1


class ActionReplayerNewHandNotEnoughPlayersTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'reset_sit_in_first_action.json'
        )
        super().setUp(self.filename, hand_idx=0)

    def test_action_replayer_new_hand_not_enough_players(self):
        # tests the `_player_sits_in_to_start_new_hand_edgecase`

        # test that skipping to a hand w/that edgecase works
        self.replayer.skip_to_hand_number(64)

        assert not self.replayer.accessor.is_predeal()
        assert self.replayer.accessor.enough_players_to_play()

        self.replayer.step_forward()
        assert not self.replayer.accessor.is_predeal()

        # test that iterating through the edgecase also works
        self.replayer.skip_to_hand_number(63)

        while True:
            try:
                self.replayer.step_forward(multi_hand=True)
            except StopIteration:
                break

        assert self.replayer.current_hand()['table']['hand_number'] == 64
        assert self.replayer.action_idx > 1

class ActionReplayerNewHandSitInOnResetTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'new_hand_not_enough_players.json'
        )
        super().setUp(self.filename, hand_idx=0)

    def test_action_replayer_new_hand_not_enough_players(self):
        self.replayer.skip_to_hand_idx(1)

        assert self.replayer.accessor.is_predeal()
        assert self.replayer.accessor.table.hand_number == 15
        assert not self.replayer.accessor.enough_players_to_play()


class ActionReplayerDeadSmallBlindBug(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'sb_replayer_bug.json'
        )
        super().setUp(self.filename, hand_number=9)

    def test_action_replayer_dead_sb_bug(self):
        while self.replayer.current_hand()['table']['hand_number'] != 10:
            self.replayer.step_forward(multi_hand=True)

        cuttlefish = self.replayer.accessor.player_by_username('cuttlefish')
        assert cuttlefish.dead_money == 1


class OwesBBOnResetTest(ActionReplayerTest):
    def setUp(self):
        self.filename = 'poker/tests/data/owes_bb_bug.json'
        super().setUp(self.filename)

    def test_owes_bb_on_reset(self):
        rep = self.replayer
        rep.skip_to_hand_number(15)
        assert not rep.accessor.player_by_username('pirate').owes_bb


class ActionReplayerSitInNonRandomDeck(GenericTableTest):
    def test_action_replayer_sit_in_non_random_deck(self):
        # self.controller.verbose = True
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,7d',
                self.cuttlefish_player: '2d,7h',
                self.ajfenix_player: '2h,7c',
                self.cowpig_player: '2c,7s',
            },
            add_log=True,
        )
        acc = self.controller.accessor
        # self.controller.verbose = True

        # Sit out all the players except one
        self.controller.dispatch('sit_out', player_id=acc.next_to_act().id)
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)
        self.controller.dispatch('sit_out', player_id=acc.next_to_act().id)
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)
        self.controller.dispatch('sit_out', player_id=acc.next_to_act().id)
        self.controller.dispatch('fold', player_id=acc.next_to_act().id)

        # There are not enough players to play
        assert len(acc.active_players()) == 1
        # import ipdb; ipdb.set_trace()
        # Now there are enough players so, start a new hand
        self.controller.dispatch('sit_in', player_id=self.cowpig_player.id)

        # Let's save the new hands and the new deck
        controller_hands = {
            plyr.username: plyr.cards_str for plyr in acc.players
        }
        controller_deck = acc.table.deck_str

        # one last fold to test that we can step forward after this
        self.controller.dispatch('call', player_id=acc.next_to_act().id)

        json_log = self.controller.log.get_log('all')
        assert len(json_log['hands']) == 2

        rep = ActionReplayer(json_log, hand_idx=0)

        assert rep.accessor.table.hand_number == 0

        # Executing sit outs and folds
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)
        rep.step_forward(multi_hand=True)

        # New hand and sit in
        assert rep.accessor.table.hand_number == 1
        rep.step_forward(multi_hand=True)

        # Replayer should use hand and deck in the logs
        for player in rep.accessor.active_players():
            assert player.cards_str == controller_hands[player.username]
        assert controller_deck.startswith(rep.accessor.table.deck_str)

        rep.step_forward(multi_hand=True)
        assert rep.accessor.table.hand_number == 1


class ActionReplayerSitInNewHandTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'playing_state_replayer_bug.json'
        )
        super().setUp(self.filename, hand_number=43)

    def test_action_replayer_sit_in_new_hand(self):
        self.replayer.step_forward(multi_hand=True)
        self.replayer.step_forward(multi_hand=True)
        self.replayer.step_forward(multi_hand=True)
        assert self.replayer.accessor.table.hand_number == 44
        assert len(self.replayer.accessor.active_players()) == 2


class DuplicatePlayersBugTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'multiple_players_bug.json'
        )
        super().setUp(self.filename, hand_number=259)

    def test_duplicate_players_bug(self):
        assert len(self.replayer.controller.accessor.players) == 3


class BadStartingStackTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'bad_starting_stack.json'
        )
        super().setUp(self.filename, hand_number=0)

    def test_bug(self):
        pass
        # import ipdb; ipdb.set_trace()
        # self.replayer.skip_to_hand_idx(0)
        # plr = self.replayer.accessor.player_by_username('ROM_Jeremy')
        # assert not self.replayer.accessor.player_has_balance(plr, 1000)

        # while self.replayer.table.hand_number < 1:
        #     self.replayer.step_forward(multi_hand=True)

        # vim = replayer.accessor.player_by_username('VIM_Diesel')
        # assert vim.stack_available == 500


class PlaystateMismatchBugTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'playstate_mismatch.json'
        )
        super().setUp(self.filename, hand_number=40)

    def test_bug(self):
        # TODO
        pass
        # import ipdb; ipdb.set_trace()
        # while self.replayer.table.hand_number < 41:
        #     self.replayer.step_forward(multi_hand=True)
        # seannyboy = self.replayer.accessor.player_by_username('seannyboy')
        # assert str(seannyboy.playing_state) == 'SIT_IN_PENDING'


class TakeSeatBugTest(ActionReplayerTest):
    def setUp(self):
        self.filename = os.path.join(
            HH_TEST_PATH, 'takeseat_bug.json'
        )
        super().setUp(self.filename, hand_number=34)

    def test_duplicate_players_bug(self):
        self.replayer.skip_to_end_of_hand()
        assert len(self.replayer.accessor.seated_players()) == 5


# class CheckWhatTest(ActionReplayerTest):
#     def setUp(self):
#         self.filename = 'poker/tests/data/owes_bb_bug.json'
#         self.filename = '../data/debug_dumps/stack_mismatch.json'
#         self.filename = 'repbugs/repbugs2019_001.json'
#         super().setUp(self.filename, verbose=True)

#     def test_stuff(self):
#         rep = self.replayer
#         # assert not rep.accessor.player_by_username('pirate').owes_bb
#         acc = lambda replayer: replayer.controller.accessor

#         monies = lambda: sum(p.stack + p.total_contributed()
#                                 for p in acc.players)

#         from poker.subscribers import InMemoryLogSubscriber
#         rep.controller.subscribers.append(InMemoryLogSubscriber(rep.accessor))

#         sart = rep.skip_to_hand_idx(0)
#         while True:
#             while True:
#                 try:
#                     rep.step_forward(multi_hand=True)
#                 except StopIteration:
#                     break
#             try:
#                 rep.next_hand()
#             except StopIteration:
#                 break

#         rep.skip_to_hand_idx(0)

#         rep.step_forward(True)
#         rep.step_forward(True)
#         rep.step_forward(True)
#         rep.step_forward(True)

#         self.replayer.skip_to_end_of_hh()
#         import ipdb; ipdb.set_trace()
#         self.replayer.controller.step()

#     def print_notes(self, rep):
#         notes = self.replayer.__notes__
#         print('====> NOTES <====')
#         if isinstance(notes, dict):
#             print('error state:')
#             print(notes['state'])
#             print('error:')
#             print(notes['err'])
#         else:
#             print(notes)
