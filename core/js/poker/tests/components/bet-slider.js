import {assertEqual, runTests} from '@/util/tests'

import {BetSliderContainer} from '@/poker/components/bet-slider'


export const bet_slider_tests = {
    test_basics() {
        global.user = {username: 'test_user'}

        const state = {animations: { state: { gamestate: {
            table: {
                total_pot: "1.00",
                bb: "5.00",
                variant: "No limit"
            },
            players: {
                playerid456: {
                    min_bet: "2.00",
                    uncollected_bets: {amt: "3.00"},
                    stack: {amt: "4.00"},
                    amt_to_call: 5,
                    current: true,
                    username: 'test_user',
                    available_actions: [
                        'BET'
                    ],
                    logged_in: true,
                }
            }
        }}}}
        const expected = {
            suggested_bets: [
                { label: 'Min', amt: 2, str: '2' },
                { label: 'All-in', amt: 7, str: '7' },
            ],
            min_bet: 2,
            // max_bet: 7,
            // step: 5,
            can_bet: true,
            can_raise: false,
        }
        assertEqual(
            BetSliderContainer.mapStateToProps(state),
            expected,
            'did not select props from state correctly',
        )
    }
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
