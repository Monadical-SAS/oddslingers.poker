"""
Live websocket integration tests to direct at a running django server.

./manage.py integration_test sockets''')
"""

import json
import os
import signal
import unittest
import threading

from time import sleep
from websocket import create_connection

from sockets.models import ROUTING_KEY, HELLO_TYPE, GOT_HELLO_TYPE, PING_TYPE
from oddslingers.utils import TimeOutException, timeout_handler, to_json_str


BASE_URL = os.environ.get('ODDSLINGERS_URL', 'http://127.0.0.1:8000')
WS_BASE_URL = os.environ.get(
    'ODDSLINGERS_WS_URL',
    BASE_URL.replace('http://', 'ws://')
            .replace(':443', '')
            .replace(':80', '')
)
VERIFY_SSL = os.environ.get('SERVER_TEST_VERIFY_SSL', 'True') == 'True'
TIMEOUT = int(os.environ.get('SERVER_TEST_TIMEOUT', '5'))
LOAD_FACTOR = int(os.environ.get('SERVER_TEST_LOAD_FACTOR', '1'))
TARGET = 'prod' if VERIFY_SSL else 'dev'

# 0 is equivalent to ssl.CERT_NONE
WS_OPTS = {} if VERIFY_SSL else {'sslopt': {'cert_reqs': 0}}


### Base Test Classes

def connect_socket(url, timeout=TIMEOUT, **kwargs):
    """set up a websocket and return the socket connection object"""

    signal.signal(
        signal.SIGALRM,
        lambda s, f: timeout_handler(s, f, f'connecting ({timeout}s)')
    )
    signal.alarm(timeout)
    try:
        sock = create_connection(url, **kwargs)
        signal.alarm(0)
        return sock
    except Exception:
        signal.alarm(0)
        print(f'[X] Failed to connect, is runserver running on {url}?')
        raise
    except Exception:
        signal.alarm(0)
        raise

def send_json(socket, data: dict, timeout=TIMEOUT):
    """
    send a json-ified dictionary, throws an exception if it takes
    more than [timeout] seconds
    """

    signal.signal(
        signal.SIGALRM,
        lambda s, f: timeout_handler(s, f, f'sending ({timeout}s)')
    )
    signal.alarm(timeout)
    try:
        result = socket.send(to_json_str(data))
        signal.alarm(0)
        return result
    except Exception:
        signal.alarm(0)
        raise

def send_action(socket, action, **kwargs):
    """send a websocket action like {type: 'FOLD'}"""
    send_json(socket, {ROUTING_KEY: action, **kwargs})

def recv_json(socket, timeout=TIMEOUT):
    """
    block until a message is received [timeout] seconds, returns None
    if nothing is received
    """

    signal.alarm(0)
    signal.signal(
        signal.SIGALRM,
        lambda s, f: timeout_handler(s, f, f'receiving ({timeout}s)')
    )
    signal.alarm(timeout)
    try:
        result = json.loads(socket.recv())
        signal.alarm(0)
        return result
    except TimeOutException:
        signal.alarm(0)
        return None
    except Exception:
        signal.alarm(0)
        raise

def recv_all_json(socket, timeout=TIMEOUT):
    """
    block for [timeout] seconds, and return a list of all received
    messages in that period
    """
    results = []
    try:
        last_result = True
        while last_result:

            signal.alarm(0)
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(timeout)
            try:
                last_result = json.loads(socket.recv())
            except TimeOutException:
                last_result = None
            signal.alarm(0)

            if last_result:
                results.append(last_result)

        return results
    except TimeOutException:
        return results

class WebSocketClientTest(unittest.TestCase):
    url = '/'

    def setUp(self):
        self.ws = connect_socket(WS_BASE_URL + self.url, **WS_OPTS)


### Behavior Tests

class TestPageSockets(WebSocketClientTest):
    url = '/_test/'

    def test_hello_on_connect(self):
        send_action(self.ws, HELLO_TYPE)

        result = recv_json(self.ws, timeout=TIMEOUT)

        assert result[ROUTING_KEY] == GOT_HELLO_TYPE, \
            f'Failed to get a HELLO response from server within '\
            f'{TIMEOUT} seconds of connecting\n{result}'

    def test_no_ping_echo(self):
        # socket that sends a ping should not get a ping back
        send_action(self.ws, PING_TYPE)

        result = recv_json(self.ws, timeout=TIMEOUT)

        assert result is None, \
            f'Got a response back on the same socket that a PING was '\
            f'sent out on\n{result}'


### Load Tests

class SocketThread(threading.Thread):
    keep_running = True

    def __init__(self, url=None, verify=VERIFY_SSL, wait=False, verbose=False,
                       get_message=None, check_response=None):
        super().__init__()
        self.url = url or (WS_BASE_URL + '/_test/')
        self.socket_options = {} if verify else {'sslopt': {'cert_reqs': 0}}
        self.verbose = verbose
        self.should_start = threading.Event()
        self.started = threading.Event()
        if not wait:
            self.should_start.set()

        self.round_trips = 0

        self.get_message = get_message or (lambda: {ROUTING_KEY: HELLO_TYPE})
        check_resp = lambda resp: resp[ROUTING_KEY] in (
                GOT_HELLO_TYPE,
                'SET_GAMESTATE',
                'UPDATE_GAMESTATE',
                'CHAT'
            )
        self.check_response = check_response or check_resp

    def run(self):
        signal.alarm(0)
        self.ws = create_connection(self.url, **self.socket_options)
        self.ws.send(to_json_str(self.get_message()))
        resp = self.ws.recv()
        resp = self.ws.recv()
        assert resp and self.check_response(json.loads(resp)), \
                'Failed to get expected response from backend.'
        self.started.set()
        self.should_start.wait()
        while self.keep_running:
            try:
                msg = self.get_message()
                self.ws.send(to_json_str(msg))
                resp = json.loads(self.ws.recv())
                if self.verbose:
                    print('sent:', msg[ROUTING_KEY],
                        '  recv:', resp[ROUTING_KEY])
                assert resp and self.check_response(resp), \
                        'Failed to get expected response from backend.'
                self.round_trips += 1
            except Exception:
                if self.keep_running:
                    raise


class TestSocketLoad(unittest.TestCase):
    def test_websocket_load(self):
        num_connections = LOAD_FACTOR * (30 if TARGET == 'prod' else 10)

        print(f'Starting {num_connections} websocket connections to '
              f'{WS_BASE_URL + "/_test/"}')
        threads = []
        for _ in range(num_connections):
            t = SocketThread()
            t.start()
            threads.append(t)

        print('Playing ping-pong for 4 seconds...')
        sleep(4)

        for t in threads:
            t.keep_running = False
            # libssl segfaults on python3.6 when closing a wss://
            #   connection with VERIFY_SSL=False
            # https://github.com/openssl/openssl/issues/2260
            # t.ws.close()
            t.join()
