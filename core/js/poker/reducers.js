import {getLoggedInPlayer} from '@/poker/selectors'


/*************************** ACTIONS ******************************************/
export const onSubmitAction = (type, args) => ({
    type: 'SUBMIT_ACTION',
    action: {type, ...args}
})

export const clearLog = () => ({
    type: 'UPDATE_LOG',
    lines: {}
})

export const sitIn = () => ({
    type: 'SUBMIT_ACTION',
    action: {type: 'JOIN_TABLE'}
})

export const joinTable = (props) => ({
    type: 'SUBMIT_ACTION',
    action: {type: 'JOIN_TABLE', args: {position: props.position}}
})

export const updateCurrentBet = (amount) => ({
    type: 'UPDATE_CURRENT_BET',
    current_bet: amount
})

export const windowResize = (props) => ({
    type: 'CHANGE_RESOLUTION',
    resolution: props.resolution
})

/************************** REDUCERS ******************************************/
export const initial_state = {
    version: -1,
    is_private: false,
    next_animation_set: [],
    logged_in_player: null,
    hand_history: [],
    current_bet: null,
    joining_table: false,
    action_submitted: false,
    table_stats: {
        avg_stack: null,
        players_per_flop_pct: null,
        hands_per_hour: null,
        avg_pot: null,
    },
    new_tourney_results: [],
    player_winnings: []
}

export const gamestate = (state=initial_state, action) => {
    switch (action.type) {
        case 'UPDATE_GAMESTATE': {
            // ignore first placeholder animations set: ['animations']
            if (action.animations && action.animations[0] === 'animations') {
                action.animations = null
            }

            const logged_in_player = getLoggedInPlayer(action.players)
            let joining_table = state.joining_table
            if (logged_in_player && joining_table) {
                joining_table = false
            }

            let action_submitted = state.action_submitted
            if (logged_in_player
                && (logged_in_player.id == action.table.to_act_id
                || logged_in_player.available_actions.some(
                    action => [
                        "SET_PRESET_CHECK",
                        "SET_PRESET_CALL",
                        "SET_PRESET_CHECKFOLD"
                    ].includes(action))
                )
            ){
                action_submitted = false
            }

            return {
                ...state,
                version: action.SEQ_NUM || state.version + 1,
                next_animation_set: action.animations || [],
                table_stats: action.table_stats || initial_state.table_stats,
                new_tourney_results: action.new_tourney_results || initial_state.new_tourney_results,
                last_stack_at_table: action.last_stack_at_table || state.last_stack_at_table,
                table_locked: action.table_locked || state.table_locked,
                action_submitted,
                joining_table,
                logged_in_player,
            }
        }
        case 'SUBMIT_ACTION': {
            // TODO: move this into websocket reducers
            const {type, ...args} = action.action  // unpack backend action
            setTimeout(() =>
                window.page.socket.send_action(type, {...args || {}}),
                0)
            switch (type) {
                case 'JOIN_TABLE':
                    return {...state, joining_table: true}
                case 'FOLD':
                case 'CALL':
                case 'CHECK':
                case 'BET':
                case 'RAISE_TO':
                    return {...state, action_submitted: true}
            }
            return state
        }
        case 'UPDATE_HANDHISTORY': {
            return {
                ...state,
                'hand_history': action.hand_history
            }
        }
        case 'UPDATE_CURRENT_BET': {
            return {...state, current_bet: action.current_bet}
        }
        case 'UPDATE_PLAYER_WINNINGS': {
            return {
                ...state,
                'player_winnings': action.player_winnings
            }
        }
        default: {
            return state
        }
    }
}
