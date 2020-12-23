import {assertEqual, runTests} from '@/util/tests'

import {getGamestate} from '@/poker/selectors'
import {select_props, compute_props} from '@/poker/components/cards'


export const seat_cards_tests = {
    test_select_props() {
        const props = {
            position: 2,
            css: {
                players: {
                    playerid456: {
                        cards: {style: {top: 1, left: 2}}
                    }
                }
            }
        }
        const state = {animations: { state: { gamestate: {
            players: {
                playerid456: {
                    id: 'playerid456',
                    position: 2,
                    cards: {'0': {card: '2d'}, '1': {card: '4h'}, style: {top: 5, left: 10}}
                }
            },
            table: {num_seats: 6, btn_idx: 2},
        }}}}
        const get_defaults = () =>
            getGamestate(state).players.playerid456.cards.style

        const expected = {
            player_id: 'playerid456',
            cards: getGamestate(state).players.playerid456.cards,
        }
        assertEqual(
            select_props(state, props, get_defaults).player_id,
            expected.player_id,
            'did not select props from state correctly',
        )
        assertEqual(
            select_props(state, props, get_defaults).cards,
            expected.cards,
            'did not select props from state correctly',
        )
        assertEqual(
            select_props(state, props, get_defaults).default_style,
            '{top, left}',
            'did not select props from state correctly',
            a => (a.top && a.left),
        )
    },

    test_select_props_without_player() {
        const props = {
            position: 2,
            css: {
                players: {}
            }
        }
        const state = {animations: { state: { gamestate: {
            players: {},
            table: {num_seats: 6, btn_idx: 2},
        }}}}
        const get_defaults = () =>
            {}

        assertEqual(
            select_props(state, props, get_defaults),
            {},
            'did not select props from state correctly when no player is at position',
        )
    },

    test_compute_props_without_player() {
        const selected_props = {player_id: null, cards: null, default_style: null}
        assertEqual(
            compute_props(selected_props),
            {},
            'did not return {} when given null player_id'
        )
    },

    test_compute_props_with_player() {
        const selected_props = {
            player_id: 'playerid456',
            cards: {'0': {card: '2d'}, '1': {card: '4h'}, style: {top: '5vw', left: '10vw'}},
            default_style: {top: '1vw', left: '2vw'}
        }
        const expected = {
            cards: selected_props.cards,
            style: {
                top: '5vw',
                left: '10vw',
            },
            className: 'cards-playerid456',
            rank_style: undefined
        }
        assertEqual(
            compute_props(selected_props),
            expected,
            'did not compute props correctly when given a real player'
        )
    },
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
