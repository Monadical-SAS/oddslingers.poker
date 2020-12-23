import React from 'react'
import SimpleWebRTC from 'simplewebrtc'
import {reduxify} from '@/util/reduxify'

import Col from 'react-bootstrap/lib/Col'
import DropdownButton from 'react-bootstrap/lib/DropdownButton'
import MenuItem from 'react-bootstrap/lib/MenuItem'
import Button from 'react-bootstrap/lib/Button'
import Label from 'react-bootstrap/lib/Label'

import {Icon} from '@/components/icons'
import {tooltip} from '@/util/dom'
import {localStorageGet, localStorageSet} from '@/util/browser'
import {hashCode, generateUUID} from '@/util/javascript'

import {onSubmitAction} from '@/poker/reducers'
import {getGamestate} from '@/poker/selectors'


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

function getUsernameColor(username) {
    const username_hash = Math.abs(hashCode(username))
    return USERNAME_COLORS[username_hash % USERNAME_COLORS.length]
}

const ToggleSound = ({muted, onChange}) =>
    <Button style={{border: 0}} {...tooltip(muted ? 'Unmute mic' : 'Mute mic')} onClick={onChange}>
        <Icon name={`microphone${muted ? '-slash' : ''} toggle-sounds`}
              style={{color: muted ? 'red' : 'initial'}}/>
        {muted}
    </Button>

const TogglePause = ({paused, onChange}) =>
    <Button style={{border: 0}} {...tooltip(paused ? 'Start video' : 'Stop video')} onClick={onChange}>
        <Icon name={paused ? 'camera' : 'camera'}
              style={{color: paused ? 'red' : 'initial'}}/>
        {paused}
    </Button>


export class ToggleMuteRemote extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            muted: false
        }
    }
    onMuteRemote() {
        this.props.onMuteRemote(this.props.video, !this.state.muted)
        this.setState({
            ...this.state,
            muted: !this.state.muted
        })
    }
    render() {
        return <Icon name={`volume-${this.state.muted ? 'off' : 'up'} toggle-remote`}
                     style={{cursor: 'pointer'}}
                     onClick={() => this.onMuteRemote()}/>
    }
}


export class VideoStream extends React.Component {
    componentDidMount() {
        this.div.appendChild(this.props.video)
    }
    shouldComponentUpdate(nextProps) {
        if (nextProps.video   != this.props.video)  return true
        return false
    }
    render() {
        return <div ref={e => {this.div = e}}></div>
    }
}

export class VideoPanelContainer extends React.Component {
    constructor(props) {
        super(props)
        this.room_id = props.room_id || global.props.gamestate.table.id
        this.nick = props.nick || (global.user ? global.user.username : `anon-${generateUUID()}`)
        this.state = {
            mode: 'off',     // off | connecting | on
            details: '',
            theirs: {},
            local: 'off',
            added_peers: 0,
            people_online: 0,
            joined: true,
            show: true,
            muted: localStorageGet('mic-muted', false),
            paused: localStorageGet('video-paused', false),
        }
    }
    onStartVideoStream() {
        if (this.webrtc) this.webrtc.startLocalVideo()
        this.setState({
            ...this.state,
            local: 'on'
        })
    }
    onStopVideoStream() {
        if (this.webrtc) this.webrtc.stopLocalVideo()
        this.setState({
            ...this.state,
            local: 'off'
        })
    }
    onShowVideo() {
        this.setState({
            ...this.state,
            show: true,
        })
        if (!this.state.joined) {
            this.webrtc.joinRoom(this.room_id)
            this.props.onSubmitAction('NEW_PEER', {nick: this.nick})
        }
    }
    onCloseVideo() {
        if (this.state.local === 'on') this.onStopVideoStream()
        this.setState({
            ...this.state,
            show: false
        })
    }
    onAddVideo(peer, video) {
        this.setState({
            ...this.state,
            mode: 'on',
            theirs: {
                ...this.state.theirs,
                [`${peer.nick}-${peer.sid}`]: {
                    video,
                    speaking: false
                }
            }
        })
    }
    onRemoveVideo(peer) {
        let new_theirs = this.state.theirs
        delete new_theirs[`${peer.nick}-${peer.sid}`]
        this.setState({
            ...this.state,
            theirs: {
                ...new_theirs
            }
        })
    }
    onRemoteSpeaking(peer, volume) {
        let new_theirs = this.state.theirs
        const obj_key = `${peer.nick}-${peer.sid}`
        if (new_theirs[obj_key]) {
            if (volume !== null && volume > -40) {
                new_theirs[obj_key].speaking = true
                this.setState({
                    ...this.state,
                    theirs: {
                        ...new_theirs,
                    }
                })
            } else {
                new_theirs[obj_key].speaking = false
                this.setState({
                    ...this.state,
                    theirs: {
                        ...new_theirs,
                    }
                })
            }
        }
    }
    onMuteRemote(video, muted){
        if (muted) {
            video.volume = 0
        } else {
            video.volume = 1
        }
    }
    componentWillReceiveProps(nextProps) {
        const new_peer = nextProps.added_peers != this.state.added_peers
        const is_me = nextProps.nick === this.nick
        if (new_peer && !is_me) {
            if (this.webrtc){
                this.webrtc.joinRoom(this.room_id)
            }
        }
        this.setState({
            ...this.state,
            added_peers: nextProps.added_peers,
            people_online: nextProps.people_online
        })
    }
    shouldComponentUpdate(nextProps, nextState) {
        if (nextState.theirs  != this.state.theirs)  return true
        if (nextState.mode    != this.state.mode)    return true
        if (nextState.details != this.state.details) return true
        if (nextState.muted   != this.state.muted)   return true
        if (nextState.paused  != this.state.paused)  return true
        if (nextState.local   != this.state.local)  return true
        if (nextState.show    != this.state.show)  return true
        if (nextProps.people_online   != this.props.people_online)  return true
        if (nextProps.username_acting   != this.props.username_acting)  return true
        return false
    }
    componentWillUnmount() {
        if (this.webrtc) {
            this.webrtc.leaveRoom()
            this.webrtc.disconnect()
            this.webrtc.webrtc.stop()
        }
    }
    componentDidMount() {
        this.setState({
            ...this.state,
            mode: 'connecting',
            details: '',
            theirs: {},
        })
        try {
            this.webrtc = new SimpleWebRTC({
                // the id/element dom element that will hold "our" video
                localVideoEl: 'video-ours',
                // the id/element dom element that will hold remote videos
                remoteVideosEl: 'video-theirs',
                // immediately ask for camera access
                autoRequestMedia: false,
                detectSpeakingEvents: true,
                url: window.location.protocol + '//' + window.location.hostname,
                nick: this.nick,
            })
        } catch(e) {
            alert('Due to technical limitations, video streaming is not available for this device, update your browser or try on a different device.')
            this.onStopVideoStream()
            return
        }
        global.page.webrtc = this.webrtc
        this.webrtc.on('iceFailed', () => {
            this.setState({
                ...this.state,
                mode: 'off',
                details: 'Failed to start streaming...'
            })
        })
        this.webrtc.on('readyToCall', () => {
            if (this.state.muted) this.webrtc.mute()
            if (this.state.paused) this.webrtc.pauseVideo()
            this.props.onSubmitAction('NEW_PEER', {nick: this.nick})
            if (!this.state.joined){
                this.webrtc.joinRoom(this.room_id)
                this.setState({
                    ...this.state,
                    joined: true
                })
            }
        })

        this.webrtc.on('videoAdded', (video, peer) => {
            if (!peer || !peer.nick || peer.nick == this.nick) return
            console.log(`[+] Video added: ${peer.nick}`, peer)

            this.onAddVideo(peer, video)

            if (peer && peer.pc) {
                peer.pc.on('iceConnectionStateChange', () => {
                    switch (peer.pc.iceConnectionState) {
                    case 'checking':
                        this.setState({
                            ...this.state,
                            mode: 'connecting',
                            details: 'Connecting to peer...',
                        })
                        break;
                    case 'connected':
                    case 'completed':
                        this.setState({
                            ...this.state,
                            mode: 'on',
                            details: 'Connection established.',
                        })
                        break;
                    case 'disconnected':
                        this.setState({
                            ...this.state,
                            mode: 'off',
                            details: 'Disconnected.',
                        })
                        this.onRemoveVideo(peer)
                        break;
                    case 'failed':
                        break;
                    case 'closed':
                        this.setState({
                            ...this.state,
                            mode: 'off',
                            details: 'Connection closed.',
                        })
                        this.onRemoveVideo(peer)
                        break;
                    }
                })
            }
        })
        this.webrtc.on('remoteVolumeChange', (peer, volume) => {
            this.onRemoteSpeaking(peer, volume)
        })
        if (this.state.muted) this.webrtc.mute()
        if (this.state.paused) this.webrtc.pauseVideo()
        this.webrtc.joinRoom(this.room_id)
        this.props.onSubmitAction('NEW_PEER', {nick: this.nick})
    }
    onTogglePause() {
        const new_state = !this.state.paused
        if (new_state)
            this.webrtc.pauseVideo()
        else
            this.webrtc.resumeVideo()
        console.log(new_state ? 'paused!' : 'unpaused!')

        this.setState({...this.state, paused: new_state})
    }
    onToggleMute() {
        const new_state = !this.state.muted
        localStorageSet('mic-muted', new_state)
        if (new_state)
            this.webrtc.mute()
        else
            this.webrtc.unmute()
        console.log(new_state ? 'muted!' : 'unmuted!')

        this.setState({...this.state, muted: new_state})
    }
    render() {
        const status_bar = <div className="video-status">
            <TogglePause paused={this.state.paused} onChange={::this.onTogglePause}/>
            &nbsp; &nbsp;

            <ToggleSound muted={this.state.muted} onChange={::this.onToggleMute}/>
            &nbsp; &nbsp;
            <DropdownButton id='video-options' title="Stream options">
                {!this.state.show ?
                    <MenuItem key="view-stream" onClick={::this.onShowVideo}>
                        View Stream
                    </MenuItem> : null}
                {this.state.show ?
                    <MenuItem key="close-stream" onClick={::this.onCloseVideo}>
                        Close Stream
                    </MenuItem> : null}
                {this.state.local === 'off' ?
                    <MenuItem key="start-stream" onClick={::this.onStartVideoStream}>
                        Start Local Stream
                    </MenuItem> : null}
                {this.state.local === 'on' ?
                    <MenuItem key="stop-stream" onClick={::this.onStopVideoStream}>
                        Stop Local Stream
                    </MenuItem> : null}
            </DropdownButton>
            &nbsp; &nbsp; &nbsp; &nbsp;
        </div>

        // decide how wide to make each video based on the total number of
        // streams we need to display
        const min_width = 6
        const num_streams = 1 + Object.keys(this.state.theirs).length
        let width_fraction = 12 / num_streams
        if (width_fraction < min_width)
            width_fraction = min_width

        return <div className="video-panel">
            <div>
                <Col sm={12}>
                    <Label bsStyle="success">[{this.state.people_online} PPL ONLINE]</Label>
                </Col>
                <Col sm={12}>
                    {status_bar}
                </Col>
            </div>
            {this.state.show && <div>
                {Object.keys(this.state.theirs).map((username, i) =>
                    <Col sm={this.props.username_acting === username ? 12 : width_fraction} key={username}>
                        <VideoStream key={`video-rem-${i}`} video={this.state.theirs[username].video}/>
                        <div className={`speaking ${this.state.theirs[username].speaking}`}></div>
                        <ToggleMuteRemote video={this.state.theirs[username].video}
                                          onMuteRemote={::this.onMuteRemote}/>
                        <small style={{color: getUsernameColor(username)}}>
                            {username.slice(0, 15)}
                        </small>
                    </Col>)}

                <Col sm={width_fraction}>
                    <video id="video-ours" className={`${this.state.local}`}/>
                    <small><br/>You</small>
                </Col>
            </div>}
        </div>
    }
}


export const VideoPanel = reduxify({
    mapStateToProps: (state) => {
        const {players, table} = getGamestate(state)
        const player_acting = players[table.to_act_id]
        const username_acting = player_acting ? player_acting.username : ''
        return {
            added_peers: state.video.added_peers,
            people_online: state.video.people_online,
            nick: state.video.nick,
            username_acting
        }
    },
    mapDispatchToProps: {
        onSubmitAction
    },
    render: (props) => {
        return <VideoPanelContainer added_peers={props.added_peers}
                                    people_online={props.people_online}
                                    nick={props.nick}
                                    username_acting={props.username_acting}
                                    onSubmitAction={props.onSubmitAction} />
    }
})
