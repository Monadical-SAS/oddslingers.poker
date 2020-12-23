import React from 'react'
import {reduxify} from '@/util/reduxify'

import {uniquify, chipAmtStr} from '@/util/javascript'
import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'

import {SteppableRangeInput} from '@/components/steppable-range-input'


export const select_props = (state) => {
    const {table, players} = getGamestate(state)
    const player = getLoggedInPlayer(players)

    const can_bet = player.available_actions.includes('BET')
    const can_raise = player.available_actions.includes('RAISE_TO')

    const uncollected_bets = Number(player.uncollected_bets.amt)
    const amt_to_call = Number(player.amt_to_call)
    const min_bet = Number(player.min_bet)
    const stack = Number(player.stack.amt)

    const total_pot = Number(table.total_pot)
    const table_sb = Number(table.sb)
    const table_variant = table.variant

    return {can_bet, can_raise, uncollected_bets, amt_to_call,
            min_bet, stack, total_pot, table_sb, table_variant}
}

const validate_bets = (bets, min_bet, max_bet, player_allin) => {
    const unique_bets = uniquify(bets, bet => bet.amt)

    let valid_bets = unique_bets.filter(bet =>
        min_bet <= bet.amt && bet.amt <= max_bet
    )

    if (valid_bets.length > 0) {
        // make sure any all-in bets are labelled All-in
        const highest_possible_bet = valid_bets.slice(-1)[0]
        if (highest_possible_bet.amt == player_allin) {
            highest_possible_bet.label = 'All-in'
        }
    }

    // hide All-in suggested bet if it's the only button
    // User can use the call button, which shows "all-in" instead
    if (valid_bets.length == 1 && valid_bets.slice(-1)[0].label == 'All-in') {
        valid_bets = []
    }

    return valid_bets
}

const adjust_bet = (bet, table_sb) => {
    const res = (bet % table_sb)
    if (res === 0) return bet
    return bet - res
}

export const bet_amounts = ({uncollected_bets, amt_to_call, min_bet,
                             stack, total_pot, table_sb, table_variant}) => {

    const including_wagers = (amt) => amt + uncollected_bets

    const amt_to_call_wagers = including_wagers(amt_to_call)
    const potsize_with_call = total_pot + amt_to_call
    const half = adjust_bet(Math.round(amt_to_call_wagers + (1/2)*potsize_with_call), table_sb)
    const two_thirds = adjust_bet(Math.round(amt_to_call_wagers + (2/3)*potsize_with_call), table_sb)
    const pot_raise = adjust_bet(Math.round(amt_to_call_wagers + potsize_with_call), table_sb)
    const is_pot_limit = table_variant.includes('Pot Limit')
    const player_allin = including_wagers(stack)
    const max_bet = is_pot_limit ? Math.min(player_allin, pot_raise) : player_allin

    const bets = [
        {label: 'Min', amt: min_bet, str: chipAmtStr(min_bet)},
        {label: '1/2', amt: half, str: chipAmtStr(half)},
        {label: '2/3', amt: two_thirds, str: chipAmtStr(two_thirds)},
        {label: 'Pot', amt: pot_raise, str: chipAmtStr(pot_raise)},
        {label: 'All-in', amt: max_bet, str: chipAmtStr(max_bet)},
    ]

    return validate_bets(bets, min_bet, max_bet, player_allin)
}

const compute_props = ({can_bet, can_raise, uncollected_bets, amt_to_call,
                        min_bet, stack, total_pot, table_sb, table_variant}) => {

    const suggested_bets = bet_amounts({uncollected_bets, amt_to_call, min_bet,
                                        stack, total_pot, table_sb, table_variant})

    return {suggested_bets, min_bet, can_bet, can_raise}
}

export const BetSliderContainer = {
    mapStateToProps: (state) => {
        return compute_props(select_props(state))
    },
    render: ({suggested_bets, min_bet, current_bet, can_bet, can_raise, onChangeBet}) => {
        return (
            (can_bet || can_raise) && suggested_bets.length ?
                <SteppableRangeInput className="bet-slider"
                                     value={current_bet || min_bet}
                                     marks={suggested_bets}
                                     onChange={onChangeBet}/>
                : null
        )
    }
}

export const BetSlider = reduxify(BetSliderContainer)
