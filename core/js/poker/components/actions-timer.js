import React from 'react'
import {reduxify} from '@/util/reduxify'

import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'

import {AutoTimedProgressBar} from '@/components/progress-bar'


export const ActionsTimer = reduxify({
    mapStateToProps: (state) => {
        const {table, players} = getGamestate(state)
        const current_player = players[table.to_act_id]
        const logged_in_player = getLoggedInPlayer(players)
        const is_current_user_acting = logged_in_player && (logged_in_player.id === table.to_act_id)
        const start_time = table.last_action_timestamp
        const total_seconds = table.seconds_to_act
        const total_timebank = current_player.timebank
        return {start_time, total_seconds, total_timebank, is_current_user_acting}
    },
    render: ({total_seconds, start_time, total_timebank, is_current_user_acting}) => {
        return <AutoTimedProgressBar show_text
                                     start_time={start_time}
                                     total_seconds={total_seconds}
                                     total_timebank={total_timebank}
                                     is_current_user_acting={is_current_user_acting}
                                     style={{height: 30}}/>
    }
})
