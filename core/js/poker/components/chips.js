import React from 'react'
import classNames from 'classnames'

import isEqual from 'lodash/isEqual'

import {getGamestate, getPlayersByPosition} from "@/poker/selectors"
import {groupByRepeated, range, chipAmtStr} from "@/util/javascript"


const CHIP_AMOUNTS = [1000000, 500000, 100000, 25000, 5000, 1000, 500, 100, 25, 5, 1]

const getChipsChange = ( total ) => {
    let chips_change = []
    let remaining_total = total
    for( let chip_index = 0;  remaining_total > 0;  chip_index++ ) {
        const chips_of_type = Math.floor( remaining_total / CHIP_AMOUNTS[chip_index] )
        chips_change = [...chips_change, ...Array(chips_of_type).fill(CHIP_AMOUNTS[chip_index])]
        remaining_total -= chips_of_type * CHIP_AMOUNTS[chip_index]
    }
    return chips_change
}

export const Chips = ({number, style, className, show_detailed_chips,
                       getChipStyle, getVerticalAlignStyle}) => {
    let chip_base_url
    let chips_change
    if (show_detailed_chips) {
        chip_base_url = '/static/images/chips/chip'
        chips_change = getChipsChange(number)
    } else {
        const chip_img = number > 2 ? 'chips' : `${number}chip`
        chip_base_url = `/static/images/chips/${chip_img}`
    }
    return <div className={'chips ' + (className || '')} style={style}>
        {number ?
            <span>
                <span className="chips-stack">
                    {show_detailed_chips ?
                        chips_change.map((chip_type, chip_idx) =>
                            <picture key={`pic-seat-${chip_idx}`} style={getChipStyle(chip_idx)}>
                                <source className="chip-img" srcSet={`${chip_base_url}${chip_type}.webp`} type="image/webp"/>
                                <img className="chip-img" src={`${chip_base_url}${chip_type}.png`} alt="Chips"/>
                            </picture>)
                        :   <picture>
                                <source className="chip-img" srcSet={`${chip_base_url}.webp`} type="image/webp"/>
                                <img className="chip-img" src={`${chip_base_url}.png`} alt="Chips"/>
                            </picture> }
                </span>
                <div className="chip-amt"
                     style={getVerticalAlignStyle && getVerticalAlignStyle(chips_change)}>
                     {chipAmtStr(number)}
                </div>
            </span>
          : <span></span>}
    </div>
}

export class PotChips extends React.Component {
    shouldComponentUpdate(nextProps) {
        if (nextProps.number != this.props.number) return true
        if (nextProps.className != this.props.className) return true
        if (nextProps.picture != this.props.picture) return true
        if (!isEqual(nextProps.style, this.props.style)) return true
        return false
    }
    render() {
        const {number, style, className, show_detailed_chips, getChipStyle} = this.props
        let chip_base_url
        let chips_change
        let grouped_chips
        if (show_detailed_chips) {
            chip_base_url = '/static/images/chips/chip'
            chips_change = getChipsChange(number)
            grouped_chips = groupByRepeated(chips_change)
        } else {
            const chip_img = number > 2 ? 'chips' : `${number}chip`
            chip_base_url = `/static/images/chips/${chip_img}`
        }
        return <div className={classNames('chips', className)} style={style}>
            {number ?
                <div>
                    {show_detailed_chips ? <div className="chip-stacks">
                        {Object.keys(grouped_chips).map((chip_type, i) => {
                            const num_chips_of_type = range(grouped_chips[chip_type])
                            return <span className="chips-stack" key={`span-pot-${i}`}>
                                {num_chips_of_type.map(( chip_idx ) =>
                                    <picture key={`pic-pot-${chip_idx}`} style={getChipStyle(chip_idx)}>
                                        <source className="chip-img" srcSet={`${chip_base_url}${chip_type}.webp`} type="image/webp"/>
                                        <img className="chip-img" src={`${chip_base_url}${chip_type}.png`} alt="Chips"/>
                                    </picture>)}
                            </span>})}
                        </div>
                        : <picture>
                              <source className="chip-img" srcSet={`${chip_base_url}.webp`} type="image/webp"/>
                              <img className="chip-img" src={`${chip_base_url}.png`} alt="Chips"/>
                          </picture>}
                    <div className="chip-amt"><span>{chipAmtStr(number)}</span></div>
                </div>
              : <span></span>}
        </div>
    }
}

export const select_props = (state, props, get_defaults) => {
    const {table, players} = getGamestate(state)
    const player = getPlayersByPosition(players)[props.position]
    if (!player) return {}
    const default_style = get_defaults(table, players, player)
    const player_id = player.id
    const uncollected_bets = player.uncollected_bets
    return {player_id, uncollected_bets, default_style}
}

export const compute_props = ({player_id, uncollected_bets, default_style}) => {
    if (!player_id || !uncollected_bets || !uncollected_bets.amt) return {}
    const style = {
        ...default_style,
        ...uncollected_bets.style,
    }
    const className = `chips-${player_id}`
    const amt = Number(uncollected_bets.amt)
    return {amt, style, className}
}
