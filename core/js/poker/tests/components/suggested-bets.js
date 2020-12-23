import {assertEqual, runTests} from '@/util/tests'

import {select_props, compute_props} from '@/poker/components/suggested-bets'


export const suggested_bets_tests = {
    test_select_props() {
        global.user = {username: 'test_user'}
        const state = {animations: { state: { gamestate: {
            table: {
                total_pot: 1,
            },
            players: {
                playerid456: {
                    min_bet: 2,
                    uncollected_bets: {amt: 3},
                    stack: {amt: 4},
                    amt_to_call: 5,
                    current: true,
                    username: 'test_user',
                    logged_in: true,
                }
            }
        }}}}
        const expected = {min_bet: 2, max_bet: 7, current_pot: 9, amt_to_call: 8}
        assertEqual(
            select_props(state, {}),
            expected,
            'did not select props from state correctly',
        )
    },

    test_compute_simple_props() {
        const props = {min_bet: 1, max_bet: 1, current_pot: 1, amt_to_call: 1}
        const expected = {
            suggested_bets: [],
        }
        assertEqual(
            compute_props(props),
            expected,
            'did not compute component props correctly given simple state'
        )
    },

    test_compute_more_props() {
        const props = {min_bet: 1, max_bet: 12, current_pot: 1, amt_to_call: 1}
        const expected = {
            suggested_bets: [
                {label: 'Min', amt: 1, str: '1'},
                {label: '1/2', amt: 2, str: '2'},
                {label: 'All-in', amt: 12, str: '12'},
            ],
        }
        assertEqual(
            compute_props(props),
            expected,
            'did not compute component props correctly given simple state'
        )
    },

    test_compute_full_props() {
        const props = {current_pot: 50, min_bet: 1, max_bet: 100, amt_to_call: 20}
        const expected = {
            suggested_bets: [
                {label: 'Min', amt: 1, str: '1'},
                {label: '1/2', amt: 45, str: '45'},
                {label: '2/3', amt: 53, str: '53'},
                {label: 'Pot', amt: 70, str: '70'},
                {label: 'All-in', amt: 100, str: '100'},
            ],
        }
        assertEqual(
            compute_props(props),
            expected,
            'did not compute component props correctly given some complex state'
        )
    },

    test_compute_props_large_allin() {
        const props = {current_pot: 40500, min_bet: 2000, max_bet: 55000, amt_to_call: 1000}
        const expected = {
            suggested_bets: [
                {label: 'Min', amt: 2000, str: Number(2000).toLocaleString()},
                {label: '1/2', amt: 21250, str: Number(21250).toLocaleString()},
                {label: '2/3', amt: 28000, str: Number(28000).toLocaleString()},
                {label: 'Pot', amt: 41500, str: Number(41500).toLocaleString()},
                {label: 'All-in', amt: 55000, str: Number(55000).toLocaleString()},
            ],
        }
        assertEqual(
            compute_props(props),
            expected,
            'did not compute component props correctly given some complex state'
        )
    },
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
