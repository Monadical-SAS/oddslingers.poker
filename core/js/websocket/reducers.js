export const initial_state = {
    ready: false,
    sent: [],
    received: [],
    max_history: 10,
    reconnects: -1,
    delay: 0,
}

// keep first n elements and last n elements of list, trimming excess out of the middle
const trim_list = (list, first=10, last=100) => {
    if (list.length <= first + last)
        return list
    return [
        ...list.slice(0, first),
        ...list.slice(-last),
    ]
}

export const websocket = (state=initial_state, action) => {
    switch (action.type) {
        case 'SOCKET_SENT':
            return {
                ...state,
                sent: [
                    ...trim_list(state.sent),
                    action.message,
                ],
            }
        case 'SOCKET_RECEIVED':
            return {
                ...state,
                delay: action.delay,
                reconnects: action.reconnects,
                received: [
                    ...trim_list(state.received),
                    action.message,
                ],
            }
        case 'SOCKET_CONNECTED':
            return {
                ...state,
                ready: true,
                delay: action.delay,
                reconnects: action.reconnects,
                sent: [
                    ...state.sent,
                    {
                        type: 'websocket.connect',
                        TIMESTAMP: (new Date).getTime(),
                    },
                ],
            }
        case 'SOCKET_DISCONNECTED':
            return {
                ...state,
                ready: false,
                delay: action.delay,
                reconnects: action.reconnects,
                sent: [
                    ...state.sent,
                    {
                        type: 'websocket.disconnect',
                        TIMESTAMP: (new Date).getTime(),
                    },
                ],
            }
        default:
            return state
    }
}
