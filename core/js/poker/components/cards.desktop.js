import React from 'react'
import {reduxify} from '@/util/reduxify'

import {calculateTableCSS, styleForWithUnits} from "@/poker/css.desktop"

import {compute_props, select_props, SeatCardsComponent} from '@/poker/components/cards'


const get_defaults = (table, players, player) => {
    const css = calculateTableCSS({table, players})
    return styleForWithUnits(css, `/players/${player.id}/cards`)
}

export const SeatCards = reduxify({
    mapStateToProps: (state, props) => {
        return compute_props(select_props(state, props, get_defaults))
    },
    render: (props) => {
        return <SeatCardsComponent {...props} />
    }
})
