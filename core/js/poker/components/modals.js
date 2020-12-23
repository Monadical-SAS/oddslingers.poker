import React from 'react'
import {reduxify} from '@/util/reduxify'
import isEmpty from 'lodash/isEmpty'

import Modal from 'react-bootstrap/lib/Modal'
import Alert from 'react-bootstrap/lib/Alert'
import Button from 'react-bootstrap/lib/Button'
import FormGroup from 'react-bootstrap/lib/FormGroup'
import FormControl from 'react-bootstrap/lib/FormControl'
import ControlLabel from 'react-bootstrap/lib/ControlLabel'
import HelpBlock from 'react-bootstrap/lib/HelpBlock'
import InputGroup from 'react-bootstrap/lib/InputGroup'
import Checkbox from 'react-bootstrap/lib/Checkbox'

import {tooltip, preventNonNumbers} from '@/util/dom'
import {select_text, openNewTab} from '@/util/browser'

import {ModalTrigger} from '@/components/modals'
import {Icon, Spinner} from '@/components/icons'

import {reportBug, pauseFrontend, resumeFrontend} from '@/poker/debugging'
import {getGamestate} from '@/poker/selectors'
import {onSubmitAction} from '@/poker/reducers'


class TableInfoModal extends ModalTrigger {
    render() {
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            {this.props.name} <small style={{float: 'right', marginTop: 5}}>{this.props.path}</small>
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <b>Type: </b> {this.props.variant} ({this.props.is_private ? 'Private' : 'Public'})<br/>
                        <b>Created By: </b> {this.props.created_by || 'OddSlingers'}<br/>
                        <b>Seats: </b> {this.props.num_seats} ({this.props.available_seats} available)<br/>
                        <b>Hands: </b> {this.props.hand_number}<br/>
                        {/*<b>Currency: </b> Play-chips (free)<br/>*/}
                        <br/>
                        <b>Small Blind: </b> {this.props.sb} chips <br/>
                        <b>Big Blind: </b> {this.props.bb} chips <br/>
                        <br/>
                        <b>Min Buyin: </b> {this.props.min_buyin} chips <br/>
                        <b>Max Buyin: </b> {this.props.max_buyin} chips <br/>
                        <b>Avg Stack: </b> {this.props.avg_stack}<br/>
                        <br/>
                        <b>Players per Flop Ratio: </b> {this.props.players_per_flop_pct}<br/>
                        <b>Avg Pot: </b> {this.props.avg_pot}<br/>
                        <b>Hands per Hour: </b> {this.props.hands_per_hour}<br/>
                        <hr/>
                        <b>Players:</b>
                        <ul>
                            {this.props.players.map(({position, username, stack}) =>
                                <li key={username}>
                                    <a href="#" onClick={() => openNewTab(`/user/${username}`)}>
                                        <b>#{position}:</b> {username}
                                    </a> ({Number(stack.amt).toLocaleString()})
                                </li>)}
                        </ul>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button bsStyle="success" onClick={::this.onClose}>
                            Ok &nbsp;<Icon name="check"/>
                        </Button>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}

const getNumberOrNA = (num, sufix) =>
    num != null ?
        `${Number(num).toLocaleString()} ${sufix || ''}`
        : 'N/A'

export const TableInfoModalTrigger = reduxify({
    mapStateToProps(state) {
        const {table, players} = getGamestate(state)
        const {table_stats} = state.gamestate
        return {
            avg_stack: getNumberOrNA(table_stats.avg_stack, 'chips'),
            players_per_flop_pct: getNumberOrNA(table_stats.players_per_flop_pct, '%'),
            avg_pot: getNumberOrNA(table_stats.avg_pot),
            hands_per_hour: getNumberOrNA(table_stats.hands_per_hour),
            sb: Number(table.sb).toLocaleString(),
            bb: Number(table.bb).toLocaleString(),
            name: table.name,
            hand_number: Number(table.hand_number).toLocaleString(),
            num_seats: table.num_seats,
            available_seats: table.available_seats,
            min_buyin: Number(table.min_buyin).toLocaleString(),
            max_buyin: Number(table.max_buyin).toLocaleString(),
            variant: table.variant,
            is_private: table.is_private,
            players: Object.values(players)
                           .map(({position, username, stack}) =>
                                ({position, username, stack}))
                           .sort((a, b) => a.position - b.position)
        }
    },
    render({avg_stack, players_per_flop_pct, avg_pot,
            hands_per_hour, sb, bb, name, hand_number, num_seats,
            available_seats, min_buyin, max_buyin, variant, is_private, players, children}) {
        return <TableInfoModal  avg_stack={avg_stack}
                                players_per_flop_pct={players_per_flop_pct}
                                avg_pot={avg_pot}
                                hands_per_hour={hands_per_hour}
                                sb={sb}
                                bb={bb}
                                name={name}
                                hand_number={hand_number}
                                num_seats={num_seats}
                                available_seats={available_seats}
                                min_buyin={min_buyin}
                                max_buyin={max_buyin}
                                variant={variant}
                                is_private={is_private}
                                players={players}>
            {children}
        </TableInfoModal>
    }
})

export class ShareTableModalTrigger extends ModalTrigger {
    constructor(props){
        super(props)
        this.state = {share_linky: `${global.location.origin}${props.table.path}`}
    }
    onInvite() {
        const invite_email = $('#new-user-email').val()
        const table_id = this.props.table.id
        $.ajax({
            url: `/api/table/invite/`,
            type: 'POST',
            data: {email: invite_email, table_id: table_id},
            success: () => {this.setState({...this.state, sent: "Sent!"})},
        })
    }
    onShow(e) {
        super.onShow(e)
        const data = {
            viewname: 'Table',
            id: this.props.table.short_id
        }
        $.post('/api/shorten_url/', data, (resp) => {
                if (resp.success){
                    this.setState({share_linky:resp.linky})
                }
            }
        )
    }
    onCopy() {
        select_text("share-link")
        document.execCommand('copy')
    }
    render() {
        const table = this.props.table
        const origin = global.location.origin
        const pre_style = {
            marginTop: 5,
            border: 0,
            paddingTop: 11,
            userSelect: 'all',
        }
        const embedableIFrame = `<iframe src="${origin}${table.path.replace('/table/', '/embed/')}" width="100%" height="62.5%"></iframe>`
        const invite_str = encodeURIComponent('Come join my poker table on Oddslingers!')
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <div style={{float:'right'}}>
                            <a target="_blank" href="#" onClick={() => openNewTab(`https://www.facebook.com/sharer/sharer.php?u=${this.state.share_linky}&quote=${invite_str}`)}>
                                <i className="text-primary fa fa-facebook-square fa-2x"/>
                            </a>&nbsp;
                            <a target="_blank" href="#" onClick={() => openNewTab(`https://twitter.com/intent/tweet?text=${invite_str}%20${this.state.share_linky}`)}>
                                <i className="fa fa-twitter-square fa-2x"/>
                            </a>
                        </div>
                        <Modal.Title id="contained-modal-title-md" style={{fontFamily:'Bungee'}}>
                            Share Table Link
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        Share this link to invite people to this table:
                        <br/>
                        <div>
                            <pre id="share-link" style={{...pre_style, border: '1px solid orange', textDecoration: 'underline'}}>
                                {this.state.share_linky}
                            </pre>
                            <Button bsStyle="default"
                                    onClick={::this.onCopy}
                                    {...tooltip("Copy to clipboard", "top")}>
                                Copy!
                            </Button>
                        </div>
                        <br/>
                        {global.user && <div>
                            Or invite a friend to this table via email: <span className="text-green green">{this.state.sent}</span>
                            <FormGroup>
                                <InputGroup>
                                    <FormControl type="email" id="new-user-email" placeholder="friend@example.com"/>
                                    <InputGroup.Button>
                                        <Button bsStyle="default" onClick={::this.onInvite}>
                                            Invite via email &nbsp;<Icon name="envelope"/>
                                        </Button>
                                    </InputGroup.Button>
                                </InputGroup>
                            </FormGroup>
                        </div>}

                        Use this code to embed this table:
                        <br/>
                        <pre style={pre_style}>{embedableIFrame}</pre>
                    </Modal.Body>
                    <Modal.Footer>
                        <Button bsStyle="success" onClick={::this.onClose}>
                            Ok &nbsp;<Icon name="check"/>
                        </Button>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}


export class ReportBugModalTrigger extends ModalTrigger {
    constructor(props, context) {
        super(props, context)
        this.state = {summary: ''}
    }
    onShow() {
        super.onShow()
        pauseFrontend()
    }
    onExit() {
        resumeFrontend()
        this.onClose()
    }
    onSubmit() {
        this.reportBug()
        this.onClose()
    }
    onSubmitWithChat(e) {
        e.preventDefault()
        this.reportBug()
        this.onClose()
        window.open('/support/', '_blank')
    }
    onChangeSummary(e) {
        console.log(e)
        this.setState({summary: e.target.value})
    }
    reportBug() {
        const notes = $('#debug-dump-modal textarea').val()
        setTimeout(() => {
            reportBug(notes)
        }, 1000)
        return true
    }
    render() {
        return <span onKeyDown={e => e.stopPropagation()}>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onExit} id="debug-dump-modal" autoFocus={false}>
                    <Modal.Header style={{backgroundColor: '#449d44'}}>
                        <Modal.Title id="contained-modal-title-md">
                            Talk to support
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        We try to keep the game working flawlessly, but occasionally something goes wrong and we have to investigate.<br/>
                        <br/>
                        Please describe the issue with at least one sentence:<br/>
                        <br/>
                        <FormGroup>
                            <FormControl componentClass="textarea"
                                         value={this.state.summary}
                                         placeholder="Type a quick summary of the issue you saw to submit a bug report..."
                                         onChange={::this.onChangeSummary}
                                         style={{minHeight: 120}}/>
                        </FormGroup>

                        If you help us fix a bug you get a "Bug Hunter" badge and 10,000 bonus chips!
                    </Modal.Body>
                    <Modal.Footer>
                        <a href="/support/" onClick={::this.onSubmitWithChat} target="_blank" style={{float:'left', marginTop: 10}} {...tooltip('Submit & open support in new window.')}>
                            Live Chat Support &nbsp;<Icon name="comments-o"/>
                        </a>
                        <Button onClick={::this.onCancel}>Cancel</Button>
                        <Button bsStyle="success" onClick={::this.onSubmit} disabled={this.state.summary.length <= 5}>
                            Submit
                        </Button>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}


class BuyChipsModalTrigger extends ModalTrigger {
    constructor(props, context) {
        super(props, context)
        this.state = {
            ...super.state,
            input_value: props.min_buyin,
        }
    }
    isValidInput() {
        const {input_value} = this.state
        const {min_buyin, max_buyin} = this.props
        return input_value <= max_buyin && input_value >= min_buyin
    }
    getValidationState() {
        let form_group_class = ''
        let help_block_display = 'none'
        if (this.isValidInput()) {
            form_group_class = 'success'
        } else if (this.state.input_value !== null) {
            form_group_class = 'error'
            help_block_display = 'block'
        }
        return {form_group_class, help_block_display}
    }
    onInputChange(e) {
        this.setState({input_value: e.target.value})
    }
    onConfirm() {
        if (this.isValidInput()) {
            this.props.onSubmitAction(
                this.action,
                {amt: this.state.input_value}
            )
            this.onClose()
        }
    }
    turnOffAutoRebuyin() {
        this.props.onSubmitAction(this.action, {amt: 0})
        this.onClose()
    }
}


export class OneTimeBuyModalTrigger extends BuyChipsModalTrigger {
    constructor(props) {
        super(props)

        this.action = 'BUY'
        this.state = {
            ...super.state,
            can_buy: true,
            input_value: this.props.legal_min_buyin
        }
    }
    componentDidMount() {
        if (this.props.legal_max_buyin === 0) {
            this.setState({can_buy: false})
        }
    }
    isValidInput() {
        const {input_value} = this.state
        const {legal_min_buyin, legal_max_buyin} = this.props

        if (!this.state.can_buy) {
            return false
        } else {
            return input_value >= legal_min_buyin && input_value <= legal_max_buyin
        }
    }
    render() {
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal className="buy-chips-modal" show onHide={::this.onClose}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            One-time buy...
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <FormGroup validationState={this.getValidationState().form_group_class}>
                            <center style={{fontSize: 17}}>
                                Add chips to this table from your playchip <a href={`/user/${global.user.username}`} target="_blank">wallet</a> balance of {global.user.balance.toLocaleString()}㆔.<br/>
                            </center><hr/>
                            <div className="chips-form">
                                <picture>
                                    <source srcSet="/static/images/chips.webp" type="image/webp"/>
                                    <img src="/static/images/chips.png" alt="Chips"/>
                                </picture>
                                <FormControl id="buyin-amt"
                                             componentClass="input"
                                             type="number"
                                             value={this.state.input_value}
                                             min={this.props.legal_min_buyin}
                                             max={this.props.legal_max_buyin}
                                             placeholder={this.props.legal_min_buyin}
                                             onChange={::this.onInputChange}
                                             onKeyDown={preventNonNumbers}/>
                                <ControlLabel>Chips</ControlLabel>
                                {this.state.can_buy ?
                                    <HelpBlock style={{display: this.getValidationState().help_block_display}}>
                                        This amount must be between {this.props.legal_min_buyin} and {this.props.legal_max_buyin}
                                        &nbsp;<Icon name="info-circle" 
                                            {...tooltip('This interval is calculed using your current stack + pending buyin and min-max buyin from the table')} />
                                    </HelpBlock>
                                    : <HelpBlock>
                                        You don't need to buy any chips
                                    </HelpBlock>}
                            </div>
                            {this.props.player_auto_rebuy ?
                                <Alert bsStyle="info">
                                    Note: You have auto-rebuy enabled, it is currently set to {Number(this.props.player_auto_rebuy).toLocaleString()} chips
                                </Alert>
                                : null}
                        </FormGroup>
                    </Modal.Body>
                    <Modal.Footer>
                        <span>
                            <Button onClick={::this.onCancel}>Cancel</Button>
                            <Button bsStyle="success" onClick={::this.onConfirm} disabled={!this.isValidInput()}>
                                Add {Number(this.state.input_value).toLocaleString()} Chips to Table
                            </Button>
                        </span>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}


const getAmountInBbs = (amount, bb) => Math.floor(amount / bb).toString()

export class AutoRebuyModalTrigger extends BuyChipsModalTrigger {
    constructor(props) {
        super(props)

        this.action = 'SET_AUTO_REBUY'
        this.state = {
            ...super.state,
            input_value: props.min_buyin,
            input_in_bbs: getAmountInBbs(props.min_buyin, this.props.bb)
        }
    }
    onAllTablesCheck(e) {
        this.setState({default_for_all_tables: e.target.checked})
    }
    onConfirm() {
        if (this.state.default_for_all_tables) {
            $.ajax({
                url: `/api/user/?id=${encodeURIComponent(global.user.id)}`,
                type: 'PATCH',
                data: JSON.stringify({ auto_rebuy_in_bbs: this.state.input_in_bbs })
            })
        }
        super.onConfirm()
    }
    onInputChange(e) {
        const {value} = e.target
        this.setState({
            input_value: value,
            input_in_bbs: getAmountInBbs(value, this.props.bb)
        })
    }
    render() {
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal className="buy-chips-modal" show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            Set Auto rebuy...
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        <center style={{fontSize: 17}}>
                            Add chips to this table periodically whenever your stack goes under the specified amount.
                            <br/>
                            Your playchip <a href={`/user/${global.user.username}`} target="_blank">wallet</a> has a balance of {global.user.balance.toLocaleString()}㆔.<br/>
                        </center><hr/>
                        <FormGroup validationState={this.getValidationState().form_group_class}>
                            {this.props.player_auto_rebuy ?
                                <Alert bsStyle="info">
                                    Auto-rebuy is currently set to {Number(this.props.player_auto_rebuy).toLocaleString()} chips
                                </Alert>
                                : null}
                            <div className="chips-form">
                                <picture>
                                    <source srcSet="/static/images/chips.webp" type="image/webp"/>
                                    <img src="/static/images/chips.png" alt="Chips"/>
                                </picture>
                                <FormControl id="buyin-amt"
                                             componentClass="input"
                                             type="number"
                                             value={this.state.input_value}
                                             min={this.props.min_buyin}
                                             max={this.props.max_buyin}
                                             placeholder={this.props.min_buyin}
                                             onChange={::this.onInputChange}
                                             onKeyDown={preventNonNumbers}/>
                                <ControlLabel>Chips ({this.state.input_in_bbs} bbs)</ControlLabel>
                                <HelpBlock style={{display: this.getValidationState().help_block_display}}>
                                    This amount must be between {this.props.min_buyin} and {this.props.max_buyin}
                                </HelpBlock>
                            </div>
                        </FormGroup>
                        <Checkbox className="chips-form"
                                  defaultChecked={this.state.default_for_all_tables}
                                  onChange={::this.onAllTablesCheck}>
                            Set {this.state.input_in_bbs} bbs default auto-rebuy on all tables
                        </Checkbox>
                    </Modal.Body>
                    <Modal.Footer>
                        <span>
                            <Button bsStyle="danger" className="pull-left" onClick={::this.turnOffAutoRebuyin}>
                                Turn off
                            </Button>
                            <Button onClick={::this.onCancel}>Cancel</Button>
                            <Button bsStyle="success" onClick={::this.onConfirm} disabled={!this.isValidInput()}>
                                Enable auto-rebuying at {Number(this.state.input_value).toLocaleString()} chips
                            </Button>
                        </span>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}


class HandHistoryModal extends ModalTrigger {
    constructor(props) {
        super(props)
        this.state = {
            ...super.state,
            offset: -1
        }
    }
    render() {
        const dummy_hh = {
            hand_number: 1,
            summary: {title: '', table_info: '', history: ['Loading hand history...']}
        }
        const {hand_history} = this.props
        const curr_hand_number = this.getCurrentIdx() + 1
        const showed_hand = (hand_history[this.getCurrentIdx()] || dummy_hh).summary
        return <span>
            <style>
                {`
                    .history-line {
                        margin-bottom: 3px;
                    }
                    .history-title {
                        font-size: 16px;
                    }
                    .history-container {
                        height: 300px;
                        overflow-y: scroll;
                    }
                `}
            </style>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            Hand History {hand_history.length > 0 ?
                                                <span>(Hand {curr_hand_number} of {hand_history.length})</span>
                                                : null}
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {hand_history.length > 0 ?
                            <div>
                                <b className="history-title">{showed_hand.title}</b>
                                <br/>
                                <i>{showed_hand.table_info}</i>
                                <br/><br/>
                                <div className="history-container">
                                    <pre>
                                        {showed_hand.history.map((line, idx) =>
                                            <p className="history-line" key={idx.toString()}>{line}</p>)}
                                    </pre>
                                </div>
                            </div>
                            : <Alert bsStyle="info">
                                <br/><br/>
                                <center style={{fontSize: '20px'}}>
                                    <Spinner/>
                                    <br/><br/>
                                    Hand history will become available once you've stayed at the table for a full hand.
                                    <br/><br/>
                                </center>
                            </Alert>}
                    </Modal.Body>
                    <Modal.Footer>
                        {hand_history.length > 0 ?
                            <span>
                                <Button style={{float: 'left'}} onClick={::this.onCancel}>Close</Button>
                                <Button bsStyle="warning"
                                        onClick={::this.onMoveBackward}>
                                    <Icon name="angle-double-left"/>
                                </Button>
                                &nbsp; &nbsp; Hand {curr_hand_number}/{hand_history.length} &nbsp; &nbsp;
                                <Button bsStyle="warning"
                                        onClick={::this.onMoveForward}>
                                    <Icon name="angle-double-right"/>
                                </Button>
                            </span>
                            : <Button bsStyle="success" onClick={::this.onClose}>
                                Ok &nbsp;<Icon name="check"/>
                            </Button>}
                    </Modal.Footer>
                </Modal>}
        </span>
    }
    getCurrentIdx() {
        return this.props.hand_history.length + this.state.offset
    }
    onShow(e) {
        super.onShow(e)
        const hand_gte = this.props.initial_hand
        const hand_lt = this.props.last_hand
        this.props.onSubmitAction(
            'GET_HANDHISTORY',
            {hand_gte, hand_lt},
        )
    }
    onClose(e) {
        this.setState({
            ...super.state,
            offset: -1,
        })
        super.onClose(e)
    }
    onMoveForward() {
        const curr_hand_number = this.getCurrentIdx() + 1
        const hh_length = this.props.hand_history.length
        if (curr_hand_number !== hh_length) {
            this.setState({
                offset: this.state.offset + 1
            })
        }
    }
    onMoveBackward() {
        const curr_hand_number = this.getCurrentIdx() + 1
        if (curr_hand_number !== 1) {
            this.setState({
                offset: this.state.offset - 1,
            })
        }
    }
}

export const HandHistoryModalTrigger = reduxify({
    mapStateToProps: (state, props) => {
        const {hand_history} = state.gamestate
        const {table} = getGamestate(state)
        const received = state.websocket.received
        const initial_hand = received.length ?
                             received[0].table.hand_number
                             : 0
        const last_hand = table.hand_number
        const modal_default_props = props
        return {hand_history, initial_hand, last_hand, modal_default_props}

    },
    mapDispatchToProps: {
        onSubmitAction
    },
    render: ({hand_history, initial_hand, last_hand, modal_default_props, onSubmitAction}) => {
        return <HandHistoryModal {...modal_default_props}
                                 hand_history={hand_history}
                                 initial_hand={initial_hand}
                                 last_hand={last_hand}
                                 onSubmitAction={onSubmitAction} />
    }
})


const getColoredWinnings = (winnings) => {
    const value = Number(winnings)
    if (value > 0) {
        return <span className="green">+{value.toLocaleString()}</span>
    }
    return <span className="red">{value.toLocaleString()}</span>
}

class PlayerWinningsModal extends ModalTrigger {
    onShow(e) {
        super.onShow(e)
        this.props.onSubmitAction('GET_PLAYER_WINNINGS')
    }
    render() {
        const {player_winnings} = this.props
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            Player Winnings
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body>
                        {isEmpty(player_winnings) ?
                            "There are not enough players to start a game"
                            : <table className="winnings-table">
                                <tbody>
                                    <tr>
                                        <th>Player</th>
                                        <th>Current Stack</th>
                                        <th>Buyins</th>
                                        <th>Total Winnings</th>
                                    </tr>
                                    {Object.keys(player_winnings || {}).map((username) =>
                                        <tr key={username}>
                                            <td>
                                                <a href="#" onClick={() => openNewTab(`/user/${username}`)}>
                                                    {username}
                                                </a>
                                            </td>
                                            <td>{Number(player_winnings[username].stack)}</td>
                                            <td>{Number(player_winnings[username].buyins)}</td>
                                            <td>{getColoredWinnings(player_winnings[username].winnings)}</td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        }
                    </Modal.Body>
                    <Modal.Footer>
                        <Button style={{float: 'right'}} onClick={::this.onCancel}>Close</Button>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}

export const PlayerWinningsModalTrigger = reduxify({
    mapStateToProps: (state, props) => {
        const {player_winnings} = state.gamestate
        const modal_default_props = props

        return {player_winnings, modal_default_props}
    },
    mapDispatchToProps: {
        onSubmitAction
    },
    render: ({player_winnings, modal_default_props, onSubmitAction}) => {
        return <PlayerWinningsModal {...modal_default_props}
                                    player_winnings={player_winnings}
                                    onSubmitAction={onSubmitAction} />
    }
})
