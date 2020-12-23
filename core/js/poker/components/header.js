import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import Button from 'react-bootstrap/lib/Button'

import {getGamestate, getPlayerBuyin} from '@/poker/selectors'
import {sitIn, onSubmitAction} from '@/poker/reducers'
import {onToggleSound} from '@/sounds/reducers'
import {TAKE_SEAT_BEHAVIOURS} from '@/constants'
import {chipAmtStr} from '@/util/javascript'
import {localStorageGet, localStorageSet, isEmbedded} from '@/util/browser'


export const mapDispatchToProps = {
    sitIn,
    onSubmitAction,
    onToggleSound
}

export const handleSitIn = (sitInFunc, table_path) => {
    if (global.user) {
        localStorageSet('passive_actions_title_blinks', 0)
        sitInFunc()
    } else {
        // redirect to login page, then back to table or embedded table
        if (isEmbedded(global)) {
            const embed_path = table_path.replace('/table/', '/embed/')
            global.location = `/accounts/login/?next=${embed_path}`
        } else {
            global.location = `/accounts/login/?next=${table_path}`
        }
    }
}

export const mapStateToProps = (state) => {
    const {table, players} = getGamestate(state)
    const {
        logged_in_player, joining_table, last_stack_at_table, table_locked
    } = state.gamestate

    const player = logged_in_player || {}
    const avail = new Set(player.available_actions || [])
    const last_stack = Number(last_stack_at_table)
    const buyin_amt = getPlayerBuyin(Number(table.min_buyin), last_stack)

    const muted_sounds = global.user ?
        global.user.muted_sounds
        : localStorageGet('muted_sounds', false)

    let user_has_enough_funds = true
    if (global.user){
        user_has_enough_funds = Number(global.user.balance || 0) >= buyin_amt
    }
    const has_bets = (state.sidebet.bets || []).length > 0

    const rebuy = player.logged_in ? {
        bb: table.bb,
        can_set_auto_rebuy: avail.has('SET_AUTO_REBUY'),
        can_buy: avail.has('BUY'),
        min_buyin: Number(table.min_buyin),
        max_buyin: Number(table.max_buyin),
        player_auto_rebuy: Number(player.auto_rebuy),
        num_seats: table.num_seats,
        legal_min_buyin: Number(player.legal_min_buyin),
        legal_max_buyin: Number(player.legal_max_buyin),
    } : null

    return {
        id: table.id,
        short_id: table.short_id,
        name: table.name,
        path: table.path,
        created_by: table.created_by,
        variant: table.variant,
        sb: Number(table.sb),
        bb: Number(table.bb),
        hand_number: Number(table.hand_number),
        num_seats: Number(table.num_seats),
        available_seats: Number(table.available_seats),
        min_buyin: Number(table.min_buyin),
        max_buyin: Number(table.max_buyin),
        can_sit: !logged_in_player,
        players: players,
        player_position: player.position,
        is_tournament: Boolean(table.tournament),
        is_private: table.is_private,
        rebuy,
        logged_in_player,
        muted_sounds,
        user_has_enough_funds,
        has_bets,
        joining_table,
        table_locked,
    }
}

class SitDownButtonComponent extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {show_sit_options: false}
    }
    onShowOptions() {
        global.history.pushState({}, this.props.name, this.props.path)
        if (global.user) {
            this.setState({show_sit_options: true && this.props.enabled})
        } else {
            handleSitIn(this.props.sitIn, this.props.path)
        }
    }
    handleSitInOption(sin_in_option) {
        if (global.user) {
            $.ajax({
                url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
                type: 'PATCH',
                data: JSON.stringify({ 'sit_behaviour': sin_in_option })
            }).done(() => handleSitIn(this.props.sitIn, this.props.path))
        }
    }
    render() {
        const use_red = (this.props.user_has_enough_funds === false
                        || this.props.table_locked)
        return this.state.show_sit_options ?
            <div className="game-header-buttons sit-in-options">
                {Object.keys(TAKE_SEAT_BEHAVIOURS).map(bhv =>
                    <Button key={bhv} bsStyle='success'
                        onClick={() => this.handleSitInOption(bhv)}
                        disabled={!this.props.enabled}>
                        {TAKE_SEAT_BEHAVIOURS[bhv]}
                    </Button>)}
            </div>
            : <div className="game-header-buttons">
                <Button bsStyle={`${this.props.enabled ? 'success' : 'default'}`}
                        className={classNames('feature-btn', {'slow-pulsing': this.props.enabled})}
                        onClick={() => this.onShowOptions()}
                        disabled={!this.props.enabled}>
                    {!this.props.mobile &&
                        <picture>
                          <source srcSet="/static/images/chair.webp" type="image/webp"/>
                          <img src="/static/images/chair.png" alt="Sit down at the table."/>
                        </picture>}
                    <b>{this.props.button_main_label}</b>
                    <br/>
                    {(this.props.user_has_enough_funds && global.user && !this.props.mobile  && !this.props.table_locked) ?
                        <img src="/static/images/chips.png" style={{
                            marginLeft: '0px',
                            marginRight: '4px',
                            bottom: '4px',
                            float: 'left',
                            height: '43px',
                            width: 'auto',
                            marginTop: '-4px',
                            opacity: '0.88',
                        }}/> : null}
                    <small className={classNames({'red': use_red})}>
                        {this.props.button_label}
                    </small>
                </Button>
            </div>
    }
}

export const SitDownButton = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: (props) => {

        let button_label = ''
        let button_main_label = 'Sit Down'
        if (!global.user) {
            button_label = `Get ${chipAmtStr(global.props.SIGNUP_BONUS)} free chips`
        } else if (props.table_locked) {
            if (global.user.cashtables_level < props.bb){
                button_main_label = 'Level locked'
                button_label = `Earn chips to unlock ${props.sb}/${props.bb}`
            } else {
                button_main_label = 'Unlock seat'
                button_label = <a href="/accounts/email/" target="_blank">Verify email address</a>
            }
        } else if (!props.available_seats) {
            button_label = 'Table is full'
        } else if (props.user_has_enough_funds === false) {
            button_label = 'Not enough chips'
        } else if (props.has_bets) {
            button_label = 'Active sidebets'
        } else {
            button_label = `${chipAmtStr(props.min_buyin)} to sit`
        }

        const is_logged_in = Boolean(global.user)
        const is_fetching_bal = is_logged_in && (global.user.balance === undefined)
        let show_sitdownbutton = true
        let enable_sitdownbutton = true

        if (is_logged_in) {
            // hide/show button completely
            show_sitdownbutton = (
                !is_fetching_bal          // hide until balance fetched via ajax
                && props.can_sit          // hide if already seated
                && !props.is_tournament)  // hide if it's a table on a tourney

            // enablde=green, disabled=greyed-out button when shown
            enable_sitdownbutton = (
                Boolean(props.available_seats)
                && props.user_has_enough_funds
                && !props.has_bets
                && !props.joining_table
                && !props.table_locked)
        }

        return show_sitdownbutton ?
            <SitDownButtonComponent {...props}
                                    enabled={enable_sitdownbutton}
                                    button_label={button_label}
                                    button_main_label={button_main_label}/>
            : null
    }
})

export class ToggleSoundsClass extends React.PureComponent {
    constructor(props) {
        super(props)
        this.state = {
            muted: false
        }
    }
    componentDidMount() {
        this.setState({
            muted: this.props.muted_sounds
        })
    }
    onToggle(){
        const {onToggleSound} = this.props
        const new_state = !this.state.muted
        onToggleSound(new_state)
        if (global.user) {
            $.ajax({
                url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
                type: 'PATCH',
                data: JSON.stringify({ muted_sounds: new_state })
            })
        } else {
            localStorageSet('muted_sounds', new_state)
        }
        this.setState({
            muted: new_state
        })
    }
}
