import socket

from oddslingers.utils import ANSI


def split_hoststr(host_str: str, defaults=('http', '127.0.0.1', 8000)):
    """extract a protocol, host, and port from a string
    e.g. https://oddslingers.com, 127.0.0.1:8000, or http://dev.local:8000
    """
    protocol, host, port = defaults
    host_str = host_str or host

    split_host = host_str.split('://', 1)

    if split_host[0] in ('http', 'https', 'wss', 'ws'):
        protocol, host_str = split_host

    try:
        host, port = host_str.rsplit(':', 1)
        port = int(port)
    except (ValueError, IndexError):
        host = host_str

    if protocol in ('https', 'wss'):
        port = 443

    return protocol, host, port


def host_type(host_str: str):
    """confirm that a string is a valid, reachable host
    e.g. 127.0.0.1:8000, http://oddslingers.com, https://oddslingers.l
    """
    protocol, host, port = split_hoststr(host_str)

    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(2)
    try:
        s.connect((host, port))
        print(f'{ANSI["green"]}[√] Host {host} is listening on port '\
              f'{port}{ANSI["reset"]}')
    except:
        print(f'{ANSI["red"]}[X] Host {host} is not accessible port '\
              f'{port}{ANSI["reset"]}')
        raise
    finally:
        s.close()

    return f'{protocol}://{host}:{port}'


def module_type(path_str: str):
    """
    confirm that a string is a valid module identifier/path that's importable 
    in this project e.g. ui.integration_tests, sockets, oddslingers.tests
    """
    if not path_str:
        return None

    try:
        exec(f'import {path_str}')
        eval(path_str)
    except (ImportError, SyntaxError):
        print(f'{ANSI["red"]}[X] Module not found! {path_str}{ANSI["reset"]}')
        raise ValueError
    return path_str
