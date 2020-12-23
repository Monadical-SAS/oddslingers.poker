import React from 'react'
import classNames from 'classnames'

import isEqual from 'lodash/isEqual'

import {suit_icons, suit_names} from '@/constants'
import {
    getGamestate,
    getPlayersByPosition,
    getLoggedInPlayerId
} from "@/poker/selectors"

class Card extends React.Component{
    render() {
        let {card, style, className, rank_style} = this.props
        // card can be passed as '2d', ['2', 'd'], or {rank: 2, suit: 'd'}
        card = card || {}
        const rank = card.rank || card[0]
        const suit = card.suit || card[1]
        const four_color_deck = global.user ? global.user.four_color_deck : true
        const cards_color = four_color_deck ? 'color4' : 'color2'

        if (suit && rank) {
            return <div className={classNames('card', `${rank}${suit}`, suit_names[suit],
                                              className, cards_color)}
                        style={style}>
                <span className="rank"
                      style={rank_style}>
                    {rank ? rank.replace('T', '10') : '-'}
                </span>
                <span className="suit">{suit_icons[suit] || '-'}</span>
            </div>
        }
        return <div className={classNames('card', 'unknown-card', className)} style={style}>
            &nbsp;<br/>&nbsp;
        </div>
    }
}


export const Cards = ({small, cards, style, className, rank_style}) => {
    const smallclass = small === "tiny" ? 'tiny-cards' : 'small-cards'
    return <div className={classNames('cards', {[smallclass]: small}, className)} style={style}>
        {cards && Object.keys(cards)
            .filter(card_id =>
                cards[card_id] && cards[card_id].card)
            .map(card_id =>
                <Card
                    key={card_id}
                    card={cards[card_id].card}
                    className={`card-${card_id}`}
                    style={cards[card_id].style || {}}
                    rank_style={rank_style}/>)}
    </div>
}

export class SeatCardsComponent extends React.Component {
    shouldComponentUpdate(nextProps) {
        if(!isEqual(nextProps.style, this.props.style)) return true
        if(!isEqual(nextProps.rank_style, this.props.rank_style)) return true
        if(!isEqual(nextProps.cards, this.props.cards)) return true
        if(nextProps.className != this.props.className) return true
        return false
    }
    render() {
        const {cards, style, className, rank_style} = this.props
        if (!cards) return null
        return <Cards small
                      cards={cards}
                      style={style}
                      className={className}
                      rank_style={rank_style}/>
    }
}

export const select_props = (state, props, get_defaults) => {
    const {table, players} = getGamestate(state)
    const logged_in_id = getLoggedInPlayerId(players)
    const player = getPlayersByPosition(players)[props.position]
    if (!player) return {}
    const default_style = get_defaults(table, players, player)
    const player_id = player.id
    const cards = player.cards
    const is_logged_in = logged_in_id == player_id
    return {player_id, cards, default_style, is_logged_in}
}

export const compute_props = ({player_id, cards, default_style, is_logged_in}) => {
    if (!player_id || !cards) return {}
    const style = {
        ...default_style,
        ...cards.style,
    }
    const className = classNames(`cards-${player_id}`, {'logged_in_cards': is_logged_in})
    const rank_style = cards.rank_style && cards.rank_style.style
    return {cards, style, className, rank_style}
}
