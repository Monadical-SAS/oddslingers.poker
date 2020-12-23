import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import Col from 'react-bootstrap/lib/Col'
import Button from 'react-bootstrap/lib/Button'

import {mapStateToProps, mapDispatchToProps} from '@/tournament_summary/components/shared'


const handleJoin = (id, tourney_path, onSubmitAction) => {
    if (global.user) {
        onSubmitAction('JOIN_TOURNAMENT')
    } else {
        // redirect to login page
        global.location = '/accounts/login/?next=' + tourney_path
    }
}

const getJoinButtonLabel = (available_entrances, user_has_enough_funds,
                            max_entrants, entrants, tournament_locked) => {
    if (tournament_locked) {
        return 'Tournament locked'
    }
    if (!available_entrances) {
        return 'Tournament is full'
    }

    if (global.user && !user_has_enough_funds) {
        return 'You lack the buyin amt'
    }
    return `${max_entrants - entrants.length}/${max_entrants} seats remaining`
}

const ActionButton = ({id, is_entrant, tournament_status, table_path,
                       entrants, max_entrants, available_entrances,
                       user_has_enough_funds, tourney_path, tournament_locked,
                       onSubmitAction}) => {

    if (tournament_status === 'STARTED') {
        return <div>
            <a href={table_path}
               target="_blank"
               className="btn btn-success tournament-action-button feature-btn slow-pulsing">
                <b>Go to Table</b>
            </a>
            {!is_entrant &&
                <iframe id="iframed-table"
                        src={`${table_path.replace("/table/", "/embed/")}?nochat=1&nowelcome=1`}>
                </iframe>}
        </div>
    }

    const enabled = !global.user
                    || available_entrances
                    && user_has_enough_funds
                    && !tournament_locked
    if (!is_entrant) {
        return <Button onClick={() => handleJoin(id, tourney_path, onSubmitAction)}
                       bsStyle={`${enabled ? 'success' : 'default'}`}
                       disabled={!enabled}
                       className={classNames('tournament-action-button',
                                             'feature-btn',
                                             {'slow-pulsing': enabled})}>
            <b>Join Tournament</b>
            <small className={classNames({'red': !enabled})}>
                {getJoinButtonLabel(available_entrances, user_has_enough_funds,
                                    max_entrants, entrants, tournament_locked)}
            </small>
        </Button>
    } else {
        return <Button onClick={() => onSubmitAction('LEAVE_TOURNAMENT')}
                       bsStyle="default"
                       className="tournament-action-button feature-btn">
            <b>Leave Tournament</b>
        </Button>
    }
}

export const TournamentActions = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: ({id, is_entrant, entrants, max_entrants, tournament_status,
              table_path, user_has_enough_funds, available_entrances,
              tourney_path, tournament_locked, onSubmitAction}) => {

        return tournament_status !== 'FINISHED' &&
            <Col lg={4} md={4} sm={12} className="tournament-actions">
                <h4>Actions</h4>
                <hr/>
                <ActionButton id={id}
                              is_entrant={is_entrant}
                              entrants={entrants}
                              max_entrants={max_entrants}
                              tournament_status={tournament_status}
                              tourney_path={tourney_path}
                              table_path={table_path}
                              available_entrances={available_entrances}
                              user_has_enough_funds={user_has_enough_funds}
                              tournament_locked={tournament_locked}
                              onSubmitAction={onSubmitAction}/>
            </Col>
    }
})
