import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import DropdownButton from 'react-bootstrap/lib/DropdownButton'
import MenuItem from 'react-bootstrap/lib/MenuItem'
import Button from 'react-bootstrap/lib/Button'
import InputGroup from 'react-bootstrap/lib/InputGroup'
import FormGroup from 'react-bootstrap/lib/FormGroup'
import FormControl from 'react-bootstrap/lib/FormControl'

import {is_mobile} from '@/util/browser'
import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'


const InputGroupButton = InputGroup.Button
const use_kb = global.user && global.user.keyboard_shortcuts

const roundValue = (val, table_sb, min_bet, max_bet) => {
    if (val !== min_bet && val !== max_bet) {
        const res = val % table_sb
        const rounded = val - res
        return rounded >= min_bet ? rounded : min_bet
    }
    return val
}

class FoldButton extends React.Component {
    constructor(props) {
        super(props)
        this.state = {show: false}
    }
    onToggle() {
        this.setState({show: !this.state.show})
    }
    onFold() {
        this.props.onSubmitAction('FOLD')
        this.onToggle()
    }
    onFoldAndShow() {
        this.props.onSubmitAction('FOLD', {show_cards: true})
        this.onToggle()
    }
    render() {
        const {can_check, all_in, disabled} = this.props
        return <DropdownButton id='fold-options'
                               className={classNames('fold-btn', {'all-in-btn': all_in})}
                               bsStyle={can_check ? 'default' : 'warning'}
                               disabled={disabled}
                               title='Fold'
                               onToggle={() => this.onToggle()}
                               onMouseDown={() => this.onToggle()}
                               open={this.state.show}
                               onMouseUp={() => this.onFold()}>
                <MenuItem key='show' onMouseUp={() => this.onFoldAndShow()}>
                    Fold & show
                </MenuItem>
        </DropdownButton>
    }
}
//<Button className={classNames('fold-btn', {'all-in-btn': all_in})}
//        bsStyle={can_check ? 'default' : 'warning'}
//        onClick={() => onSubmitAction('FOLD')}
//        disabled={disabled}>
//        Fold
//</Button>

const CheckButton = ({onSubmitAction, disabled=false}) =>
    <Button className="check-btn"
            bsStyle="success"
            onClick={() => onSubmitAction('CHECK')}
            disabled={disabled}>
            Check
    </Button>

const CallButton = ({amt_to_call, all_in, onSubmitAction, disabled=false}) =>
    <Button className={classNames('call-btn', {'all-in-btn': all_in})}
            onClick={() => onSubmitAction('CALL')}
            disabled={disabled}>
            Call {amt_to_call.toLocaleString()} {all_in ? '(All-in)': null}
    </Button>

const BetButton = ({current_bet, min_bet, player_allin, onSubmitAction, onChangeBet,
                    table_sb, disabled=false}) =>
    <Button disabled={disabled}
            className={classNames('bet-btn', {pulsing: current_bet})}
            bsStyle="success"
            onMouseDown={() => onChangeBet(roundValue(current_bet, table_sb, min_bet, player_allin))}
            onClick={() => onSubmitAction('BET', {amt: current_bet || min_bet})}>
            {(current_bet == player_allin) ?
                'All-in'
              : 'Bet'}
    </Button>

const RaiseButton = ({current_bet, min_bet, player_allin, onSubmitAction, onChangeBet,
                      table_sb, disabled=false}) =>
    <Button disabled={disabled}
            className={classNames('bet-btn', {pulsing: current_bet})}
            bsStyle="success"
            onMouseDown={() => onChangeBet(roundValue(current_bet, table_sb, min_bet, player_allin))}
            onClick={() => onSubmitAction('RAISE_TO', {amt: current_bet || min_bet})}>
            {(current_bet == player_allin) ? 'All-in' : 'Raise to'}
    </Button>


export const BetInput = reduxify({
    mapStateToProps: (state, props) => {
        const {players, table} = getGamestate(state)
        const player = getLoggedInPlayer(players)
        const is_tournament = Boolean(table.tournament)

        const including_wagers = (amt) =>
            Number(amt) + Number(player.uncollected_bets.amt)

        const amt_to_call = Number(player.amt_to_call)
        const table_sb = table.sb

        const player_allin = including_wagers(player.stack.amt)
        const min_bet = Number(player.min_bet)
        const current_bet = props.current_bet
        const all_in = amt_to_call >= Number(player.stack.amt)

        const can_fold = player.available_actions.includes('FOLD')
        const can_check = player.available_actions.includes('CHECK')
        const can_call = player.available_actions.includes('CALL')
        const can_bet = player.available_actions.includes('BET')
        const can_raise = player.available_actions.includes('RAISE_TO')

        return {
            can_fold, can_check, can_call, can_bet, can_raise, table_sb, is_tournament,
            current_bet, min_bet, player_allin, amt_to_call, all_in
        }
    },
    render: ({can_fold, can_check, can_call, can_bet, can_raise, current_bet, submitted, table_sb,
              is_tournament, min_bet, player_allin, amt_to_call, all_in, onChangeBet, onSubmitAction}) => {

        // auto-focus into bet field
        const is_chat_focused = $('#chat-input').is(':focus')
        if (!is_mobile() && (can_bet || can_raise) && !is_chat_focused) {
            setTimeout(() => {$('input.bet-input').click().focus()}, 50)
        }

        return <div className={`btn-row ${use_kb ? 'keyboard-shortcuts-enabled' : ''}`}>
            {can_fold &&
                <FoldButton onSubmitAction={onSubmitAction}
                            can_check={can_check}
                            disabled={submitted}
                            all_in={all_in} />}

            {can_check &&
                <CheckButton onSubmitAction={onSubmitAction}
                             disabled={submitted} />}

            {can_call &&
                <CallButton
                    amt_to_call={amt_to_call}
                    all_in={all_in}
                    disabled={submitted}
                    onSubmitAction={onSubmitAction} />}

            {(can_bet || can_raise) ?
                <FormGroup className="bet-group">
                    <InputGroup>
                        <InputGroupButton>
                            {can_bet ?
                                <BetButton
                                    table_sb={table_sb}
                                    min_bet={min_bet}
                                    player_allin={player_allin}
                                    current_bet={current_bet}
                                    onSubmitAction={onSubmitAction}
                                    onChangeBet={(val) => is_tournament ? {} : onChangeBet(val)}
                                    disabled={submitted} />
                              : <RaiseButton
                                    table_sb={table_sb}
                                    min_bet={min_bet}
                                    player_allin={player_allin}
                                    current_bet={current_bet}
                                    onChangeBet={(val) =>  is_tournament ? {} : onChangeBet(val)}
                                    onSubmitAction={onSubmitAction}
                                    disabled={submitted} />}
                        </InputGroupButton>
                        <FormControl
                            type="number"
                            id='bet-input'
                            className="bet-input"
                            placeholder={min_bet}
                            value={current_bet || ''}
                            min={min_bet}
                            max={player_allin}
                            step={table_sb}
                            onChange={(e) => {onChangeBet(e.target.value)}}
                            onKeyUp={(e) => {
                                if (e.keyCode == 13) {
                                    if (current_bet == min_bet / 2) {
                                        onSubmitAction('CALL')
                                    } else if (current_bet >= min_bet) {
                                        onSubmitAction(can_raise ? 'RAISE_TO' : 'BET', {
                                            amt: roundValue(current_bet, table_sb, min_bet, player_allin)
                                        })
                                    }
                                }}}/>
                    </InputGroup>
                </FormGroup>
              : null}
        </div>

    }
})
