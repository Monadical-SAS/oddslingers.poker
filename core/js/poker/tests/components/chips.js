import {assertEqual, runTests} from '@/util/tests'

import {getGamestate} from '@/poker/selectors'
import {select_props, compute_props} from '@/poker/components/chips'


export const seat_chips_tests = {
    test_select_props() {
        const props = {
            position: 2,
            css: {
                players: {
                    playerid456: {
                        uncollected_bets: {style: {top: 1, left: 2}}
                    }
                }
            }
        }
        const state = {animations: { state: { gamestate: {
            players: {
                playerid456: {
                    id: 'playerid456',
                    position: 2,
                    uncollected_bets: {amt: '200.00', style: {top: 5, left: 10}},
                }
            },
            table: {num_seats: 6, btn_idx: 2},
        }}}}

        const get_defaults = () =>
            getGamestate(state).players.playerid456.uncollected_bets.style

        const expected = {
            player_id: 'playerid456',
            uncollected_bets: getGamestate(state).players.playerid456.uncollected_bets,
            default_style: {top: '1vw', left: '2vw'},
        }
        assertEqual(
            select_props(state, props, get_defaults).player_id,
            expected.player_id,
            'did not select props from state correctly',
        )
        assertEqual(
            select_props(state, props, get_defaults).uncollected_bets,
            expected.uncollected_bets,
            'did not select props from state correctly',
        )
        assertEqual(
            select_props(state, props, get_defaults).default_style,
            '{top, left}',
            'did not select props from state correctly',
            a => (a.top && a.left),
        )
    },

    test_compute_props_with_chips() {
        const selected_props = {
            player_id: 'playerid456',
            uncollected_bets: {amt: 200, style: {top: '5vw', left: '10vw'}},
            default_style: {top: '1vw', left: '2vw'},
        }
        const expected = {
            amt: selected_props.uncollected_bets.amt,
            style: {top: '5vw', left: '10vw'},
            className: 'chips-playerid456',
        }
        assertEqual(
            compute_props(selected_props),
            expected,
            'did not compute props correctly when given a real player with chips'
        )
    },

    test_player_without_chips() {
        const selected_props = {
            player_id: 'playerid456',
            uncollected_bets: null,
            default_style: {top: '1vw', left: '2vw'},
        }

        assertEqual(
            compute_props(selected_props),
            {},
            'did not return empty props when player has no chips',
        )
    },
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
