import React from 'react'
import {reduxify} from '@/util/reduxify'

import Button from 'react-bootstrap/lib/Button'

import {tooltip} from '@/util/dom'
import {uniquify} from '@/util/javascript'

import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'


export const select_props = (state) => {
    const {table, players} = getGamestate(state)
    const player = getLoggedInPlayer(players)

    const including_wagers = (amt) =>
        Number(amt) + Number(player.uncollected_bets.amt)

    const min_bet = Number(player.min_bet)
    const max_bet = including_wagers(player.stack.amt)
    const amt_to_call = including_wagers(player.amt_to_call)
    const current_pot = Number(table.total_pot) + amt_to_call

    return {min_bet, max_bet, current_pot, amt_to_call}
}

export const compute_props = ({min_bet, max_bet, current_pot, amt_to_call}) => {
    const half = Math.round(amt_to_call + (1/2)*current_pot)
    const two_thirds = Math.round(amt_to_call + (2/3)*current_pot)
    const pot = Math.round(amt_to_call + current_pot)
    const bets = [
        {label: 'Min', amt: min_bet, str: min_bet.toLocaleString()},
        {label: '1/2', amt: half, str: half.toLocaleString()},
        {label: '2/3', amt: two_thirds, str: two_thirds.toLocaleString()},
        {label: 'Pot',     amt: pot, str: pot.toLocaleString()},
        {label: 'All-in',  amt: max_bet, str: max_bet.toLocaleString()},
    ]
    const is_valid = (amt) =>{
        return amt >= min_bet && amt <= max_bet
    }
    const unique_bets = uniquify(bets, bet => bet.amt)

    let valid_bets = unique_bets.filter(bet => is_valid(bet.amt))

    // make sure any all-in bets are labelled All-in
    const highest_possible_bet = valid_bets.slice(-1)[0]
    if (highest_possible_bet.amt == max_bet) {
        highest_possible_bet.label = 'All-in'
    }

    // hide All-in suggested bet if it's the only button
    // User can use the call button, which shows "all-in" instead
    if (valid_bets.length == 1 && highest_possible_bet.label == 'All-in') {
        valid_bets = []
    }

    return {suggested_bets: valid_bets}
}

export const SuggestedBets = reduxify({
    mapStateToProps: (state) => {
        return compute_props(select_props(state))
    },
    render: ({suggested_bets, onChangeBet}) => {
        return <div className="bet-suggestions">

            {suggested_bets.map(({amt, label, str}) =>
                <Button
                    onClick={() => onChangeBet(amt)}
                    {...tooltip(str, 'top')}>
                        {label}
                </Button>)}
        </div>
    }
})
