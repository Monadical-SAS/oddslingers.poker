
const initial_state = {
    added_peers: 0,
}

export const video = (state=initial_state, action) => {
    switch (action.type) {
        case 'NEW_PEER':
            return {
                added_peers: state.added_peers + 1,
                nick: action.nick,
                people_online: action.people_online
            }
        default:
            return state
    }
}
