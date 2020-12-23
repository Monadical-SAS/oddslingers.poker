from time import sleep

from django.core.management.base import BaseCommand

from sockets.integration_tests import SocketThread

DEFAULT_TEST_TARGET = 'http://127.0.0.1:8000/_test/'
DEFAULT_LOAD = 10
DEFAULT_TIME = 4

def convert_ws_url(url):
    return url.replace('https://', 'wss://').replace('http://', 'ws://')


class Command(BaseCommand):
    help = 'Run a socket stress test on the server'

    def add_arguments(self, parser):
        parser.add_argument(
            '-H', '--host', 
            type=str, 
            required=False, 
            default=DEFAULT_TEST_TARGET
        )
        parser.add_argument(
            '-l', '--load', 
            type=int, 
            required=False, 
            default=DEFAULT_LOAD
        )
        parser.add_argument(
            '-t', '--time', 
            type=int, 
            required=False, 
            default=DEFAULT_TIME
        )

    def handle(self, host=DEFAULT_TEST_TARGET, load=DEFAULT_LOAD, 
                     time=DEFAULT_TIME, verbosity=1, **args):
        ws_url = convert_ws_url(host)

        print(f'Starting {load} websocket connections to {ws_url}')
        threads = []
        for _ in range(load):
            t = SocketThread(
                url=ws_url, 
                verify=('oddslingers.com' in ws_url), 
                wait=True, 
                verbose=verbosity > 0, 
                get_message=lambda: {'type': 'GET_GAMESTATE'}
            )
            t.start()
            t.started.wait()
            threads.append(t)

        print(f'Opened {load} conections.')
        for thread in threads:
            thread.should_start.set()

        print(f'Playing ping-pong for {time} seconds...')
        sleep(time)

        total_msgs = 0

        for t in threads:
            t.keep_running = False
            total_msgs += t.round_trips
            # libssl segfaults on python3.6 when closing a wss:// 
            #   connection with VERIFY_SSL=False
            # https://github.com/openssl/openssl/issues/2260
            # t.ws.close()
            t.join()

        print(f'[√] Done, sent {total_msgs} messages in {time} seconds. '\
              f'({total_msgs / time} rtps)')
