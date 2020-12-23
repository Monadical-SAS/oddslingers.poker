/*eslint no-unused-vars: ["error", { "ignoreRestSiblings": true }]*/

import React from 'react'
// import {reduxify} from '@/util/reduxify'

// import Row from 'react-bootstrap/lib/Row'
// import Col from 'react-bootstrap/lib/Col'
// import Nav from 'react-bootstrap/lib/Nav'
// import NavItem from 'react-bootstrap/lib/NavItem'
import Button from 'react-bootstrap/lib/Button'

// import {Icon} from '@/components/icons'
// import {getOrderedPlayerIds} from '@/poker/selectors'
// import {clearLog} from '@/poker/reducers'
import {prettyJSON} from '@/util/debugging'


// const tableDebugLog = (table) => {
//     const keys = Object.keys(table).filter(key =>
//         ['id', 'name', 'path', 'variant', 'sb', 'bb'].includes(key))

//     return keys.map(key =>
//         `${ljust((key + ':'), 12)} ${JSON.stringify(table[key])}`
//     ).join('\n')
// }


// const playerDebugLog = (players) => {
//     const player_ids = getOrderedPlayerIds(players)

//     return player_ids.map(id => {
//         const {username, ...rest} = players[id]
//         const details = Object.keys(rest).sort().map(key => `${key}: ${JSON.stringify(rest[key])}`).join(', ')
//         return `${ljust((username + ':'), 12)} ${details}`
//     }).join('\n')
// }


//

// export class TableDebugPanelComponent extends React.Component {
//     state = {
//         activeTab: "table state",
//         recvs: [],
//     }
//     onChangeTab(tab) {
//         this.setState({...this.state, activeTab: tab})
//     }
//     // componentDidMount() {
//     //     // hook into websocket to get all received messages
//     //     const socket_onmessage = global.socket._onmessage
//     //     const patched_onmessage = (message) => {
//     //         this.setState({
//     //             ...this.state,
//     //             recvs: [...this.state.recvs, JSON.parse(message.data)]
//     //         })
//     //         socket_onmessage.call(global.socket, message)
//     //     }
//     //     global.socket._onmessage = patched_onmessage
//     // }
//     dynamicLoad(url) {
//         $.get(url + '?props_json=1').done((response) => {
//             global.history.pushState({}, '', url)
//             const {table, players, animations} = response.gamestate
//             console.log('dynamicLoad', table, players, animations)
//             // global.store.dispatch({type: 'SET_GAMESTATE', table, players})
//             global.store.dispatch({type: 'UPDATE_GAMESTATE', table, players, animations})
//         })
//     }
//     onStepHand(direction) {
//         const path = document.location.pathname.split('/')  // /debugger/hh_009/5/0/  => ["", "debugger", "hh_009", "5", "0", ""]
//         path[3] = Number(path[3]) + direction
//         path[4] = 0
//         const nextpath = path.join('/')
//         this.dynamicLoad(nextpath)
//     }
//     onStepAction(direction) {
//         const path = document.location.pathname.split('/')  // /debugger/hh_009/5/0/  => ["", "debugger", "hh_009", "5", "0", ""]
//         path[4] = Number(path[4]) + direction
//         const nextpath = path.join('/')
//         this.dynamicLoad(nextpath)
//     }
//     render() {
//         const {table, players, queue, clearLog} = this.props
//         const {activeTab, recvs} = this.state

//         return <Row className="debug-panel">
//             <style>{debugger_style}</style>
//             <Col md={6}>
//                 <div id="logactions">
//                     <small title="Queued animations" className="queue-length">{queue.length}</small>
//                     <Button onClick={this.onStepHand.bind(this, -1)}>Hand &nbsp; <Icon name="angle-double-left"/></Button>&nbsp;
//                     <Button onClick={this.onStepAction.bind(this, -1)}><Icon name="arrow-left"/> &nbsp; Action</Button>&nbsp;
//                     <Button onClick={() => {}}><Icon name="angle-left"/> &nbsp; Last RECV</Button>&nbsp;
//                     <Button onClick={clearLog}>Pause</Button>&nbsp;
//                     <Button onClick={() => {}}>Next Animation &nbsp; <Icon name="angle-right"/></Button>&nbsp;
//                     <Button onClick={this.onStepAction.bind(this, 1)}>Action &nbsp; <Icon name="arrow-right"/></Button>&nbsp;
//                     <Button onClick={this.onStepHand.bind(this, 1)}>Hand &nbsp; <Icon name="angle-double-right"/></Button>&nbsp;
//                 </div>
//                 <pre id="gamelog">
//                     {JSON.stringify(queue)}
//                 </pre>
//             </Col>
//             <Col md={6}>
//                 <Nav bsStyle="tabs" activeKey={activeTab} onSelect={::this.onChangeTab}>
//                     <NavItem eventKey="recvs" style={{float: 'right'}} className="recvs">RECVs &nbsp;</NavItem>
//                     <NavItem eventKey="animation" style={{float: 'right'}}>Current Animation</NavItem>
//                     <NavItem eventKey="table state">Table State</NavItem>
//                     <NavItem eventKey="diff">Diff</NavItem>
//                     <NavItem eventKey="target state">Target State</NavItem>
//                 </Nav>
//                 <pre id="gamestate">
//                     {(activeTab == 'table state') &&
//                         <div>
//                             {tableDebugLog(table)}
//                             <hr/>
//                             {playerDebugLog(players)}
//                         </div>}
//                     {(activeTab == 'diff') &&
//                         <div>
//                         </div>}
//                     {(activeTab == 'target state') &&
//                         <div>
//                         </div>}
//                     {(activeTab == 'recvs') &&
//                         <div>
//                             {recvs.map(action => {
//                                 const {type, TIMESTAMP, ...data} = action
//                                 return <div>{`${type}: ${JSON.stringify(data)}`}</div>
//                             })}
//                         </div>}
//                     {(activeTab == 'animation') &&
//                         <div>
//                         </div>}
//                 </pre>
//             </Col>
//         </Row>
//     }
// }

// export const TableDebugPanel = reduxify({
//     mapStateToProps: ({gamestate, animations}) => ({
//         table: animations.gamestate.table || gamestate.table,
//         players: animations.gamestate.players || gamestate.players,
//         queue: animations.queue || [],
//     }),
//     mapDispatchToProps: {
//         clearLog
//     },
//     render: ({table, players, queue, clearLog}) => {
//         return <TableDebugPanelComponent table={table}
//                                          players={players}
//                                          queue={queue}
//                                          clearLog={clearLog}/>
//     }
// })

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
