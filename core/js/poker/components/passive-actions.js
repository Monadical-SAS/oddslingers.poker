import React from 'react'
import {reduxify} from '@/util/reduxify'

import Button from 'react-bootstrap/lib/Button'
import Modal from 'react-bootstrap/lib/Modal'

import {Icon} from '@/components/icons'
import {ModalTrigger} from '@/components/modals'
import {getGamestate, getSatPlayers, getLoggedInPlayer} from '@/poker/selectors'
import {onSubmitAction} from '@/poker/reducers'
import {tooltip} from '@/util/dom'
import {localStorageGet, localStorageSet} from '@/util/browser'



const LabeledCheckBox = ({label, checked, onChange, disabled, tooltip_str}) =>
    <label style={{opacity: disabled ? 0.5 : 1}}
           {...tooltip(tooltip_str, 'top')}>
        <input type='checkbox'
               disabled={disabled}
               checked={checked}
               onChange={onChange}/>
        &nbsp;{label}
    </label>


class MuckAfterWinningCheckBox extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            muck_after_winning: props.muck_after_winning
        }
    }
    onToggleMuck(muck) {
        this.setState({
            muck_after_winning: muck
        })
        $.ajax({
            url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
            type: 'PATCH',
            data: JSON.stringify({ muck_after_winning: muck }),
            success: () => { global.user.muck_after_winning = muck }
        })
    }
    render() {
        return <LabeledCheckBox
                    tooltip_str={''}
                    checked={this.state.muck_after_winning}
                    onChange={() => this.onToggleMuck(!this.state.muck_after_winning)}
                    label='Muck after winning'/>
    }
}


class AutoFoldCheckBox extends React.Component {
    constructor(props) {
        super(props)

        this.state = {
            autofolding: this.props.tourney_sitting_out
        }
    }
    setAutofold(autofolding) {
        if (autofolding) {
            this.props.onSubmitAction('SIT_IN')
        } else {
            this.props.onSubmitAction('SIT_OUT')
        }
    }
    toggleAutofold() {
        const current_autofolding = this.state.autofolding
        this.setState({autofolding: !current_autofolding})
        this.setAutofold(current_autofolding)
    }
    componentDidUpdate(prevProps) {
        if (this.props.tourney_sitting_out !== prevProps.tourney_sitting_out) {
            this.setState({autofolding: this.props.tourney_sitting_out})
        }
    }
    render() {
        return <div>
            <LabeledCheckBox
                tooltip_str="Useful when you need to go out a few minutes"
                checked={this.state.autofolding}
                onChange={::this.toggleAutofold}
                label="Auto fold hands"/>
            {this.state.autofolding &&
                <Button bsStyle="success"
                        className="feature-btn slow-pulsing sit-back-button"
                        onClick={::this.toggleAutofold}>
                <b>Sit Back In</b>
            </Button>}
        </div>
    }
}

export class SitCheckboxes extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            sit_in_next_hand: props.sit_in_next_hand,
            sit_in_at_blinds: props.sit_in_at_blinds,
            sit_out_next_hand: props.sit_out_next_hand,
            sit_out_at_blinds: props.sit_out_at_blinds
        }
    }
    onToggleSitIn(sit_in) {
        this.setState({
            ...this.state,
            sit_in_at_blinds: false,
            sit_out_next_hand: false,
            sit_out_at_blinds: false,
            sit_in_next_hand: sit_in
        })
        if (sit_in) {
            this.props.onSubmitAction('SIT_IN')
        } else {
            this.props.onSubmitAction('SIT_OUT')
        }
    }
    onToggleSitOut(sit_in) {
        this.setState({
            ...this.state,
            sit_in_next_hand: false,
            sit_in_at_blinds: false,
            sit_out_at_blinds: false,
            sit_out_next_hand: !sit_in
        })
        if (sit_in) {
            this.props.onSubmitAction('SIT_IN')
        } else {
            this.props.onSubmitAction('SIT_OUT')
        }
    }
    componentWillReceiveProps(nextProps) {
        if (this.state.sit_in_next_hand != nextProps.sit_in_next_hand ||
            this.state.sit_out_next_hand != nextProps.sit_out_next_hand ||
            this.state.sit_in_at_blinds != nextProps.sit_in_at_blinds ||
            this.state.sit_out_at_blinds != nextProps.sit_out_at_blinds) {

            this.setState({
                sit_in_at_blinds: nextProps.sit_in_at_blinds,
                sit_out_next_hand: nextProps.sit_out_next_hand,
                sit_out_at_blinds: nextProps.sit_out_at_blinds,
                sit_in_next_hand: nextProps.sit_in_next_hand
            })
        }
    }
    onToggleSitAtBlinds(sit_in, action, key) {
        this.setState({
            ...this.state,
            sit_in_next_hand: false,
            sit_in_at_blinds: false,
            sit_out_next_hand: false,
            sit_out_at_blinds: false,
            [key]: sit_in
        })
        this.props.onSubmitAction(action, {set_to: sit_in})
    }
    render() {
        const {sitting_out, not_enough_chips, tournament, muck_after_winning,
               tourney_sitting_out, onSubmitAction} = this.props

        if (tournament) {
            return <div className="autofold-options">
                <AutoFoldCheckBox
                    onSubmitAction={onSubmitAction}
                    tourney_sitting_out={tourney_sitting_out}/>
                <MuckAfterWinningCheckBox muck_after_winning={muck_after_winning} />
            </div>
        }

        return sitting_out ?
            <div className="checkboxes">
                <LabeledCheckBox
                    disabled={not_enough_chips}
                    tooltip_str={not_enough_chips ? 'Need more chips to play.' : ''}
                    checked={this.state.sit_in_next_hand}
                    onChange={() => this.onToggleSitIn(!this.state.sit_in_next_hand)}
                    label='Sit in next hand'/>
                <br/>
                <LabeledCheckBox
                    disabled={not_enough_chips}
                    tooltip_str={not_enough_chips ? 'Need more chips to play.' : ''}
                    checked={this.state.sit_in_at_blinds}
                    onChange={() => this.onToggleSitAtBlinds(!this.state.sit_in_at_blinds,
                                                             'SIT_IN_AT_BLINDS',
                                                             'sit_in_at_blinds')}
                    label='Sit in at blinds'/>
                <br/>
                <MuckAfterWinningCheckBox muck_after_winning={muck_after_winning} />
            </div>
        :
            <div className="checkboxes">
                <LabeledCheckBox
                    disabled={false}
                    tooltip_str={not_enough_chips ? 'Need more chips to play.' : ''}
                    checked={this.state.sit_out_next_hand}
                    onChange={() => this.onToggleSitOut(this.state.sit_out_next_hand)}
                    label='Sit out next hand'/>
                <br/>
                <LabeledCheckBox
                    disabled={false}
                    tooltip_str={not_enough_chips ? 'Need more chips to play.' : ''}
                    checked={this.state.sit_out_at_blinds}
                    onChange={() => this.onToggleSitAtBlinds(!this.state.sit_out_at_blinds,
                                                             'SIT_OUT_AT_BLINDS',
                                                             'sit_out_at_blinds')}
                    label='Sit out at blinds'/>
                <br/>
                <MuckAfterWinningCheckBox muck_after_winning={muck_after_winning} />
            </div>
    }
}


export const SitButton = ({sitting_out, onSubmitAction}) =>
    <div className="sit-button">
        {sitting_out ?
            <Button bsStyle="success"
                    className="feature-btn slow-pulsing"
                    onClick={() => onSubmitAction('SIT_IN')}>
                <b>Sit In</b>
            </Button>
            : <Button onClick={() => onSubmitAction('SIT_OUT')}>
                  <b>Sit Out</b>
            </Button>}
    </div>

export class LeaveSeatModalTrigger extends ModalTrigger {
    handleClick() {
        const {sitting_out, is_leaving_seat} = this.props
        if (is_leaving_seat) {
            this.cancelLeaving()
        } else if (!sitting_out) {
            this.onShow()
        } else {
            this.onConfirm()
        }
    }
    cancelLeaving() {
        this.props.onSubmitAction(
            'TAKE_SEAT',
            {position: this.props.player_position}
        )
    }
    onConfirm() {
        // Disable onbeforeunload event to quit the second confirmation by default
        global.onbeforeunload = null

        this.props.onSubmitAction('LEAVE_SEAT')
        if(this.props.redirect_to_tables) {
            global.location = '/tables'
        }
        this.onClose()
    }
    render() {
        return <span>
            <span onClick={::this.handleClick}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            Leave Seat
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        Leaving in middle of a game folds
                        your hand and you'll have to wait for the blinds
                        again before rejoining, are you sure you want to leave?
                    </Modal.Body>
                    <Modal.Footer>
                        <Button onClick={::this.onCancel}>
                            Cancel &amp; Stay
                        </Button> &nbsp;
                        <Button bsStyle="success" onClick={::this.onConfirm}>
                            {Object.keys(this.props.cards).length > 0 && "Fold &"} Leave Seat &nbsp;<Icon name="sign-out"/>
                        </Button>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}

export class BlinkingTitle extends React.Component {
    constructor(props) {
        super(props)

        this.state = {
            show_help: false,
            flashes: localStorageGet('passive_actions_title_blinks', 0)
        }
    }
    blink() {
        this.setState({
            show_help: !this.state.show_help,
            flashes: this.state.flashes + 1
        })
        localStorageSet('passive_actions_title_blinks', this.state.flashes + 1)
    }
    componentDidMount() {
        this.interval = setInterval(::this.blink, 1500)
    }
    componentWillUnmount() {
        clearInterval(this.interval)
    }
    render() {
        let title = ""
        if (this.props.sitting_out) {
            if(this.props.sit_in_next_hand || this.props.sit_in_at_blinds) {
                title = "SITTING IN SHORTLY"
            } else {
                if (this.state.show_help && this.state.flashes < 10) {
                    title = "CHECK AN OPTION TO SIT IN"
                } else {
                    title = "JOIN GAME"
                }
            }
        } else {
            title = 'LEAVE GAME'
        }
        return title
    }
}

export const mapStateToProps = (state) => {
    const {table, players} = getGamestate(state)
    const logged_in_player = getLoggedInPlayer(players)
    const player = logged_in_player || {}
    const is_acting = player && (player.id === table.to_act_id)
    const between_hands = table.between_hands
    const avail = new Set(player.available_actions || [])
    const not_enough_sat_players = getSatPlayers(players).length < 2
    const is_leaving_seat = player.playing_state === 'LEAVE_SEAT_PENDING'
    const tourney_sitting_out = player.playing_state === 'TOURNEY_SITTING_OUT'

    return {
        sitting_out: player.sitting_out,
        player_position: player.position,
        sit_in_at_blinds: player.sit_in_at_blinds,
        sit_in_next_hand: player.sit_in_next_hand,
        sit_out_at_blinds: player.sit_out_at_blinds,
        sit_out_next_hand: player.sit_out_next_hand,
        muck_after_winning: global.user && global.user.muck_after_winning,
        can_sit: !logged_in_player,
        can_leave: avail.has('LEAVE_SEAT'),
        // if a player is sitting out, they can always sit in unless
        //  they don't have enough chips
        not_enough_chips: player.sitting_out && !avail.has('SIT_IN') && !player.sit_in_next_hand,
        tournament: table.tournament,
        cards: player.cards,
        is_leaving_seat,
        tourney_sitting_out,
        between_hands,
        not_enough_sat_players,
        is_acting
    }
}

export const mapDispatchToProps = {
    onSubmitAction
}

export const LeaveSeatButton = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        const {can_sit, between_hands, is_leaving_seat, tournament} = props

        const label_with_status = is_leaving_seat ? 'Leaving at end of hand...'
                                                  : 'Leave Seat'
        return !can_sit && !between_hands && !tournament ?
            <LeaveSeatModalTrigger {...props}>
                <Button bsStyle="default"
                        className="leave-seat">
                    <b>{label_with_status}</b>
                    <Icon name={`${is_leaving_seat ? 'times' : 'sign-out'}`}/>
                </Button>
            </LeaveSeatModalTrigger>
            : null
    }
})

export const LeaveToPage = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {
        const {can_sit, between_hands, is_leaving_seat, tournament} = props

        if (tournament) {
            return <Button bsStyle="default"
                           onClick={() => global.location = tournament.path}
                           className="leave-seat">
                <b>Go to summary page</b>
                <Icon name="arrow-right"/>
            </Button>
        }

        const label_with_status = is_leaving_seat ? 'Leaving...'
                                                  : 'Leave to Games Page'
        return !can_sit && !between_hands ?
            <LeaveSeatModalTrigger {...props} redirect_to_tables={true}>
                <Button bsStyle="default"
                        className="leave-seat">
                    <b>{label_with_status}</b>
                    <Icon name={`${is_leaving_seat ? 'times' : 'sign-out'}`} />
                </Button>
            </LeaveSeatModalTrigger>
            : null
    }
})
