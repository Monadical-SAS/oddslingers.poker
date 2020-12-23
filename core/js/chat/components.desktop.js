import {reduxify} from '@/util/reduxify'

import {ChatContainer} from '@/chat/components'


export const Chat = reduxify({
    mapStateToProps: (state, props) => {
        return {
            chat: state.chat,
            is_tournament: props.is_tournament,
        }
    },
    ...ChatContainer
})
