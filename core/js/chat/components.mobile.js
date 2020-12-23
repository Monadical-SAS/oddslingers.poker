import {reduxify} from '@/util/reduxify'

import {ChatContainer} from '@/chat/components'

import {is_portrait} from '@/util/browser'
import {getGamestate, getLoggedInPlayer} from "@/poker/selectors"


export const Chat = reduxify({
    mapStateToProps: (state) => {
        const {players} = getGamestate(state)
        const player = getLoggedInPlayer(players)

        const logged_in_id = player && player.id
        const logged_in = logged_in_id !== null
        return {
            show: !logged_in && is_portrait(),
            chat: state.chat,
        }
    },
    ...ChatContainer
})
