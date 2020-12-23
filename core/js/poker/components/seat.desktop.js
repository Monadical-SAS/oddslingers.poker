import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import {
    getGamestate,
    getPlayersByPosition,
    getPlayerBuyin
} from '@/poker/selectors'
import {calculateTableCSS, styleForWithUnits} from '@/poker/css.desktop'
import {SidebetPlayer} from '@/sidebets/containers'
import {
    EmptySeatComponent,
    PlayerName,
    compute_props,
    mapDispatchToProps,
    onPlayerStackClick,
} from '@/poker/components/seat'


const select_props = (state, props) => {
    const {table, players} = getGamestate(state)
    const {sidebets_enabled} = table
    const {
        logged_in_player, joining_table, last_stack_at_table, table_locked
    } = state.gamestate

    let player = getPlayersByPosition(players)[props.position]
    const to_act_id = table.to_act_id
    const css = calculateTableCSS({table, players})
    // TODO: properly handle default css for empty seats with no player
    const tournament = table.tournament
    const last_stack = Number(last_stack_at_table)
    const buyin_amt = getPlayerBuyin(Number(table.min_buyin), last_stack)

    let enough_funds = true
    if (global.user){
        enough_funds = Number(global.user.balance || 0) >= buyin_amt
    }

    if (!player) {
        player = {id: null, short_id: 'empty', position: props.position, cards: []}
        player.style = css.emptySeats[props.position]
        return {player, logged_in_player, default_style: {}, joining_table, enough_funds,
                tournament, table_locked}
    }

    const default_style = styleForWithUnits(css, `/players/${player.id}`)

    const is_logged_in = logged_in_player && logged_in_player.id == player.id

    return {to_act_id, tournament, player, logged_in_player, is_logged_in, css,
            default_style, sidebets_enabled, position: props.position}
}

export const Seat = reduxify({
    mapStateToProps: (state, props) => {
        return compute_props(select_props(state, props))
    },
    mapDispatchToProps,
    render: ({player_id, stack, enable_chips_clicking, tournament,
              logged_in_player, outerStyle, innerStyle, className,
              joinTable, joining_table, enough_funds, sidebets_enabled,
              table_locked}) => {

        const onJoinTable = (props) => {
            if (global.user) {
                joinTable(props)
            }
            else {
                global.location = '/accounts/login/?next=' + global.location.pathname
            }
        }

        if (!player_id) {
            const display_empty_seat = !joining_table
                                        && enough_funds
                                        && !logged_in_player
                                        && !table_locked
            return !tournament ?
                <EmptySeatComponent style={outerStyle}
                                    display={display_empty_seat}
                                    onJoinTable={!logged_in_player && onJoinTable}/>
                : null
        }

        return <div className="seatbox" style={outerStyle}>
            <div className={className} style={innerStyle}>
                {sidebets_enabled && <SidebetPlayer player_id={player_id}/>}
                <PlayerName player_id={player_id}/>

                <div onClick={enable_chips_clicking ? onPlayerStackClick : null}
                     className={classNames("player-stack", {'clickable': enable_chips_clicking})}>
                    {Number(stack.amt || 0).toLocaleString()} chips
                    {enable_chips_clicking && <span className="caret"></span>}
                </div>
                <br/>
            </div>
        </div>
    }
})
