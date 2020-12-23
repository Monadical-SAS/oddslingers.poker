import React from 'react'
import classNames from 'classnames'
import {reduxify} from '@/util/reduxify'

import {getGamestate} from '@/poker/selectors'
import {Notification} from '@/notifications/components'


export const Notifications = reduxify({
    mapStateToProps: (state) => {
        const {table} = getGamestate(state)
        return {
            notifications: state.notifications.notifications_list,
            notifications_ready: table.notifications_ready
                              || table.badge_ready
                              || table.level_notifications_ready,
        }
    },
    render: ({notifications, notifications_ready, className}) => {
        return <div className={classNames('notification-container', className)}>
            {notifications.map((notification, i) =>
                <Notification notification={notification}
                              notifications_ready={notifications_ready}
                              key={`notif-${i}`} />)}
        </div>
    }
})
