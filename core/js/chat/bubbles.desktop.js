import React from 'react'
import {reduxify} from '@/util/reduxify'
import {localStorageGet} from '@/util/browser'

import {getGamestate, getPlayersByPosition, getLastUserChatLine} from '@/poker/selectors'
import {calculateTableCSS} from "@/poker/css.desktop"
import {truncText} from '@/util/javascript'
import {CHAT_BUBBLE_MAX_TIME, CHAT_BUBBLE_MAX_LENGTH} from '@/constants'

const getLastRecentUserChatMsg = (chat_lines, username) => {
    const last_line = getLastUserChatLine(chat_lines, username)
    if (last_line == null) return null

    const msg_length = Math.min(last_line.message.length, CHAT_BUBBLE_MAX_LENGTH)
    const offset = 35 * msg_length - 2000
    const visible_time = CHAT_BUBBLE_MAX_TIME + offset
    if (Date.now() - last_line.timestamp*1000 > visible_time){
        return null
    }
    return last_line.message
}

const select_props = (state, props) => {
    const {table, players} = getGamestate(state)
    let player = getPlayersByPosition(players)[props.position]

    let last_chat_msg = null
    if (player){
        last_chat_msg = getLastRecentUserChatMsg(state.chat.lines, player.username)
    }

    const css = calculateTableCSS({table, players})
    const outerStyle = {...css.emptySeats[props.position]}

    let show_bubble = true
    if (global.user) {
        show_bubble = global.user.show_chat_bubbles
    } else {
        const local_val = localStorageGet('show_chat_bubbles')
        show_bubble = local_val !== null ? local_val === "true" : true
    }


    return {outerStyle, last_chat_msg, show_bubble}

}

class ChatBubbleComponent extends React.Component {
    constructor(props){
        super(props)
        this.state = {show: true}
    }
    hideBubble(){
        this.setState({show: false})
    }
    render(){
        const {msg, style} = this.props
        return this.state.show ?
                <div className="bubblebox" style={style} onMouseEnter={::this.hideBubble}>
                    <div className="chat-bubble" style={{color: 'black'}}>
                        {truncText(msg, CHAT_BUBBLE_MAX_LENGTH)}
                    </div>
                </div>
            : null
    }
}

export const ChatBubbles = reduxify({
    mapStateToProps: (state, props) => {
        return select_props(state, props)
    },
    render: ({outerStyle, last_chat_msg, show_bubble}) => {
        const show = show_bubble && last_chat_msg
        return show ?
            <ChatBubbleComponent style={outerStyle} msg={last_chat_msg}/>
        : null
    }
})
