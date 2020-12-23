import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import {getGamestate, getPlayersByPosition} from '@/poker/selectors'
import {calculateTableCSS, styleForWithUnits} from '@/poker/css.mobile'

import {SidebetPlayer} from '@/sidebets/containers'

import {
    PlayerName,
    compute_props
} from '@/poker/components/seat'


const select_props = (state, props) => {
    const {table, players} = getGamestate(state)
    const {sidebets_enabled} = table

    let player = getPlayersByPosition(players)[props.position]
    const tournament = table.tournament
    const logged_in_player = state.gamestate.logged_in_player
    const to_act_id = table.to_act_id
    const css = calculateTableCSS({table, players})
    if (!player) {
        player = {id: null, short_id: 'empty', position: props.position, cards: []}
        player.style = css.emptySeats[props.position]
        return {player, logged_in_player, default_style: {}, tournament}
    }

    // TODO: properly handle default css for empty seats with no player
    const default_style = styleForWithUnits(css, `/players/${player.id}`)
    const is_logged_in = logged_in_player && logged_in_player.id == player.id

    return {to_act_id, player, tournament, is_logged_in, default_style, sidebets_enabled}
}

export const Seat = reduxify({
    mapStateToProps: (state, props) => {
        return compute_props(select_props(state, props))
    },
    render: ({player_id, stack, outerStyle, innerStyle, sidebets_enabled, className}) => {

        if (!player_id) {
            return null
        }

        return <div className="seatbox" style={outerStyle}>
            <div className={className} style={innerStyle}>
                {sidebets_enabled && <SidebetPlayer player_id={player_id}/>}
                <PlayerName player_id={player_id}/>
                <div className={classNames("player-stack")}>
                    {Number(stack.amt || 0).toLocaleString()}
                </div>
                <div className='thinking'>...</div>
                <br/>
            </div>
        </div>
    }
})
