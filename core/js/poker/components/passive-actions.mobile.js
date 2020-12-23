import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import Button from 'react-bootstrap/lib/Button'
import {Icon} from '@/components/icons'

import {
    mapStateToProps,
    mapDispatchToProps,
    SitCheckboxes,
    SitButton,
    LeaveSeatModalTrigger,
    BlinkingTitle
} from '@/poker/components/passive-actions'

export const PassiveActions = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: ({sitting_out, sit_in_at_blinds, sit_in_next_hand, between_hands,
              sit_out_at_blinds, sit_out_next_hand, not_enough_chips,
              is_acting, onSubmitAction, not_enough_sat_players, muck_after_winning,
              is_leaving_seat, player_position, tournament, tourney_sitting_out,
              cards}) => {

        return !is_acting && !between_hands ?
            <div className="passive-actions">
                <div className={classNames('actions-title', {join: sitting_out, leave: !sitting_out})}>
                    <BlinkingTitle sitting_out={sitting_out}
                                   sit_in_next_hand={sit_in_next_hand}
                                   sit_in_at_blinds={sit_in_at_blinds}/>
                </div>
                {!is_leaving_seat &&
                    <span>
                        {not_enough_sat_players ?
                            <SitButton sitting_out={sitting_out} onSubmitAction={onSubmitAction}/>
                            : <SitCheckboxes sitting_out={sitting_out}
                                            sit_in_next_hand={sit_in_next_hand}
                                            sit_in_at_blinds={sit_in_at_blinds}
                                            sit_out_next_hand={sit_out_next_hand}
                                            sit_out_at_blinds={sit_out_at_blinds}
                                            muck_after_winning={muck_after_winning}
                                            not_enough_chips={not_enough_chips}
                                            tournament={tournament}
                                            tourney_sitting_out={tourney_sitting_out}
                                            onSubmitAction={onSubmitAction}/>
                        }
                    </span>
                }
                {!tournament &&
                    <div className="leave-seat-button" style={{ width: is_leaving_seat ? '100%' : '22%' }}>
                        <LeaveSeatModalTrigger sitting_out={sitting_out}
                                               player_position={player_position}
                                               is_leaving_seat={is_leaving_seat}
                                               cards={cards}
                                               onSubmitAction={onSubmitAction}>
                            <Button bsStyle="default">
                                <span className="label">
                                    {is_leaving_seat && 'Leaving... (Cancel)'}
                                </span>
                                <Icon name={`${is_leaving_seat ? 'times' : 'sign-out'}`}/>
                            </Button>
                        </LeaveSeatModalTrigger>
                    </div>}
            </div>
            : null
    }
})
