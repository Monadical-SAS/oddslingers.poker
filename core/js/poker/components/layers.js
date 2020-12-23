import React from 'react'
import {reduxify} from '@/util/reduxify'

import {getUrlParams} from '@/util/browser'
import {range} from '@/util/javascript'

import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'

import {PreActions} from '@/poker/components/pre-actions'
import {CurrentActions} from '@/poker/components/current-actions'


export const ForEachPosition = reduxify({
    mapStateToProps: (state) => {
        const {num_seats} = getGamestate(state).table
        return {num_seats}
    },
    render: ({component, num_seats, className}) => {
        const Component = component
        return <div className={className}>
            {range(num_seats).map(position =>
                <Component key={position} position={position}/>)}
        </div>
    }
})

export const confirmClose = (event) => {
    const message = "Are you sure you want leave the table while you're playing?"
    event = event || global.event
    if (event) {
        event.returnValue = message
    }

    return message
}

export const mapStateToProps = (state) => {
    const {table, players} = getGamestate(state)
    const logged_in_player = getLoggedInPlayer(players)
    const className = table.className || ''
    // Animations changes the table.className to '', this causes css bugs
    const gameVariantClass = table.variant.includes('Omaha') ? 'omaha' : ''

    const show_chat = !(getUrlParams().nochat || false)

    const tournament = table.tournament

    return {logged_in_player, show_chat, tournament, className, gameVariantClass}
}

export const tournamentHasFinished = (tournament) => {
    return tournament && tournament.status === 'FINISHED'
}

export const BackgroundLayer = () =>
    <div className="table-layer layer-background"></div>

export const FeltLayer = () =>
    <div className="table-layer layer-felt">
        <div className="felt"></div>
    </div>

export const ActionsLayer = () =>
    <div className="table-layer layer-actions">
       <CurrentActions/>
    </div>

export const PreActionsLayer = () =>
    <div className="table-layer layer-pre-actions">
       <PreActions/>
    </div>
