import React from 'react'

import Button from 'react-bootstrap/lib/Button'

import {activeAnimations, currentAnimations,
        computeAnimatedState} from 'redux-time/node/util'

import {onKeyPress, onKonamiCode} from '@/util/browser'
import {dump_message_history} from '@/websocket/main'
import {UP_ARROW, DOWN_ARROW} from '@/constants'

global.activeAnimations = activeAnimations
global.currentAnimations = currentAnimations


export const debugNotify = (title, description, bsStyle='danger') => {
    console.log(title, ':', description)
    global.page.store.dispatch({
        type: 'NOTIFICATION',
        notifications: [
            {
                type: 'debug',
                noIcon: true,
                bsStyle,
                title,
                description,
            }
        ]
    })
}

export const ForcedActions = () =>
    <div>
        Force Next Action: &nbsp;
        <Button onClick={forceAction.bind(this, 'FOLD')}>Fold</Button>
        <Button onClick={forceAction.bind(this, 'CALL')}>Call</Button>
        <Button onClick={forceAction.bind(this, 'CHECK')}>Check</Button>
        <Button onClick={forceAction.bind(this, 'BET')}>Bet</Button>
        <Button onClick={forceAction.bind(this, 'RAISE_TO')}>Raise</Button>
    </div>


global.activeAnims = () => {
    const a = global.s().animations
    return activeAnimations({
        anim_queue: a.queue,
        warped_time: a.warped_time,
        former_time: a.former_time,
    })
}
global.compState = () => {
    const a = global.s().animations
    return computeAnimatedState({
        animations: a.queue,
        warped_time: a.warped_time,
        former_time: a.former_time,
    })
}
global.writeToFile = (obj, fn, sep) => {
    if (sep === undefined)
        sep = "  "
    var a = global.document.createElement('a')
    var text = JSON.stringify(obj, null, sep)
    a.href = global.URL.createObjectURL(new Blob([text], {type : 'application/json'}))
    var filename = fn || 'data.json'
    a.download = filename
    // Append anchor to body.
    document.body.appendChild(a)
    a.click()
    // Remove anchor from body
    document.body.removeChild(a)
}

global.stateDump = () => {
    // TODO: write a test that breaks if the schema changes
    const store = global.s()
    return {
        latest_action: store.latest_action,
        msglog: store.msglog,
        version: store.version,
        animations: store.animations,
        server_time: store.server_time,
        logged_in_player: store.logged_in_player,
    }
}

global.bugDump = function(notes, filename) {
    // download a frontend dump to file
    const data_dump = {
        notes,
        dump: global.stateDump(),
    }
    global.writeToFile(data_dump, filename, "  ")
}

export const reportBug = (notes) => {
    pauseFrontend()
    const state = global.page.store.getState()
    const frontend_log = {
        notes,
        user: global.user,
        view: global.props.view,
        url: global.props.url,
        url_name: global.props.url_name,
        settings: {
            'DEBUG': global.props.DEBUG,
            'GIT_SHA': global.props.GIT_SHA,
            'ENVIRONMENT': global.props.ENVIRONMENT,
            'TIME_ZONE': global.props.TIME_ZONE,
        },
        store: {
            animations: state.animations,
            gamestate: state.gamestate,
        },
        time: {
            system_time: (new Date).getTime(),
            server_time: global.page.time.getActualTime(),
            warped_time: global.page.time.getWarpedTime(),
            server_offset: global.page.time.server_offset,
            delay: global.page.socket.delay,
            reconnects: global.page.socket.reconnects,
        },
        ...dump_message_history(state),
    }
    const succeeded = global.page.socket.send_action('REPORT_BUG', {frontend_log})
    if (succeeded) {
        // success message will come in via backend dispatch of a NOTIFICATION
        console.log('[!] Sent bug report...', frontend_log)
        resumeFrontend()
    } else {
        $('#debug-dump-reason').slideDown()
        alert('Failed to submit the bug report, please message us on the Support page! Thank you for your patience!')
        window.open('/support/')
    }
}
global.reportBug = reportBug

export const pauseFrontend = () => {
    global.page.store.dispatch({type: 'SET_SPEED', speed: 0})
}

export const resumeFrontend = () => {
    global.page.store.dispatch({type: 'SET_SPEED', speed: 1})
}

export const pauseBackend = () => {
    global.page.socket.send_action('DEBUG_PAUSE_ACTION')
}

export const resumeBackend = () => {
    global.page.socket.send_action('DEBUG_RESUME_ACTION')
}

export const togglePause = () => {
    if (global.page.game_paused) {
        debugNotify('Resuming backend tablebeat & animations...')
        resumeFrontend()
        resumeBackend()
        global.page.game_paused = false
    } else {
        debugNotify('Pausing backend tablebeat & animations...')
        pauseFrontend()
        pauseBackend()
        global.page.game_paused = true
    }
}

export const forceAction = (type) => {
    debugNotify(`Forcing next action: ${type}...`)
    global.page.socket.send_action('DEBUG_FORCE_ACTION', {action: type})
}

export const nextAction = () => {
    debugNotify('Forcing random next action...')
    global.page.socket.send_action('DEBUG_FORCE_ACTION')
}

export const givePlaytestingChips = () => {
    debugNotify('Giving extra chips for playtesting...')
    global.page.socket.send_action('DEBUG_GIVE_CHIPS')
}

const upLevelCashtables = () => {
    debugNotify('Leveling up on cash tables...', '', 'warning')
    global.page.socket.send_action('DEBUG_UP_LEVEL_CASHTABLES')
}

const downLevelCashtables = () => {
    debugNotify('Leveling down on cash tables...', '', 'warning')
    global.page.socket.send_action('DEBUG_DOWN_LEVEL_CASHTABLES')
}

const upLevelTournaments = () => {
    debugNotify('Leveling up on tournaments...', '', 'warning')
    global.page.socket.send_action('DEBUG_UP_LEVEL_TOURNAMENTS')
}

const downLevelTournaments = () => {
    debugNotify('Leveling down on tournaments...', '', 'warning')
    global.page.socket.send_action('DEBUG_DOWN_LEVEL_TOURNAMENTS')
}

export const addDebugKeycommands = () => {
    if (global.user && global.user.is_staff){
        onKeyPress(UP_ARROW, upLevelCashtables, 'ctrlKey')
        onKeyPress(DOWN_ARROW, downLevelCashtables, 'ctrlKey')
        onKeyPress(UP_ARROW, upLevelTournaments, 'shiftKey')
        onKeyPress(DOWN_ARROW, downLevelTournaments, 'shiftKey')
    }
    onKeyPress("n", nextAction, 'ctrlKey')
    onKeyPress("p", togglePause, 'ctrlKey')
    onKonamiCode(givePlaytestingChips)
}
