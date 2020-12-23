import React from 'react'
import {reduxify} from '@/util/reduxify'

import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'
import {onSubmitAction} from '@/poker/reducers'

import {
    NewSidebetModalButton,
    ChangeSidebetModalButton
} from '@/sidebets/components'


export const SidebetPlayer = reduxify({
    mapStateToProps: (state, props) => {
        const {players, table} = getGamestate(state)
        const player = players[props.player_id]
        const animation_ends = table.animation_ends

        const max_amt = Math.round(player.stack.amt * 0.1)

        const bets = state.sidebet.bets || []
        const active_bets = bets.filter(bet =>
            bet.player.id === props.player_id &&
            (bet.status !== 'Closed')
        )

        if(!active_bets.length){
            const {odds} = {odds: 1.0}
            const logged_in_player = getLoggedInPlayer(players)
            const can_sidebet = logged_in_player === null && global.user

            return {odds, can_sidebet, player_name: player.username, max_amt}
        }

        const current_value = active_bets.reduce((acc, bet) =>
            acc + Number(bet.current_value), 0)

        const total_amt = active_bets.reduce((acc, bet) =>
            acc + Number(bet.amt), 0)

        let value_class = ''
        if (current_value < total_amt) {
            value_class = 'red'
        } else if (current_value !== total_amt) {
            value_class = 'green'
        }
        return {active_bets, animation_ends, current_value,
                value_class, max_amt}
    },
    mapDispatchToProps: {
        onSubmitAction
    },
    render: (props) => {
        if (props.active_bets) {
            return <ChangeSidebetModalButton {...props} />
        }
        return props.can_sidebet ? <NewSidebetModalButton {...props} /> : null
    }
})
