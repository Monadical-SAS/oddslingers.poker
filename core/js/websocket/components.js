import React from 'react'
import classNames from 'classnames'

import {reduxify} from '@/util/reduxify'
import {tooltip} from '@/util/dom'
import {Spinner} from '@/components/icons'



const SignalBars = ({latency}) => {
    const best = 300
    const worst = 2000

    const percent = 1 - ((latency - best) / (worst - best))
    const level = Math.min(Math.max(Math.round(percent * 5), 1), 5)

    return <a href="/speedtest/"
              target="_blank"
              className={classNames('signal-bars', `level-${level}`)}
              {...tooltip(`🔵 Latency: ${(latency).toFixed(0)}ms`, 'bottom')}>
        <div className={`bar ${level > 0 ? 'full' : ''}`}/>
        <div className={`bar ${level > 1 ? 'full' : ''}`}/>
        <div className={`bar ${level > 2 ? 'full' : ''}`}/>
        <div className={`bar ${level > 3 ? 'full' : ''}`}/>
        <div className={`bar ${level > 4 ? 'full' : ''}`}/>
    </a>
}

export const SocketStatus = reduxify({
    mapStateToProps: (state) => {
        const {ready, delay, reconnects} = state.websocket

        const queued_msg = global.page.socket.queue[0]
        let unsent_actions = ''

        if (reconnects != -1 && queued_msg && !ready) {
            unsent_actions = (
               ' Waiting to send: ' +
                (queued_msg.type == 'SUBMIT_ACTION' ? 
                    queued_msg.action.type
                  : queued_msg.type)
                .split('_').join(' ')
            )
        }
        return {ready, delay, reconnects, unsent_actions}
    },
    render: ({ready, delay, reconnects, unsent_actions}) => {
        let detail
        if (reconnects == -1) {
            detail = 'Opening websocket connection.'
        } else if (!ready) {
            const plural = (reconnects.length == 1) ? '' : 's'
            detail = `${reconnects} reconnect${plural}.${unsent_actions}`
        }
        return (ready ?
            <SignalBars latency={delay}/>
          : <div className="signal-badge"
                    {...tooltip(detail, 'bottom')}>
                    {(reconnects > 5) ?
                        'Bad connection'
                      : 'Connecting'}...&nbsp; &nbsp;<Spinner/>
            </div>)
    }
})
