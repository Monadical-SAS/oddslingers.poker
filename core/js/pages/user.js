import React from 'react'
import ReactDOM from 'react-dom'
import classNames from 'classnames'

import format from 'date-fns/format'
import addSeconds from 'date-fns/add_seconds'
import differenceInHours from 'date-fns/difference_in_hours'
import differenceInMinutes from 'date-fns/difference_in_minutes'
import differenceInSeconds from 'date-fns/difference_in_seconds'
import distanceInWordsToNow from 'date-fns/distance_in_words_to_now'

import Row from 'react-bootstrap/lib/Row'
import Col from 'react-bootstrap/lib/Col'
import Alert from 'react-bootstrap/lib/Alert'
import Modal from 'react-bootstrap/lib/Modal'
import Button from 'react-bootstrap/lib/Button'
import Checkbox from 'react-bootstrap/lib/Checkbox'
import FormControl from 'react-bootstrap/lib/FormControl'
import ControlLabel from 'react-bootstrap/lib/ControlLabel'
import FormGroup from 'react-bootstrap/lib/FormGroup'
import HelpBlock from 'react-bootstrap/lib/HelpBlock'
import Tabs from 'react-bootstrap/lib/Tabs'
import Tab from 'react-bootstrap/lib/Tab'

import {Icon} from '@/components/icons'
import {Notification} from '@/notifications/components'
import {DealerIcon} from '@/poker/components/board'

import {tooltip, preventNonNumbers} from '@/util/dom'
import {TAKE_SEAT_BEHAVIOURS} from '@/constants'
import {range, chipAmtStr} from '@/util/javascript'
import {CSRFToken} from '@/util/react'
import {getUserBalance} from '@/util/browser'



const onBuyChips = () => {
    const quantity = 1000
    $.post(global.location.pathname, {type: 'BUY_CHIPS', quantity}, (resp) => {
        if (resp.success) {
            $('#user-balance').html(Number(resp.balance).toLocaleString() + ' Chips')
            $('.mini-stacks').css('opacity', '1')
            global.location.reload()
        } else {
            alert(`Could not buy chips: ${resp.details}`)
            global.location.reload()
        }
    })
}

const validateUsername = (to_user) => {
    if (to_user.length == 0) return 'warning'
    return 'success'
}
const validateAmount = (amt, max_amount) => {
    if (amt.length == 0) return 'warning'
    if (isNaN(Number(amt))) return 'error'
    if (Number(amt) % 1 !== 0) return 'error'
    if (Number(amt) <= 0 || Number(amt) > Number(max_amount)) return 'error'
    return 'success'
}

class TimedChipsButton extends React.Component {
    constructor(props) {
        super(props)
        this.end_time = addSeconds(Date.now(), this.props.wait_to_deposit)
    }
    componentDidMount() {
        if (Number(this.props.wait_to_deposit) > 0) {
            global.setInterval(::this.forceUpdate, 1000)
        }
    }
    render() {
        const now = Date.now()
        const remaining = {
            as_words: distanceInWordsToNow(this.end_time),
            hours: differenceInHours(this.end_time, now),
            minutes: differenceInMinutes(this.end_time, now) % 60,
            seconds: differenceInSeconds(this.end_time, now) % 60,
        }
        const must_wait = now < this.end_time
        return <div>
            <Button bsStyle="success"
                    onClick={onBuyChips}
                    title={`Free chips can be collected in ${remaining.as_words}.`}
                    disabled={must_wait}>
                🎉&nbsp; Collect {
                    Number(this.props.amount_of_chips).toLocaleString()
                } free Chips! &nbsp;🎉
            </Button><br/>
            {must_wait &&
                <h4>
                    <Icon name="clock-o"/>&nbsp;
                    {remaining.hours > 0 ? `${remaining.hours}:` : ''}
                    {remaining.minutes}:
                    {remaining.seconds < 10 ? `0${remaining.seconds}` : remaining.seconds} remaining!
                </h4>
            }
        </div>
    }
}

class ProfilePictureSelector extends React.Component {
    constructor(props) {
        super(props)
        this.state = {show: false}
    }
    onCloseModal() {
        this.setState({show: false})
    }
    onOpenModal() {
        this.setState({show: true})
    }
    onChoosePicture(picture) {
        $.ajax({
            url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
            type: 'PATCH',
            data: {'picture': picture},
            success: () => {document.location.reload()},
        })
    }
    render() {
        const {profile_pictures} = this.props
        return (
            <div className="picture-action">
                <span style={{cursor: 'pointer'}} onClick={::this.onOpenModal}>
                    Edit profile picture &nbsp;
                    <i className="edit-icon">
                        <Icon name="camera"/>
                    </i>
                </span>
                {this.state.show &&
                <Modal bsSize="large" aria-labelledby="contained-modal-title-lg" id="picture-picker"
                        show={this.state.show}
                        onHide={::this.onCloseModal}>
                    <Modal.Header closeButton>
                        <Modal.Title id="contained-modal-title-lg" style={{fontFamily:'Bungee'}}>click to choose your profile picture</Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {profile_pictures.map(picture =>
                            <img key={picture}
                                 className="profile-choice"
                                 src={`/static/images/profile_pictures/${picture}`}
                                 onClick={this.onChoosePicture.bind(this, picture)}/>
                        )}
                    </Modal.Body>
                </Modal>}
            </div>
        )
    }
}

class ChipTransfer extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            show:false,
            to_user:props.to_user || '',
            amount:'',
            max_amount:props.max_amount,
            resp_message:'',
            waiting_confirmation:false,
            lock_dst: Boolean(props.to_user),
            can_send: global.user && global.user.has_verified_email,
        }
    }
    onCloseModal() {
        this.setState({
            show: false,
            resp_message: '',
        })
        if (this.state.can_send && !this.state.lock_dst)
            global.location.reload()
    }
    onOpenModal() {
        this.setState({show: true})
    }
    onSendChips() {
        const {to_user, amount, can_send} = this.state
        if (!can_send) return
        if (to_user.length == 0 || amount.length == 0){
            this.setState({resp_message:'All fields must be filled out'})
            if (to_user.length == 0) {
                $('#to_user').focus()
            } else {
                $('#amount').focus()
            }
            return
        }
        if (to_user.includes("@") && !this.state.waiting_confirmation){
            this.setState({
                waiting_confirmation:true,
                resp_message:[
                    <b key="b_key">Are you sure you want to send chips to an email address?.</b>,
                    <br key="br_key"/>,
                    "Chips will no longer be available for you",
                ]
            })
            return
        }
        this.setState({
            resp_message:"Sending...",
            waiting_confirmation:false,
        })
        $.post(global.location.pathname, {type:'SEND_CHIPS', to_user, amount}, (resp) => {
            if (resp.success) {
                const new_balance = Number(resp.balance).toLocaleString()
                this.setState({
                    max_amount:resp.balance,
                    to_user:this.state.lock_dst ? this.state.to_user : '',
                    amount:'',
                    resp_message:[
                        `Sent ㆔${resp.quantity} chips to ${this.state.to_user}.`,
                        <br key="br_key"/>,
                        `Your new balance: ${new_balance}`
                    ]
                }, () => {
                    if (this.state.lock_dst){
                        $('#amount').focus()
                    } else {
                        $('#to_user').focus()
                    }
                })
            } else {
                this.setState({resp_message:[
                    "Could not send chips:",
                    <br key="br_key"/>,
                    `${resp.details}`
                ]})
            }
        })
    }
    setUsername(e){
        this.setState({to_user:e.target.value})
    }
    setAmount(e){
        this.setState({amount:e.target.value})
    }
    handleKeyPress(e){
        if(e.key === "Enter"){
            this.onSendChips()
        }
    }
    render() {
        const max_amount = Number(this.state.max_amount).toLocaleString()
        const foot_button_style = this.state.waiting_confirmation ?
                                        {float:'left'} : null
        const foot_button_label = this.state.waiting_confirmation ?
                                        'I understand' : 'Send'
        return (
            <span>
                <Button bsStyle="primary"
                        onClick={::this.onOpenModal}
                        title={`Send chips to ${this.state.lock_dst ? this.state.to_user : 'a friend'}`}>
                    Send chips 💸
                </Button>
                {this.state.show &&
                <Modal bsSize="small" aria-labelledby="contained-modal-title-lg"
                        show={this.state.show}
                        onHide={::this.onCloseModal}>
                    <Modal.Header closeButton>
                        <Modal.Title id="contained-modal-title-lg" style={{fontFamily:'Bungee'}}>
                            Send chips
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                    {this.state.can_send ?
                        <span><center>
                        <FormGroup validationState={validateUsername(this.state.to_user)}>
                            <FormControl id="to_user"
                                         type="text"
                                         placeholder={"Username or email"}
                                         autoFocus={!this.state.lock_dst}
                                         value={this.state.to_user}
                                         onKeyPress={::this.handleKeyPress}
                                         onChange={::this.setUsername}
                                         disabled={this.state.lock_dst}/>
                        </FormGroup>
                        <FormGroup
                            validationState={validateAmount(this.state.amount, this.props.max_amount)}>
                            <FormControl id="amount" type="number" min="0"
                                         placeholder="Amount" autoComplete="off"
                                         autoFocus={this.state.lock_dst}
                                         value={this.state.amount}
                                         onChange={::this.setAmount}
                                         onKeyPress={::this.handleKeyPress}
                                         onKeyDown={preventNonNumbers}/>
                            <HelpBlock>{`(max ㆔${max_amount})`}</HelpBlock>
                        </FormGroup></center>
                        <div>{this.state.resp_message}</div>
                        </span>
                        :
                        <span>
                            Please <a href="/accounts/email/" target="_blank">
                            verify your email address
                            </a> in order to be able to send chips.
                        </span>
                    }
                    </Modal.Body>
                    {this.state.can_send &&
                    <Modal.Footer>
                        <Button bsStyle="success"
                                onClick={::this.onSendChips}
                                style={foot_button_style}>
                            {foot_button_label}
                        </Button>
                    </Modal.Footer>}
                </Modal>}
            </span>
        )
    }
}

const getTransferDescription = (transfer) => {
    const create_href = ({path, label}) => <a href={`${global.location.origin}${path}`}
                                              target="_blank" key="a_key">{label}</a>
    const the_link = transfer.path == null ? transfer.label : create_href(transfer)
    if (transfer.name == 'user') {
        if (transfer.type == 'credit') {
            return [the_link, ` sent you chips`]
        } else {
            return [`Sent chips to `, the_link]
        }
    } else if (transfer.name == 'poker table') {
        if (transfer.type == 'credit') {
            return [`Cashed out of `, the_link]
        } else {
            return [`Bought into `, the_link]
        }
    } else if (transfer.name == 'freezeout') {
        if (transfer.type == 'credit') {
            if (transfer.notes.includes("withdrawal"))
                return [`Withdrew from tournament `, the_link]
            return [`Won in tournament `, the_link]
        } else {
            return [`Bought into `, the_link]
        }
    } else if (transfer.name == 'cashier') {
        if (transfer.type == 'credit') {
            try {
                const json_notes = JSON.parse(transfer.notes)
                return json_notes.src_username == transfer.label ?
                       [`Chips claimed from `, the_link, `'s email invitation`]
                     : [transfer.notes]
            } catch (e) {
                return [transfer.notes]
            }
        } else {
            try {
                const json_notes = JSON.parse(transfer.notes)
                const mailto_href = <a href={`mailto:${json_notes.dst_email}`}
                                    target="_blank" key="a_key">{json_notes.dst_email}</a>
                return json_notes.claimed ?
                    [`Sent chips by email to `, the_link]
                  : [`Chips with invitation sent to `, mailto_href]
            } catch (e) {
                return [`Paid to the OddSlingers Cashier`]
            }
        }
    } else {
        if (transfer.type == 'credit') {
            return [`Collected from ${transfer.label}`]
        } else {
            return [`Sent to ${transfer.label}`]
        }
    }
}

class TransferHistory extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            show: false,
            fetching: false,
            error: false,
            transfers: undefined,
        }
    }
    onCloseModal() {
        this.setState({
            show: false,
            fetching: false,
            error: false,
            transfers: undefined,
        })
    }
    onOpenModal() {
        this.setState({
            show: true,
            fetching: true,
        })
        $.post(global.location.pathname, {type:'TRANSFER_HISTORY'}, (resp) => {
            if (resp.success) {
                this.setState({
                    fetching: false,
                    error: false,
                    transfers: resp.transfers,
                })
            } else {
                this.setState({
                    fetching: false,
                    error: true,
                    transfers: undefined,
                })
            }
        })
    }
    render() {
        return (
            <span>
                <Button bsStyle="default" onClick={::this.onOpenModal}>
                    Transaction History
                </Button>
                {this.state.show &&
                <Modal aria-labelledby="contained-modal-title-lg"
                        show={this.state.show}
                        onHide={::this.onCloseModal}>
                    <Modal.Header closeButton>
                        <Modal.Title id="contained-modal-title-lg" style={{fontFamily:'Bungee'}}>
                            Transaction History
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <center>
                            {this.state.fetching &&
                                <Icon name="spinner fa-spin fa-2x"/>}
                            {this.state.error &&
                                <span>Oops. Something went terrible wrong.</span>}
                            {this.state.transfers &&
                                <span>
                                <Row key="header" style={{textAlign: 'left', fontWeight: 800}}>
                                    <Col xs={3}>Time</Col>
                                    <Col xs={2}>Amount</Col>
                                    <Col xs={7}>Description</Col>
                                    <br/><hr/>
                                </Row>
                                <div style={{overflowY: 'auto', maxHeight: 400}}>
                                <div style={{overflowX: 'hidden'}}>
                                {this.state.transfers.map((transfer, idx) => {
                                    const the_sign = transfer.type == 'credit' ? '+' : '-'
                                    return <span key={idx}>
                                        <Row style={{textAlign: 'left'}}>
                                            <Col xs={3}>
                                                {format(transfer.timestamp, 'MMM Do, HH:mm')}
                                            </Col>
                                            <Col xs={2}>
                                                <span className={`tr-hi-${transfer.type}`}>
                                                    {the_sign}{parseInt(transfer.amt).toLocaleString()}
                                                </span>
                                            </Col>
                                            <Col xs={7}>
                                                {getTransferDescription(transfer)}
                                            </Col>
                                        </Row>
                                        <hr/>
                                    </span>
                                })}
                                </div>
                                </div>
                                </span>
                            }
                        </center>
                    </Modal.Body>
                </Modal>}
            </span>
        )
    }
}

class SessionList extends React.Component {
    constructor(props) {
        super(props)
        this.state = {sessions: null, session_msg: null}
    }
    onGetSessions() {
        $.get('/api/user/sessions/', (response) => {
            if (response.success) {
                this.setState({session_msg: null, sessions: response.sessions})
            } else {
                this.setState({session_msg: 'Failed to fetch sessions...'})
            }
        })
        this.setState({session_msg: 'Loading sessions...'})
        return true
    }
    onHideSessions() {
        this.setState({sessions: []})
    }
    onEndSession(session_id) {
        $.ajax({
            url: `/api/user/sessions/?session_id=${encodeURIComponent(session_id)}`,
            type: 'DELETE',
            success: function() {
                global.location = '/accounts/login/?next=/user/'
            }
        })
        this.setState({session_msg: 'Ending session...'})
        return true
    }
    render() {
        const sessions_msg = this.state.session_msg || ''
        const sessions_list = (this.state.sessions || []).map(sesh =>
            <div key={sesh.session_id}>
                Device: <span title={sesh.user_agent}>{sesh.device}</span><br/>
                Last seen: {format(sesh.last_activity, 'MMM Do YYYY h:mm:ss a')}<br/>
                Location: {sesh.location || 'unknown location'}<br/>
                IP: {sesh.ip}<br/>
                <a href="#" onClick={() => this.onEndSession(sesh.session_id)} style={{color: "red"}}>
                    {sesh.current ?
                        'Log me out'
                      : 'End session'}
                </a>
            </div>)

        return <div>
            <a href="#" onClick={() => this.onEndSession('all')}>Log out from all devices</a><br/>
            <a href="#" onClick={sessions_list.length ? (() => this.onHideSessions()) : (() => this.onGetSessions())}>{sessions_list.length ? 'Hide' : 'View'} log-in activity</a>
            <div id="user-sessions">
                {sessions_msg}
                {sessions_list}
            </div>
            <div>Last Login:<br/>{format(this.props.user.last_login, 'MMM Do YYYY h:mm:ss a')}</div>
        </div>
    }
}

class PreferencesPanel extends React.Component {
    handleDataChange(e, source, checkbox=false, on_success=null) {
        const value = checkbox ? e.target.checked : e.target.value
        this.setState({ [source]: value })
        if (source === 'light_theme') {
            $.ajax({
                url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
                type: 'PATCH',
                data: JSON.stringify({ [source]: value }),
                success: () => { document.location.reload() }
            })
        } else {
            $.ajax({
                url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
                type: 'PATCH',
                data: JSON.stringify({ [source]: value }),
                success: on_success
            })
        }
    }
}

class AccountPreferences extends PreferencesPanel {
    constructor(props) {
        super(props)

        this.state = {
            light_theme: global.user.light_theme,
        }
    }
    render() {
        const {profile_user} = this.props
        return <span>
            <br/><br className="hide-me"/>
            <center>
                <b>{profile_user.username}</b><br/>
                <b>{profile_user.email || 'No email set'}</b><br/>
                <a href="/accounts/email/">Change email</a>
                <br/>
                <a href="/accounts/password/change/">Change password</a>
                <br/><br className="hide-me"/>
                <Checkbox defaultChecked={this.state.light_theme}
                          onChange={(e) => this.handleDataChange(e, 'light_theme', true)}>
                    Light theme
                </Checkbox>
                
                <br className="hide-me"/>
                <hr/>
                <br className="hide-me"/>

                <SessionList user={profile_user}/>
                
                <br className="hide-me"/>
                <hr/>
                <a href="/support">View support requests</a>
                <br/>
                <small>
                    <a href="/support?message=Account%20Data%20Download">
                        Download Account Data &nbsp;
                        <Icon name="download"/>
                    </a><br/>
                    <a href="/support?message=Account%20Deletion">
                        Delete Account &nbsp;
                        <Icon name="trash"/>
                    </a>
                </small>
                <hr/>
                <small><a href="/support">Contact support</a> for questions about your account.</small>
            </center>
        </span>
    }
}

class GamePreferences extends PreferencesPanel {
    constructor(props) {
        super(props)

        this.state = {
            muted_sounds: global.user.muted_sounds,
            auto_rebuy_in_bbs: global.user.auto_rebuy_in_bbs,
            rebuy_validation_state: null,
            four_color_deck: global.user.four_color_deck,
            sit_behaviour: global.user.sit_behaviour,
            keyboard_shortcuts: global.user.keyboard_shortcuts,
            muck_after_winning: global.user.muck_after_winning,
        }
    }

    handleRebuy(e) {
        const value = e.target.value
        //console.log(value, value < 50, value > 200, value != 0, (value < 50 || value > 200) && value != 0)
        if ((value < 50 || value > 200) && (value != 0 || value === '')) {
            this.setState({rebuy_validation_state: 'error'})
        } else {
            this.setState({ rebuy_validation_state: null })
            this.handleDataChange(e, 'auto_rebuy_in_bbs')
        }
    }

    render() {
        return <span>
            <br className="hide-me"/><br className="hide-me"/>
            <Checkbox defaultChecked={this.state.four_color_deck}
                      onChange={(e) => this.handleDataChange(e, 'four_color_deck', true)}>
                4-color deck
            </Checkbox>
            <Checkbox defaultChecked={this.state.muted_sounds}
                      onChange={(e) => this.handleDataChange(e, 'muted_sounds', true)}>
                Mute sounds
            </Checkbox>
            <Checkbox defaultChecked={this.state.muck_after_winning}
                      onChange={(e) => this.handleDataChange(e, 'muck_after_winning', true)}>
                Muck after winning
            </Checkbox>
            <Checkbox defaultChecked={this.state.keyboard_shortcuts}
                      onChange={(e) => this.handleDataChange(e, 'keyboard_shortcuts', true)}>
                Use keyboard shortcuts&nbsp;<Icon name="question-circle"
                                                  data-html="true"
                                                  {...tooltip(`<div align='left'>
                                                                 Use your keyboard to play:</br>
                                                                 &nbsp;&nbsp;F for fold</br>
                                                                 &nbsp;&nbsp;C for Call/Check</br>
                                                                 &nbsp;&nbsp;B/R for bet or raise to</br>
                                                                 &nbsp;&nbsp;A for all-in</div>`, 'top')}/>
            </Checkbox>
            <FormGroup className="one-line"
                       validationState={this.state.rebuy_validation_state}>
                <ControlLabel>
                    Auto rebuy in bbs <Icon name="question-circle"
                                            {...tooltip('If your stack falls below this many bbs, you will automatically rebuy to make up the difference.', 'top')}/>
                </ControlLabel>
                <FormControl type="number"
                             defaultValue={this.state.auto_rebuy_in_bbs}
                             onChange={::this.handleRebuy}
                             onKeyDown={preventNonNumbers}
                             style={{width: 155}}/>
                {this.state.rebuy_validation_state === 'error' &&
                    <HelpBlock>
                        This value should be between 50 and 200 or should be 0 to disable auto-rebuy.
                    </HelpBlock>}
            </FormGroup>
            <FormGroup className="one-line">
                <ControlLabel>
                    Sit in behaviour <Icon name="question-circle"
                                           {...tooltip('Default sit-in behaviour when you take a seat at a table.', 'top')}/>
                </ControlLabel>
                <FormControl componentClass="select"
                             defaultValue={this.state.sit_behaviour}
                             onChange={(e) => this.handleDataChange(e, 'sit_behaviour')}>
                    {Object.keys(TAKE_SEAT_BEHAVIOURS).map(bhv =>
                        <option key={bhv} value={bhv}>{TAKE_SEAT_BEHAVIOURS[bhv]}</option>)}
                </FormControl>
            </FormGroup>
        </span>
    }
}

class ChatPreferences extends GamePreferences {
    constructor(props) {
        super(props)

        this.state = {
            show_dealer_msgs: global.user.show_dealer_msgs,
            show_win_msgs: global.user.show_win_msgs,
            show_chat_msgs: global.user.show_chat_msgs,
            show_spectator_msgs: global.user.show_spectator_msgs,
            show_chat_bubbles: global.user.show_chat_bubbles,
            show_playbyplay: global.user.show_playbyplay,
        }
    }

    render() {
        return <span>
            <br className="hide-me"/><br className="hide-me"/>
            <Checkbox defaultChecked={this.state.show_playbyplay}
                      onChange={(e) => this.handleDataChange(e, 'show_playbyplay', true)}>
                Show Play-By-Play panel
            </Checkbox>
            <Checkbox defaultChecked={this.state.show_dealer_msgs}
                      onChange={(e) => this.handleDataChange(e, 'show_dealer_msgs', true)}>
                Show dealer messages
            </Checkbox>
            <Checkbox defaultChecked={this.state.show_win_msgs}
                      onChange={(e) => this.handleDataChange(e, 'show_win_msgs', true)}>
                Show win messages
            </Checkbox>
            <Checkbox defaultChecked={this.state.show_chat_msgs}
                      onChange={(e) => this.handleDataChange(e, 'show_chat_msgs', true)}>
                Show player messages
            </Checkbox>
            <Checkbox defaultChecked={this.state.show_spectator_msgs}
                      onChange={(e) => this.handleDataChange(e, 'show_spectator_msgs', true)}>
                Show spectator messages
            </Checkbox>
            <Checkbox defaultChecked={this.state.show_chat_bubbles}
                      onChange={(e) => this.handleDataChange(e, 'show_chat_bubbles', true)}>
                Show chat bubbles on table
            </Checkbox>
        </span>
    }
}

class BioPreference extends PreferencesPanel {
    constructor(props){
        super(props)
        this.state = {
            show_textarea: false,
            request_sent: false,
            status: "",
            bio: props.user.bio,
            new_bio: "",
        }
    }
    onEditBio(){
        if(!this.props.user.is_me) return
        this.setState(
            {show_textarea: !this.state.show_textarea},
            () => $('#bio-edit').focus()
        )
    }
    handleKeyPress(e){
        if (this.state.request_sent) return
        switch (e.keyCode) {
            case 13: {
                this.handleDataChange(e, 'bio', false, () => {
                    this.setState({
                        request_sent: false,
                        status: "",
                        bio: this.state.new_bio,
                        new_bio: "",
                    })
                })
                this.setState({
                    request_sent: true,
                    status: 'Saving...',
                    show_textarea: false,
                })
                break
            }
            case 27: {
                this.setState({show_textarea: false})
                break
            }
        }
    }
    setInputText(e){
        this.setState({new_bio: e.target.value})
    }
    render(){
        const profile_user = this.props.user

        if (profile_user.is_robot) {
            return (
                <div className="profile-bio">
                    <p>{profile_user.bio}</p>
                    <div className="bot-personality">
                        <p className="personality-title">Preflop Playstyle:</p>
                        <p className="personality-desc">{profile_user.personality.preflop}</p>
                        <p className="personality-title">General Playstyle:</p>
                        <p className="personality-desc">{profile_user.personality.postflop}</p>
                    </div>
                </div>
            )
        }

        return (
            <div className="profile-bio">
                <span>{this.state.status}</span>
                {this.state.show_textarea ?
                    <textarea type="text" id="bio-edit"
                              value={this.state.new_bio}
                              onChange={::this.setInputText}
                              onKeyDown={::this.handleKeyPress}
                              placeholder={this.state.bio || 'Type in your bio then press ENTER to save...'}/>
                    : <p>{this.state.bio}</p>
                }
                {profile_user.is_me &&
                    <i className="edit-icon" onClick={::this.onEditBio}>
                        Click to set bio &nbsp;
                        <Icon name="pencil"/>
                    </i>
                }
            </div>
        )
    }
}

class LevelProgressBars extends React.Component {
    constructor(props){
        super(props)
        const {
            earned_chips,
            cashtables_level,
            levels_constants
        } = this.props.user
        const {
            cash_game_bbs,
            n_bb_to_next_level,
        } = levels_constants


        let perc_tables = 100
        if (cashtables_level != cash_game_bbs.slice(-1)[0]){ // not max level
            const next_bb = cash_game_bbs.find(bb => bb > cashtables_level)
            perc_tables = earned_chips * 100 / (n_bb_to_next_level * next_bb)
        }


        const perc_level = cash_game_bbs.indexOf(cashtables_level) * 100 / (cash_game_bbs.length - 1)
        const perc_global = perc_level + perc_tables / cash_game_bbs.length

        this.state = {
            show: false,
            fetching: false,
            error: false,
            badges_data: undefined,
            tables_data: undefined,
            tournaments_data: undefined,
            perc_tables,
            perc_global,
        }
    }
    componentDidMount(){
        const global_bar = document.getElementById('global-bar')
        const {perc_global} = this.state
        global_bar.style.width = `${Math.min(perc_global, 100)}%`
    }
    onShowModal(){
        this.setState({
            show: true,
            fetching: true,
        })
        $.post(global.location.pathname, {type:'LEVELS_PROGRESS'}, (resp) => {
            if (resp.success) {
                this.setState({
                    fetching: false,
                    error: false,
                    badges_data: resp.badges,
                    tables_data: resp.tables,
                    tournaments_data: resp.tournaments,
                })
            } else {
                this.setState({
                    fetching: false,
                    error: true,
                    badges_data: undefined,
                    tables_data: undefined,
                    tournaments_data: undefined,
                })
            }
        })
    }
    onCloseModal(){
        this.setState({
            show: false,
            fetching: false,
            error: false,
            badges_data: undefined,
            tables_data: undefined,
            tournaments_data: undefined,
        })
    }
    render(){
        const {
            earned_chips,
            cashtables_level,
            tournaments_level,
            levels_constants
        } = this.props.user
        const {
            cash_game_bbs,
            tourney_buyin_amts,
            n_bb_to_next_level,
        } = levels_constants
        const {perc_tables} = this.state

        const next_bb = cash_game_bbs.find(bb => bb > cashtables_level)
        const sb = next_bb / 2
        const next_tourney_buyin = tourney_buyin_amts.find(buyin => buyin > tournaments_level)
        const next_cashtables_goal = n_bb_to_next_level * next_bb
        const is_maxlevel_cashtables = cashtables_level >= cash_game_bbs.slice(-1)[0]
        const chips_remaining = Math.max(next_cashtables_goal - earned_chips, 0)

        return <span style={{fontSize: 16}}>
            <div style={{textAlign: 'center'}} onClick={::this.onShowModal}>
                <br/>
                <div id="level-container" className='profile-main-panel'>
                    <h3>Level</h3>
                    <h2>{cash_game_bbs.indexOf(cashtables_level) + 1}</h2>
                    <div id="global-bar-container">
                        {cash_game_bbs.map((_, i) => {
                            const offset = (78.7 - 21) * i / (cash_game_bbs.length - 1) + 21
                            return ![0, cash_game_bbs.length].includes(i) ?
                                    <span className="tick-mark"
                                         key={i}
                                         style={{left: `${offset}%`}}><b>{i == 12 ? '' : i+1}</b></span>
                                    : null
                        })}
                        <div id="global-bar"></div>
                    </div>
                    <b>Win ㆔{chipAmtStr(chips_remaining)} more to unlock Level {cash_game_bbs.indexOf(cashtables_level) + 2}!</b>
                    <br/><br/>
                    <i style={{fontSize: 16}}>
                        Play on tables up to ㆔{cashtables_level / 2}/{cashtables_level}<br/>
                        and tournaments up to ㆔{tournaments_level}<br/>
                        to earn chips and unlock harder games.
                    </i>
                    <br/>
                    <hr/>
                    {is_maxlevel_cashtables ?
                        'Congratulations! You have unlocked all table levels.'
                        : <b style={{fontSize:16}}>
                            You're {Math.trunc(perc_tables)}% of the way to unlocking Level {cash_game_bbs.indexOf(cashtables_level) + 2}.
                        </b>
                    }
                    <br/><br/>
                    <Button>
                        Details
                    </Button>
                    <br/><br/>
                </div>

            </div>

            {this.state.show &&
                <Modal aria-labelledby="contained-modal-title-lg"
                        show={this.state.show}
                        onHide={::this.onCloseModal}>
                    <Modal.Header closeButton>
                        <Modal.Title id="contained-modal-title-lg" style={{fontFamily:'Bungee'}}>
                            {this.props.user.username}: Level {cash_game_bbs.indexOf(cashtables_level) + 1}/13
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <center>
                            <img src={this.props.user.profile_image} className="profile-picture" style={{maxWidth: 200}}/><br/><br/>
                            <h2>{this.props.user.username}</h2>
                            <h3 {...tooltip(`Out of ${cash_game_bbs.length} levels total.`, 'top')}>
                                Level {cash_game_bbs.indexOf(cashtables_level) + 1}
                                <br/><br/>
                                <i style={{fontSize:18}}>
                                    {Math.trunc(perc_tables)}% of the way to Level {cash_game_bbs.indexOf(cashtables_level) + 2}
                                </i>
                            </h3>
                            <br/>
                            <small style={{fontSize:16}}>
                                You've earned ㆔{chipAmtStr(earned_chips)} of ㆔{chipAmtStr(next_cashtables_goal)} chips needed to unlock Level {cash_game_bbs.indexOf(cashtables_level) + 2}.
                            </small>
                            <hr/>
                        </center>
                        {this.state.badges_data &&
                            <span>
                                <Icon name="arrow-right" />&nbsp;&nbsp;
                                    ㆔{parseInt(this.state.badges_data).toLocaleString()} of those chips came from the OddSlingers cashier
                                <br/>
                            </span>
                        }
                        {this.state.tables_data &&
                            <span>
                            {Object.keys(this.state.tables_data).map(bb => {
                                const data = this.state.tables_data[bb]
                                const sb = data.sb
                                const label = data.earnings >= 0 ? 'won' : 'lost'
                                const hands = data.hands
                                return hands > 0 ?
                                    <span key={bb}>
                                        <Icon name="arrow-right" />&nbsp;&nbsp;
                                            {label} ㆔{Math.abs(data.earnings).toLocaleString()} at {sb}/{bb} tables over {hands} hands
                                        <br/>
                                    </span>
                                    : null
                            })}
                            </span>
                        }
                        {this.state.tournaments_data &&
                            <span>
                            {Object.keys(this.state.tournaments_data).map(buyin_amt => {
                                const data = this.state.tournaments_data[buyin_amt]
                                const label = data.earnings > 0 ? 'won' : 'lost'
                                return data.earnings != 0 ?
                                    <span key={buyin_amt}>
                                        <Icon name="arrow-right" />&nbsp;&nbsp;
                                            {label} ㆔{Math.abs(data.earnings)} at {chipAmtStr(buyin_amt)} tournaments
                                        <br/>
                                    </span>
                                    : null
                            })}
                            </span>
                        }
                        <center>
                            {this.state.fetching &&
                                <Icon name="spinner fa-spin fa-2x"/>}
                            {this.state.error &&
                                <span>Oops. Something went terribly wrong.</span>}
                            <hr/><br/>
                            <small style={{fontSize:18}}>
                                You can currently join tables with blinds up to ㆔{cashtables_level / 2}/{cashtables_level}<br/>
                                and tournaments with buyins up to ㆔{tournaments_level} (Level {cash_game_bbs.indexOf(cashtables_level) + 1}).
                            </small>
                            <br/><br/>
                            {is_maxlevel_cashtables ?
                                'Congratulations! You have unlocked all table levels.'
                                : <i style={{fontSize:16}}>
                                     Level {cash_game_bbs.indexOf(cashtables_level) + 2} unlocks tables
                                     with blinds up to ㆔{sb}/{next_bb}<br/>
                                     and tournaments with buyins up to ㆔{next_tourney_buyin}.
                                  </i>
                            }
                            <br/><br/>
                            <a href="/tables/">
                                <Button bsStyle="success" style={{fontSize: 18}}>
                                    Play ㆔{cashtables_level / 2}/{cashtables_level} games to win chips and unlock Level {cash_game_bbs.indexOf(cashtables_level) + 2}!
                                </Button>
                            </a>
                            <br/><br/>
                        </center>
                    </Modal.Body>
                </Modal>
            }
        </span>
    }
}

const isMe = (username) => username
    && global.user
    && username == global.user.username

const TableThumbnail = ({table}) => {

    return <a href={table.path} key={table.path} className="table-thumbnail-container">
        <Col sm={2}
            className={classNames('table-thumbnail')}>
            <h4>
                <b>
                    {table.name}
                </b>
            </h4>
            {table.variant}

            <div style={{ textAlign: 'center' }}>
                Blinds: {chipAmtStr(table.sb)}/{chipAmtStr(table.bb)}
                &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;
                Min Buyin: {chipAmtStr(table.min_buyin)}
                &nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;
                {table.stats &&
                    <span style={{ color: 'blue' }}
                        data-html="true"
                        {...tooltip(`Players per Flop Ratio: ${table.stats.players_per_flop_pct}</br>
                                       Average Pot: ${table.stats.avg_pot}</br>
                                       Hands per Hour: ${table.stats.hands_per_hour}`)}>
                        Stats
                    </span>}
            </div>

            <hr />
            <div className="players-list">
                {range(table.num_seats).map(position =>
                    table.players[position] === undefined ?
                        <Row className="player-row" key={position}>
                            <Col xs={2} style={{ textAlign: "left" }}>
                                {(table.btn_idx === position) && <DealerIcon/>}
                            </Col>
                            <Col xs={6} style={{ color: "grey", textAlign: "left" }}>(empty)</Col>
                            <Col xs={4}></Col>
                        </Row>
                        :
                        <Row className="player-row" key={position}>
                            <Col xs={6} style={{
                                textAlign: "left",
                                fontWeight: isMe(table.players[position].username) ?
                                    800 : "initial",
                            }}>
                                {table.players[position].username}
                            </Col>
                            <Col xs={4} style={{
                                textAlign: "right",
                                fontWeight: isMe(table.players[position].username) ?
                                    800 : "initial",
                            }}>
                                {chipAmtStr(table.players[position].stack)}
                            </Col>
                        </Row>

                )}
            </div>
            <br />
            <div id="table-info-wrapper" style={{ float: "bottom" }}>
                <div className="player-count">
                    <Icon name="users" title="Players" /> {Object.keys(table.players).length}/{table.num_seats}
                </div>
            </div>
        </Col>
    </a>
}


class CongratsModal extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            show: props.user.new_achievements != null
        }
        if (this.state.show)
            $('.page-userprofile').css('background-image', 'url("/static/images/confeti.gif")')
    }
    render() {
        const modalClose = () => {
            this.setState({show: false})
            $('.page-userprofile').css('background-image', '')
        }
        const new_achievements = this.props.user.new_achievements

        return this.state.show &&
            <Modal show={this.state.show}
                   onHide={modalClose}
                   className="congrats-modal"
                   size="lg">
                <Modal.Header closeButton>
                    <Modal.Title id="contained-modal-title-lg" style={{fontFamily:'Bungee'}}>
                        Recent achievements
                    </Modal.Title>
                </Modal.Header>
                <Modal.Body style={{backgroundImage: 'url("/static/images/confeti.gif'}}>
                    <h1><center>Congratulations</center></h1>
                    <hr/>
                    {new_achievements.levels &&
                        <span className={'congrats-span'}>
                            Now you can join:<br/>
                            {Object.keys(new_achievements.levels).map(lvl_type => {
                                const old_lvl = new_achievements.levels[lvl_type].old
                                const new_lvl = new_achievements.levels[lvl_type].new
                                const the_type = lvl_type.startsWith('cashtables') ? 'big blind' : 'buyin'
                                return new_lvl > old_lvl ?
                                    <span key={lvl_type} className={'congrats-span'}>
                                        <Icon name="star-o" />&nbsp;&nbsp;
                                            {lvl_type.replace('_level', '')} up to ㆔{chipAmtStr(new_lvl)} {the_type}
                                        <br/>
                                    </span>
                                    : null
                            })}
                        </span>
                    }
                    {new_achievements.badges &&
                        <span className={'congrats-span'}>
                            More badges for you:<br/>
                            {Object.keys(new_achievements.badges).map(badge_name =>
                                <span key={badge_name} className={'congrats-span'}>
                                    <Icon name="star-o" />&nbsp;&nbsp;
                                        {badge_name.replace('_', ' ')}: {new_achievements.badges[badge_name]}
                                    <br/>
                                </span>
                            )}
                        </span>
                    }
                </Modal.Body>
                <Modal.Footer>
                    <Button bsStyle="success" onClick={modalClose}>
                        Poker!
                    </Button>
                </Modal.Footer>
            </Modal>
    }
}


class UserProfile extends React.Component {
    constructor(props){
        super(props)
        this.state = {
            balance: null,
        }
    }
    componentDidMount(){
        getUserBalance((balance) => {
            this.setState({balance})
        })
    }
    render(){
        const {
            profile_user, tables, badges, leaderboard_badges,
            profile_pictures, wait_to_deposit
        } = this.props
        const missing_email = (profile_user.is_me && !profile_user.email)
        const show_sendchips_as_visitor = this.state.balance
                                      && !profile_user.is_me
                                      && !profile_user.is_robot

        return <div className="container user-page">
        {missing_email ?
            <Alert bsStyle="warning" className="missing-email-alert">
                You need to verify an email address in order to access your User Profile.

                <br/><br/>
                <a href="/accounts/email/" className="btn btn-default">
                    Set an email <Icon name="angle-double-right"/>
                </a>
            </Alert>
          : null}
        <CongratsModal user={profile_user}/>
        <Row className={missing_email ? "row-locked" : ''}>
            <Col lg={4} md={4} sm={12} className="profile-info">
                {profile_user.is_me ?
                    <div className="profile-main-panel">
                        <h4>Preferences</h4>
                        <br className="hide-me"/>
                        <Tabs defaultActiveKey={1} id="preferences-tabs">
                            <Tab eventKey={1} title="Account">
                                <AccountPreferences profile_user={profile_user}/>
                            </Tab>
                            <Tab eventKey={2} title="Poker">
                                <GamePreferences profile_user={profile_user}/>
                            </Tab>
                            <Tab eventKey={3} title="Chat">
                                <ChatPreferences profile_user={profile_user}/>
                            </Tab>
                        </Tabs>
                    </div>
                  : null}
            </Col>
            <Col lg={4} md={4} sm={12} className="center-panel">
                <div className="picture-container">
                    <img src={profile_user.profile_image} className="profile-picture"/>
                    {profile_user.is_me &&
                        <ProfilePictureSelector profile_pictures={profile_pictures}/>}
                </div>
                <h3 style={{textAlign: 'center'}}>
                    {profile_user.username} &nbsp;
                    {profile_user.is_robot &&
                        <Icon name='laptop' {...tooltip('AI Player', 'top')}/>
                    }
                    {profile_user.is_me &&
                        <i style={{color: 'dodgerblue'}}> (me)</i>}
                    {profile_user.is_staff &&
                        <i style={{color: 'red'}}> (staff)</i>}
                    <br/>
                </h3>
                <BioPreference user={profile_user}/>
                {show_sendchips_as_visitor &&
                    <div style={{textAlign: 'center'}}>
                        <ChipTransfer max_amount={this.state.balance}
                                      to_user={profile_user.username}/>
                    </div>
                }
                <br/><br/>
                {profile_user.is_me &&
                    <LevelProgressBars user={profile_user}/>}

                <br/><br/>
                <div className="center-bonus">
                      {/*<a href="https://discord.gg/USPweBy" className="cta-link btn btn-success" target="_blank" rel="noopener" {...tooltip('Open Discord community')}>
                            <Icon name="comments"/>&nbsp;
                            <i>Chat with {profile_user.username}</i>
                        </a>*/}
                    {global.user && global.user.is_staff &&
                        <div style={{border: '1px dashed red'}}>
                            Admin Actions
                            <br/>
                            <a href={`/admin/oddslingers/user/${profile_user.id}/change/`}
                               className="btn btn-warning btn-sm">
                                Edit User &nbsp;<Icon name="pencil"/>
                            </a>
                            &nbsp; &nbsp;
                            <form action={`/hijack/username/${profile_user.username}/`} method="post">
                                <CSRFToken/>
                                <Button type="submit" bsStyle="sm" bsStyle="danger">
                                    View site as {profile_user.username} &nbsp;<Icon name="search"/>
                                </Button>
                            </form>
                        </div>}
                </div>
            </Col>
            <Col lg={4} md={4} sm={12} className="profile-info">
                {profile_user.is_me ?
                    <div className="profile-main-panel">
                        <h4>Play-Chip Wallet</h4>
                        <br className="hide-me"/>
                        <Tabs defaultActiveKey={1} id="wallet-tabs">
                            <Tab eventKey={1} title="Current Season">
                                <div style={{textAlign: 'center'}}>
                                    <br className="hide-me"/>
                                    <h3>Your Total Balance<br/>
                                    ㆔<b id="user-balance">
                                        {(Number(profile_user.balance) + Number(profile_user.chips_in_play)).toLocaleString()} Chips
                                    </b>&nbsp;
                                    </h3>
                                    <br className="hide-me"/>
                                    <TimedChipsButton onBuyChips={onBuyChips}
                                                      wait_to_deposit={wait_to_deposit}
                                                      amount_of_chips={profile_user.bonus_constants.free_chips_bonus}/>
                                    {!profile_user.has_verified_email &&
                                        <small>
                                            <a href="/accounts/email/" target="_blank">
                                            Verify your email and get ㆔{
                                                Number(profile_user.bonus_constants.email_verified_bonus).toLocaleString()
                                            } chips
                                            </a>
                                        </small>
                                    }
                                    <br className="hide-me"/>
                                    <br className="hide-me"/>
                                    <div className="cashier-details">
                                        <Col xs={6}>
                                            Chips<br/>In play<br/>
                                            ㆔<span className='greendeets'> {Number(profile_user.chips_in_play).toLocaleString()}</span>
                                        </Col>
                                        <Col xs={6}>
                                            Chips<br/>Available<br/>
                                             ㆔<span className='greendeets'>{Number(profile_user.balance).toLocaleString()}</span>
                                        </Col>
                                    </div>
                                    <br/><br/><br/><br/>
                                    <br className="hide-me"/><br className="hide-me"/>
                                    <hr/>
                                    <ChipTransfer max_amount={profile_user.balance}/> &nbsp; &nbsp;
                                    <TransferHistory/>
                                    <hr/>
                                    <small>See our <a href="/faq">FAQ</a> for more info about play-chips.</small>
                                </div>
                            </Tab>

                            <Tab eventKey={2} title="Past Seasons">
                                <br/>
                                <h4>Your winnings for past seasons:</h4>

                                {Object.keys(profile_user.past_seasons).length ?
                                    <span>
                                    <br/>
                                    <Row key="header" style={{textAlign: 'center', fontWeight: 800}}>
                                        <Col xs={4}>Season end</Col>
                                        <Col xs={4}>Balance</Col>
                                        <Col xs={4}>Ranking</Col>
                                    </Row>
                                    <hr/>
                                    {Object.values(profile_user.past_seasons).map((season, idx) =>
                                        <span key={idx}>
                                            <Row style={{textAlign: 'center'}}>
                                                <Col xs={3}>{`${season['end']}`}</Col>
                                                <Col xs={5}>{`㆔${chipAmtStr(season['winnings'], true)}`}</Col>
                                                <Col xs={4}>{`${season['ranking']}`}</Col>
                                            </Row>
                                            <hr/>
                                        </span>
                                    )}
                                    </span>
                                :   <p>There are no records for your first season.</p>}

                                <br/>
                                <center>
                                    <Alert bsStyle="info">
                                        Players are ranked each season based on how many chips they've won.

                                        <br/><br/>
                                        See the <a href="/leaderboard">leaderboard</a> for more info...
                                    </Alert>
                                </center>
                            </Tab>
                        </Tabs>

                    </div>
                  : null}
            </Col>
        </Row>
        <Row>
            {!profile_user.is_robot ?
                <Col lg={4} md={4} sm={12} className="profile-badges">
                    <div className="profile-main-panel">
                        <Tabs defaultActiveKey={1} id="badges-tabs">
                            <Tab eventKey={1} title={`${Object.keys(badges).length} ${Object.keys(badges).length == 1 ? 'Badge' : 'Badges'}`}>
                                <h4>
                                    <i style={{color: 'orange'}} className="fa fa-star"></i>&nbsp;
                                </h4>
                                {Object.keys(badges).length ?
                                    <div className="badges-scroll"
                                         ss-container="true"
                                         ref={() => global.SimpleScrollbar.initAll()}>
                                        <div className='badge-container'>
                                            {/* Badges use the Notification component for display */}
                                            {Object.values(badges).map((badge, idx) =>
                                            <Notification notification={badge} key={idx} noClose/>)}
                                        </div>
                                    </div>
                                  : <Alert bsStyle="warning">{profile_user.is_me ? 'You have' : 'User has'} no badges yet.</Alert>}
                            </Tab>

                            <Tab eventKey={2} title={`${Object.keys(leaderboard_badges).length} Trophy Case`}>
                                <h4>
                                    <i style={{color: '#1171d6'}} className="fa fa-star"></i>&nbsp;
                                </h4>
                                {Object.keys(leaderboard_badges).length ?
                                    <div className="badges-scroll"
                                         ss-container="true"
                                         style={{height: 600}}
                                         ref={() => global.SimpleScrollbar.initAll()}>
                                        <div className='badge-container'>
                                            {/* Badges use the Notification component for display */}
                                            {Object.values(leaderboard_badges).map((badge, idx) =>
                                            <Notification notification={badge} key={idx} noClose/>)}
                                        </div>
                                    </div>
                                  : <Alert bsStyle="warning">
                                        {profile_user.is_me ? 'You have' : 'User has'} no leaderboard badges yet.
                                        <br/>
                                        <br/>
                                        Trophy case badges can be earned
                                        by placing in the top leaderboard
                                        rankings for the week or season.
                                    </Alert>}
                            </Tab>
                        </Tabs>
                    </div>
                </Col>
              : null
            }
            <Col md={profile_user.is_robot ? 12 : 8} sm={12} className="profile-tables">
                <div className="profile-main-panel">
                    <h4>Tables</h4>
                    <hr/>
                    {(tables && tables.length) ?
                        <div className="tables-list">
                            {tables.map(table => <TableThumbnail table={table} key={table.id}/>)}
                        </div>
                      : <Alert bsStyle="warning">
                            {profile_user.is_me ?
                                <span>
                                    You are not at any currently active tables.
                                    <br/><br/>
                                    For past table buyin & cashout history check "Transaction History" under your Wallet.
                                </span>
                              : <div>
                                    User has no publicly visible tables.<br/>
                                </div>}
                        </Alert>}
                    <br/>
                </div>
            </Col>
        </Row>
    </div>
    }
}

ReactDOM.render(
    React.createElement(UserProfile, global.props),
    global.react_mount,
)
