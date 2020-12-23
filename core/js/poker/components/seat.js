import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import isEqual from 'lodash/isEqual'

import {AutoTimedProgressBar} from '@/components/progress-bar'

import {getGamestate, getLoggedInPlayer, getSatPlayers} from '@/poker/selectors'
import {joinTable} from '@/poker/reducers'
import {ACTION_COLORS} from '@/constants'

export class EmptySeatComponent extends React.Component {
    shouldComponentUpdate(nextProps) {
        if (!isEqual(nextProps.style, this.props.style)) return true
        if (nextProps.mobile != this.props.mobile) return true
        if (nextProps.display != this.props.display) return true
        return false
    }
    render() {
        const {style, onJoinTable, mobile, display} = this.props
        return <span>{display &&
                <div style={{...style, opacity: onJoinTable ? undefined : 0.3}}
                     className="empty-seatbox"
                     onClick={onJoinTable || (() => {})}>
                    <div className="seat">
                        {onJoinTable ?
                            (mobile ?
                                <span></span>
                                : <span>Empty Seat<br/>click to sit</span>)
                            : null}
                    </div>
                </div>
            }
        </span>
    }
}

const getLastActionStr = (player, table, not_enough_sat_players) => {
    const is_acting = table.to_act_id == player.id
    const last_action = player.last_action

    if (not_enough_sat_players && !player.sitting_out) {
        return 'READY'
    }
    if (player.is_autofolding || player.sitting_out) {
        return 'SIT OUT'
    }
    if (player.sit_in_at_blinds || player.sit_in_next_hand) {
        return 'WAITING'
    }
    if (table.tournament && last_action === 'SIT_OUT') {
        return null
    }
    if (is_acting || !last_action) {
        return null
    }
    if (player.is_all_in) {
        return 'ALL IN'
    }
    if (last_action == 'RAISE_TO') {
        return 'RAISE'
    }
    return last_action.replace('_', ' ')
}

export const onPlayerStackClick = () => {
    const $dropdown = $('#rebuy-menu').parent()
    const $dropdown_list = $dropdown.find('.dropdown-menu')
    $dropdown_list.addClass('fixed-on-seat')
    $(document).click((e) => {
        if (!$dropdown_list.is(':hidden') && !$(e.target).is('.player-stack')) {
            $dropdown.removeClass('open')
        }
    })
    $dropdown.toggleClass('open')
}

export const PlayerName = reduxify({
    mapStateToProps: (state, props) => {
        const {table, players} = getGamestate(state)
        const player = players[props.player_id]

        const username = player.username.slice(0, 16)

        const logged_in_player = getLoggedInPlayer(players)

        const is_current_user_acting = logged_in_player && (table.to_act_id === logged_in_player.id)

        const is_acting = table.to_act_id == player.id

        const show_progress = is_acting && !player.logged_in
        const timebank = player.timebank

        const seconds_to_act = table.seconds_to_act
        const last_action_timestamp = table.last_action_timestamp
        const not_enough_sat_players = getSatPlayers(players).length < 2
        const last_action_str = getLastActionStr(player, table, not_enough_sat_players)
        const action_color = ACTION_COLORS[last_action_str] || 'silver'

        return {username, last_action_str, timebank, action_color, show_progress,
                seconds_to_act, last_action_timestamp, is_current_user_acting}
    },
    mapDispatchToProps: () => {
        return {
            onAwakenBackend() {
                // make sure socket is still available since this can be called after a long delay
                // (they may have dynamicHotloaded a new page with no socket)
                if (global.socket && global.socket.send_action && !global.frontend_paused) {
                    global.socket.send_action('AWAKEN')
                }
            },
        }
    },
    render: ({username, last_action_str, timebank, action_color, show_progress,
              seconds_to_act, last_action_timestamp, is_current_user_acting,
              onAwakenBackend}) => {
        return <span>
            <div className="player-name">
                <a href={`/user/${username}`} target="_blank" style={{pointerEvents: 'initial'}}>
                    {show_progress ?
                        <AutoTimedProgressBar
                            total_seconds={seconds_to_act}
                            start_time={last_action_timestamp}
                            total_timebank={timebank}
                            is_current_user_acting={is_current_user_acting}
                            onOutOfTime={onAwakenBackend}>
                            {username}
                        </AutoTimedProgressBar>
                        : username}
                </a>
            </div>
            {last_action_str &&
                <div className="action-label">
                    <div className="action-label-arrow"></div>
                    <div className={classNames('action-label-inner', action_color)}>
                        {last_action_str}
                    </div>
                </div>}
        </span>
    }
})

export const compute_props = ({to_act_id, player, tournament, logged_in_player, sidebets_enabled,
                               is_logged_in, default_style, joining_table, enough_funds, table_locked}) => {
    const outerStyle = {
        ...default_style,
        ...player.style,
    }
    const player_id = player.id
    const classes = ['seat', `seat-${player.short_id}`, `position-${player.position}`]

    // confusion because frontend uses "active" to mean "currently acting"
    // and backend uses it to mean "seated & ready to play"
    const active_seat = player.is_active
    const is_next_to_act = to_act_id == player.id
    const is_logged_in_player = player.is_current
    if (active_seat) classes.push('active-seat')
    if (is_next_to_act) classes.push('next-to-act')
    if (is_logged_in_player) classes.push('current')
    if (player.last_action) classes.push(player.last_action)

    let innerStyle = {}
    if (player.sitting_out) {
        innerStyle = {opacity: 0.5}
    }
    const className = classes.join(' ')
    const stack = player.stack
    const enable_chips_clicking = is_logged_in && !tournament
    return {player_id, stack, outerStyle, innerStyle, className, logged_in_player, sidebets_enabled,
            is_logged_in, joining_table, enough_funds, enable_chips_clicking, tournament, table_locked}
}

export const mapDispatchToProps = {
    joinTable
}
