import {anim_delay, frontend_anims_from_backend_anim} from '@/poker/animations'
import {calculateTableCSS} from '@/poker/css.desktop'
import {calculateTableCSS as calculateTableCSSMobile } from '@/poker/css.mobile'

import {is_mobile} from '@/util/browser'
import {ljust} from '@/util/javascript'


var requestAnimationFrame = global.requestAnimationFrame || ((f) => setTimeout(f, 0))


const getLastAnimationTime = (anim_queue) => {
    let former_time = -1
    for (let anim of anim_queue) {
        // if any animations start after END_SNAPTO, move the END_SNAPTO after them
        if (anim.start_time >= former_time) {
            former_time = anim.start_time
        }
        // if any animations end after END_SNAPTO starts, move END_SNAPTO after them
        if (anim.end_time != Infinity && anim.end_time >= former_time) {
            // make sure final SNAPTO starts after everything in the animation set
            former_time = anim.end_time
        }
        // both start and end checks to ensure former_time comes after both
        // anims with duration, and instant BECOMEs with no duration
    }
    if (former_time === -1 || anim_queue.length == 0) {
        console.log('Could not find last animation time for empty or malformed anim_queue')
        debugger
    }
    return former_time
}

function adjust_final_snapto(anim_queue) {
    if (!anim_queue.length) return
    if (anim_queue.slice(-1)[0].type != 'BECOME') {
        console.log({anim_queue})
        throw 'No SNAPTO found in anim_queue! anim_queue must contain at least one SNAPTO:BECOME.'
    }
    if (anim_queue.length > 1) {
        // label the first and last SNAPTO for easier debugging
        let first_snapto = anim_queue[0]
        first_snapto.source_type = first_snapto.source_type.replace('SNAPTO', 'INIT_SNAPTO')
        let last_snapto = anim_queue.slice(-1)[0]
        last_snapto.source_type = last_snapto.source_type.replace('SNAPTO', 'END_SNAPTO')

        // make sure END_SNAPTO nevers starts before previous animations end
        last_snapto.start_time = getLastAnimationTime(anim_queue) + 1
    }
}

export const new_gamestate_animations = (animations, start_time, note) => {
    // maybe determine start_at here
    // in the event of too many queued animations, start_at should == now()
    let anims_to_dispatch = []

    const first_animation_start_time = start_time
    let anim_start_time = start_time

    let css = {}
    // calculate CSS positions of everything based on initial SNAPTO state
    if (animations[0] && animations[0].type == 'SNAPTO') {
        const initial_gamestate = animations[0].value
        if (is_mobile()) {
            css = calculateTableCSSMobile(initial_gamestate)
        } else {
            css = calculateTableCSS(initial_gamestate)
        }
    }

    if (global.DEBUG) {
        console.groupCollapsed(
            '%cTRANSLATING ANIMATIONS:', 'color:orange',
            ljust(animations.map(anim => anim.type).join(', '), 49),
            {backend: animations},
        )
    }

    // translate backend anims to frontend
    for (let animation of animations) {
        let next_anims = []
        try {
            next_anims = frontend_anims_from_backend_anim(anim_start_time, animation, css)
        } catch(e) {
            console.log(
                `%cFailed to translate ${animation.type} into frontend animation! ${e.message || ''}`,
                'color:red',
                animation,
            )
        }

        if (global.DEBUG) {
            const next_types = ljust(next_anims.map(anim => anim.type).join(', '), 40)
            console.log(
                ' ', anim_start_time, ljust(animation.type, 14),
                '->', next_types, ljust(`${anim_delay(animation.type)}ms`, 6),
                {frontend: next_anims},
            )
        }

        // tag animations with action that triggered them for easier debugging
        anims_to_dispatch = [
            ...anims_to_dispatch,
            ...next_anims.map(anim => ({
                ...anim,
                source_type: `${note}:${animation.type}`,
            }))
        ]

        anim_start_time += anim_delay(animation.type)
    }

    // adjust last SNAPTO timing to prevent overwriting an animation
    adjust_final_snapto(anims_to_dispatch)

    if (global.DEBUG) {
        console.log(
            'ANIMATION DURATION:', first_animation_start_time,
            '-> to', anim_start_time,
            '                      Total:',
            anim_start_time - first_animation_start_time, 'ms',
        )
        console.log('-'.repeat(72))
        console.groupEnd()
    }

    return anims_to_dispatch
}

export class PokerDispatcher {
    constructor(store, time, initial_state, server_time) {
        this.store = store
        this.time = time
        this.store.subscribe(::this.handleStateChange)
        this.last_version = 0
        this.initial_state = initial_state
        if (server_time) this.time.setActualTime(server_time)
        this.setInitialState(initial_state)
    }
    setInitialState(initial_state) {
        const {
            table, players, chat, sidebets, last_stack_at_table, table_locked
        } = initial_state
        this.store.dispatch({
            type: 'UPDATE_GAMESTATE',
            table,
            chat,
            players,
            sidebets,
            last_stack_at_table,
            table_locked,
            animations: [{
                type: 'SNAPTO',
                value: {table, players},
            }],
            TIMESTAMP: 0,
            SEQ_NUM: -1,
        })
    }
    getNextAnimStartTime(anim_queue) {
        // make sure next batch of animations starts after currently running ones finish
        let next_anims_start = this.time.getActualTime()
        const end_of_existing_anims = anim_queue.length ?
            getLastAnimationTime(anim_queue)
          : next_anims_start - 1

        // if we're over 5 seconds behind the currently running animations
        if (end_of_existing_anims - 8000 > next_anims_start) {
            console.log(
                '%c[!] Frontend animations were over 5 seconds behind newest gamestate!', 'color:red',
                '(set animation speed to 50x for 1 second)',
                {next_anims_start, end_of_existing_anims, queue: anim_queue},
            )
            this.store.dispatch({type: 'SET_ANIMATION_SPEED', speed: 500})
            setTimeout(() => this.store.dispatch({type: 'SET_ANIMATION_SPEED', speed: 1}), 1000)
        }
        // if we're less than 5 seconds behind, just run next anims once current ones finish
        else if (end_of_existing_anims > next_anims_start) {
            next_anims_start = end_of_existing_anims + 1
        }
        return next_anims_start
    }
    handleStateChange() {
        // console.log('RUNNING POKER DISPATCHER')
        const {gamestate, animations} = this.store.getState()
        const version = gamestate.version

        // if we got a new gamestate upate, add its animations to the animations.queue
        if (version != this.last_version) {
            this.last_version = version

            // compute start time for next animation set
            const next_anims_start = version == -1 ?
                0 : this.getNextAnimStartTime(animations.queue)

            const next_anims = new_gamestate_animations(
                gamestate.next_animation_set,
                next_anims_start,
                version,
            )

            if (version == -1) {
                this.store.dispatch({type: 'ANIMATE', animations: next_anims})
            } else {
                requestAnimationFrame(() => {
                    this.store.dispatch({type: 'ANIMATE', animations: next_anims})
                })
            }
        }
    }
}

export const startPokerProcess = (store, time, initial_state) => {
    return new PokerDispatcher(store, time, initial_state)
}
