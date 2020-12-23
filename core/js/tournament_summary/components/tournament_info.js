import React from 'react'
import {reduxify} from '@/util/reduxify'

import {chipAmtStr} from '@/util/javascript'
import {Icon} from '@/components/icons'
import {tooltip} from '@/util/dom'

import {mapStateToProps} from '@/tournament_summary/components/shared'


const getStatusWithColor = (status) => {
    let color = 'white'
    let status_text = status
    switch(status) {
        case 'PENDING':
            color = 'gold'
            status_text = 'WAITING FOR PLAYERS...'
            break
        case 'STARTED':
            color = 'green'
            break
        case 'FINISHED':
            color = 'brown'
            break
    }
    return <span style={{color}}>{status_text}</span>
}

export const TournamentInfo = reduxify({
    mapStateToProps,
    render: ({max_entrants, entrants, buyin_amt, game_variant, tournament_status}) => {
        return <div>
            <div className="tourney-prize" {...tooltip('Prize')}>
                <Icon name="trophy"/>&nbsp; {chipAmtStr(max_entrants * buyin_amt)}
            </div>
            <div className="tournament-info">
                <div className="game-variant" {...tooltip('Game Variant')}>{game_variant}</div>
                <div className="buyin-amt" {...tooltip('Buyin Amount')}>
                    <picture>
                        <source srcSet="/static/images/chips.webp" type="image/webp"/>
                        <img src="/static/images/chips.png" alt="Chips"/>
                    </picture>&nbsp;
                    {chipAmtStr(buyin_amt)}
                </div>
                <div {...tooltip('Entrants')}>
                    <Icon name="group" />&nbsp; {entrants.length} / {max_entrants}
                </div>
                <div {...tooltip('Tournament Status')}>{getStatusWithColor(tournament_status)}</div>
            </div>
        </div>
    }
})
