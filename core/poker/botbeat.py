import os
import sys
import logging
import traceback
import subprocess

from typing import Optional, List
from time import sleep

from raven.contrib.django.raven_compat.models import client
from django.utils import timezone
from django.conf import settings

from oddslingers.utils import ANSI
from oddslingers.system import find_process, stop_process
from oddslingers.tasks import track_analytics_event
from support.artifacts import assemble_botbeat_info
from support.incidents import ticket_from_botbeat_exception

from .bots import get_robot_move
from .models import PokerTable
from .controllers import controller_for_table
from .heartbeat_utils import (
    HeartbeatEnvironment,
    queue_redis_dispatch,
    pop_redis_dispatch,
    peek_redis_dispatch,
    list_redis_dispatch,
)

logger = logging.getLogger('poker')


### Heartbeat Queue Functions

def queue_botbeat_dispatch(table_id: str) -> None:
    return queue_redis_dispatch(
        settings.REDIS_BOTBEAT_KEY,
        table_id
    )


def pop_botbeat_dispatch() -> Optional[str]:
    dispatch = pop_redis_dispatch(settings.REDIS_BOTBEAT_KEY)
    assert dispatch is None or isinstance(dispatch, str)
    return dispatch


def peek_botbeat_dispatch() -> Optional[str]:
    dispatch = peek_redis_dispatch(settings.REDIS_BOTBEAT_KEY)
    assert dispatch is None or isinstance(dispatch, str)
    return dispatch


def list_botbeat_dispatch() -> List[str]:
    return list_redis_dispatch(settings.REDIS_BOTBEAT_KEY)


### Heartbeat Process Management

# name of the management command that calls botbeat_entrypoint
COMMAND_NAME = 'bot_heartbeat'

def botbeat_pid(exclude_pid: int=None) -> Optional[int]:
    return find_process(COMMAND_NAME, exclude_pid=exclude_pid)


def stop_botbeat(exclude_pid: int=None, block: bool=True) -> bool:
    pid = botbeat_pid(exclude_pid=exclude_pid)
    if pid:
        return stop_process(pid, block=block)
    return False


def start_botbeat(fork=True, daemonize=True,
                  share_db=False, verbose=True, stupid=False) -> Optional[int]:
    stupid = stupid or settings.POKER_AI_STUPID

    if settings.IS_TESTING:
        # only run a single heartbeat loop when testing since we cannot fork
        botbeat_loop(loop=False, verbose=False, stupid=stupid)
        return None

    pid = botbeat_pid()
    if pid:
        return pid

    if not settings.AUTOSTART_BOTBEAT:
        print(f'[X] Not starting botbeat because '
              f'settings.AUTOSTART_BOTBEAT = False')
        return None

    if fork:
        manage_path = os.path.join(settings.BASE_DIR, 'manage.py')
        if settings.DEBUG:
            log_file = sys.stdout
        else:
            log_file = open(settings.BOTBEAT_LOG, 'a+')
            logger.info(
                f'[i] Logging botbeat stdout to {settings.BOTBEAT_LOG}'
            )

        subprocess.Popen(
            [
                'python',
                manage_path,
                COMMAND_NAME,
                '--daemonize',
                *(('--stupid',) if stupid else ()),
            ],
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setpgrp,
        )
        return botbeat_pid()
    else:
        botbeat_entrypoint(daemonize=daemonize,
                           share_db=share_db,
                           verbosity=verbose,
                           stupid=stupid)
        # if fork is false, the function runs forever and never returns
        return None


def botbeat_entrypoint(loop=True, verbose=True,
                       stupid=False, **config) -> None:
    stupid = stupid or settings.POKER_AI_STUPID

    with HeartbeatEnvironment([COMMAND_NAME], **config):
        botbeat_loop(loop=loop, verbose=verbose, stupid=stupid)


### Heartbeat Content

def botbeat_loop(loop=True, verbose=True, stupid=settings.POKER_AI_STUPID):
    exception = Exception('Failed to start.')
    failing_table = None
    try:
        while True:
            queued_tables = list_botbeat_dispatch()

            try:
                botbeat_step(queued_tables, verbose=verbose, stupid=stupid)
            except Exception as err:
                exception = err
                if settings.IS_TESTING:
                    import ipdb; ipdb.set_trace()

                # get failing table id attached to exception by botbeat_step
                if hasattr(err, 'table_id'):
                    failing_table = PokerTable.objects.get(id=err.table_id)

                botbeat_info = assemble_botbeat_info(
                    queued_tables,
                    failing_table,
                    stupid
                )
                ticket = ticket_from_botbeat_exception(
                    failing_table,
                    exception,
                    traceback.format_exc(),
                    botbeat_info
                )

                client.extra_context({
                    'ticket_id': ticket.id,
                    'ticket_dir': ticket.dir,
                    'artifacts': ticket.artifacts,
                })
                raise

            if not loop:
                break

    except Exception:
        # if supposed to run forever, but stopped for some reason
        msg = f'Botbeat quit due to errors on {failing_table}! {exception}'
        track_analytics_event.send('botbeat', msg)
        raise


def botbeat_step(queued_tables, verbose=True, stupid=settings.POKER_AI_STUPID):
    # print(f'botbeat_loop(queued_tables={queued_tables}, verbose={verbose}, stupid={stupid})')
    dispatch_msg = None
    delay_tables = []

    if queued_tables:
        delay_tables = []

        # look for a table with a bot that's ready to play.
        #   any with delays should be rotated to the back of the queue
        for table_id in queued_tables:
            try:
                try:
                    next_table = PokerTable.objects.get(id=table_id)
                except Exception as err:
                    msg = f'Error querying tbl_id {table_id} in botbeat: {err}'
                    warn(msg)
                    continue

                ctrl = controller_for_table(next_table)
                acc = ctrl.accessor

                if not acc.robot_is_next():
                    # msg = f'Table {table_id} queued to botbeat but '\
                    #        'robot is not next'
                    # warn(msg)
                    continue

                start_ts = timezone.now().timestamp()
                try:
                    ai_move = get_robot_move(
                        acc,
                        ctrl.log,
                        delay=not settings.POKER_AI_INSTANT,
                        stupid=stupid
                    )
                except Exception as err:
                    if settings.IS_TESTING or stupid:
                        raise type(err).with_traceback(err.__traceback__)

                    msg = (
                        'getting random move because get_smart_move() failed:'
                        f'\n{traceback.format_exc()}'
                    )
                    now_str = timezone.now().strftime('%Y-%m-%d.%H-%M-%S')
                    filename = f'smart_err_{acc.table.short_id}_{now_str}.log'
                    filepath = os.path.join(settings.DEBUG_DUMP_DIR, filename)
                    with open(filepath, 'w+') as f:
                        f.write(msg)
                    ai_move = get_robot_move(
                        acc,
                        ctrl.log,
                        delay=not settings.POKER_AI_INSTANT,
                        stupid=True,
                    )

                end_ts = timezone.now().timestamp()

                if ai_move is None:
                    delay_tables.append(table_id)
                else:
                    action_type, kwargs = ai_move
                    dispatch_msg = {
                        'table_id': table_id,
                        'action': {
                            'type': action_type,
                            **kwargs,
                        },
                    }
                    break

            except Exception as e:
                e.table_id = table_id
                raise

    for table_id in delay_tables:
        queue_botbeat_dispatch(table_id)
        check_id_match(table_id, pop_botbeat_dispatch())

    if dispatch_msg is None:
        # print('Nothing to dispatch; sleeping')
        if not settings.IS_TESTING:
            sleep(1)
    else:
        from .tablebeat import queue_tablebeat_dispatch

        # Log action details and timing to stdout
        if verbose:
            player_id = dispatch_msg['action']['player_id']
            action_name = dispatch_msg['action']['type'].ljust(16)
            player = acc.player_by_player_id(player_id).username
            thinking = round((end_ts - start_ts)*1000, 1)
            is_stupid = 'stupid' if stupid else 'smart'

            print(
                f'{ANSI["black"]}[*] BOT : {action_name} {player}'
                f'({is_stupid}) {thinking}ms @ {acc.table.name} '
                f'({acc.table.short_id}) {ANSI["reset"]}'
            )

        queue_tablebeat_dispatch(
            dispatch_msg['table_id'],
            dispatch_msg['action']
        )

        # This should work because the last table_id looked at
        #   should be the one that the move was made for.
        #   Otherwise the table_id might get popped w/the delay_tables
        #   and then re-queued by the tablebeat before getting here.
        check_id_match(dispatch_msg['table_id'], pop_botbeat_dispatch())


def warn(msg, table=None):
    if settings.DEBUG:
        print(msg)
    else:
        extra = {
            'table_id': table.id,
            'table_name': table.name,
            'table_ts': table.modified,
            'table_hand_number': table.hand_number,
        } if table else {}
        logger.warning(msg, extra=extra)

    if settings.IS_TESTING:
        raise Exception(f'Got warning {msg}')


def check_id_match(id1, id2):
    if id1 != id2:
        # can happen during deploys or if redis gets out-of-date for any reason
        # TODO: debug further
        # warn(f'botbeat queue table_id mismatch: {id1} != {id2}')
        pass
