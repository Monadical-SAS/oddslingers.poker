import React from 'react'
import {reduxify} from '@/util/reduxify'

import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'
import {onSubmitAction, updateCurrentBet} from '@/poker/reducers'
import {playSound} from '@/sounds/reducers'

import {ActionsTimer} from '@/poker/components/actions-timer'
import {BetSlider} from '@/poker/components/bet-slider'
import {BetInput} from '@/poker/components/bet-input'
import {Icon} from '@/components/icons'

import {change_favicon} from '@/util/browser'


export class CurrentActionsComponent extends React.Component {
    onChangeBet(amt) {
        const max_bet = this.props.max_bet
        const current_bet = Number(amt) > max_bet ? max_bet : Number(amt)
        this.props.updateCurrentBet(current_bet)
    }
    onSubmitAction(type, args={}) {
        this.props.onSubmitAction(type, args)
    }
    componentDidMount() {
        this.props.playSound('your_turn')
        document.title = '...Your action ' + document.title
        change_favicon('/static/images/alert-favicon.png')
    }
    componentWillUnmount() {
        this.props.updateCurrentBet(null)
        const title = document.title
        document.title = title.replace('...Your action ', '')
        change_favicon('/favicon.ico')
    }
    render() {
        const {submitted, current_bet} = this.props
        return <div className="actions">
            <ActionsTimer/>
            {!submitted ?
                <BetSlider current_bet={current_bet} onChangeBet={::this.onChangeBet}/>
                : <Icon name="spinner fa-spin fa-2x"/>}
            <BetInput current_bet={current_bet}
                      submitted={submitted}
                      onSubmitAction={::this.onSubmitAction}
                      onChangeBet={::this.onChangeBet}/>
        </div>
    }
}

export const CurrentActions = reduxify({
    mapStateToProps: (state) => {
        const {table, players} = getGamestate(state)
        const player = getLoggedInPlayer(players)

        const including_wagers = (amt) =>
            Number(amt) + Number(player.uncollected_bets.amt)

        const is_pot_limit = table.variant.includes('Pot Limit')
        const amt_to_call = including_wagers(player.amt_to_call)
        const potsize_with_call = Number(table.total_pot) + Number(player.amt_to_call)
        const pot_raise = Math.round(amt_to_call + potsize_with_call)

        const player_allin = including_wagers(player.stack.amt)
        const max_bet = is_pot_limit ? Math.min(player_allin, pot_raise) : player_allin
        const can_act = table.to_act_id == player.id
        const submitted = state.gamestate.action_submitted
        const current_bet = state.gamestate.current_bet
        return {can_act, max_bet, submitted, current_bet}
    },
    mapDispatchToProps: {
        playSound,
        onSubmitAction,
        updateCurrentBet
    },
    render: (props) => props.can_act ? <CurrentActionsComponent {...props}/> : null
})
