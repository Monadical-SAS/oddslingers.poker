import React from 'react'
import {reduxify} from '@/util/reduxify'

import {LOGGED_USER_SPECIFIC_SOUNDS} from '@/constants'
import {getGamestate, getLoggedInPlayer} from '@/poker/selectors'
import {localStorageGet} from '@/util/browser'
import {generateUUID} from '@/util/javascript'
import {SoundComponent} from '@/sounds/components'
import {clearSounds} from '@/sounds/reducers'


const getSoundForPlayer = (sound, logged_in_player) => {
    if (LOGGED_USER_SPECIFIC_SOUNDS.hasOwnProperty(sound)) {
        if (logged_in_player && logged_in_player.winner) {
            return LOGGED_USER_SPECIFIC_SOUNDS[sound]
        }
    }
    return sound
}

export const Sounds = reduxify({
    mapStateToProps: (state) => {
        const {table, players} = getGamestate(state)
        const logged_in_player = getLoggedInPlayer(players)
        let muted_sounds
        if (state.sounds.muted === undefined) {
            muted_sounds = global.user ?
                global.user.muted_sounds
                : localStorageGet('muted_sounds', false)
        } else {
            muted_sounds = state.sounds.muted
        }
        const sound = getSoundForPlayer(
            table.sound || state.sounds.sound,
            logged_in_player
        )
        return { sound, muted_sounds }
    },
    mapDispatchToProps: {
        clearSounds
    },
    render: ({sound, muted_sounds, clearSounds}) => {
        return <div>
            {sound ?
                <SoundComponent sound={sound}
                                muted_sounds={muted_sounds}
                                key={generateUUID()}
                                clearSounds={clearSounds}/>
                : null}
        </div>
    }
})
