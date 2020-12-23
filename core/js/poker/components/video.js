import React from 'react'
import {connect} from '@/util/react'
import {Icon} from '@/components/icons'

import {startStreaming, stopStreaming} from '@/video/reducers'

import {VideoStream} from '@/video/containers'



export const ToggleableVideo = connect({
    mapStateToProps: () => ({
        stream_id: global.myStream && global.user.id
    }),
    mapDispatchToProps: () => ({
        onToggleStreaming(enable) {
            if (enable)
                startStreaming(global.page.store)
            else
                stopStreaming(global.page.store)
        }
    }),
    render: ({stream_id, onToggleStreaming}) =>
        <div onClick={() => (onToggleStreaming(!stream_id), true)}>
            {stream_id ? 
                <VideoStream stream_id={stream_id} style={{width: '100%', height: 'auto'}}/>
              : <div className="video-stream">
                    <Icon name="tv" style={{fontSize: 44}}/><br/>
                    Start Streaming
                </div>}
        </div>
})
