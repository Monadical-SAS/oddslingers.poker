import React from 'react'
import classNames from 'classnames'
import {reduxify} from '@/util/reduxify'

import Button from 'react-bootstrap/lib/Button'
import Col from 'react-bootstrap/lib/Col'

import {Icon} from '@/components/icons'
import {tooltip} from '@/util/dom'
import {mapStateToProps, mapDispatchToProps} from '@/tournament_summary/components/shared'

const kickPlayer = (onSubmitAction, tournament_id, kicked_user) => {
    onSubmitAction('LEAVE_TOURNAMENT', {kicked_user})
}


const RegularEntrants = ({entrants, tournament_status, tournament_admin,
                          presence, onSubmitAction, id}) => {
    const is_pending = tournament_status === 'PENDING'
    const can_kick = is_pending
                     && global.user
                     && tournament_admin
                     && global.user.username === tournament_admin.username
    return entrants.map(entrant => {
        const is_inactive = is_pending
                            && !presence[entrant.username]
                            && !entrant.is_robot
                            && !entrant.is_robot
        return <span
            key={entrant.id}
            className={classNames('entrant', {'inactive': is_inactive})}>
            <img className='profile-img'
                src={entrant.profile_image}/>
            <div className='entrant-details'>
                <b className="entrant-name">
                    {(tournament_admin && entrant.username === tournament_admin.username) ?
                        <Icon name='shield'
                                style={{ color: 'red' }}
                                {...tooltip('Tournament Admin', 'top')}/>
                        : null}
                    <a href={`/user/${entrant.username}/`}>
                        &nbsp;{entrant.username}
                        {is_inactive ? ' (inactive)' : ''}
                        {entrant.is_robot ? ' (bot)' : ''}
                    </a>
                </b>
                <br/>
            </div>
            {(can_kick && entrant.username !== tournament_admin.username) ?
                <span onClick={() => kickPlayer(onSubmitAction, id, entrant.username)}
                        className='tournament-kick-span' >
                    <Icon name='times-circle'
                            id='tournament-kick-icon'
                            {...tooltip('Kick out player')}/></span>
                : null
            }
        </span>
    })
}

const InGameEntrants = ({entrants}) => {
    return entrants.map(entrant =>
        <span
            key={entrant.id}
            className={classNames('entrant', {'inactive': !entrant.playing})}>
            <img className='profile-img'
                src={entrant.profile_image}/>
            <div className='entrant-details'>
                <b className="entrant-name">
                    <a href={`/user/${entrant.username}/`}>
                        &nbsp;{entrant.username}
                        {!entrant.playing ? ' (eliminated)' : ''}
                    </a>
                </b>
                <br/>
                {Number(entrant.stack) > 0 &&
                    <span className="entrant-stack">
                        <picture>
                            <source srcSet="/static/images/chips.webp" type="image/webp" />
                            <img src="/static/images/chips.png" alt="Chips" />
                        </picture>&nbsp;
                        {entrant.stack}
                    </span>}
            </div>
        </span>
    )
}

export const TournamentEntrants = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: ({entrants, presence, tournament_status, tournament_admin, id,
              available_entrances, onSubmitAction}) => {

        const can_add_bot = global.user
                            && global.user.username === tournament_admin.username
                            && tournament_status === 'PENDING'
                            && available_entrances

        return <Col lg={4} md={4} sm={12} className="tournament-entrants">
            <h4>Entrants</h4>
            {can_add_bot ?
                <Button bsStyle="primary"
                        onClick={() => onSubmitAction('JOIN_TOURNAMENT', {'robot': true})}
                        className="add-robot">
                    <Icon name="plus"/> Add Bot
                </Button>
                : null
            }
            <hr/>
            <div className="entrants-scroll">
                {tournament_status === 'STARTED' ?
                    <InGameEntrants entrants={entrants}/>
                    : <RegularEntrants entrants={entrants}
                                       tournament_status={tournament_status}
                                       tournament_admin={tournament_admin}
                                       presence={presence}
                                       id={id}
                                       onSubmitAction={onSubmitAction}/>}
            </div>
        </Col>
    }
})