import React from 'react'
import {reduxify} from '@/util/reduxify'

import Row from 'react-bootstrap/lib/Row'

import {Icon} from '@/components/icons'
import {tooltip} from '@/util/dom'

import {TournamentRedirect} from '@/tournament_summary/components/tournament_redirect'
import {TournamentInfo} from '@/tournament_summary/components/tournament_info'
import {TournamentResults} from '@/tournament_summary/components/tournament_results'
import {TournamentActions} from '@/tournament_summary/components/tournament_actions'
import {TournamentChat} from '@/tournament_summary/components/tournament_chat'
import {TournamentEntrants} from '@/tournament_summary/components/tournament_entrants'
import {TournamentNotifications} from '@/tournament_summary/components/tournament_notifications'
import {mapStateToProps} from '@/tournament_summary/components/shared'


export const TournamentSummaryComponent = reduxify({
    mapStateToProps,
    render: ({name, is_private}) => {
        return<div className='table-grid tournament-summary'
                   id="react-table-page">
            <TournamentRedirect/>
            <TournamentNotifications/>
            <h1 className="oddslingers-text-logo">
                {is_private && <Icon name='eye-slash' {...tooltip('Private Game')} />}&nbsp;
                {name}
            </h1>
            <TournamentInfo/>
            <Row className="tournament-summary-sections">
                <TournamentChat/>
                <TournamentEntrants/>
                <TournamentResults/>
                <TournamentActions/>
            </Row>
        </div>
    }
})