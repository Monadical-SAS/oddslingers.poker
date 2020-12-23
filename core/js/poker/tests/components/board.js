import {assertEqual, runTests} from '@/util/tests'

import {BoardContainer} from "@/poker/components/board.desktop"


export const board_tests = {
    test_board_with_players() {
        global.location = {origin: 'https://tests.l'}
        const state = {animations: { state: { gamestate: {
            table: {
                board: {
                    cards: {'0': {card: '2d'}, '1': {card: '4h'}, style: {top: 5, left: 10}}
                },
                total_pot: '400000.00000',
                path: '/table/12345'
            },
            players: {
                playerid456: {
                    id: 'playerid456',
                    position: 2,
                },
                playerid457: {
                    id: 'playerid457',
                    position: 3,
                }
            }
        }}}}

        const expected = {
            board: {
                cards: {'0': {card: '2d'}, '1': {card: '4h'}, style: {top: 5, left: 10}}
            },
            is_empty_table: true,
            has_pot: true,
            total_pot_string: '400,000',
            share_url: 'https://tests.l/table/12345',
            tournament: undefined,
            tweet_url: 'https://twitter.com/intent/tweet?text=Join%20the%20poker%20game%20on%20%40OddSlingers%3A%20undefined%20https%3A%2F%2Ftests.l%2Ftable%2F12345',
            discord_url: 'https://discord.gg/Avx4bds',
        }

        assertEqual(
            BoardContainer.mapStateToProps(state, {}),
            expected,
            'did not map state to props correctly when given some players to the table'
        )
    },

    test_empty_table_board() {
        global.location = {origin: 'https://tests.l'}
        const state = {animations: { state: { gamestate: {
            table: {
                board: {
                    cards: {style: {top: 5, left: 10}}
                },
                total_pot: '0.00',
                path: '/table/12345'
            },
            players: {},
        }}}}

        const expected = {
            board: {
                cards: {style: {top: 5, left: 10}}
            },
            is_empty_table: true,
            has_pot: false,
            total_pot_string: '0',
            share_url: 'https://tests.l/table/12345',
            tournament: undefined,
            tweet_url: 'https://twitter.com/intent/tweet?text=Join%20the%20poker%20game%20on%20%40OddSlingers%3A%20undefined%20https%3A%2F%2Ftests.l%2Ftable%2F12345',
            discord_url: 'https://discord.gg/Avx4bds',
        }

        assertEqual(
            BoardContainer.mapStateToProps(state, {}),
            expected,
            'did not map state to props correctly when no players are given to the table'
        )
    },
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
