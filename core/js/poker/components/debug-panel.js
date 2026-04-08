/*eslint no-unused-vars: ["error", { "ignoreRestSiblings": true }]*/

import React from 'react'

import { Button } from 'react-bootstrap'

import {prettyJSON} from '@/util/debugging'












export class TableDebugPanel extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            curr_gamestate: props.gamestate,
            prev_gamestate: []
        }
    }
    onUpdateGamestate(gamestate) {
        this.setState({
            prev_gamestate: this.state.curr_gamestate,
            curr_gamestate: gamestate
        })
    }
    render() {
        const {store, gamestate, children} = this.props
        return <div className='debug-panel'>
            <div className='table-debug-container'>
                {children}
            </div>
            <div className='debug-actions'>
                {gamestate.debugger === 'FrontendDebugger' ?
                    <FrontendActionButtons store={store}
                                           onUpdate={(gs) => this.onUpdateGamestate(gs)}
                                           idx={gamestate.idx}
                                           ticket_id={gamestate.ticket_id}/> :
                    <BackendActionButtons store={store}
                                          onUpdate={(gs) => this.onUpdateGamestate(gs)}
                                          ticket_id={gamestate.ticket_id}/>
                }
            </div>
            <pre className='curr-debug-info'>
                {prettyJSON(this.state.curr_gamestate)}
            </pre>
            <pre className='prev-debug-info'>
                {prettyJSON(this.state.prev_gamestate)}
            </pre>
        </div>

    }
}

export class FrontendActionButtons extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            action_idx: props.idx
        }
        this.store = props.store
        this.base_url = `/support/${props.ticket_id}/fdebugger?props_json=1`
    }
    get_subtract_url(){
        const min = Math.max(this.state.action_idx - 1, 0)
        const idx = `message_idx=${min}`
        const operation = `op=sub`
        return `${this.base_url}&${idx}&${operation}`
    }
    get_add_url(){
        const idx = `message_idx=${this.state.action_idx + 1}`
        const operation = `op=add`
        return `${this.base_url}&${idx}&${operation}`
    }
    onDynamicLoad(get_url_func) {

        $.get(get_url_func()).done((response) => {

            const {table, players, animations, idx} = response.gamestate
            this.setState({action_idx: idx})
            this.props.onUpdate(response.gamestate)
            this.store.dispatch({type: 'UPDATE_GAMESTATE', table, players, animations})
        })
    }
    render() {
        return <div>
            Frontend Debugger
            <div>
                <Button onClick={() => this.onDynamicLoad(() => this.get_subtract_url())}>
                    Prev Action
                </Button>
                <Button onClick={() => this.onDynamicLoad(() => this.get_add_url())}>
                    Next Action
                </Button>
            </div>
            Action index: {this.state.action_idx}
        </div>
    }
}


export class BackendActionButtons extends React.Component {
    constructor(props) {
        super(props)
        this.state = {
            action_idx: 0,
            hand_number: 0
        }
        this.store = props.store
        this.base_url = `/support/${props.ticket_id}/bdebugger?props_json=1`
    }
    onStepHand(direction) {
        const min = Math.max(this.state.hand_number + direction, 0)
        this.onDynamicLoad(this.get_hand_url(min))
    }
    onStepAction(direction) {
        const min = Math.max(this.state.action_idx + direction, 0)
        this.onDynamicLoad(this.get_action_url(min))
    }
    get_hand_url(min){
        const hand_number = `hand_number=${min}`
        const action = `action_idx=${0}`
        return `${this.base_url}&${hand_number}&${action}`
    }
    get_action_url(min){
        const hand_number = `hand_number=${this.state.hand_number}`
        const action = `action_idx=${min}`
        return `${this.base_url}&${hand_number}&${action}`
    }
    onDynamicLoad(url) {

        $.get(url).done((response) => {
            const {table, players, animations, action_idx, hand_number} = response.gamestate
            this.props.onUpdate(response.gamestate)
            this.store.dispatch({type: 'UPDATE_GAMESTATE', table, players, animations})
            this.setState({
                ...this.state,
                action_idx: parseInt(action_idx),
                hand_number: parseInt(hand_number)
            })
        })
    }
    render() {
        return <div>
            Backend Debugger. Hand: {this.state.hand_number} Action: {this.state.action_idx}
            <div>
                <Button onClick={() => this.onStepAction(-1)}>
                    Prev Action
                </Button>
                <Button onClick={() => this.onStepAction(1)}>
                    Next Action
                </Button>
            </div>
            <div>
                <Button onClick={() => this.onStepHand(-1)}>
                    Prev Hand
                </Button>
                <Button onClick={() => this.onStepHand(1)}>
                    Next Hand
                </Button>
            </div>
        </div>
    }
}
