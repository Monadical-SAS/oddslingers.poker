import React from 'react'
import {reduxify} from '@/util/reduxify'

import Checkbox from 'react-bootstrap/lib/Checkbox'

import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'


class PreActionsComponent extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            total_call_amt:0,
            preset_call: false,
            preset_check: false,
            preset_checkfold: false,
        }
    }
    setPresetCall(val, set_val) {
        const new_val = set_val ?
                         val : 0
        this.setState({
            preset_check: false,
            preset_checkfold: false,
            preset_call: set_val,
            total_call_amt: new_val,
        })
        this.setPreset('SET_PRESET_CALL', new_val)
    }
    setPresetCheck(val) {
        this.setState({
            total_call_amt:0,
            preset_call: false,
            preset_checkfold: false,
            preset_check: val,
        })
        this.setPreset('SET_PRESET_CHECK', val)
    }
    setPresetCheckFold(val) {
        this.setState({
            total_call_amt:0,
            preset_call: false,
            preset_check: false,
            preset_checkfold: val,
        })
        this.setPreset('SET_PRESET_CHECKFOLD', val)
    }
    setPreset(action, val) {
        this.props.onSubmitAction(action, {set_to: val})
    }
    resetState() {
        this.setState({
            total_call_amt:0,
            preset_check: false,
            preset_call: false,
            preset_checkfold: false,
        })
    }
    componentWillMount() {
        this.resetState()
    }
    componentWillUpdate(nextProps, nextState) {
        if (nextState === this.state) {
            if (this.state.total_call_amt !== nextProps.preset_call) {
                if (this.state.preset_call){
                    this.setPresetCall(this.state.total_call_amt, true)
                }
            }
            if (this.state.preset_check !== nextProps.preset_check) {
                this.setPresetCheck(this.state.preset_check)
            }
            if (this.state.preset_checkfold !== nextProps.preset_checkfold) {
                this.setPresetCheckFold(this.state.preset_checkfold)
            }
        }

        const has_preset_call = this.state.total_call_amt !== 0
        const preset_call_changed = nextProps.total_call_amt !== this.state.total_call_amt
        if (has_preset_call && preset_call_changed){
            this.resetState()
        }
    }
    render() {
        const {amt_to_call, total_call_amt, can_set_preset_call,
               can_set_preset_check, can_set_preset_checkfold} = this.props

        return <div className="preactions">
            <div className="checkbox-actions">
                {can_set_preset_call &&
                    <Checkbox
                        checked={this.state.preset_call}
                        onChange={() => this.setPresetCall(total_call_amt, !this.state.preset_call)}>
                        &nbsp;Call {amt_to_call.toLocaleString()}
                    </Checkbox>}
                {can_set_preset_check &&
                    <Checkbox
                        checked={this.state.preset_check}
                        onChange={() => this.setPresetCheck(!this.state.preset_check)}>
                        &nbsp;Check
                    </Checkbox>}
                {can_set_preset_checkfold &&
                    <Checkbox
                        checked={this.state.preset_checkfold}
                        onChange={() => this.setPresetCheckFold(!this.state.preset_checkfold)}>
                        &nbsp;{amt_to_call === 0 ? 'Check/Fold' : 'Fold'}
                    </Checkbox>}
            </div>
        </div>
    }
}

export const PreActions = reduxify({
    mapStateToProps: (state) => {
        const {players, table} = getGamestate(state)
        const player = getLoggedInPlayer(players)
        const avail = new Set(player.available_actions)

        const can_set_preset_call = avail.has('SET_PRESET_CALL')
        const can_set_preset_check = avail.has('SET_PRESET_CHECK')
        const can_set_preset_checkfold = avail.has('SET_PRESET_CHECKFOLD')

        const to_act_id = table.to_act_id
        const between_hands = table.between_hands
        const is_acting = player.id === to_act_id
        const can_preset = (can_set_preset_call ||
                            can_set_preset_check ||
                            can_set_preset_checkfold)

        const is_leaving_seat = player.playing_state === 'LEAVE_SEAT_PENDING'

        const show = (!between_hands && !is_acting && can_preset && !is_leaving_seat)

        return {
            preset_call: Number(player.preset_call),
            amt_to_call: Number(player.amt_to_call),
            total_call_amt: Number(player.amt_to_call) + Number(player.uncollected_bets.amt),
            preset_check: player.preset_check,
            preset_checkfold: player.preset_checkfold,
            to_act_id,
            show,
            can_set_preset_call,
            can_set_preset_check,
            can_set_preset_checkfold,
        }
    },
    mapDispatchToProps: (dispatch) => {
        return {
            onSubmitAction: (type, args) => {
                dispatch({type: 'SUBMIT_ACTION', action: {type, ...args}})
            },
        }
    },
    render: (props) => {
        return props.show ?
            <PreActionsComponent {...props}
                ref={(preactions) => {
                    global.preactionsComponent = preactions
                }} />
            : null
    },
})
