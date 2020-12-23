/*eslint no-unused-vars: ["error", { "ignoreRestSiblings": true }]*/

// special websocket message types used for managing the connection
const HELLO_TYPE = 'HELLO'
const GOT_HELLO_TYPE = 'GOT_HELLO'
const PING_TYPE = 'PING'
const PING_RESPONSE_TYPE = 'PING'
const RECONNECT_TYPE = 'RECONNECT'
const TIME_SYNC_TYPE = 'TIME_SYNC'

const BACKGROUND_ACTIONS = ['CHAT', TIME_SYNC_TYPE, PING_TYPE, HELLO_TYPE]  // dont show the loading bar for these actions

export const dump_message_history = (state) => {
    const {websocket} = state || global.page.store.getState()
    return {
        http_to_backend: [{
            'url': global.location.pathname,
            'method': 'GET',
            'params': {'props_json': 1},
            'username': global.user ? global.user.username : null,
        }],
        http_to_frontend: [{
            'class': 'JsonResponse',
            'status_code': 200,
            'json': global.props,
        }],
        ws_to_backend: websocket.sent,
        ws_to_frontend: websocket.received,
    }
}
global.dump_message_history = dump_message_history


/* Socket wrapper that gracefully handles disconnects and passes messages to redux as actions. */
export class SocketRouter {
    constructor(store, notifier, loadStart, loadFinish, socket_path, time) {
        // takes a redux store, optional functions to display notifications & loading bars, and an optional socket_url
        const noop = () => {}

        this.ready = false
        this._initialSetupFinished = false
        this.queue = []
        this.reconnects = -1
        this.delay = 0
        this.sent_seq_num = 0
        this.recv_seq_num = 0
        this.store = store || {dispatch: noop}
        this.time = time || {}
        this.notifier = notifier || noop
        this.loadStart = loadStart || noop
        this.loadFinish = loadFinish || noop
        this.socket_url = this._socketURL(socket_path)
        this.disconnected_timeout = null
        this._setupSocket()
        global.addEventListener('unload', this.close.bind(this, false))  // send proper disconnect when page is closed
    }
    send_json(message) {
        const strmessage = JSON.stringify(message)
        const {type, TIMESTAMP, ...data} = message

        if (this.ready) {
            console.log(`%c[<] SENT ${this.sent_seq_num}:`, 'color:blue', (type || ''), data)
            this.socket.send(strmessage)
            this.store.dispatch({type: 'SOCKET_SENT', message})
            return true
        } else if (type == HELLO_TYPE || type == PING_TYPE) {
            if (this.socket) {
                console.log(`%c[<] SENT ${this.sent_seq_num}:`, 'color:blue', (type || ''), data)
                this.socket.send(strmessage)
                this.store.dispatch({type: 'SOCKET_SENT', message})
                return true
            } else {
                // dont send control msgs while socket is down, don't bother queueing either
                console.log('%c[<] NOT SENDING: ', 'color:red', (type || ''), data)
                return false
            }
        } else {
            if (this._initialSetupFinished) {
                console.log('%c[!] QUEUED:', 'color:red', (type || ''), data)
            }
            this.queue.push(message)
        }
        return false
    }
    send_action(type, data = {}) {
        if (!BACKGROUND_ACTIONS.includes(type)) {
            this.loadStart()
        }
        this.notifier(type + '...', true)
        const TIMESTAMP = Date.now()
        const SEQ_NUM = this.sent_seq_num++
        return this.send_json({TIMESTAMP, SEQ_NUM, ...data, type})
    }
    _setupSocket() {
        if (this.disconnected_timeout) {
            clearTimeout(this.disconnected_timeout)
            this.disconnected_timeout = null
        }
        this.ready = false
        this._start_connection_ts = Date.now()
        this.socket = new WebSocket(this.socket_url)
        this.socket.onopen = this._onopen.bind(this)
        this.socket.onclose = this.close.bind(this, true)  // reconnect if socket closes unexpectedly
    }
    _socketURL(socket_path) {
        const host = global.location.hostname
        const port = global.location.port ? ':' + global.location.port : ''
        const prefix = global.location.protocol == 'https:' ? 'wss:' : 'ws:'
        let path = socket_path || global.location.pathname
        path = path.endsWith('/') ? path.substring(0, path.length-1) : path
        return `${prefix}//${host}${port}${path}/`
    }

    _onopen() {
        // timing
        this._finished_connection_ts = Date.now()
        this.delay = (this._finished_connection_ts - this._start_connection_ts)/2

        console.log(`%c[+] SOCKET CONNECTED ${this.delay * 2}ms`, 'color:orange')
        if (this.disconnected_timeout) {
            clearTimeout(this.disconnected_timeout)
            this.disconnected_timeout = null
        }
        this.socket.onmessage = this._onmessage.bind(this)
        this.reconnects++
        this.store.dispatch({
            type: 'SOCKET_CONNECTED',
            delay: this.delay,
            reconnects: this.reconnects,
        })
        this.notifier('Checking server sync...', true)
        this.send_action(HELLO_TYPE, {
            page: document.title,
            url: document.location.toString(),
            component: global.component,
        })
        this._flush()

        if (!this.time_sync_id) {
            this.time_sync_id = setTimeout(() => {
                this.time_sync_sent = Date.now()
                this.send_action(TIME_SYNC_TYPE)
                this.time_sync_id = null
            }, 5000)
        }
    }
    close(reopen=false) {
        this.store.dispatch({
            type: 'SOCKET_DISCONNECTED',
            delay: this.delay,
            reconnects: this.reconnects,
        })
        if (this.reconnects != -1) {
            console.log('%c[X] DISCONNECTED:', 'color:red', (new Date()).toTimeString().split(' ')[0])
        }
        const noop = () => {}
        this.socket = this.socket || {}
        this.socket.close = this.socket.close || noop
        this.socket.onmessage = noop
        this.socket.onopen = noop
        this.socket.onclose = noop
        if (reopen) {
            // dont hammer the server by having everyone reconnect at the same time
            const random_wait = 2 + Math.round(Math.random()*4*10)/10
            this.notifier('Websocket disconnected, attempting to reconnect in 4s...', true)
            console.log(`%c[*] ATTEMPTING TO RECONNECT IN ${random_wait}s...`, 'color:orange')
            if (!this.disconnected_timeout) {
                this.disconnected_timeout = setTimeout(::this._setupSocket, random_wait * 1000)
            }
        }
        this.ready = false
        this.socket.close()
        this.socket = null
    }
    _flush() {
        this.queue.reverse()
        if (this.ready)
            this.queue = this.queue.filter(action => !this.send_json(action))
        this.queue.reverse()
        return this.queue
    }
    _onmessage(str_message) {
        const message = {...JSON.parse(str_message.data), SEQ_NUM: this.recv_seq_num++}
        // Timing-critical branches
        if (this._initialSetupFinished) {
            this.delay = this.time.getActualTime() - message.TIMESTAMP
        }
        if (message.type == TIME_SYNC_TYPE) {
            this.time_sync_recv = Date.now()
            this.delay = (this.time_sync_recv - this.time_sync_sent) / 2                  // latency = rtt/2
            this.time.setActualTime(Math.round(Number(message.TIMESTAMP)) + this.delay)   // server_time = server_timestamp + latency
        }
        if (!this.time_sync_id) {
            this.time_sync_id = setTimeout(() => {
                this.time_sync_sent = Date.now()
                this.send_action(TIME_SYNC_TYPE)
                this.time_sync_id = null
            }, this.delay > 1500 ? 5000 : (5 * 60 * 1000))
        }

        if ('requestIdleCallback' in window) {
            global.requestIdleCallback(() => {
                this.store.dispatch({
                    type: 'SOCKET_RECEIVED',
                    delay: this.delay,
                    reconnects: this.reconnects,
                    message,
                })
            }, {timeout: 200})
        } else {
            this.store.dispatch({
                type: 'SOCKET_RECEIVED',
                delay: this.delay,
                reconnects: this.reconnects,
                message,
            })
        }
        const {type, TIMESTAMP, SEQ_NUM, ...data} = message
        console.groupEnd()
        console.groupCollapsed(`%c[>] RECV ${SEQ_NUM}:`, 'color:green', (type || ''), data)

        if (message.details)
            console.log(message.details)

        if (message.type == GOT_HELLO_TYPE) {
            if (global.user && !message.user_id) {
                // we are logged in but backend thinks we aren't, happens on runserver reload
                // because backend lost our session auth info, have to reconnect
                console.log('RECONNECTING due to runserver reload...')
                global.location.reload()
            }
            this.ready = true
            this._initialSetupFinished = true
            this._flush()
            this.loadFinish()

            // TODO: refactor this out of the websockets code, or make it officially depend on warped-time
            const system_time = Date.now()
            const server_time = Math.round(Number(TIMESTAMP)) + this.delay
            this.time.setActualTime(server_time)

            console.log('-'.repeat(72))
            console.log(
                ' USER SYSTEM TIME ',     system_time, '\n',
                'SERVER TIME      ',      server_time, '\n',
                'SOCKET LATENCY   ',      this.delay, '\n',
                'TOTAL CLOCK OFFSET',    this.time.server_offset, '\n',
            )
            console.log('-'.repeat(72))

            const latency_desc = this._humanizeSpeed(this.delay)

            this.notifier(
                `Websocket Connection Speed: ${this.delay.toFixed(0)}ms (${latency_desc})` +
                (this.reconnects ?
                    ` ${this.reconnects} reconnects.`
                  :''),
                false,
            )
            console.log('%c[i] LATENCY:', 'color:lightblue', `${this.delay.toFixed(0)}ms (${latency_desc})`)
            if (this.reconnects)
                console.log('%c[i] RECONNECTS:', 'color:orange', this.reconnects)
            setTimeout(this.notifier, 3000)  // hide notifier after 3sec
        } else if (message.type == RECONNECT_TYPE) {
            // dont bother reconstrucitng a socket, just refresh the page
            global.location.reload()
        } else if (message.type == PING_TYPE) {
            this.send_action(PING_RESPONSE_TYPE)
        }

        // if response has any errors, display them (an error can be a plain str or a dict)
        // e.g. errors = ['text1', {text: 'text2'}, {style: 'success', text: 'text3'}]
        (message.errors || []).map(error =>
            this.store.dispatch({type: 'NOTIFICATION', notification: {
                type: 'error',
                bsStyle: error.style || 'danger',
                title: 'Websocket Error',
                description: error.text || error,
            }}))

        if (type) {
            if ('requestIdleCallback' in window) {
                global.requestIdleCallback(() => {
                    this.store.dispatch(message)
                    this.loadFinish()
                    this.notifier()
                }, {timeout: 200})
            } else {
                this.store.dispatch(message)
                this.loadFinish()
                this.notifier()
            }
        }
        console.groupEnd()
    }

    _humanizeSpeed(milliseconds) {
        if (milliseconds < 100) return 'responsive'
        if (milliseconds < 200) return 'fast'
        if (milliseconds < 500) return 'ok'
        if (milliseconds < 800) return 'slow'
        if (milliseconds < 1200) return 'very slow'
        if (milliseconds > 1200) return 'extremely bad'
    }
}

global.SocketRouter = SocketRouter


// class Socket {
//     constructor(store) {
//         store.onStateChange(::this.handleStoreChange)
//         this._last_sent = null
//     }
//     handleStoreChange(getState) {
//         const new_sent = getState().websocket.sent
//         if (new_sent != this._last_sent) {
//             for (let msg of sent) {
//                 this.handleSend(msg)
//             }
//         }
//     }
//     handleSend(msg) {
//         this.socket.send(msg)
//     }
//     handleReceive(msg) {
//         this.store.dispatch('WS_RECEIVE')
//         this.store.dispatch(msg)
//     }
// }
