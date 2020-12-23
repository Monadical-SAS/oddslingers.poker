import React from 'react'
import {reduxify} from '@/util/reduxify'

import {Notification} from '@/notifications/components'

import {mapStateToProps} from '@/tournament_summary/components/shared'


export const TournamentNotifications = reduxify({
    mapStateToProps,
    render: ({notifications}) => {
        return <div className='notification-container'>
            {notifications.map((notification, i) =>
                <Notification notification={notification} key={`notif-${i}`}/>)}
        </div>
    }
})
