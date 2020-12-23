import React from 'react'
import classNames from 'classnames'

import Row from 'react-bootstrap/lib/Row'
import Col from 'react-bootstrap/lib/Col'
import Modal from 'react-bootstrap/lib/Modal'
import Alert from 'react-bootstrap/lib/Alert'
import Button from 'react-bootstrap/lib/Button'
import FormGroup from 'react-bootstrap/lib/FormGroup'
import FormControl from 'react-bootstrap/lib/FormControl'
import ControlLabel from 'react-bootstrap/lib/ControlLabel'

import {ModalTrigger} from '@/components/modals'
import {SteppableRangeInput} from '@/components/steppable-range-input'


export class SidebetModalTrigger extends ModalTrigger {
    constructor(props) {
        super(props)
        this.state = {value: 1, validation_class: null, msg: ''}
        this.marks = []
        const max_slider_bet = 100
        for (let i = 0; i < max_slider_bet + 10; i += max_slider_bet/10) {
            this.marks.push({
                amt: i,
                label: i,
            })
        }
    }
    onRoundSidebet(value) {
        this.setState({
            ...this.state,
            value: Math.round(value)
        })
    }
    onChangeSidebet(value) {
        this.setState({
            value: value,
            validation_class: 'success',
            msg: ''
        })
    }
    onConfirm() {
        if(Number(global.user.balance) < this.state.value) {
            this.setState({
                ...this.state,
                validation_class: 'error',
                msg: 'Not enough chips'
            })
        } else if(this.state.value > this.props.max_amt) {
            this.setState({
                ...this.state,
                validation_class: 'error',
                msg: `Max bet: ${this.props.max_amt}`
            })
        } else if(this.state.value == 0){
            this.setState({
                ...this.state,
                validation_class: 'error',
                msg: `Cannot bet 0 chips`
            })
        } else {
            this.props.onSubmitAction('CREATE_SIDEBET', {
                player_id: this.props.player_id,
                amt: this.state.value
            })
            this.onClose()
        }
    }
    render() {
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal className="side-bet-modal" show onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            Place sidebet on {this.props.player_name}
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body className='text-center'>
                        <Alert bsStyle="info">
                            You can place a sidebet for a player you're watching.
                            If they win chips, so do you!
                        </Alert>
                        <FormGroup className="sidebet-group"
                                   validationState={this.state.validation_class}>
                            <ControlLabel>
                            Amount{this.state.validation_class === 'error'?
                                   `: ${this.state.msg}` : ''}
                            </ControlLabel>
                            <FormControl
                                type="number"
                                className="sidebet-input"
                                placeholder='0'
                                value={this.state.value}
                                min={0}
                                max={Number(global.user.balance)}
                                onKeyUp={(e) => this.onRoundSidebet(e.target.value)}
                                onChange={(e) => this.onChangeSidebet(e.target.value)}
                                step={1}
                                />
                        </FormGroup>
                        <FormGroup className="sidebet-odds">
                            <ControlLabel>Odds</ControlLabel>
                            <FormControl
                                disabled={true}
                                type="number"
                                className="sidebet-input"
                                placeholder='0'
                                value={this.props.odds}
                                />
                        </FormGroup><br/>
                        <SteppableRangeInput className="sidebet-slider"
                                             value={this.state.value}
                                             min={1}
                                             max={Number(global.user.balance)}
                                             marks={this.marks}
                                             button_step={1}
                                             onChange={(val) => this.onChangeSidebet(val)}/>
                        <br/>
                    </Modal.Body>
                    <Modal.Footer>
                        <span>
                            <Button onClick={::this.onCancel}>Cancel</Button>
                            <Button bsStyle="success" onClick={::this.onConfirm}>
                                Start
                            </Button>
                        </span>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}


const MultiValueBets = ({bets, html_key, object_key, use_class=false}) =>{
    return bets.map((bet, i) =>
        <span className={classNames({[bet.value_class]: use_class})}
              key={`${html_key}-${i}`}>
              {bet[object_key]}<br/>
        </span> )
}


export class ChangeSidebetModalTrigger extends ModalTrigger {
    constructor(props) {
        super(props)
        this.state = {value: 1, validation_class: null, msg: ''}
    }
    onChangeSidebet(value) {
        this.setState({
            value: value,
            validation_class: 'success',
            msg: ''
        })
    }
    onRoundSidebet(value) {
        this.setState({
            ...this.state,
            value: Math.round(value)
        })
    }
    onConfirm() {
        if(Number(global.user.balance) < this.state.value) {
            this.setState({
                ...this.state,
                validation_class: 'error',
                msg: 'Not enough chips'
            })
        } else if(this.state.value > this.props.max_amt) {
            this.setState({
                ...this.state,
                validation_class: 'error',
                msg: `Max bet: ${this.props.max_amt}`
            })
        } else if(this.state.value == 0){
            this.setState({
                ...this.state,
                validation_class: 'error',
                msg: `Cannot bet 0 chips`
            })
        } else {
            this.props.onSubmitAction('CREATE_SIDEBET', {
                player_id: this.props.active_bets[0].player.id,
                amt: this.state.value
            })
            this.onClose()
        }
    }
    onEndSidebet() {
        this.props.onSubmitAction('CLOSE_SIDEBET', {
            player_id: this.props.active_bets[0].player.id,
        })
        this.onClose()
    }
    render() {
        return <span>
            <span onClick={::this.onShow}>
                {this.props.children}
            </span>
            {this.state.show &&
                <Modal className="side-bet-modal" bsSize='large' show
                       onHide={::this.onClose} autoFocus={false}>
                    <Modal.Header>
                        <Modal.Title style={{fontFamily:'Bungee'}}>
                            Sidebet info
                        </Modal.Title>
                    </Modal.Header>
                    <Modal.Body className='text-center'>
                        <br/>
                        <Row>
                            <Col xs={4}>
                                <b>Player:</b><br/>{this.props.active_bets[0].player.username}
                            </Col>
                            <Col xs={4}>
                                <b>Current Stack:</b><br/>{this.props.active_bets[0].current_stack}
                            </Col>
                            <Col xs={4}>
                                <b>Status:</b><br/>
                                {this.props.active_bets[0].status}
                            </Col>
                        </Row>
                        <br/>
                        <Row>
                            <Col xs={4} sm={2}>
                                <b>Initial Stack:</b><br/>
                                <MultiValueBets bets={this.props.active_bets}
                                                html_key='initial-stack'
                                                object_key='starting_stack'/>
                            </Col>
                            <Col xs={4} sm={2}>
                                <b>Amount:</b><br/>
                                <MultiValueBets bets={this.props.active_bets}
                                                html_key='amount'
                                                object_key='amt'/>
                            </Col>
                            <Col xs={4} sm={2}>
                                <b>Odds:</b><br/>
                                <MultiValueBets bets={this.props.active_bets}
                                                html_key='odds'
                                                object_key='odds'/>
                            </Col>
                            <Col xs={4} sm={2} className='sidebet-value'>
                                <b>Current Amount:</b><br/>
                                <MultiValueBets bets={this.props.active_bets}
                                                html_key='current-value'
                                                object_key='current_value'
                                                use_class={true}/>
                            </Col>
                            <Col xs={4} sm={2}>
                                <b>Created:</b><br/>
                                <MultiValueBets bets={this.props.active_bets}
                                                html_key='created'
                                                object_key='created'/>
                            </Col>
                            <Col xs={4} sm={2}>
                                <b>Info:</b><br/>
                                {this.props.active_bets.map((bet, i) =>
                                    <span key={`info-${i}`}>
                                        {bet.from_rebuy ?
                                            'carried bet over due to rebuy'
                                            : '--'
                                        }<br/>
                                    </span>)}
                            </Col>
                        </Row>
                        <br/>
                        <Row>
                        <br/>
                            <Col xs={6}>
                                <FormGroup className="sidebet-group"
                                           validationState={this.state.validation_class}>
                                    <ControlLabel>
                                        Add sidebet {this.state.validation_class === 'error'?
                                                `: ${this.state.msg}` : ''}
                                    </ControlLabel>
                                    <FormControl
                                        type="number"
                                        className="sidebet-input"
                                        placeholder='0'
                                        value={this.state.value}
                                        min={0}
                                        max={Number(global.user.balance)}
                                        onKeyUp={(e) => this.onRoundSidebet(e.target.value)}
                                        onChange={(e) => this.onChangeSidebet(e.target.value)}
                                        step={1}
                                        />
                                </FormGroup>
                            </Col>
                            <Col xs={6}>
                                <b>Close Sidebets:</b><br/>
                                <Button bsStyle="default" onClick={::this.onEndSidebet}>
                                    Close on new hand
                                </Button>
                            </Col>
                        </Row>
                    </Modal.Body>
                    <Modal.Footer>
                        <span>
                            <Button onClick={::this.onCancel}>Close</Button>
                            <Button bsStyle="success" onClick={::this.onConfirm}>
                                Add sidebet on new hand
                            </Button>
                        </span>
                    </Modal.Footer>
                </Modal>}
        </span>
    }
}
