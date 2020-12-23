import React from 'react'
import {reduxify} from '@/util/reduxify'
import classNames from 'classnames'

import {
    mapStateToProps,
    mapDispatchToProps,
    SitCheckboxes,
    SitButton,
    LeaveSeatButton,
    BlinkingTitle
} from '@/poker/components/passive-actions'


export const PassiveActions = reduxify({
    mapStateToProps,
    mapDispatchToProps,
    render: ({sitting_out, sit_in_at_blinds, sit_in_next_hand, between_hands,
              sit_out_at_blinds, sit_out_next_hand, not_enough_chips,
              not_enough_sat_players, tournament, onSubmitAction,
              is_leaving_seat, tourney_sitting_out, muck_after_winning}) => {

        return <div className="passive-actions">
            {!between_hands &&
                <span>
                    <div className={classNames('actions-title', {'join': sitting_out, 'leave': !sitting_out})}>
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
                        <div className="leave-seat-button" style={{width: is_leaving_seat ? '100%' : '20%'}}>
                            <LeaveSeatButton/>
                        </div>}
                </span>
            }
        </div>
    }
})
