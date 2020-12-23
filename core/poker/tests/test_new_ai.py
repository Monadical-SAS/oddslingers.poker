import random
import logging  # noqa

from django.test import TestCase, tag

from poker.bot_personalities import DEFAULT_BOT, bot_personality
from poker.new_ai import (
    read_cache, preflop_open, situation_is_preflop_open,
    get_smart_move, chaos_adjusted, get_player_ranges,
    player_hand_ratio_preflop, stackpot_fold_equity_scalar
)
from poker.monte_carlo import monte_carlo, overall_hand_percentile
from poker.hand_ranges import (
    Hand, HandRange, PREFLOP_HANDS, preflop_range, pruned,
    with_hand_values, PREFLOP_HAND_VALUES, FULL_RANGE,
    PREFLOP_BASE_CALC_RANGES,
)
from poker.tests.test_controller import (
    SixPlayerTableTest, GenericTableTest
)
from poker.cards import INDICES, Card
from poker.constants import NL_BOUNTY
from poker.controllers import BountyController


def get_plyr_range(plyr, log):
    json_log = log.get_log(
        player='all',
        current_hand_only=True
    )
    ranges = get_player_ranges(log.accessor, json_log)
    return ranges[plyr.username]


class HandRangeTest(TestCase):
    def test_preflop_range(self):
        strong_range = preflop_range(0.02)

        assert Hand(('Ah', 'Ad')) in strong_range
        assert Hand(('Ad', 'Ah')) in strong_range

        assert Hand(('Ad', 'Ts')) not in strong_range
        assert Hand(('Ts', 'Ad')) not in strong_range

        assert len(set(strong_range)) == len(strong_range) # no duplicates

        swapped = [Hand((c1, c0)) for c0, c1 in strong_range]

        # because (Ah, Ac) == (Ac, Ah)
        swapped_union = set(swapped).union(set(strong_range))
        assert len(swapped_union) == len(strong_range)

    def test_remove_duplicates(self):
        hand_range = HandRange.from_descriptions('AA,KK,AKo,27o,27s,2s7s')
        assert len(hand_range) == len(set(hand_range))
        assert Hand('7s2s') in hand_range

    def test_prune_known_cards(self):
        starting_cards = [
            ('Ah', 'Ad'),
            ('Ad', 'Ts'),
            ('2s', 'Ah'),
            ('5d', '6d'),
        ]
        known_cards = ['Ah', 'Qd']
        expected_handrange = HandRange([
            ('Ad', 'Ts'),
            ('5d', '6d'),
        ])

        handrange = HandRange(starting_cards)
        # can pass in a Hand object
        pruned_hr = pruned(handrange, known_cards=Hand(known_cards))
        assert pruned_hr == expected_handrange

        handrange = HandRange(starting_cards)
        # or an iterable of card objects
        pruned_hr = pruned(
            handrange,
            known_cards={Card(card) for card in known_cards}
        )
        assert pruned_hr == expected_handrange

        handrange = HandRange(starting_cards)
        # or a hand string
        pruned_hr = pruned(handrange, known_cards=''.join(known_cards))
        assert pruned_hr == expected_handrange

    def test_set_values_and_pruning(self):
        hand_values = {
            **PREFLOP_HAND_VALUES,
            Hand('2s3h'): 0.95,
            Hand('2s7h'): 0.87,
            Hand('AcKh'): 0,
        }

        full_range = preflop_range(1)

        adjusted_range = with_hand_values(full_range, hand_values)

        # hands are automatically sorted by value high->low
        assert adjusted_range[0] == Hand('2s3h')
        assert adjusted_range[1] == Hand('2s7h')
        assert adjusted_range[-1] == Hand('KhAc')

        # pruning takes hand_values into account
        assert Hand('KhAc') in adjusted_range
        pruned_range = pruned(
            adjusted_range,
            keep_ratio=0.9,
            known_cards='6h'
        )
        assert len(adjusted_range) > len(pruned_range)
        assert Hand('KhAc') not in pruned_range
        assert Hand('6c6d') in pruned_range
        # known card was pruned
        assert Hand('6c6h') not in pruned_range

        # test pruned range constructor
        pruned_range_constructed = HandRange(
            full_range,
            hand_values=hand_values,
            keep_ratio=0.9,
            known_cards='6h'
        )

        assert pruned_range == pruned_range_constructed


@tag('monte-carlo')
class MonteCarloTest(TestCase):
    def test_monte_carlo(self):
        true_prob = lambda hand: [
            eq for h, eq in PREFLOP_HANDS
            if h == hand
        ].pop()

        myhand = 'AcAh'
        carlo_output = monte_carlo([myhand, *PREFLOP_BASE_CALC_RANGES])
        observed_prob = carlo_output['results']['equity'][0]
        diff = abs(true_prob('AA') - observed_prob)
        # print(observed_prob)
        assert diff < 0.005

        myhand = '2sAh'
        carlo_output = monte_carlo([myhand, *PREFLOP_BASE_CALC_RANGES])
        observed_prob = carlo_output['results']['equity'][0]
        diff = abs(true_prob('A2o') - observed_prob)
        # print(observed_prob)
        assert diff < 0.005

        myhand = '5d6d'
        true_prob = 0.241
        carlo_output = monte_carlo([myhand, 'AcAh', 'AsKs'])
        observed_prob = carlo_output['results']['equity'][0]
        diff = abs(true_prob - observed_prob)
        assert diff < 0.005

        true_prob = 1.0
        carlo_output = monte_carlo(
            [
                '5d6d',
                HandRange.from_descriptions('AK,AQ,AJ,ATs,AA,KK,QQ,JJ,TT'),
                HandRange.from_descriptions('AA,KK,QQ'),
            ],
            board=Hand(['4d', '3d', '2d'])
        )
        observed_prob = carlo_output['results']['equity'][0]
        diff = abs(true_prob - observed_prob)
        assert diff == 0, 'no possible dealout beats the straight flush'

    def test_dynamic_monte_carlo_with_hand_tacking(self):
        r1 = HandRange([
            Hand(('5d', '6d')),
            Hand(('Ad', 'As')),
            Hand(('Kc', 'Qc')),
        ])
        r2 = HandRange([
            Hand(('Ac', 'Ah')),
            Hand(('Kh', '8h')),
            Hand(('Ts', 'Tc')),
        ])
        r3 = HandRange('AsKs,8h9s,9sTs')
        board = Hand(['4d', '3d', '2d'])
        handvals = monte_carlo([r1, r2, r3], board)['results']['hand_values']
        assert (
            handvals[Hand('5d6d')]
          > handvals[Hand('AdAs')]
        )
        assert (
            handvals[Hand('AdAs')]
          > handvals[Hand('8h9s')]
        )
        assert (
            handvals[Hand('5d6d')]
          > handvals[Hand('KsAs')]
        )
        assert (
            handvals[Hand('AcAh')]
          > handvals[Hand('TcTs')]
        )

    def test_hand_percentile(self):
        assert overall_hand_percentile('AcTs') < 0.2
        assert overall_hand_percentile('4cTs') > 0.8

        board = '4d7d9d'

        assert overall_hand_percentile('Ad8d', board) < 0.05
        assert overall_hand_percentile('9c9s', board) < 0.1
        assert overall_hand_percentile('4s7c', board) < 0.2
        assert overall_hand_percentile('Js3s', board) > 0.8


class AIUtilsTest(TestCase):
    def test_chaos_adjust(self):
        # default is no adjustment
        for _ in range(10):
            x = random.random()
            assert chaos_adjusted(x) == x

        for _ in range(25):
            x = random.random()
            chaos = random.random()
            adjusted = chaos_adjusted(x, chaos)
            # never goes outside bounds
            assert (1 - chaos) * x <= adjusted <= (1 + chaos) * x
            assert 0 <= adjusted <= 1


class PreflopOpenTest(SixPlayerTableTest):
    def test_preflop_open(self):
        self.table.btn_idx = 0
        self.table.sb_idx = None
        self.table.bb_idx = None
        self.table.table_type = NL_BOUNTY
        self.controller.step()

        def preflop_personality(vpip, limper, limp_balance):
            return {
                **DEFAULT_BOT,
                'preflop': {
                    'heads_up': {
                        'btn': vpip,
                        'bb': vpip,
                    },
                    'ring': {
                        # at a 10-player table, UTG is 7
                        7: vpip,
                        6: vpip,
                        5: vpip,
                        4: vpip,
                        # at a 6-player table, UTG is 3
                        3: vpip,
                        2: vpip,
                        1: vpip,
                        'btn': vpip,
                        'sb': vpip,
                        'bb': vpip,
                    },
                },
                'chaotic': 0.0,  # so we don't get random anomalies in tests
                'limper': limper,
                'limp_balance': limp_balance,
            }

        def behaviour(me, hand, vpip=0.25, limper=0.0, limp_balance=1):
            me.cards = hand
            return preflop_open(
                me,
                self.accessor,
                personality=preflop_personality(vpip, limper, limp_balance)
            )[0]

        def assert_behaviour_rate(expected_behaviour, expected_rate, me, hand,
                                  vpip=1, limper=0.5, limp_balance=1):
            # TODO: profile this
            move = lambda: behaviour(me, hand, vpip, limper, limp_balance)
            rate = sum(
                move() == expected_behaviour
                for _ in range(500)
            ) / 500.0

            # odds of false negative infinitessimally small
            assert abs(rate - expected_rate) < 0.25

        for _ in range(6):
            me = self.accessor.next_to_act()
            assert behaviour(me, ('Ac', 'As')) == 'RAISE_TO'
            # always open 72
            assert behaviour(me, ('2c', '7s')) == 'RAISE_TO'
            assert behaviour(me, ('2c', '3s')) == 'FOLD'

            # fold everything when vpip == 0
            assert behaviour(me, ('Ac', 'As'), vpip=0) == 'FOLD'
            # play everything when vpip == 1
            assert behaviour(me, ('2c', '3s'), vpip=1) == 'RAISE_TO'

            # bb will check
            expected_limp = 'CHECK' if me.position == 2 else 'CALL'

            assert behaviour(me, ('Ac', 'As'), limper=1) == expected_limp
            # always open 72
            assert behaviour(me, ('2c', '7s'), limper=1) == expected_limp
            assert behaviour(me, ('2c', '3s'), limper=1) == 'FOLD'

            # limp bottom of range @ 1 - half limp balance rate
            assert_behaviour_rate(
                expected_limp, 0.99, me, ('2c', '3s'),
                limp_balance=0
            )
            assert_behaviour_rate(
                expected_limp, 0.8, me, ('2c', '3s'),
                limp_balance=0.4
            )
            # limp top of range @ half limp balance rate
            assert_behaviour_rate(
                'RAISE_TO', 0.99, me, ('2c', '7s'),
                limp_balance=0
            )
            assert_behaviour_rate(
                'RAISE_TO', 0.7, me, ('Ac', 'As'),
                limp_balance=0.6
            )

            # limp 50% everything when balance is 1
            assert_behaviour_rate(
                expected_limp, 0.5, me, ('2c', '3s'),
                limp_balance=1
            )
            # should almost always raise top of range when balance is at 1
            assert_behaviour_rate(
                'RAISE_TO', 0.5, me, ('2c', '7s'),
                limp_balance=1
            )
            assert_behaviour_rate(
                'RAISE_TO', 0.5, me, ('Ac', 'As'),
                limp_balance=1
            )

            self.controller.dispatch(expected_limp, player_id=me.id)

    def test_situation_is_preflop_open(self):
        self.ahnuld_player.seated = False
        self.alexeimartov_player.seated = False

        ctrl = self.controller
        acc = ctrl.accessor

        ctrl.step()

        me = acc.next_to_act()
        assert situation_is_preflop_open(me, acc)
        ctrl.dispatch('CALL', player_id=me.id)  # UTG

        me = acc.next_to_act()
        assert situation_is_preflop_open(me, acc)
        ctrl.dispatch('FOLD', player_id=me.id)  # BTN

        me = acc.next_to_act()
        assert situation_is_preflop_open(me, acc)
        ctrl.dispatch('CALL', player_id=me.id)  # SB

        me = acc.next_to_act()
        assert situation_is_preflop_open(me, acc)
        ctrl.dispatch('RAISE_TO', player_id=me.id, amt=4)  # BB

        me = acc.next_to_act()
        assert not situation_is_preflop_open(me, acc)
        ctrl.dispatch('CALL', player_id=me.id)  # UTG

        me = acc.next_to_act()
        assert not situation_is_preflop_open(me, acc)
        ctrl.dispatch('FOLD', player_id=me.id, amt=10)  # SB


        me = acc.next_to_act()
        assert not situation_is_preflop_open(me, acc)
        ctrl.dispatch('BET', player_id=me.id, amt=25)  # UTG

        me = acc.next_to_act()
        assert not situation_is_preflop_open(me, acc)
        ctrl.dispatch('RAISE_TO', player_id=me.id, amt=50)  # BB

        me = acc.next_to_act()
        assert not situation_is_preflop_open(me, acc)


@tag('monte-carlo')
class PlayerRangeUpdate5betPreTest(SixPlayerTableTest):
    def test_player_range_update_5bet_pre(self):
        self.setup_hand(
            blinds_positions={
                'btn_pos': 5,
                'sb_pos': 0,
                'bb_pos': 1,
            },
            add_log=True,
        )
        utg = self.players[2]
        mid = self.players[3]
        co = self.players[4]
        btn = self.players[5]
        sb = self.players[0]
        bb = self.players[1]

        ctrl = self.controller
        log = ctrl.log

        ctrl.dispatch('CALL', player_id=utg.id)
        utg_limp_range = get_plyr_range(utg, log)
        assert Hand('JcJh') in utg_limp_range
        assert Hand('Js9s') in utg_limp_range
        assert Hand('6hQc') not in utg_limp_range

        ctrl.dispatch('RAISE_TO', player_id=mid.id, amt=10)
        mid_raise_range = get_plyr_range(mid, log)
        assert Hand('TdTc') in mid_raise_range
        assert Hand('QhKh') in mid_raise_range
        assert Hand('Td6d') not in mid_raise_range

        ctrl.dispatch('FOLD', player_id=co.id)
        ctrl.dispatch('CALL', player_id=btn.id)
        btn_call_range = get_plyr_range(btn, log)
        assert len(btn_call_range) > len(mid_raise_range)
        assert Hand('7s8s') in btn_call_range

        ctrl.dispatch('RAISE_TO', player_id=sb.id, amt=35)
        sb_3bet_range = get_plyr_range(sb, log)
        assert len(sb_3bet_range) < len(mid_raise_range)
        assert Hand('QsQh') in sb_3bet_range
        assert Hand('As9h') not in sb_3bet_range

        ctrl.dispatch('RAISE_TO', player_id=bb.id, amt=99)
        bb_4bet_range = get_plyr_range(bb, log)
        assert len(bb_4bet_range) < len(sb_3bet_range)
        assert Hand('KsKh') in bb_4bet_range
        assert Hand('AsKs') in bb_4bet_range
        assert Hand('AsTd') not in bb_4bet_range

        ctrl.dispatch('RAISE_TO', player_id=utg.id, amt=200)
        utg_5bet_range = get_plyr_range(utg, log)
        assert len(utg_5bet_range) < len(bb_4bet_range)
        assert Hand('KsKh') in utg_5bet_range
        assert Hand('AhQs') not in utg_5bet_range


@tag('monte-carlo')
class PreflopRatioTest(TestCase):
    def test_preflop_ratio(self):
        def get_base_range(position, n_players, bbs_preflop):
            ratio = player_hand_ratio_preflop(position,
                                              n_players,
                                              bbs_preflop)
            return preflop_range(ratio)

        LIMP = 1
        MINRAISE = 2
        RAISE = 3
        THREEBET = 9
        FOURBET = 27
        FIVEBET = 75
        SIXBET = 165

        normal_bb_amts = [
            LIMP,
            MINRAISE,
            RAISE,
            THREEBET,
            FOURBET,
            FIVEBET,
            SIXBET,
        ]

        for gametype in ('heads_up', 'ring'):
            for pos in DEFAULT_BOT['preflop'][gametype]:
                n_plyrs = 2 if gametype == 'heads_up' else 6
                normal_range = get_base_range(pos, n_plyrs, RAISE)
                if pos not in (2, 3):
                    assert Hand('AsJc') in normal_range
                    assert Hand('8s7s') in normal_range
                    assert Hand('Kc9c') in normal_range
                assert Hand('8s2c') not in normal_range
                assert Hand('9c4s') not in normal_range

                for bb_amt in normal_bb_amts:
                    hr = get_base_range(pos, n_plyrs, bb_amt)
                    # AKs should always be in a range
                    assert Hand('AsKs') in hr

                    # J5o should almost never be in a range
                    if not ((gametype == 'heads_up' or pos == 'bb')
                            and bb_amt < 4):
                        assert Hand('Js5c') not in hr


        # AJo should be gone after 5-bet at 6-max
        assert Hand('AsJh') not in get_base_range('sb', 6, FIVEBET)

        # AQo and JJ should be gone after 6-bet UTG at 6-max
        assert Hand('AhQc') not in get_base_range(3, 6, SIXBET)
        assert Hand('ThTc') not in get_base_range(3, 6, SIXBET)

        # JTs in typical 3bet range
        assert Hand('TcJc') in get_base_range(1, 6, THREEBET)


@tag('monte-carlo')
class PlayerRangeUpdatePortflopTest(SixPlayerTableTest):
    def test_player_range_update_postflop(self):
        self.setup_hand(
            blinds_positions={
                'btn_pos': 0,
                'sb_pos': 1,
                'bb_pos': 2,
            },
            add_log=True,
            board_str='Kc,9h,8h,6c,6d'
        )
        utg = self.players[3]
        mid = self.players[4]
        co = self.players[5]
        btn = self.players[0]
        sb = self.players[1]
        bb = self.players[2]

        ctrl = self.controller
        log = ctrl.log

        ctrl.dispatch('RAISE_TO', player_id=utg.id, amt=7)
        ctrl.dispatch('FOLD', player_id=mid.id)
        ctrl.dispatch('CALL', player_id=co.id)
        ctrl.dispatch('CALL', player_id=btn.id)
        ctrl.dispatch('FOLD', player_id=sb.id)
        ctrl.dispatch('CALL', player_id=bb.id)

        utg_preflop = get_plyr_range(utg, log)
        co_preflop = get_plyr_range(co, log)
        bb_preflop = get_plyr_range(bb, log)
        assert Hand('AsTs') in co_preflop
        assert Hand('QhTh') in co_preflop

        ctrl.dispatch('CHECK', player_id=bb.id)
        ctrl.dispatch('BET', player_id=utg.id, amt=20)
        ctrl.dispatch('CALL', player_id=co.id)
        ctrl.dispatch('CALL', player_id=btn.id)
        ctrl.dispatch('CALL', player_id=bb.id)

        utg_flop = get_plyr_range(utg, log)
        co_flop = get_plyr_range(co, log)
        bb_flop = get_plyr_range(bb, log)

        assert len(utg_flop) < len(utg_preflop)
        co_shrink = (len(co_preflop) - len(co_flop)) / len(co_preflop)
        bb_shrink = (len(bb_preflop) - len(bb_flop)) / len(bb_preflop)
        assert co_shrink > bb_shrink, \
            'bb had better pot odds, so could call with more range'
        assert Hand('AsTs') not in co_flop
        assert Hand('QhTh') in co_flop

        ctrl.dispatch('CHECK', player_id=bb.id)
        ctrl.dispatch('CHECK', player_id=utg.id)
        ctrl.dispatch('BET', player_id=co.id, amt=75)
        ctrl.dispatch('FOLD', player_id=btn.id)
        # all-in
        ctrl.dispatch('RAISE_TO', player_id=bb.id, amt=173)

        utg_turn = get_plyr_range(utg, log)
        co_turn = get_plyr_range(co, log)
        bb_turn = get_plyr_range(bb, log)
        assert Hand('QhTh') in co_preflop

        assert len(utg_turn) == len(utg_flop), \
            'checking does not change range'
        co_shrink = (len(co_flop) - len(co_turn)) / len(co_flop)
        bb_shrink = (len(bb_flop) - len(bb_turn)) / len(bb_flop)
        assert bb_shrink > co_shrink, \
            'bb raised big, so range shrink should be greater'


@tag('monte-carlo')
class PlayerRangeUpdateCachingTest(GenericTableTest):
    def test_player_range_update_caching(self):
        self.setup_hand(add_log=True)
        ctrl = self.controller
        acc = ctrl.accessor
        log = ctrl.log

        nxt = ctrl.accessor.next_to_act()
        ctrl.dispatch('FOLD', player_id=nxt.id)

        from poker import new_ai
        get_player_ranges(
            acc,
            log.get_log(player='all', current_hand_only=True)
        )
        ctrl.step()
        placeholder = new_ai.update_ranges
        def error(*args, **kwargs):
            raise Exception(
                'ranges should be cached, update_ranges'
                'should therefore not be called'
            )
        new_ai.update_ranges = error

        # this should throw an error if ranges are not cached
        get_player_ranges(
            acc,
            log.get_log(player='all', current_hand_only=True)
        )

        new_ai.update_ranges = placeholder


@tag('monte-carlo')
class BountyRangesUpdateTest(GenericTableTest):
    def test_bounty_ranges_update(self):
        self.table.table_type = NL_BOUNTY
        self.controller = BountyController(
            self.table,
            self.players,
            subscribers=[]
        )
        self.accessor = self.controller.accessor
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ts,5c',
                self.cuttlefish_player: 'Jc,Jd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: '7c,2d',
            },
            add_log=True,
        )

        ctrl = self.controller
        log = ctrl.log

        ctrl.dispatch('RAISE_TO', amt=10, player_id=self.cowpig_player.id)
        for _ in range(3):
            ctrl.dispatch('FOLD', player_id=ctrl.accessor.next_to_act().id)

        assert ctrl.accessor.current_pot() > 100, 'should be a bounty'
        for plyr in self.players:
            if plyr is not self.cowpig_player:
                rng = get_plyr_range(plyr, log)
                assert len(rng) == len(FULL_RANGE)


@tag('monte-carlo')
class PlayerRangeTest(SixPlayerTableTest):
    def test_player_ranges(self):
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Jc,Jd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: 'Td,Qd',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: '8h,9h',
            },
            add_log=True,
            board_str='Ad,9d,Js',
        )
        ctrl = self.controller
        acc = ctrl.accessor
        log = ctrl.log

        json_log = log.get_log(player='all', current_hand_only=True)
        plyr_ranges = get_player_ranges(acc, json_log)

        # ranges all the same before anyone acts
        for _, plyr_range in plyr_ranges.items():
            assert len(plyr_range) == len(preflop_range(1))

        # raising lowers the range size
        cowpig_range = plyr_ranges['cowpig']
        ctrl.dispatch('RAISE_TO', player_id=self.cowpig_player.id, amt=10)
        json_log = log.get_log(player='all', current_hand_only=True)
        new_ranges = get_player_ranges(acc, json_log)
        assert len(new_ranges['cowpig']) < len(cowpig_range)

        # folding eliminates range
        ctrl.dispatch('FOLD', player_id=self.alexeimartov_player.id)
        json_log = log.get_log(player='all', current_hand_only=True)
        new_ranges = get_player_ranges(acc, json_log)
        assert 'alexeimartov' not in new_ranges

        ctrl.dispatch('CALL', player_id=self.ahnuld_player.id)
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)

        # later position means a wider range of cards
        json_log = log.get_log(player='all', current_hand_only=True)
        preflop_ranges = get_player_ranges(acc, json_log)
        assert len(preflop_ranges['pirate']) > len(preflop_ranges['ahnuld'])
        assert len(preflop_ranges['ahnuld']) > len(preflop_ranges['cowpig'])

        # make sure they're being cached correctly
        _, _, cached_ranges = read_cache(acc)
        for r1, r2 in zip(preflop_ranges.values(), cached_ranges.values()):
            assert r1 == r2

        # when flop comes, ranges are pruned and reevaluated
        ctrl.dispatch('FOLD', player_id=self.ajfenix_player.id)
        json_log = log.get_log(player='all', current_hand_only=True)
        postflop_ranges = get_player_ranges(acc, json_log)

        # j9 got a lot stronger because it is 2 pair now
        j9_preflop = preflop_ranges['pirate'].percentile('Jh9h')
        j9_postflop = postflop_ranges['pirate'].percentile('Jh9h')
        assert j9_postflop < j9_preflop

        # postflop ranges are smaller because board cards were pruned
        for plyr in acc.showdown_players(0):
            preflop_size = len(preflop_ranges[plyr.username])
            postflop_size = len(postflop_ranges[plyr.username])
            assert preflop_size > postflop_size

        # players who saw flop:
        # sb (cuttlefish)
        # utg (cowpig)
        # co (ahnuld)
        # btn (pirate)

        # low range
        assert Hand('KhTh') in postflop_ranges['cuttlefish']
        # semibluff range
        assert Hand('QdTd') in postflop_ranges['cuttlefish']
        # value range
        assert Hand('9s9h') in postflop_ranges['cuttlefish']

        ctrl.dispatch('BET', player_id=self.cuttlefish_player.id, amt=40)
        json_log = log.get_log(player='all', current_hand_only=True)
        ranges = get_player_ranges(acc, json_log)
        # low range
        if Hand('KhTh') in ranges['cuttlefish']:
            print(ranges)
        assert Hand('KhTh') not in ranges['cuttlefish']
        # semibluff range
        assert Hand('QdTd') in ranges['cuttlefish']
        # value range
        assert Hand('9s9h') in ranges['cuttlefish']

        # make sure they're being cached correctly
        _, _, cached_ranges = read_cache(acc)
        for r1, r2 in zip(cached_ranges.values(), ranges.values()):
            assert r1 == r2


@tag('monte-carlo')
class ClearCallTest(GenericTableTest):
    def test_clear_call(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: '4h,5h',
                self.ajfenix_player: 'Ac,Kc',
                self.cowpig_player: 'As,Qs',
            },
            add_log=True,
        )
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cowpig_player.id,
                      amt=100)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('FOLD', player_id=self.cuttlefish_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] == 'CALL'


@tag('monte-carlo')
class EasyFoldTest(GenericTableTest):
    def test_clear_fold(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: '2s,3h',
                self.cuttlefish_player: '4h,6h',
                self.ajfenix_player: 'Ac,Kc',
                self.cowpig_player: 'As,Qs',
            },
            board_str='Ad,Qc,9c',
            add_log=True,
        )
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cowpig_player.id,
                      amt=8)
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.ajfenix_player.id,
                      amt=25)
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
        # flop should be dealt now
        ctrl.dispatch('CHECK', player_id=self.cuttlefish_player.id)
        ctrl.dispatch('BET',
                      player_id=self.ajfenix_player.id,
                      amt=40)
        ctrl.dispatch('RAISE_TO',
                      player_id=self.cowpig_player.id,
                      amt=75)

        # just some sanity checks
        assert self.accessor.table.board_str == 'Ad,Qc,9c'
        assert self.cowpig_player.cards_str == 'As,Qs'

        move = get_smart_move(ctrl.accessor, ctrl.log)
        if move[0] == 'RAISE_TO':
            assert False, 'AHA! fold equity is broken'
        assert move[0] == 'FOLD'


@tag('monte-carlo')
class PrefopShouldFoldTest(SixPlayerTableTest):
    def test_preflop_should_fold(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: '2c,3d',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: 'Jc,Js',
            },
            add_log=True,
        )

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] == 'FOLD'
        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] == 'FOLD'
        ctrl.dispatch('FOLD', player_id=self.alexeimartov_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'
        ctrl.dispatch('FOLD', player_id=self.ahnuld_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'
        ctrl.dispatch('FOLD', player_id=self.pirate_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'
        ctrl.dispatch('FOLD', player_id=self.cuttlefish_player.id)


@tag('monte-carlo')
class DontFoldCheckedToTest(SixPlayerTableTest):
    def test_dont_fold_checked_to(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: '2c,3d',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: 'Jc,Js',
            },
            add_log=True,
            board_str='7d,7c,9d',
        )

        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        ctrl.dispatch('FOLD', player_id=self.alexeimartov_player.id)
        ctrl.dispatch('RAISE_TO', player_id=self.ahnuld_player.id, amt=8)
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
        ctrl.dispatch('FOLD', player_id=self.ajfenix_player.id)

        # flop comes out
        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'
        ctrl.dispatch('CHECK', player_id=self.cuttlefish_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'
        ctrl.dispatch('CHECK', player_id=self.ahnuld_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'
        ctrl.dispatch('CHECK', player_id=self.pirate_player.id)

        move = get_smart_move(ctrl.accessor, ctrl.log)
        assert move[0] != 'FOLD'


''' seats are:
    0: pirate       (400)
    1: cuttlefish   (300)
    2: ajfenix      (200)
    3: cowpig       (100)
    4: alexeimartov (400)
    5: ahnuld       (200)
    6: skier_5      (300)
'''
@tag('monte-carlo')
class DontBluffWithoutFETest(SixPlayerTableTest):
    def test_bluff_without_FE(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: 'Jc,Jd',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: '8h,9h',
            },
            add_log=True,
            board_str='Ad,Kd,Qs',
        )

        ctrl.dispatch('RAISE_TO', player_id=self.cowpig_player.id, amt=9)
        ctrl.dispatch('FOLD', player_id=self.alexeimartov_player.id)
        ctrl.dispatch('RAISE_TO', player_id=self.ahnuld_player.id, amt=30)
        ctrl.dispatch('RAISE_TO', player_id=self.pirate_player.id, amt=110)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
        ctrl.dispatch('FOLD', player_id=self.ajfenix_player.id)
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.ahnuld_player.id)

        # flop comes out
        ctrl.dispatch('CHECK', player_id=self.cuttlefish_player.id)

        # cowpig is all in; ahnuld should never bluff here
        assert stackpot_fold_equity_scalar(ctrl.accessor) == 0
        move = get_smart_move(ctrl.accessor, ctrl.log)#, verbose=True)
        assert move[0] == 'CHECK'


class PerfTest(TestCase):
    def test_perf(self):
        # example2 in monte_carlo
        handranges = ["AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c,AhTh,AsTs,TcAc,KcJc,KhJh,KsJs,Ah9h,As9s,Ac9c,KcQc,KhQh,6s6d,6s6c,6s6h,6d6c,6d6h,6c6h,JcTc,JsTs,ThJh,TdJd,QcTc,QhTh,QdTd,AhTc,AhTs,AhTd,AsTc,AsTh,AsTd,ThAc,AcTs,AcTd,KcTc,KhTh,KsTs,Ah8h,8sAs,8cAc,Ah7h,As7s,7cAc,Ah5h,5sAs,Ac5c,KcQh,KcQd,KhQc,KhQd,QcKs,QhKs,KsQd,Ah6h,As6s,Ac6c,5s5h,5s5d,5s5c,5h5d,5h5c,5d5c,Ah8s,Ah8d,Ah8c,8sAc,As8d,As8h,As8c,8dAc,8hAc,Kc9c,Kh9h,9sKs,KcJs,KcJh,KcJd,KhJc,KhJs,KhJd,JcKs,KsJh,KsJd,JcQc,QhJh,QdJd,8s9s,9h8h,8d9d,8c9c,Ah9s,Ah9c,Ah9d,As9h,As9c,As9d,9sAc,9hAc,Ac9d,4d4c,4d4s,4d4h,4c4s,4c4h,4s4h,7h6h,7d6d,6s7s,7c6c,Ah4h,As4s,4cAc,Jc8c,8sJs,8dJd,8hJh,KcTh,KcTs,KcTd,KhTc,KhTs,KhTd,TcKs,KsTh,KsTd,Ah3h,As3s,3cAc,Ah7d,Ah7c,Ah7s,7hAs,7hAc,As7d,As7c,7dAc,Ac7s,Kc8c,Kh8h,8sKs,Ah5s,Ah5d,Ah5c,5sAc,5hAs,5hAc,5dAs,5dAc,As5c,Ah6s,Ah6d,Ah6c,6hAs,6hAc,As6d,As6c,6sAc,6dAc,Ah4d,Ah4c,Ah4s,As4h,As4d,As4c,4hAc,4dAc,4sAc,JcQh,JcQd,QcJs,QcJh,QcJd,QhJs,QhJd,QdJs,QdJh,Kc9s,Kc9h,Kc9d,Kh9s,Kh9c,Kh9d,9hKs,Ks9c,Ks9d,Kc7c,Kh7h,Ks7s,Qc9c,Qh9h,Qd9d,Ah2h,As2s,Ac2c,QcTh,QcTs,QcTd,TcQh,TcQd,QhTs,QhTd,QdTh,QdTs,Kc6c,Kh6h,Ks6s,Jc9c,9sJs,9hJh,Jd9d,8s7s,7h8h,7d8d,8c7c,8sTs,Tc8c,8dTd,8hTh,Kc5c,Kh5h,5sKs,Qc8c,Qh8h,8dQd,Ah3c,Ah3s,Ah3d,As3c,As3d,As3h,3sAc,3dAc,Ac3h,Kc7h,Kc7d,Kc7s,Kh7d,Kh7c,Kh7s,7hKs,7dKs,Ks7c,JcTh,JcTs,JcTd,TcJs,TcJh,TcJd,JsTh,JsTd,ThJd,TsJh,TsJd,JhTd,5s6s,5h6h,5d6d,5c6c,3h3d,3h3s,3h3c,3d3s,3d3c,3s3c,2s2d,2s2h,2s2c,2d2h,2d2c,2h2c,5s4s,5h4h,5d4d,4c5c,Kc8s,Kc8d,Kc8h,Kh8s,Kh8d,Kh8c,Ks8d,Ks8h,Ks8c,Ah2d,Ah2s,Ah2c,2dAs,2dAc,2hAs,2hAc,As2c,2sAc,Kc3c,Kh3h,Ks3s,Qc9s,Qc9h,Qc9d,9sQh,9sQd,Qh9c,Qh9d,9hQd,Qd9c,Kc4c,Kh4h,4sKs,Kc6h,Kc6s,Kc6d,Kh6s,Kh6d,Kh6c,6hKs,Ks6d,Ks6c,Qc7c,7hQh,7dQd,Qc6c,6hQh,Qd6d,8sQc,8sQh,8sQd,Qc8d,Qc8h,Qh8d,Qh8c,8hQd,Qd8c,9cTc,9sTs,9hTh,Td9d,Kc2c,Kh2h,2sKs,5dQd,Qc5c,5hQh,Jc9s,Jc9h,Jc9d,9sJh,9sJd,9hJs,9hJd,Js9c,Js9d,9cJh,9cJd,Jh9d,Kc5s,Kc5h,Kc5d,Kh5s,Kh5d,Kh5c,5hKs,5dKs,Ks5c,Kc4h,Kc4d,Kc4s,Kh4d,Kh4c,Kh4s,4hKs,4dKs,4cKs,Jc7c,7hJh,7dJd,Js7s,Qc7h,Qc7d,Qc7s,7hQd,Qh7d,Qh7c,Qh7s,Qd7c,Qd7s,Qc3c,Qh3h,Qd3d,Qc4c,4hQh,4dQd,Qc6h,Qc6s,Qc6d,6hQd,Qh6s,Qh6d,Qh6c,Qd6s,Qd6c,8s6s,6h8h,8d6d,8c6c,9cTh,9cTs,9cTd,Tc9s,Tc9h,Tc9d,9sTh,9sTd,9hTs,9hTd,Th9d,Ts9d,Jc8s,Jc8d,Jc8h,8sJh,8sJd,8dJs,8dJh,8hJs,8hJd,Js8c,8cJh,8cJd,Kc3s,Kc3d,Kc3h,Kh3c,Kh3s,Kh3d,3cKs,Ks3d,Ks3h,Kc2d,Kc2h,Kc2s,Kh2d,Kh2s,Kh2c,2dKs,2hKs,Ks2c,Jc5c,5sJs,5hJh,5dJd,5sQc,5sQh,5sQd,5dQc,5dQh,Qc5h,5hQd,Qh5c,Qd5c,Jc6c,6hJh,6sJs,6dJd,Qc4h,Qc4d,Qc4s,4hQd,Qh4d,Qh4c,Qh4s,4cQd,4sQd,2dQd,Qc2c,2hQh,7hTh,Tc7c,7dTd,7sTs,7h9h,9s7s,7d9d,7c9c,Jc4c,4hJh,4dJd,4sJs,Jc7h,Jc7d,Jc7s,7hJs,7hJd,7dJs,7dJh,Js7c,7cJh,7cJd,7sJh,7sJd,8sTc,8sTh,8sTd,Tc8d,Tc8h,8dTh,8dTs,8hTs,8hTd,8cTh,8cTs,8cTd,5s7s,5h7h,5d7d,7c5c,Jc3c,3sJs,3dJd,Jh3h,6hTh,Tc6c,6sTs,6dTd,8s9h,8s9c,8s9d,9s8d,9s8h,9s8c,9h8d,9h8c,8d9c,8h9c,8h9d,8c9d,7hTc,7hTs,7hTd,Tc7d,Tc7s,7dTh,7dTs,7sTh,7sTd,Th7c,7cTs,7cTd,5sTs,5hTh,5dTd,Tc5c,Jc5s,Jc5h,Jc5d,5sJh,5sJd,5hJs,5hJd,5dJs,5dJh,Js5c,5cJh,5cJd,6h4h,4d6d,4c6c,4s6s,Jc6h,Jc6s,Jc6d,6hJs,6hJd,6sJh,6sJd,Js6d,Js6c,6dJh,Jh6c,Jd6c,4h3h,3c4c,4d3d,4s3s,Tc4c,4hTh,4dTd,4sTs,Qc3s,Qc3d,Qc3h,Qh3c,Qh3s,Qh3d,3cQd,3sQd,Qd3h,6h9h,9s6s,6d9d,9c6c,Jc2c,2dJd,2hJh,2sJs,2dQc,2dQh,Qc2h,Qc2s,2hQd,Qh2s,Qh2c,2sQd,Qd2c,Jc4h,Jc4d,Jc4s,4hJs,4hJd,4dJs,4dJh,4cJs,4cJh,4cJd,4sJh,4sJd,5s9s,5h9h,5d9d,9c5c,Jc3s,Jc3d,Jc3h,3cJs,3cJh,3cJd,3sJh,3sJd,Js3d,Js3h,3dJh,Jd3h,7h9s,7h9c,7h9d,9s7d,9s7c,7d9h,7d9c,9h7s,9h7c,7s9c,7s9d,7c9d,Tc3c,3sTs,Th3h,3dTd,6hTc,6hTs,6hTd,Tc6s,Tc6d,6sTh,6sTd,Th6d,Th6c,6dTs,Ts6c,Td6c,5s8s,5h8h,5d8d,8c5c,8s7h,8s7d,8s7c,7h8d,7h8c,7d8h,7d8c,8h7c,8h7s,8d7c,8d7s,8c7s,2dTd,2hTh,Tc2c,2sTs,5sTc,5sTh,5sTd,5hTc,5hTs,5hTd,5dTc,5dTh,5dTs,Th5c,Ts5c,5cTd,6h9s,6h9c,6h9d,9s6d,9s6c,9h6s,9h6d,9h6c,6s9c,6s9d,6d9c,6c9d,Jc2d,Jc2h,Jc2s,2dJs,2dJh,2hJs,2hJd,2sJh,2sJd,Js2c,2cJh,2cJd,9s4s,4h9h,4d9d,4c9c,Tc4h,Tc4d,Tc4s,4hTs,4hTd,4dTh,4dTs,4cTh,4cTs,4cTd,4sTh,4sTd,5s9h,5s9c,5s9d,5h9s,5h9c,5h9d,5d9s,5d9h,5d9c,9s5c,9h5c,5c9d,8s6h,8s6d,8s6c,6h8d,6h8c,8h6s,8h6d,8h6c,8d6s,8d6c,6s8c,8c6d,9s3s,3c9c,9h3h,3d9d,2d9d,2h9h,9s2s,2c9c,8s4s,4h8h,4d8d,4c8c,Tc3s,Tc3d,Tc3h,3cTh,3cTs,3cTd,3sTh,3sTd,Th3d,3dTs,Ts3h,Td3h,7h6s,7h6d,7h6c,6h7d,6h7c,6h7s,7d6s,7d6c,6s7c,6d7c,6d7s,7s6c,7h4h,4d7d,4c7c,4s7s,5s8h,5s8d,5s8c,8s5h,8s5d,8s5c,5h8d,5h8c,5d8h,5d8c,8h5c,8d5c,2dTc,2dTh,2dTs,2hTc,2hTs,2hTd,Tc2s,2sTh,2sTd,Th2c,2cTs,2cTd,8s3s,3c8c,8h3h,8d3d,9s4h,9s4d,9s4c,4h9c,4h9d,4d9h,4d9c,4c9h,4c9d,9h4s,4s9c,4s9d,5s7h,5s7d,5s7c,5h7d,5h7c,5h7s,5d7h,5d7c,5d7s,7h5c,7d5c,7s5c,8s2s,2d8d,2h8h,8c2c,5s6h,5s6d,5s6c,5h6s,5h6d,5h6c,5d6h,5d6s,5d6c,6h5c,6s5c,6d5c,9s3c,9s3d,9s3h,3c9h,3c9d,9h3s,9h3d,3s9c,3s9d,3d9c,9c3h,3h9d,6h3h,3c6c,3s6s,6d3d,5s3s,5h3h,5d3d,3c5c,7h3h,3c7c,7d3d,3s7s,8s4h,8s4d,8s4c,4h8d,4h8c,4d8h,4d8c,4c8h,4c8d,4s8h,4s8d,4s8c,2d9s,2d9h,2d9c,2h9s,2h9c,2h9d,9s2c,2s9h,2s9c,2s9d,9h2c,2c9d,5s4h,5s4d,5s4c,5h4d,5h4c,5h4s,5d4h,5d4c,5d4s,4h5c,4d5c,4s5c,7h4d,7h4c,7h4s,4h7d,4h7c,4h7s,4d7c,4d7s,4c7d,4c7s,7d4s,4s7c,6h4d,6h4c,6h4s,4h6s,4h6d,4h6c,4d6s,4d6c,4c6s,4c6d,4s6d,4s6c,2d6d,2h6h,2s6s,2c6c,5s2s,2d5d,5h2h,2c5c,8s2d,8s2h,8s2c,2d8h,2d8c,2h8d,2h8c,2s8h,2s8d,2s8c,8h2c,8d2c,2d7d,2h7h,2s7s,7c2c,2d4d,2h4h,2s4s,4c2c,8s3c,8s3d,8s3h,3c8h,3c8d,8h3s,8h3d,8d3s,8d3h,3s8c,8c3d,8c3h,7h3c,7h3s,7h3d,3c7d,3c7s,7d3s,7d3h,3s7c,7c3d,7c3h,3d7s,7s3h,5s3c,5s3d,5s3h,5h3c,5h3s,5h3d,5d3c,5d3s,5d3h,3s5c,3d5c,5c3h,6h3c,6h3s,6h3d,3c6s,3c6d,3s6d,3s6c,6s3d,6s3h,6d3h,3d6c,6c3h,2d3d,2h3h,3c2c,2s3s,2d7h,2d7c,2d7s,2h7d,2h7c,2h7s,7h2s,7h2c,2s7d,2s7c,7d2c,2c7s,5s2d,5s2h,5s2c,2d5h,2d5c,5h2s,5h2c,5d2h,5d2s,5d2c,2h5c,2s5c,4h3c,4h3s,4h3d,3c4d,3c4s,4d3s,4d3h,4c3s,4c3d,4c3h,4s3d,4s3h,2d6h,2d6s,2d6c,2h6s,2h6d,2h6c,6h2s,6h2c,2s6d,2s6c,6s2c,6d2c,2d4h,2d4c,2d4s,2h4d,2h4c,2h4s,4h2s,4h2c,2s4d,2s4c,4d2c,4s2c,2d3c,2d3s,2d3h,2h3c,2h3s,2h3d,3c2s,2s3d,2s3h,3s2c,3d2c,2c3h", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c,AhTh,AsTs,TcAc,KcJc,KhJh,KsJs,Ah9h,As9s,Ac9c,KcQc,KhQh,6s6d,6s6c,6s6h,6d6c,6d6h,6c6h,JcTc,JsTs,ThJh,TdJd,QcTc,QhTh,QdTd,AhTc,AhTs,AhTd,AsTc,AsTh,AsTd,ThAc,AcTs,AcTd,KcTc,KhTh,KsTs,Ah8h,8sAs,8cAc,Ah7h,As7s,7cAc,Ah5h,5sAs,Ac5c,KcQh,KcQd,KhQc,KhQd,QcKs,QhKs,KsQd,Ah6h,As6s,Ac6c,5s5h,5s5d,5s5c,5h5d,5h5c,5d5c,Ah8s,Ah8d,Ah8c,8sAc,As8d,As8h,As8c,8dAc,8hAc,Kc9c,Kh9h,9sKs,KcJs,KcJh,KcJd,KhJc,KhJs,KhJd,JcKs,KsJh,KsJd,JcQc,QhJh,QdJd,8s9s,9h8h,8d9d,8c9c,Ah9s,Ah9c,Ah9d,As9h,As9c,As9d,9sAc,9hAc,Ac9d,4d4c,4d4s,4d4h,4c4s,4c4h,4s4h,7h6h,7d6d,6s7s,7c6c,Ah4h,As4s,4cAc,Jc8c,8sJs,8dJd,8hJh,KcTh,KcTs,KcTd,KhTc,KhTs,KhTd,TcKs,KsTh,KsTd,Ah3h,As3s,3cAc,Ah7d,Ah7c,Ah7s,7hAs,7hAc,As7d,As7c,7dAc,Ac7s,Kc8c,Kh8h,8sKs,Ah5s,Ah5d,Ah5c,5sAc,5hAs,5hAc,5dAs,5dAc,As5c,Ah6s,Ah6d,Ah6c,6hAs,6hAc,As6d,As6c,6sAc,6dAc,Ah4d,Ah4c,Ah4s,As4h,As4d,As4c,4hAc,4dAc,4sAc,JcQh,JcQd,QcJs,QcJh,QcJd,QhJs,QhJd,QdJs,QdJh,Kc9s,Kc9h,Kc9d,Kh9s,Kh9c,Kh9d,9hKs,Ks9c,Ks9d,Kc7c,Kh7h,Ks7s,Qc9c,Qh9h,Qd9d,Ah2h,As2s,Ac2c,QcTh,QcTs,QcTd,TcQh,TcQd,QhTs,QhTd,QdTh,QdTs,Kc6c,Kh6h,Ks6s,Jc9c,9sJs,9hJh,Jd9d,8s7s,7h8h,7d8d,8c7c,8sTs,Tc8c,8dTd,8hTh,Kc5c,Kh5h,5sKs,Qc8c,Qh8h,8dQd,Ah3c,Ah3s,Ah3d,As3c,As3d,As3h,3sAc,3dAc,Ac3h,Kc7h,Kc7d,Kc7s,Kh7d,Kh7c,Kh7s,7hKs,7dKs,Ks7c,JcTh,JcTs,JcTd,TcJs,TcJh,TcJd,JsTh,JsTd,ThJd,TsJh,TsJd,JhTd,5s6s,5h6h,5d6d,5c6c,3h3d,3h3s,3h3c,3d3s,3d3c,3s3c,2s2d,2s2h,2s2c,2d2h,2d2c,2h2c,5s4s,5h4h,5d4d,4c5c,Kc8s,Kc8d,Kc8h,Kh8s,Kh8d,Kh8c,Ks8d,Ks8h,Ks8c,Ah2d,Ah2s,Ah2c,2dAs,2dAc,2hAs,2hAc,As2c,2sAc,Kc3c,Kh3h,Ks3s,Qc9s,Qc9h,Qc9d,9sQh,9sQd,Qh9c,Qh9d,9hQd,Qd9c,Kc4c,Kh4h,4sKs,Kc6h,Kc6s,Kc6d,Kh6s,Kh6d,Kh6c,6hKs,Ks6d,Ks6c,Qc7c,7hQh,7dQd,Qc6c,6hQh,Qd6d,8sQc,8sQh,8sQd,Qc8d,Qc8h,Qh8d,Qh8c,8hQd,Qd8c,9cTc,9sTs,9hTh,Td9d,Kc2c,Kh2h,2sKs,5dQd,Qc5c,5hQh,Jc9s,Jc9h,Jc9d,9sJh,9sJd,9hJs,9hJd,Js9c,Js9d,9cJh,9cJd,Jh9d,Kc5s,Kc5h,Kc5d,Kh5s,Kh5d,Kh5c,5hKs,5dKs,Ks5c,Kc4h,Kc4d,Kc4s,Kh4d,Kh4c,Kh4s,4hKs,4dKs,4cKs,Jc7c,7hJh,7dJd,Js7s,Qc7h,Qc7d,Qc7s,7hQd,Qh7d,Qh7c,Qh7s,Qd7c,Qd7s,Qc3c,Qh3h,Qd3d,Qc4c,4hQh,4dQd,Qc6h,Qc6s,Qc6d,6hQd,Qh6s,Qh6d,Qh6c,Qd6s,Qd6c,8s6s,6h8h,8d6d,8c6c,9cTh,9cTs,9cTd,Tc9s,Tc9h,Tc9d,9sTh,9sTd,9hTs,9hTd,Th9d,Ts9d,Jc8s,Jc8d,Jc8h,8sJh,8sJd,8dJs,8dJh,8hJs,8hJd,Js8c,8cJh,8cJd,Kc3s,Kc3d,Kc3h,Kh3c,Kh3s,Kh3d,3cKs,Ks3d,Ks3h,Kc2d,Kc2h,Kc2s,Kh2d,Kh2s,Kh2c,2dKs,2hKs,Ks2c,Jc5c,5sJs,5hJh,5dJd,5sQc,5sQh,5sQd,5dQc,5dQh,Qc5h,5hQd,Qh5c,Qd5c,Jc6c,6hJh,6sJs,6dJd,Qc4h,Qc4d,Qc4s,4hQd,Qh4d,Qh4c,Qh4s,4cQd,4sQd,2dQd,Qc2c,2hQh,7hTh,Tc7c,7dTd,7sTs,7h9h,9s7s,7d9d,7c9c,Jc4c,4hJh,4dJd,4sJs,Jc7h,Jc7d,Jc7s,7hJs,7hJd,7dJs,7dJh,Js7c,7cJh,7cJd,7sJh,7sJd,8sTc,8sTh,8sTd,Tc8d,Tc8h,8dTh,8dTs,8hTs,8hTd,8cTh,8cTs,8cTd,5s7s,5h7h,5d7d,7c5c,Jc3c,3sJs,3dJd,Jh3h,6hTh,Tc6c,6sTs,6dTd,8s9h,8s9c,8s9d,9s8d,9s8h,9s8c,9h8d,9h8c,8d9c,8h9c,8h9d,8c9d,7hTc,7hTs,7hTd,Tc7d,Tc7s,7dTh,7dTs,7sTh,7sTd,Th7c,7cTs,7cTd,5sTs,5hTh,5dTd,Tc5c,Jc5s,Jc5h,Jc5d,5sJh,5sJd,5hJs,5hJd,5dJs,5dJh,Js5c,5cJh,5cJd,6h4h,4d6d,4c6c,4s6s,Jc6h,Jc6s,Jc6d,6hJs,6hJd,6sJh,6sJd,Js6d,Js6c,6dJh,Jh6c,Jd6c,4h3h,3c4c,4d3d,4s3s,Tc4c,4hTh,4dTd,4sTs,Qc3s,Qc3d,Qc3h,Qh3c,Qh3s,Qh3d,3cQd,3sQd,Qd3h,6h9h,9s6s,6d9d,9c6c,Jc2c,2dJd,2hJh,2sJs,2dQc,2dQh,Qc2h,Qc2s,2hQd,Qh2s,Qh2c,2sQd,Qd2c,Jc4h,Jc4d,Jc4s,4hJs,4hJd,4dJs,4dJh,4cJs,4cJh,4cJd,4sJh,4sJd,5s9s,5h9h,5d9d,9c5c,Jc3s,Jc3d,Jc3h,3cJs,3cJh,3cJd,3sJh,3sJd,Js3d,Js3h,3dJh,Jd3h,7h9s,7h9c,7h9d,9s7d,9s7c,7d9h,7d9c,9h7s,9h7c,7s9c,7s9d,7c9d,Tc3c,3sTs,Th3h,3dTd,6hTc,6hTs,6hTd,Tc6s,Tc6d,6sTh,6sTd,Th6d,Th6c,6dTs,Ts6c,Td6c,5s8s,5h8h,5d8d,8c5c,8s7h,8s7d,8s7c,7h8d,7h8c,7d8h,7d8c,8h7c,8h7s,8d7c,8d7s,8c7s,2dTd,2hTh,Tc2c,2sTs,5sTc,5sTh,5sTd,5hTc,5hTs,5hTd,5dTc,5dTh,5dTs,Th5c,Ts5c,5cTd,6h9s,6h9c,6h9d,9s6d,9s6c,9h6s,9h6d,9h6c,6s9c,6s9d,6d9c,6c9d,Jc2d,Jc2h,Jc2s,2dJs,2dJh,2hJs,2hJd,2sJh,2sJd,Js2c,2cJh,2cJd,9s4s,4h9h,4d9d,4c9c,Tc4h,Tc4d,Tc4s,4hTs,4hTd,4dTh,4dTs,4cTh,4cTs,4cTd,4sTh,4sTd,5s9h,5s9c,5s9d,5h9s,5h9c,5h9d,5d9s,5d9h,5d9c,9s5c,9h5c,5c9d,8s6h,8s6d,8s6c,6h8d,6h8c,8h6s,8h6d,8h6c,8d6s,8d6c,6s8c,8c6d,9s3s,3c9c,9h3h,3d9d,2d9d,2h9h,9s2s,2c9c,8s4s,4h8h,4d8d,4c8c,Tc3s,Tc3d,Tc3h,3cTh,3cTs,3cTd,3sTh,3sTd,Th3d,3dTs,Ts3h,Td3h,7h6s,7h6d,7h6c,6h7d,6h7c,6h7s,7d6s,7d6c,6s7c,6d7c,6d7s,7s6c,7h4h,4d7d,4c7c,4s7s,5s8h,5s8d,5s8c,8s5h,8s5d,8s5c,5h8d,5h8c,5d8h,5d8c,8h5c,8d5c,2dTc,2dTh,2dTs,2hTc,2hTs,2hTd,Tc2s,2sTh,2sTd,Th2c,2cTs,2cTd,8s3s,3c8c,8h3h,8d3d,9s4h,9s4d,9s4c,4h9c,4h9d,4d9h,4d9c,4c9h,4c9d,9h4s,4s9c,4s9d,5s7h,5s7d,5s7c,5h7d,5h7c,5h7s,5d7h,5d7c,5d7s,7h5c,7d5c,7s5c,8s2s,2d8d,2h8h,8c2c,5s6h,5s6d,5s6c,5h6s,5h6d,5h6c,5d6h,5d6s,5d6c,6h5c,6s5c,6d5c,9s3c,9s3d,9s3h,3c9h,3c9d,9h3s,9h3d,3s9c,3s9d,3d9c,9c3h,3h9d,6h3h,3c6c,3s6s,6d3d,5s3s,5h3h,5d3d,3c5c,7h3h,3c7c,7d3d,3s7s,8s4h,8s4d,8s4c,4h8d,4h8c,4d8h,4d8c,4c8h,4c8d,4s8h,4s8d,4s8c,2d9s,2d9h,2d9c,2h9s,2h9c,2h9d,9s2c,2s9h,2s9c,2s9d,9h2c,2c9d,5s4h,5s4d,5s4c,5h4d,5h4c,5h4s,5d4h,5d4c,5d4s,4h5c,4d5c,4s5c,7h4d,7h4c,7h4s,4h7d,4h7c,4h7s,4d7c,4d7s,4c7d,4c7s,7d4s,4s7c,6h4d,6h4c,6h4s,4h6s,4h6d,4h6c,4d6s,4d6c,4c6s,4c6d,4s6d,4s6c,2d6d,2h6h,2s6s,2c6c,5s2s,2d5d,5h2h,2c5c,8s2d,8s2h,8s2c,2d8h,2d8c,2h8d,2h8c,2s8h,2s8d,2s8c,8h2c,8d2c,2d7d,2h7h,2s7s,7c2c,2d4d,2h4h,2s4s,4c2c,8s3c,8s3d,8s3h,3c8h,3c8d,8h3s,8h3d,8d3s,8d3h,3s8c,8c3d,8c3h,7h3c,7h3s,7h3d,3c7d,3c7s,7d3s,7d3h,3s7c,7c3d,7c3h,3d7s,7s3h,5s3c,5s3d,5s3h,5h3c,5h3s,5h3d,5d3c,5d3s,5d3h,3s5c,3d5c,5c3h,6h3c,6h3s,6h3d,3c6s,3c6d,3s6d,3s6c,6s3d,6s3h,6d3h,3d6c,6c3h,2d3d,2h3h,3c2c,2s3s,2d7h,2d7c,2d7s,2h7d,2h7c,2h7s,7h2s,7h2c,2s7d,2s7c,7d2c,2c7s,5s2d,5s2h,5s2c,2d5h,2d5c,5h2s,5h2c,5d2h,5d2s,5d2c,2h5c,2s5c,4h3c,4h3s,4h3d,3c4d,3c4s,4d3s,4d3h,4c3s,4c3d,4c3h,4s3d,4s3h,2d6h,2d6s,2d6c,2h6s,2h6d,2h6c,6h2s,6h2c,2s6d,2s6c,6s2c,6d2c,2d4h,2d4c,2d4s,2h4d,2h4c,2h4s,4h2s,4h2c,2s4d,2s4c,4d2c,4s2c,2d3c,2d3s,2d3h,2h3c,2h3s,2h3d,3c2s,2s3d,2s3h,3s2c,3d2c,2c3h", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c,AhTh,AsTs,TcAc,KcJc,KhJh,KsJs,Ah9h,As9s,Ac9c,KcQc,KhQh", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c,AhTh,AsTs,TcAc,KcJc,KhJh,KsJs,Ah9h,As9s,Ac9c,KcQc,KhQh,6s6d,6s6c,6s6h,6d6c,6d6h,6c6h,JcTc,JsTs,ThJh,TdJd,QcTc,QhTh,QdTd,AhTc,AhTs,AhTd,AsTc,AsTh,AsTd,ThAc,AcTs,AcTd,KcTc,KhTh,KsTs", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c,AhTh,AsTs,TcAc,KcJc,KhJh,KsJs,Ah9h,As9s,Ac9c,KcQc,KhQh,6s6d,6s6c,6s6h,6d6c,6d6h,6c6h,JcTc,JsTs,ThJh,TdJd,QcTc,QhTh,QdTd,AhTc,AhTs,AhTd,AsTc,AsTh,AsTd,ThAc,AcTs,AcTd,KcTc,KhTh,KsTs,Ah8h,8sAs,8cAc,Ah7h,As7s,7cAc,Ah5h,5sAs,Ac5c,KcQh,KcQd,KhQc,KhQd,QcKs,QhKs,KsQd", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c,AhTh,AsTs,TcAc,KcJc,KhJh,KsJs,Ah9h,As9s,Ac9c,KcQc,KhQh,6s6d,6s6c,6s6h,6d6c,6d6h,6c6h,JcTc,JsTs,ThJh,TdJd,QcTc,QhTh,QdTd,AhTc,AhTs,AhTd,AsTc,AsTh,AsTd,ThAc,AcTs,AcTd,KcTc,KhTh,KsTs", "AhAc,AhAs,AcAs,KcKh,KcKs,KhKs,QcQh,QcQd,QhQd,KcAc,AhKh,AsKs,KcAh,KcAs,AhKs,KhAs,KhAc,KsAc,JcJh,JcJd,JcJs,JhJd,JhJs,JdJs,AhQh,QcAc,TsTd,TsTh,TsTc,TdTh,TdTc,ThTc,AhQc,AhQd,QcAs,AsQh,AsQd,QhAc,QdAc,JcAc,AhJh,AsJs,9c9h,9c9s,9c9d,9h9s,9h9d,9s9d,JcAh,JcAs,AhJs,AhJd,AsJh,AsJd,JsAc,AcJh,AcJd,8h8s,8h8d,8h8c,8s8d,8s8c,8d8c,7s7d,7s7h,7s7c,7d7h,7d7c,7h7c"]  # noqa
        board = "AdKdQs"

        from timeit import default_timer as timer

        iters = 0
        times = [timer()]
        results = []
        for _ in range(iters):
            results.append(monte_carlo(handranges, board))
            times.append(timer())

        if iters:
            total = times[-1] - times[0]
            assert len(times) == iters + 1
            diffs = [
                times[i + 1] - times[i]
                for i in range(iters)
            ]
            avg = sum(diffs) / iters
            _min = min(diffs)
            _max = max(diffs)
            print(f'{iters} calls in {total} seconds.')
            print(f'avg: {avg}; min: {_min}, max: {_max}')
            proc_times = [
                result['results']['total_proc_time']
                for result in results
            ]
            print('---')
            print(f'subprocess call times:')
            avg = sum(proc_times) / iters
            _min = min(proc_times)
            _max = max(proc_times)
            print(f'avg: {avg}; min: {_min}, max: {_max}')

        iters = 0
        if iters:
            cards = [Card(c) for c in INDICES]
            start = timer()
            for i in range(iters):
                cards[i % 52] == cards[(i * i) % 52]
            total = timer() - start
            rate = iters / total
            print(f'{iters} comparisons in {total} seconds, {rate} c/s')


@tag('monte-carlo')
class ExaminePersonalityTest(SixPlayerTableTest):
    '''
    this test is essentially a tool to provide insights when tweaking
    bot personality parameters
    '''

    PERSONALITIES = [
        # 'CompilesDavis',
        # 'Nanopoleon',
        # 'AntoninScala',
        # 'BIOSeph_Stalin',
        # 'DLL_Cool_J',
        # 'DigitJonesDiary',
        # 'Vim_Diesel',
        # 'KernelSanders',
        # 'ROM_Jeremy',
        # 'ArrayPotter',
        # 'Paul_GNUman',
        # 'AnsibleBuress',
        # 'ElbitsPresley',
        # 'JamesPerlJones',
        # 'RuthDataGinsberg',
        # 'MCMC_Escher',
    ]
    def examine(self):
        # logging.getLogger('robots').setLevel(logging.DEBUG)
        for bot_name in self.PERSONALITIES:
            get_smart_move(
                self.accessor,
                self.controller.log,
                personality=bot_personality(bot_name)
            )

    def examine_preflop(self, bot_name):
        print(f'\n>> {bot_name}')
        personality = bot_personality(bot_name)

        for mode in personality['preflop']:
            print(mode)
            for pos in personality['preflop'][mode]:
                prange = preflop_range(personality['preflop'][mode][pos])
                print(f'\t{pos}: {repr(prange)}')

    def test_examine_preflop_open(self):
        for bot_name in self.PERSONALITIES:
            self.examine_preflop(bot_name)

    def test_multiway_limp(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Kc,Ts',
                self.cuttlefish_player: 'Qc,6d',
                self.ajfenix_player: '2s,5h',
                self.cowpig_player: 'Jc,Tc',
                self.alexeimartov_player: '8d,9d',
                self.ahnuld_player: '8h,9h',
            },
            add_log=True,
            board_str='Ad,Ks,6s,3d,3s',
        )
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        ctrl.dispatch('CALL', player_id=self.alexeimartov_player.id)
        ctrl.dispatch('CALL', player_id=self.ahnuld_player.id)
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        ctrl.dispatch('CALL', player_id=self.cuttlefish_player.id)
        ctrl.dispatch('CHECK', player_id=self.ajfenix_player.id)

        self.examine()
        ctrl.dispatch('CHECK', player_id=self.cuttlefish_player.id)
        self.examine()
        ctrl.dispatch('CHECK', player_id=self.ajfenix_player.id)
        self.examine()
        ctrl.dispatch('CHECK', player_id=self.cowpig_player.id)
        self.examine()
        ctrl.dispatch('CHECK', player_id=self.alexeimartov_player.id)
        self.examine()
        ctrl.dispatch('CHECK', player_id=self.ahnuld_player.id)
        self.examine()
        ctrl.dispatch('CHECK', player_id=self.pirate_player.id)

        self.examine()
        ctrl.dispatch('CHECK', player_id=self.cuttlefish_player.id)
        self.examine()
        ctrl.dispatch('BET', player_id=self.ajfenix_player.id, amt=12)
        self.examine()
        ctrl.dispatch('FOLD', player_id=self.cowpig_player.id)
        self.examine()
        ctrl.dispatch('CALL', player_id=self.alexeimartov_player.id)
        self.examine()
        ctrl.dispatch('FOLD', player_id=self.ahnuld_player.id)
        self.examine()
        ctrl.dispatch('CALL', player_id=self.pirate_player.id)
        self.examine()
        ctrl.dispatch('FOLD', player_id=self.cuttlefish_player.id)

        self.examine()

    def test_3bet_3barrel(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: 'Jc,Jd',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: '8h,9h',
            },
            add_log=True,
            board_str='Ad,Kd,Qs',
        )
        self.examine()
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        # TODO

    def test_3way_flop_checkraise(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: 'Jc,Jd',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: '8h,9h',
            },
            add_log=True,
            board_str='Ad,Kd,Qs',
        )
        self.examine()
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        # TODO

    def test_4way_river_explosion(self):
        ctrl = self.controller
        self.setup_hand(
            blinds_positions={'btn_pos': 0, 'sb_pos': 1, 'bb_pos': 2},
            player_hole_cards={
                self.pirate_player: 'Ac,Kc',
                self.cuttlefish_player: 'Qc,Qd',
                self.ajfenix_player: '2s,3h',
                self.cowpig_player: 'Jc,Jd',
                self.alexeimartov_player: '2d,3c',
                self.ahnuld_player: '8h,9h',
            },
            add_log=True,
            board_str='Ad,Kd,Qs',
        )
        self.examine()
        ctrl.dispatch('CALL', player_id=self.cowpig_player.id)
        # TODO
