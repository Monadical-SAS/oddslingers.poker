import React from 'react'
import ReactDOM from 'react-dom'
import classNames from 'classnames'
import format from 'date-fns/format'

import Button from 'react-bootstrap/lib/Button'
import FormControl from 'react-bootstrap/lib/FormControl'
import DropdownButton from 'react-bootstrap/lib/DropdownButton'
import MenuItem from 'react-bootstrap/lib/MenuItem'

import {is_centered, onKeyPress, is_mobile} from '@/util/browser'
import {ljust, hashCode} from '@/util/javascript'
import {linkifyLinks} from '@/util/dom'
import {localStorageGet, localStorageSet} from '@/util/browser'
import {
    CHAT_REPLACEMENTS, CHAT_PRESETS, MS_BETWEEN_MSGS, UP_ARROW
} from '@/constants'

import {Icon} from '@/components/icons'
import {PlayByPlay} from '@/chat/play-by-play'
import {sendChatMessage, chat_side_effects} from '@/chat/reducers'
import {getLastUserChatLine} from '@/poker/selectors'
// import {VideoPanel} from '@/video/components'


const USERNAME_COLORS = [
    'teal',
    'lime',
    'orange',
    'aqua',
    'purple',
    'yellow',
    'fuchsia',
    'olive',
]

const isDealerSpecie = (specie) =>
    specie === 'dealer'

const getUsernameColor = (username, species) => {
    if (!username || !username.length)
        return ''
    if (species === 'dealer') {return ''}
    if (species === 'observer') {return 'gray'}
    if (species === 'staff') {return 'red'}

    const username_hash = Math.abs(hashCode(username))
    return USERNAME_COLORS[username_hash % USERNAME_COLORS.length]
}

const getChatLineClass = (username, species) => {
    const msg_type = isDealerSpecie(species)
                        ? 'dealer-msg'
                        : 'chat-msg'
    return 'chat-line ' + msg_type + (species === 'staff' ? ' chat-bold' : '')
}

const getChatSpeakerClass = (username, species) => {
    if (isDealerSpecie(species))
        return ''
    return 'chat-username ' + getUsernameColor(username, species)
}

const getChatMessageClass = (username, species) => {
    return species === 'observer' ? 'chat-message-light' : 'chat-message-normal'
}

const getDateFromTimestamp = (date) => {
    return format(date, 'h:mm:ss')
}

const speciesTitle = (species) => {
    if (species === 'staff') {return ' (staff) '}
    if (species === 'observer') {return ' (observer) '}
    return ''
}

const addCheckedIcon = (checked) =>
    checked ? <Icon name='check'/> : null

const parseTagProps = (tag) => {
    const children = tag.split('|').slice(-1)[0]

    if (!children.length)
        return null

    if (!tag.includes('|'))
        return {children}

    return {children, ...JSON.parse(tag.split('|')[0])}
}

export const colorizeChatMessage = (message) => {
    // e.g. FLOP: 8♦, Q♠, J♠

    // Step 1: replace matches in str with tags that we can parse
    for (let [pattern, replacement] of CHAT_REPLACEMENTS) {
        message = message.replace(pattern, replacement)
    }

    // Step 2: convert concatted string tags to list of react elements
    const elems = message.split('|||').map((tag, idx) =>
        <span {...parseTagProps(tag)} key={idx}/>)

    return elems
}



class ChatLine extends React.Component {
    shouldComponentUpdate(nextProps) {
        if (this.props.message != nextProps.message) return true
        return false
    }
    render() {
        const {speaker, species, timestamp, message} = this.props
        const time = getDateFromTimestamp(new Date(timestamp*1000))
        return <div className={getChatLineClass(speaker, species)}
                    title={`${speaker}: ${time}`}>
            <span className={getChatSpeakerClass(speaker, species)}>
                {isDealerSpecie(species) ?
                    ''
                  : ljust((speaker + speciesTitle(species) + '>'), 10)}
            </span>
            {(message == '====NEW HAND====') ? <center><br/>〰〰〰〰<br/><br/></center> :
                <span className={getChatMessageClass(speaker, species)}>
                    {isDealerSpecie(species) ?
                        colorizeChatMessage(message)
                      : linkifyLinks(message)}
                </span>
            }
            <span className="chat-timestamp">
                {time}
            </span>
        </div>
    }
}

class ChatComponent extends React.Component {
    constructor(props){
        super(props)
        const local_pbp = localStorageGet('show_playbyplay')
        const show_playbyplay = local_pbp !== null ? local_pbp === "true" : true
        const local_bbls = localStorageGet('show_chat_bubbles')
        const show_chat_bubbles = local_bbls !== null ? local_bbls === "true" : true
        const chat_filters = global.user ? {
            show_dealer_msgs: global.user.show_dealer_msgs,
            show_win_msgs: global.user.show_win_msgs,
            show_chat_msgs: global.user.show_chat_msgs,
            show_spectator_msgs: global.user.show_spectator_msgs,
            show_chat_bubbles: global.user.show_chat_bubbles,
            show_playbyplay: global.user.show_playbyplay,
        } : {
            show_dealer_msgs: true,
            show_win_msgs: true,
            show_chat_msgs: true,
            show_spectator_msgs: true,
            show_chat_bubbles: show_playbyplay,
            show_playbyplay: show_chat_bubbles,
        }

        this.state = {
            input_text: '',
            show: !is_centered() || props.show,
            class_name: '',
            last_sent_msg_ts: Date.now(),
            show_chat_presets: false,
            ...chat_filters
        }
    }
    onShow() {
        this.setState({
            ...this.state,
            show: true,
        })
    }
    onHide() {
        this.setState({
            ...this.state,
            show: false,
        })
    }
    onToggleMessages(message_type) {
        this.setState({
            ...this.state,
            [message_type]: !this.state[message_type],
        }, () => {
            if (global.user) {
                global.user.show_playbyplay = this.state.show_playbyplay
                global.user.show_chat_bubbles = this.state.show_chat_bubbles
            } else {
                localStorageSet('show_chat_bubbles', String(this.state.show_chat_bubbles))
                localStorageSet('show_playbyplay', String(this.state.show_playbyplay))
            }
            chat_side_effects()
        })

        if (global.user) {
            $.ajax({
                url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
                type: 'PATCH',
                data: JSON.stringify({ [message_type]: !this.state[message_type] })
            })
        }
    }
    onChatTyping(e) {
        if(e.key === "Enter"){
            this.onSubmit()
        }
    }
    componentDidMount(){
        onKeyPress(UP_ARROW, ::this.autofillLastLine, null)
    }
    sendChatMessage(message) {
        if (!global.user)
            global.location = '/accounts/login/?next=' + global.location.pathname

        if (Date.now() - this.state.last_sent_msg_ts > MS_BETWEEN_MSGS){
            this.props.sendChatMessage(message)
            this.setState({last_sent_msg_ts: Date.now()})
        }
    }
    clickPreset(e){
        this.sendChatMessage($(e.target).text())
    }
    onSubmit() {
        const le_message = this.state.input_text
        if (le_message){
            this.sendChatMessage(le_message.slice(0, 1000))
            this.setState({input_text: ''})
        }
    }
    filterChatLine(line) {
        if (line.species === 'dealer') {
            if (line.speaker === 'Dealer') {
                return this.state.show_dealer_msgs
            } else if (line.speaker === 'winner_info') {
                return this.state.show_win_msgs
            }
        } else if (line.species === 'observer') {
            return this.state.show_spectator_msgs
        }
        return this.state.show_chat_msgs
    }
    componentWillReceiveProps(nextProps){
        if (nextProps.chat.resolution !== this.props.chat.resolution){
            if (nextProps.chat.resolution === 'centered'){
                this.setState({
                    ...this.state,
                    show: false
                })
            } else if (nextProps.chat.resolution === 'desktop'){
                this.setState({
                    ...this.state,
                    show: true
                })
            }
        }
    }
    autofillLastLine(){
        if (global.user && document.activeElement === ReactDOM.findDOMNode(this.refs.chatInput)){
            const last_line = getLastUserChatLine(this.props.chat.lines, global.user.username)
            if (last_line != null){
                this.setState({input_text: last_line.message})
            }
        }
    }
    setInputText(e){
        this.setState({input_text: e.target.value})
    }
    toggleChatPresets(){
        this.setState({show_chat_presets: !this.state.show_chat_presets})
    }
    render() {
        const {chat, show, is_tournament} = this.props
        return <div className={classNames('chat-container',
                                          {'logged-chat': show, 'full-height-chat': this.state.show || show})}>
            {!this.state.show && !show && !is_tournament ?
                <Button onClick={::this.onShow} className="toggle-chat">
                    Chat
                </Button>
              : null}
            {show || this.state.show || is_tournament?
                <div className={classNames('text-chat', this.state.class_name)}>
                    {/*global.props.SHOW_VIDEO_STREAMS ? <VideoPanel/> : null*/}

                    <div className="chat-passive-actions">
                        <DropdownButton pullRight
                                        className={classNames('chat-top-button', {'top-right-rounded': !is_centered()})}
                                        id="chat-settings"
                                        title={<Icon name="gear"/>}>

                            <MenuItem key="show-dealer-msgs"
                                      onClick={() => this.onToggleMessages('show_dealer_msgs')}>
                                {addCheckedIcon(this.state.show_dealer_msgs)}
                                Show dealer messages
                            </MenuItem>
                            <MenuItem key="show-winning-msgs"
                                      onClick={() => this.onToggleMessages('show_win_msgs')}>
                                {addCheckedIcon(this.state.show_win_msgs)}
                                Show winning messages
                            </MenuItem>
                            <MenuItem key="show-spectator-msgs"
                                      onClick={() => this.onToggleMessages('show_spectator_msgs')}>
                                {addCheckedIcon(this.state.show_spectator_msgs)}
                                Show spectator messages
                            </MenuItem>
                            {(global.user && !is_tournament) &&
                                <MenuItem key="show-chat-bubbles"
                                          onClick={() => this.onToggleMessages('show_chat_bubbles')}>
                                    {addCheckedIcon(this.state.show_chat_bubbles)}
                                    Show chat bubbles
                                </MenuItem>
                            }
                            {!is_tournament &&
                                <MenuItem key="show-chat"
                                          onClick={() => this.onToggleMessages('show_chat_msgs')}>
                                    {addCheckedIcon(this.state.show_chat_msgs)}
                                    Show chat
                                </MenuItem>
                            }
                            {(global.user && !is_mobile() && !is_tournament) &&
                                <MenuItem key="show-playbyplay"
                                          onClick={() => this.onToggleMessages('show_playbyplay')}>
                                    {addCheckedIcon(this.state.show_playbyplay)}
                                    Show Play-By-Play panel
                                </MenuItem>
                            }
                        </DropdownButton>

                        <Button className='chat-top-button top-right-rounded chat-close-button'
                                onClick={::this.onHide}>
                            <Icon name="times"/>
                        </Button>
                    </div>

                    <div className="chat-wrapper">
                        {(!is_tournament && !is_mobile()) ?
                            <div>
                                <PlayByPlay />
                                <Button onClick={() => this.onToggleMessages('show_playbyplay')}
                                        id='play-by-play-toggle'>
                                    <Icon name={`angle-${this.state.show_playbyplay ? 'up': 'down'}`}/>
                                </Button>
                            </div> : null
                        }

                        <div className="lines-container">
                            <div ss-container="true"
                                 ref={() => global.SimpleScrollbar.initAll()}
                                 className="lines-wrapper">

                                <div className="chat-lines">
                                    {chat.lines
                                         .filter(chat_line =>
                                                    this.filterChatLine(chat_line))
                                         .map((chat_line, idx) =>
                                                 <ChatLine key={chat_line.timestamp || idx}
                                                           {...chat_line}/>)}
                                </div>
                            </div>
                        </div>
                        {this.state.show_chat_presets &&
                            <div className="chat-presets">
                                {CHAT_PRESETS.map((preset, i) =>
                                    <div className={classNames("chat-preset", "noselect")}
                                         onClick={::this.clickPreset}
                                         key={i}>
                                            {preset}
                                    </div>
                                )}
                            </div>
                        }
                        <div className="chat-actions">
                            <button className="toggle-chat-presets"
                                    onClick={::this.toggleChatPresets}>🙂</button>
                            <FormControl id="chat-input"
                                         ref="chatInput"
                                         type="text"
                                         placeholder="Message"
                                         value={this.state.input_text}
                                         onChange={::this.setInputText}
                                         onKeyPress={::this.onChatTyping}/>

                            {global.user ?
                                <Button bsStyle="primary" onClick={::this.onSubmit}>
                                    Send
                                </Button>
                              : <Button bsStyle="primary" onClick={::this.onSubmit}>
                                    Log In <br/> Send <Icon name="angle-double-right"/>
                                </Button>}
                        </div>
                    </div>
                </div>
              : null}
        </div>
    }
}

export const ChatContainer = {
    mapDispatchToProps: {
        sendChatMessage
    },
    render({show, chat, is_tournament, sendChatMessage}) {
        return <ChatComponent chat={chat}
                              show={show}
                              is_tournament={is_tournament}
                              sendChatMessage={sendChatMessage}/>
    }
}
