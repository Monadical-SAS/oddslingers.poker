/*************************** ACTIONS ******************************************/
export const playSound = (sound) => ({
    type: 'PLAY_SOUND',
    sound
})

export const clearSounds = () => ({
    type: 'CLEAR_SOUNDS'
})

export const onToggleSound = (mute) => ({
    type: 'TOGGLE_SOUNDS',
    muted: mute
})

/*************************** REDUCERS ******************************************/
const initial_state = {
    sound: '',
    muted: undefined
}

export const sounds = (state=initial_state, action) => {
    switch (action.type) {
        case 'PLAY_SOUND':
            return {
                sound: action.sound,
                muted: state.muted
            }
        case 'TOGGLE_SOUNDS':
            return {
                sound: state.sound,
                muted: action.muted
            }
        case 'CLEAR_SOUNDS':
            return {
                sound: '',
                muted: state.muted
            }
        default:
            return state
    }
}
