import json
import signal
import redis
import logging

from typing import Optional, Union, List
from contextlib import contextmanager

from django import db
from django.conf import settings

from oddslingers.utils import ANSI, to_json_str, is_testing
from oddslingers.system import DOUBLE_FORK

logger = logging.getLogger('heartbeat')
redis_queue = redis.Redis(**settings.REDIS_CONF)


### Exception Classes

class HeartbeatException(Exception):
    pass


class HeartbeatAlreadyRunningException(HeartbeatException):
    pass


class HeartbeatEmptyException(HeartbeatException):
    pass


### Table Action Queue Functions

DispatchValue = Union[dict, str]


def queue_redis_dispatch(key: str, dispatch: DispatchValue) -> None:
    """add a json dict to a queue identified by the given key"""
    json_dispatch = bytes(to_json_str(dispatch), 'utf-8')
    redis_queue.rpush(key, json_dispatch)


def pop_redis_dispatch(key: str,
                       timeout: int=0) -> Optional[DispatchValue]:
    """pop a json dict off the queue identified by the given key"""
    timeout = timeout or settings.HEARTBEAT_POLL
    dispatch = redis_queue.blpop(key, timeout=timeout)

    if dispatch and dispatch[0] == key.encode('utf-8'):
        return json.loads(dispatch[1].decode())

    return None


def peek_redis_dispatch(key: str,
                        timeout: int=0) -> Optional[DispatchValue]:
    """peek at the top of a queue identified by the given key"""
    timeout = timeout or settings.HEARTBEAT_POLL
    dispatch = redis_queue.blpop(key, timeout=timeout)

    if dispatch and dispatch[0] == key.encode('utf-8'):
        redis_queue.lpush(key, dispatch[1])
        return json.loads(dispatch[1].decode())

    return None


def list_redis_dispatch(key: str) -> List[DispatchValue]:
    """get the list of all values in the queue identified by the given key"""
    vals = redis_queue.lrange(key, 0, -1)
    if not vals:
        return []
    return [
        json.loads(val.decode()) if isinstance(val, bytes) else json.loads(val)
        for val in vals
    ]


@contextmanager
def HeartbeatEnvironment(cmd, daemonize=True, share_db=False,
                         allow_multiple=False, verbosity=1, **config):
    """Context Manager to step in and out of the special django process
       setup needed to run the heartbeat process.  This handles:
         - preventing multiple heartbeats from running at once
         - closing the parent's db connections
         - double-forking the child heartbeat process off the parent
         - reopening new db connections for the child process
         - handling Ctrl+C and SIGTERMs and exiting gracefully
    """
    # Only for certain local dev testing situations, uncomment if needed:
    # if not allow_multiple:
    #     existing_pid = find_process(*cmd)
    #     if existing_pid:
    #         msg = f'{cmd} is already running pid={existing_pid}'
    #         raise HeartbeatAlreadyRunningException()

    if verbosity:
        msg = f'{ANSI["lightyellow"]}[*] Starting '\
              f'{" ".join(cmd)} {ANSI["reset"]}'
        logger.info(msg)

    # dont share connection with fork, connections will be re-opened
    # when needed by child process
    # http://stackoverflow.com/questions/8242837/django-multiprocessing-and-database-connections
    if not share_db:
        db.connections.close_all()

    # we dont want web worker process to own heartbeats, they should
    #   run independently.
    # web workers die at the end of every request, so if we dont double fork
    # the spawned heartbeats will be killed as well once the request is over
    if daemonize:
        DOUBLE_FORK()

    with GracefulExitHandler(cmd):
        yield


@contextmanager
def GracefulExitHandler(cmd):
    """Context Manager to handle gracefully capturing Ctrl+C and SIGTERMs"""

    def signal_handler(_signo, _stack_frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, signal_handler)
    try:
        yield

    except KeyboardInterrupt:
        logger.info(f'\n{ANSI["green"]}'
                    f'[X] Stopped ./manage.py {" ".join(cmd)} (CTRL-C) '
                    f'{ANSI["reset"]}')

    except SystemExit as e:
        exit_signal = int(str(e)) or 'SIGTERM'
        logger.info(f'\n{ANSI["red"]}'
                    f'[X] Stopped ./manage.py {" ".join(cmd)} ({exit_signal})'
                    f'{ANSI["reset"]}')


def print_empty_tablebeat_stopped(table, reason):
    if settings.DEBUG:
        print(f'{ANSI["lightyellow"]}[i] Stopping table '\
            f'heartbeat because {reason}: '\
            f'{table.short_id} ({table}) '\
            f'{ANSI["reset"]}')


@is_testing
def redis_has_dispatch(key: str) -> bool:
    """returns true if redis queue has a message
    and pushes it back, False otherwise"""
    dispatch = redis_queue.lpop(key)
    if dispatch:
        redis_queue.lpush(key, dispatch)
        return True
    return False
