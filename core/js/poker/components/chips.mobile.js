import React from 'react'
import {reduxify} from '@/util/reduxify'

import isEqual from 'lodash/isEqual'

import {calculateTableCSS, styleForWithUnits} from "@/poker/css.mobile"

import {compute_props, select_props, Chips} from '@/poker/components/chips'


const getChipStyle = (curr_idx) => ({
    bottom: curr_idx * 2
})

const get_defaults = (table, players, player) => {
    const css = calculateTableCSS({table, players})
    return styleForWithUnits(css, `/players/${player.id}/uncollected_bets`)
}

class SeatChipsComponent extends React.Component {
    shouldComponentUpdate(nextProps) {
        if(nextProps.amt != this.props.amt) return true
        if(nextProps.className != this.props.className) return true
        if(!isEqual(nextProps.style, this.props.style)) return true
        return false
    }
    render() {
        const {amt, style, className} = this.props
        return <Chips number={amt}
                      show_detailed_chips={false}
                      style={style}
                      className={className}
                      getChipStyle={getChipStyle}/>
    }
}

export const SeatChips = reduxify({
    mapStateToProps: (state, props) => {
        return compute_props(select_props(state, props, get_defaults))
    },
    render: (props) => {
        return <SeatChipsComponent {...props} />
    }
})
