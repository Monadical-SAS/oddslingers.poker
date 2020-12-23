import React from 'react'

import {play_sound, isEmbedded} from '@/util/browser'


export class SoundComponent extends React.Component {

    componentDidMount() {
        if (!this.props.muted_sounds && !isEmbedded()) {
            play_sound(`/static/audio/${this.props.sound}.mp3`)
            this.props.clearSounds()
        }
    }

    render() {
        return null
    }
}
