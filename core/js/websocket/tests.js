#!/usr/bin/env babel-node

import {assertEqual, runTests} from '@/util/tests'

import {SocketRouter} from '@/websocket/main'


export const socket_setup_tests = {
    test_socket_init() {
        // Stubs for Window dependencies
        class WebSocket {}
        global.WebSocket = WebSocket
        global.addEventListener = () => {}
        global.location = {
            port: null,
            protocol: 'https:',
            hostname: 'tests',
            pathname: '/test/',
            reload() {},
        }

        const router = new SocketRouter()

        assertEqual(router.ready, false,        'Socket router reported ready before connected.')
        assertEqual(router.queue.length, 0,     'Socket router queue was not empty on init.')

        const result = router.send_action({type: 'TEST'})

        assertEqual(
            result,
            'Falsey',
            'Socket router reported message sent even though not connected.',
            a => !a,
        )
        assertEqual(router.queue.length, 1,     'Socket router failed to queue message before connection.')
        assertEqual(router.reconnects, -1,      'Socket router reported reconnects before inital connection.')

    }
}

if (require.main === module) {
    runTests(exports, __filename, process.argv)
}
