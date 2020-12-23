import {select_props, bet_amounts} from '@/poker/components/bet-slider'

const canShortcut = (player) => {
    const activeElem = document.activeElement
    return player && (activeElem == document.body || $('#bet-input').is(':focus'))
}

const fold = (store) => {
    const player = store.getState().gamestate.logged_in_player
    const can_fold = player.available_actions.includes('FOLD')
    if (can_fold){
        store.dispatch({'type': 'SUBMIT_ACTION','action': {'type': 'FOLD'}})
    }
    const preactions = global.preactionsComponent
    if (preactions && preactions.props.can_set_preset_checkfold){
        preactions.setPresetCheckFold(
            !preactions.state.preset_checkfold
        )
    }
}

const call_check = (store) => {
    const player = store.getState().gamestate.logged_in_player
    const can_check = player.available_actions.includes('CHECK')
    const can_call = player.available_actions.includes('CALL')
    if (can_check){
        store.dispatch({'type': 'SUBMIT_ACTION','action': {'type': 'CHECK'}})
    } else if (can_call){
        store.dispatch({'type': 'SUBMIT_ACTION','action': {'type': 'CALL'}})
    }
    const preactions = global.preactionsComponent
    if (preactions){
        const {
            can_set_preset_call,
            can_set_preset_check,
            total_call_amt,
        } = preactions.props

        if (can_set_preset_check){
            preactions.setPresetCheck(
                !preactions.state.preset_check
            )
        } else if (can_set_preset_call){
            preactions.setPresetCall(
                total_call_amt,
                !preactions.state.preset_call
            )
        }
    }
}

const bet_raise = (store) => {
    const player = store.getState().gamestate.logged_in_player
    const can_bet = player.available_actions.includes('BET')
    const can_raise = player.available_actions.includes('RAISE_TO')
    const amt = store.getState().gamestate.current_bet || player.min_bet
    if (can_bet || can_raise){
        store.dispatch({'type': 'SUBMIT_ACTION','action': {
            'type': can_raise ? 'RAISE_TO' : 'BET',
            'amt': Number(amt)
        }})
    }
}

const all_in = (store) => {
    const player = store.getState().gamestate.logged_in_player
    const can_raise = player.available_actions.includes('RAISE_TO')
    const can_bet = player.available_actions.includes('BET')
    const bets = bet_amounts(select_props(store.getState())).map(bet => bet.amt)
    if (can_raise || can_bet){
        store.dispatch({'type': 'SUBMIT_ACTION','action': {
            'type': can_raise ? 'RAISE_TO' : 'BET',
            'amt': bets.slice(-1)[0] || player.min_bet
        }})
    }
}

const decrease_bet = (store) => {
    const player = store.getState().gamestate.logged_in_player
    const amt = Number(store.getState().gamestate.current_bet || player.min_bet)
    const bets = bet_amounts(select_props(store.getState())).map(bet => bet.amt)
    const closest_amt = bets.reduce((p, c) => Math.abs(c-amt)<Math.abs(p-amt) ? c : p)
    const idx = bets.indexOf(closest_amt)
    const valid_idx = Math.min(Math.max(idx - 1, 0), bets.length - 1)
    store.dispatch({
        'type': 'UPDATE_CURRENT_BET',
        'current_bet': bets[valid_idx]
    })
}

const increase_bet = (store) => {
    const player = store.getState().gamestate.logged_in_player
    const amt = Number(store.getState().gamestate.current_bet || player.min_bet)
    const bets = bet_amounts(select_props(store.getState())).map(bet => bet.amt)
    const closest_amt = bets.reduce((p, c) => Math.abs(c-amt)<Math.abs(p-amt) ? c : p)
    const idx = bets.indexOf(closest_amt)
    const valid_idx = Math.min(Math.max(idx + 1, 0), bets.length - 1)
    store.dispatch({
        'type': 'UPDATE_CURRENT_BET',
        'current_bet': bets[valid_idx]
    })
}

const shortcut_mapping = {
    'F': fold,
    'C': call_check,
    'B': bet_raise,
    'R': bet_raise,
    'A': all_in,
    'ARROWLEFT': decrease_bet,
    'ARROWRIGHT': increase_bet,
}

export const addKeyboardShortcuts = (store) => {
    let keys = {}

    // Clean pressed keys when losing window focus
    global.onblur = () => keys = {}

    const keyHandler = (e) => {
        keys[e.keyCode] = e.type == 'keydown'
        Object.keys(keys).map(k => keys[k] == false ? delete keys[k] : keys[k])
        if (Object.keys(keys).length != 1) return

        // Prevent multiple requests
        if (store.getState().gamestate.action_submitted) return

        const player = store.getState().gamestate.logged_in_player
        if (!canShortcut(player)) return

        const key = e.key.toUpperCase()
        if (!(key in shortcut_mapping)) return

        shortcut_mapping[key](store)
    }
    global.addEventListener("keydown", keyHandler, true)
    global.addEventListener("keyup", keyHandler, true)
}
