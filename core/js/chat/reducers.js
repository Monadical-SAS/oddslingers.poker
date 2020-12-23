/*************************** ACTIONS ******************************************/
export const sendChatMessage = (text) => ({
    type: 'SUBMIT_ACTION',
    action: {
        type: 'CHAT',
        args: {text},
    }
})


/************************** REDUCERS ******************************************/

const jQuery = global['$']

export const initial_state = {
    lines: [],
    resolution: 'desktop',
}

export const chat_side_effects = () => {
    // Scroll history to bottom when new lines come in
    if (!jQuery) return

    jQuery('.ss-content').animate({scrollTop: jQuery('.ss-content').prop('scrollHeight')}, 1000)
}

export const chat = (state=initial_state, action) => {
    switch (action.type) {
        case 'UPDATE_GAMESTATE':
        case 'UPDATE_TOURNAMENT_STATE':
        case 'UPDATE_CHAT':
            chat_side_effects(action)
            return {...state, lines: [...state.lines, ...(action.chat || [])].slice(-100)}
        case 'CHANGE_RESOLUTION':
            return {...state, resolution: action.resolution}
        default:
            return state
    }
}
