import React from 'react'
import ReactDOM from 'react-dom'

import {createStore, combineReducers} from 'redux'
import {Provider} from 'react-redux'
import {animationsReducer, startAnimation} from 'redux-time'

import {initial_state as anim_state} from 'redux-time/node/reducers'

import {gamestate} from '@/poker/reducers'
import {chat} from '@/chat/reducers'
import {notifications} from '@/notifications/reducers'
import {sounds} from '@/sounds/reducers'
import {video} from '@/video/reducers'
import {sidebet} from '@/sidebets/reducers'
import {websocket} from '@/websocket/reducers'

import {Notifications} from '@/notifications/containers'
import {Sounds} from '@/sounds/containers'
import {NewVisitorModal} from '@/components/new-visitor-modal'
import {TournamentResultModal} from '@/components/tournament-modals'
import {startPokerProcess} from '@/poker/process'
// import {ForcedActions} from '@/poker/debugging'

import {SwapTable} from '@/components/swaptable'

import {TableDebugPanel} from '@/poker/components/debug-panel'


global.initial_state = {
    gamestate: global.props.gamestate,
    chat: {lines: []},
}

global.WebSocket = null


export const TableDebugger = {
    view: `ui.views.pages.${global.props.gamestate.debugger}`,

    init(props, autostart=false) {

        if (props.gamestate) {
            global.loading.init_start = Date.now()
            if (global.DEBUG) {
                // time between page finished loading and initialization running
                const parse_time = global.loading.init_start - global.loading.end
                console.groupCollapsed(`%c[+] PARSED JS ${parse_time}ms`, 'color:orange')
            }
            props.gamestate.table.last_action_timestamp = Date.now()

            const initial_state = {
                animations: {
                    ...anim_state,
                    max_time_travel: 300,
                }
            }

            const store = this.setupStore({
                gamestate,
                websocket,
                chat,
                notifications,
                sounds,
                video,
                sidebet,
                animations: animationsReducer,
                ...(props.SHOW_VIDEO_STREAMS ? [video] : []),
            }, initial_state)
            const time = this.setupAnimation(store, {}, autostart)
            const poker = this.setupPoker(store, time, props.gamestate)
            const socket = this.setupSocket()
            global.loading.init_end = Date.now()
            if (global.DEBUG) {
                console.groupEnd()
                // time between page finished loading and initialization running
                const init_time = global.loading.init_end - global.loading.init_start
                const username = global.user ? global.user.username : 'anon'
                console.log(`%c[+] INITIALIZED PAGE ${init_time}ms: ${username}@${global.ENVIRONMENT}`, 'color:orange', this.view)
            }

            // this group of references define everything available to a Page
            return {props, store, socket, time, poker}
        }
        return {}
    },
    setupStore(reducers, initial_state) {
        // create the redux store for the page
        return createStore(combineReducers(
            reducers,
            initial_state,
        ))
    },
    setupAnimation(store, initial_state, autostart) {
        // trigger re-rendering on every requestAnimationFrame
        return startAnimation(store, initial_state, autostart)
    },
    setupPoker(store, time, initial_gamestate) {
        // handle translating incoming messages into frontend animations
        return startPokerProcess(store, time, initial_gamestate)
    },
    setupSocket() {
        // create the websocket connection to the backend
        return {name: 'MockSocket', queue: [], close: () => {}}

    },
    tearDown({socket}) {
        if (socket) {
            socket.close()
        }
    },
    render({store, props}) {
        return props ? <Provider store={store}>
            <div className="table-page" id="react-table-page">
                <Notifications/>
                <Sounds/>
                <TableDebugPanel store={store} gamestate={props.gamestate}>
                    <SwapTable/>
                </TableDebugPanel>
                {/*<br/><br/>*/}
                {/*props.DEBUG ?
                    <ForcedActions/> : null*/}
                {/*props.DEBUG ?
                    <div style={{textAlign: 'center'}}>
                        <AnimationControls full_state={true} expanded={false}/>
                    </div>: null*/}
                {/*props.DEBUG ?
                    <div style={{textAlign: 'center'}}>
                        <AnimationTimeline expanded={false}/>
                    </div>: null*/}
                <TournamentResultModal/>
                <NewVisitorModal/>
            </div>
        </Provider>
        :
        <div id="ticket-not-found">
            Ticket Not Found
        </div>
    },
    mount(props, mount_point) {
        global.page = this.init(props, true)
        ReactDOM.render(
            this.render(global.page),
            mount_point,
        )
    },
}

if (global.react_mount) {
    // we're in a browser, so mount the page
    TableDebugger.mount(global.props, global.react_mount)
}
