import React from 'react'
import ReactDOM from 'react-dom'

import {createStore, combineReducers} from 'redux'
import {Provider} from 'react-redux'

import {websocket} from '@/websocket/reducers'
import {tournament_summary} from '@/tournament_summary/reducers'
import {chat} from '@/chat/reducers'

import {SocketRouter} from '@/websocket/main'
import {TournamentSummaryComponent} from '@/tournament_summary/components'


export const TournamentSummary = {
    view: 'ui.views.pages.TournamentSummary',
    init(props) {
        const time = {
            getActualTime: () => Date.now(),
            setActualTime: () => {}
        }

        const store = this.setupStore({
            websocket,
            tournament_summary,
            chat
        }, {})
        const socket = this.setupSocket(store, time)

        this.setupState(store, props)

        return {socket, store, props}
    },
    setupStore(reducers, initial_state) {
        // create the redux store for the page
        return createStore(combineReducers(
            reducers,
            initial_state,
        ))
    },
    setupSocket(store, time) {
        // create the websocket connection to the backend
        if (!global.WebSocket) return {name: 'MockSocket', close: () => {}}

        return new SocketRouter(
            store,
            global.navbarMessage,
            global.loadStart,
            global.loadFinish,
            '',
            time,
        )
    },
    setupState(store, props) {
        store.dispatch({
            type: 'UPDATE_TOURNAMENT_STATE',
            id: props.id ,
            name: props.name,
            tourney_path: props.tourney_path,
            table_path: props.table_path,
            tournament_status: props.tournament_status,
            game_variant: props.game_variant,
            max_entrants: props.max_entrants,
            buyin_amt: props.buyin_amt,
            entrants: props.entrants,
            user_funds: props.user_funds,
            results: props.results,
            tournament_admin: props.tournament_admin,
            chat: props.chat,
            is_private: props.is_private,
            is_locked: props.is_locked,
        })
        store.dispatch({
            type: 'UPDATE_GAMESTATE',
            players: props.players
        })
    },
    render({store, props}) {
        return <Provider store={store}>
            <TournamentSummaryComponent {...props}/>
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
    TournamentSummary.mount(global.props, global.react_mount)
}
