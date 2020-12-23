import React from 'react'

import {tooltip} from '@/util/dom'

import {reduxify} from '@/util/reduxify'
import {Icon} from '@/components/icons'

import {styleFor} from '@/poker/css'
import {calculateTableCSS} from '@/poker/css.desktop'
import {getGamestate, getPlayersByPosition} from '@/poker/selectors'


export const TableBotProfileComponent = ({bot_profile, style}) => {
    return <a href={`/user/${bot_profile.username}`} target="_blank" className='bot-profile-container' style={style}>
        <div className="bot-center-panel">
            <h4 style={{textAlign: 'center'}}>
                {bot_profile.username} &nbsp;
                <Icon name='laptop' {...tooltip('AI Player', 'top')}/>
            </h4>
            <div className="profile-bio" style={{textAlign: 'center'}}>
                <p>{bot_profile.bio}</p>
                <div className="bot-personality">
                    <p className="personality-title">Preflop Playstyle:</p>
                    <p className="personality-desc">{bot_profile.personality_preflop}</p>

                    <p className="personality-title">General Playstyle:</p>
                    <p className="personality-desc">{bot_profile.personality_postflop}</p>
                </div>
            </div>
        </div>
    </a>
}



const select_props = (state, props) => {
    const {table, players} = getGamestate(state)

    let player = getPlayersByPosition(players)[props.position]
    const css = calculateTableCSS({table, players})

    return {player, css}
}


const compute_props = ({player, css}) => {

    let show = false
    if (!player || !player.is_robot) {
        return {show}
    }
    show = true
    const default_style = styleFor(css, `/players/${player.id}`)

    const style = {
        top: default_style.top + 25,
        left: default_style.left
    }
    return {show, player, style}
}

export const TableBotProfile = reduxify({
    mapStateToProps: (state, props) => {
        return compute_props(select_props(state, props))
    },
    render: (props) => {
        return props.show ?
            <TableBotProfileComponent bot_profile={props.player}
                                      style={props.style}/>
            : null
    }
})
