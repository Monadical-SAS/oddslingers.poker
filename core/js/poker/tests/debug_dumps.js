import 'colors'
import {loadJson} from '@/util/node'


// dispatch an array of redux actions to a store
export const dispatchActions = (store, actions) => {
    actions.map(action => {
        const action_desc = JSON.stringify(action).slice(0, 80) + '...'
        if (global.DEBUG) {
            console.log('[>] RECV: ', action.type, action_desc)
        }
        store.dispatch(action)
    })
    return store
}

let _cached_dumps = {}

// Given a JS Page and a debug dump, intitialize the page and optionally apply redux actions
export const loadDebugDump = (Page, path, replay=false) => {
    const debug_dump = _cached_dumps[path] || loadJson(path)
    _cached_dumps[path] = debug_dump
    const props = debug_dump.http_to_frontend[0].json
    const dump_view = props.view
    const page_view = Page.view
    if (!dump_view.includes(page_view)) {
        console.log(`[!] Warning, loading debug dump from ${dump_view} into a frontend Page that expects ${page_view}!`.yellow)
    }
    const page = Page.init(props)
    page.debug_dump = debug_dump

    if (page.store && replay) {
        dispatchActions(page.store, debug_dump.ws_to_frontend)
    }

    return page
}

// get the hand number for a given websocket message SEQ_NUM
export const handNumForSeq = (messages, seq_num) => {
    const seq_msg = messages.filter(msg => msg.SEQ_NUM == seq_num)[0]
    return seq_msg.table.hand_number
}

// get the websocket msg SEQ_NUM for a given hand number
export const seqNumForHand = (messages, hand_num) => {
    const msgs_for_hand = messages.filter(msg =>
        msg.table.hand_number == hand_num)
    return msgs_for_hand[0].SEQ_NUM
}

// replay incoming websocket messages up to a given sequence number
export const replayUpTo = (page, seq_num=-1) => {
    // reset the whole page
    page.init(page.props)
    if (seq_num == 0) return page.store
    if (seq_num > 0) {
        // dispatch actions up to given seq_num
        const actions = page.debug_dump.ws_to_frontend.slice(seq_num)
        return dispatchActions(page.store, actions)
    }
    if (seq_num < 0) {
        // negative indexing lets us dispatch up to last action with -1
        const num_msgs = page.debug_dump.ws_to_frontend.length
        const actions = page.debug_dump.ws_to_frontend.slice(num_msgs + seq_num)  // e.g. 10 + (-2) => 8
        return dispatchActions(page.store, actions)
    }
}

// replay incoming websocket messages and animate up to a given seq_num
export const tickUpTo = (page, seq_num) => {
    // reset the whole page, and dispatch actions up to seq_num
    page.store = replayUpTo(page, seq_num)

    // find the animations for the given SEQ_NUM
    const {animations} = page.store.getState()
    const anims_for_seq = animations.queue.filter(anim => {
        const anim_seq_num = anim.source_type.split(':')[0]
        return anim_seq_num == seq_num
    })

    // tick to the start time of the first animation + 100ms
    const start_time = anims_for_seq[0].start_time
    page.store.dispatch({
        type: 'TICK',
        warped_time: start_time + 100,
        former_time: start_time,
    })
    return page.store
}
