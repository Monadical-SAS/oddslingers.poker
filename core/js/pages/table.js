import React from 'react'
import ReactDOM from 'react-dom'
import parse from 'date-fns/parse'
import differenceInSeconds from 'date-fns/difference_in_seconds'

import {createStore, combineReducers} from 'redux'
import {Provider} from 'react-redux'
import {animationsReducer, startAnimation} from 'redux-time'

import {initial_state as anim_state} from 'redux-time/node/reducers'

import {websocket} from '@/websocket/reducers'
import {gamestate} from '@/poker/reducers'
import {chat} from '@/chat/reducers'
import {notifications} from '@/notifications/reducers'
import {sounds} from '@/sounds/reducers'
// import {video} from '@/video/reducers'

import {sidebet} from '@/sidebets/reducers'

import {Notifications} from '@/notifications/containers'
import {Sounds} from '@/sounds/containers'
import {SocketRouter} from '@/websocket/main'
import {NewVisitorModal} from '@/components/new-visitor-modal'
import {TournamentResultModal} from '@/components/tournament-modals'
import {startPokerProcess} from '@/poker/process'
// import {ForcedActions} from '@/poker/debugging'

import {SwapTable} from '@/components/swaptable'
import {addDebugKeycommands} from '@/poker/debugging'
import {addKeyboardShortcuts} from '@/poker/keyboard_shortcuts'
import {asyncGetUserBalance} from '@/util/browser'

global.loading = global.loading || {end: Date.now()}
if (!global.history) {
    global.history = global.history || {pushState: () => {}}
}

export const Table = {
    view: 'ui.views.pages.Table',

    init(props, autostart=false) {
        global.loading.init_start = Date.now()
        if (global.DEBUG) {
            // time between page finished loading and initialization running
            const parse_time = global.loading.init_start - global.loading.end
            console.groupCollapsed(`%c[+] PARSED JS ${parse_time}ms`, 'color:orange')
        }
        // set the navbar url to the pretty + UUID Version
        const {path, name} = props.gamestate.table
        const safe_name = (name.replace(/-/g, '').replace(/ /g, '-').replace(/\//g, ':'))
        global.history.pushState({}, name, `${path}${safe_name}/`)

        // reset last_action_timestamp if table has been doormant for >60s
        const last_action = parse(props.gamestate.table.last_action_timestamp)
        const now = Date.now()
        if (differenceInSeconds(now, last_action) > 60) {
            props.gamestate.table.last_action_timestamp = Date.now()
        }

        const initial_state = {
            animations: {
                ...anim_state,
                max_time_travel: 300,
            }
        }

        const store = this.setupStore({
            websocket,
            gamestate,
            chat,
            notifications,
            sounds,
            // video,
            sidebet,
            animations: animationsReducer,
            // ...(props.SHOW_VIDEO_STREAMS ? [video] : []),
        }, initial_state)
        const time = this.setupAnimation(store, {}, autostart)
        const poker = this.setupPoker(store, time, props.gamestate)
        const socket = this.setupSocket(store, time, props.gamestate.table.path)

        global.loading.init_end = Date.now()
        if (global.DEBUG) {
            console.groupEnd()
            // time between page finished loading and initialization running
            const init_time = global.loading.init_end - global.loading.init_start
            const username = global.user ? global.user.username : 'anon'
            console.log(`%c[+] INITIALIZED PAGE ${init_time}ms: ${username}@${global.ENVIRONMENT}`, 'color:orange', this.view)
        }
        if (global.DEBUG || (global.user && global.user.is_staff)) {
            addDebugKeycommands()
        }
        if(global.user && global.user.keyboard_shortcuts){
            addKeyboardShortcuts(store)
        }

        // get user balance async
        asyncGetUserBalance(() => {
            store.dispatch({'type': 'UPDATE_GAMESTATE'})
        })

        // this group of references define everything available to a Page
        return {props, store, time, poker, socket}
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
    setupSocket(store, time, path) {
        // create the websocket connection to the backend
        if (!global.WebSocket) return {name: 'MockSocket', close: () => {}}

        return new SocketRouter(
            store,
            global.navbarMessage,
            global.loadStart,
            global.loadFinish,
            path,
            time,
        )

    },
    tearDown({socket}) {
        if (socket) {
            socket.close()
        }
    },
    render({store}) {
        return <Provider store={store}>
            <div className="table-page" id="react-table-page">
                <Notifications/>
                <Sounds/>
                <SwapTable/>
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
    Table.mount(global.props, global.react_mount)
}
