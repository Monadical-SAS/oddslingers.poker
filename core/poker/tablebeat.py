import subprocess
import os
import sys
import traceback

from datetime import timedelta
from typing import Optional, List

from raven.contrib.django.raven_compat.models import client
from django.utils import timezone
from django.conf import settings
from django.contrib.auth import get_user_model

from oddslingers.utils import ANSI, debug_print_io
from oddslingers.system import find_process, stop_process
from oddslingers.tasks import track_analytics_event
from support.artifacts import assemble_tablebeat_info
from support.incidents import ticket_from_tablebeat_exception

from .constants import HIDE_TABLES_AFTER_N_HANDS
from .bots import get_robot_move
from .models import PokerTable
from .game_utils import fuzzy_get_table, suspend_table
from .controllers import (
    controller_for_table,
    InvalidAction,
    RejectedAction
)

from .botbeat import (
    botbeat_pid,
    start_botbeat,
    queue_botbeat_dispatch,
    list_botbeat_dispatch,
)
from .heartbeat_utils import (
    HeartbeatEnvironment,
    queue_redis_dispatch,
    pop_redis_dispatch,
    peek_redis_dispatch,
    list_redis_dispatch,
    logger,
    print_empty_tablebeat_stopped
)


### Heartbeat Queue Functions

def queue_tablebeat_dispatch(table_id: str, action: dict) -> None:
    return queue_redis_dispatch(f'{settings.REDIS_TABLEBEAT_KEY}-{table_id}', action)

def pop_tablebeat_dispatch(table_id: str) -> Optional[dict]:
    dispatch = pop_redis_dispatch(f'{settings.REDIS_TABLEBEAT_KEY}-{table_id}')
    assert dispatch is None or isinstance(dispatch, dict)
    return dispatch

def peek_tablebeat_dispatch(table_id: str) -> Optional[dict]:
    dispatch = peek_redis_dispatch(f'{settings.REDIS_TABLEBEAT_KEY}-{table_id}')
    assert dispatch is None or isinstance(dispatch, dict)
    return dispatch

def list_tablebeat_dispatch(table_id: str) -> List[dict]:
    return list_redis_dispatch(f'{settings.REDIS_TABLEBEAT_KEY}-{table_id}')

### Heartbeat Process Management

# the name of the management command that calls tablebeat_entrypoint
COMMAND_NAME = 'table_heartbeat'


def tablebeat_pid(table: PokerTable, exclude_pid: int=None) -> Optional[int]:
    return find_process(COMMAND_NAME, table.short_id, exclude_pid=exclude_pid)


def stop_tablebeat(table: PokerTable, exclude_pid=None, block=True) -> bool:
    pid = tablebeat_pid(table, exclude_pid=exclude_pid)
    if pid:
        return stop_process(pid, block=block)
    return False


def start_tablebeat(table: PokerTable, fork=True,
                    daemonize=True, share_db=False, verbose=True) -> Optional[int]:
    """
    start the table heartbeat process which manages timed events
    and bot actions
    """
    if settings.IS_TESTING:
        # only run a single heartbeat loop when testing since we cannot fork
        tablebeat_loop(table.id, loop=False, verbose=False)
        return None

    pid = tablebeat_pid(table)
    if pid:
        return pid

    if not settings.AUTOSTART_TABLEBEAT:
        print(f'[X] Not starting tablebeat because '
              f'settings.AUTOSTART_TABLEBEAT = False: {table}')
        return None

    if fork:
        manage_path = os.path.join(settings.BASE_DIR, 'manage.py')
        if settings.DEBUG:
            log_file = sys.stdout
        else:
            log_path = settings.TABLEBEAT_LOG.format(table.short_id)
            log_file = open(log_path, 'a+')
            logger.info(f'[i] Logging heartbeat stdout to {log_path}')

        subprocess.Popen(
            [
                'python',
                manage_path,
                COMMAND_NAME,
                str(table.id),
                '--daemonize',   # if fork=True, daemonize is always True
            ],
            stdout=log_file,
            stderr=log_file,
            preexec_fn=os.setpgrp,
        )
        return tablebeat_pid(table)

    else:
        tablebeat_entrypoint(table_id=str(table.id),
                             daemonize=daemonize,
                             share_db=share_db,
                             verbosity=verbose)
        # if fork is false, this function never returns because
        # tablebeat_entrypoint runs the heartbeat runloop synchronously
        return None


def tablebeat_entrypoint(table_id: str, daemonize=True, share_db=False,
                         force_run=False, loop=True, verbosity=1, **_) -> None:
    """entrypoint for the table_heartbeat managment command"""

    table = fuzzy_get_table(table_id, only=('id',))
    full_id = str(table.id)
    short_id = table.short_id

    with HeartbeatEnvironment([COMMAND_NAME, short_id], daemonize=daemonize,
                              share_db=share_db, verbosity=verbosity):
        tablebeat_loop(full_id, loop=loop, verbose=verbosity)


def kill_tablebeats(system_wide=True) -> int:
    """
    kill all table heartbeat processes, to be called when runserver
    restarts
    """

    # restrict to tables listed in the database
    if not system_wide:
        stopping = 0
        for table in PokerTable.objects.all().only('id'):
            stopping += stop_tablebeat(table, block=False)
        msg = f'{ANSI["red"]}[X] Killing {stopping} heartbeats \
                from DB {settings.DB}... {ANSI["reset"]}'
        logger.info(msg)
        return stopping

    # kill all heartbeats on system
    heartbeat_procs = subprocess.Popen(['ps', 'axw'], stdout=subprocess.PIPE)
    procs = [
        line for line in heartbeat_procs.stdout
        if b'tablebeat' in line
    ]
    msg = f'{ANSI["red"]}[X] Killing {len(procs)} heartbeats... '\
          f'{ANSI["reset"]}'
    logger.info(msg)

    for line in procs:
        pid = line.decode().strip().split()[0]
        subprocess.Popen(['kill', pid])

    return len(procs)


### Heartbeat Content

def tablebeat_loop(table_id: str, loop=True, verbose=True, peek=True):
    """main table heartbeat runloop"""
    table = PokerTable.objects.get(id=table_id)
    # print('tablebeat_loop table:', table)

    controller = controller_for_table(table)
    controller.dispatch_timing_reset()
    exception = Exception('Failed to start.')
    pause = False

    while True:
        # get any table IO from queue (peek, then pop once finished to
        #   guarantee at-least-once)
        if not settings.IS_TESTING or peek:
            message = peek_tablebeat_dispatch(table_id)
        else:
            message = None

        try:
            controller.dispatch_kick_inactive_players()

            # table heartbeat should stop if:
            #   - no sockets open and no humans seated and hn > HIDE_TABLES_AFTER_N_HANDS
            #   - nobody seated for ~2mins
            human_sitting = message and message.get('type') == 'JOIN_TABLE'
            no_humans_seated = not controller.accessor.seated_humans()
            no_humans = no_humans_seated and not human_sitting
            crickets = not table.sockets.filter(active=True).exists()
            arxvable = table.hand_number >= HIDE_TABLES_AFTER_N_HANDS
            tutorial_or_not_arxv = (not arxvable) or table.is_tutorial
            pause_robots = no_humans and crickets and tutorial_or_not_arxv

            if pause_robots:
                print_empty_tablebeat_stopped(table, 'no humans or sockets')
                pause = True
                break

            pause_tutorial = crickets and table.is_tutorial
            if pause_tutorial:
                msg = 'no sockets and is tutorial'
                print_empty_tablebeat_stopped(table, msg)
                pause = True
                break

            nobody_home = not controller.accessor.seated_players()
            time_since_act = timezone.now() - table.last_action_timestamp
            snoozeville = time_since_act > timedelta(minutes=2)
            pause_empty = nobody_home and snoozeville

            if pause_empty:
                print_empty_tablebeat_stopped(table, 'inactive')
                pause = True
                break

            if table.tournament and controller.accessor.tournament_is_over():
                print_empty_tablebeat_stopped(table, 'finished tournament')
                pause = True
                break

            refresh_users(controller)
            # print('tablebeat_loop message:', message)
            modified_timestamp = tablebeat_step(
                controller,
                message.copy() if message else None,
                verbose=verbose,
            )

            # complain if someone else changes DB data besides controller
            table.refresh_from_db(fields=('modified',))
            if table.modified != modified_timestamp:
                table.refresh_from_db()
                controller = controller_for_table(table)
                raise Exception('Table was modified by something other '
                                'than the heartbeat process. '
                                f'modified_timestamp: {modified_timestamp}')

        except RejectedAction as e:
            traceback.print_exc()
            if settings.POKER_REJECTED_ACTIONS_WARNINGS:
                logger.warning(str(e), extra={
                    'table_id': table_id,
                    'table_name': table.name,
                    'table_variant': table.variant,
                    'tablebeat_pid': tablebeat_pid(table),
                    'table_ts': table.modified,
                    'queued_message': message,
                    'table_hand_number': table.hand_number,
                })

        except InvalidAction as e:
            traceback.print_exc()
            if settings.POKER_INVALID_ACTIONS_WARNINGS:
                logger.warning(str(e), extra={
                    'table_id': table_id,
                    'table_name': table.name,
                    'table_variant': table.variant,
                    'tablebeat_pid': tablebeat_pid(table),
                    'table_ts': table.modified,
                    'queued_message': message,
                    'table_hand_number': table.hand_number,
                })

        except Exception as e:
            exception = e
            tb = traceback.format_exc()

            tablebeat_info = assemble_tablebeat_info(table, message)
            ticket = ticket_from_tablebeat_exception(table, e, tb, tablebeat_info)

            if settings.POKER_PAUSE_ON_EXCEPTION:
                suspend_table(table)
                client.extra_context({
                    'table_name': table.name,
                    'table_id': table_id,
                    'ticket_id': ticket.id,
                    'ticket_dir': ticket.dir,
                    'artifacts': ticket.artifacts,
                })
                raise

        finally:
            if message is not None:
                popped_message = pop_tablebeat_dispatch(table_id)
                assert popped_message == message, (
                    'Message at top of queue was changed '
                    'while it was still being processed!')

        if pause or not loop:
            break

    if pause:
        # this is used in testing
        return "paused"

    # if supposed to run forever, but stopped for some reason
    if loop:
        track_analytics_event.send(
            str(table),
            f'Heartbeat {table.short_id} quit due to errors! {exception}'
        )
        raise Exception(f'Tablebeat quit due to errors! {exception}')


_last_botbeat_start = timezone.now() - timezone.timedelta(seconds=5)


def tablebeat_step(controller, message: dict=None, verbose=True):
    """logic for a single step of the table heartbeat loop"""
    # print('tablebeat_step message:', message)
    if message:
        debug_print_io(out=False, content=message)

        # if table IO came in, dispatch it to the controller as an action
        action = message.pop('type')

        if action == 'PLAYER_CLOSE_TABLE':
            pass
            # too noisy with many users, uncomment if you need it for debugging
            # acc = controller.accessor
            # plyr = acc.player_by_player_id(message['player_id'])
            # is_cashtable = acc.table.tournament is None
            
            # track_analytics_event.send(
            #     plyr.username,
            #     f'closed table unexpectedly',
            #     topic=acc.table.zulip_topic if is_cashtable\
            #           else acc.table.tournament.zulip_topic,
            #     stream="Tables" if is_cashtable else "Tournaments",
            # )
        elif action == 'FORCE_ACTION':
            if controller.accessor.robot_is_next():
                ai_action, kwargs = get_robot_move(
                    controller.accessor,
                    controller.log,
                    delay=False,
                    stupid=True,
                    suggested=message['suggested'],
                )
                controller.dispatch(ai_action, **kwargs)
        else:
            controller.dispatch(action, **message)

    else:
        # fix any sat-out bots -- allows recovery if a heartbeat error
        #   causes a bot to sit out
        controller.dispatch_sit_in_for_bots()

        # botbeat handles robot moves
        if controller.accessor.robot_is_next():
            # print('bot is next')
            # gets all queued tables
            tables_queued = list_botbeat_dispatch()

            # print(f'tables_queued: {tables_queued}')
            table = controller.accessor.table

            table_id = str(table.id)
            if table_id not in tables_queued:
                # print(f'{table_id} not found; pushing')
                queue_botbeat_dispatch(table_id)

            if settings.DEBUG:
                five_sec_ago = timezone.now() - timezone.timedelta(seconds=5)
                if not botbeat_pid() and (_last_botbeat_start < five_sec_ago):
                    start_botbeat()

    controller.timed_dispatch()

    return controller.table.modified


def refresh_users(controller):
    User = get_user_model()
    table = controller.accessor.table
    updated_users = {
        str(user.id): user for user in User.objects.filter(
            player__table_id=table.id,
            player__seated=True,
        )
    }
    for player in controller.accessor.players:
        user_id = str(player.user.id)
        if user_id in updated_users:
            # fast case, updated user is already in our list
            #   of fresh user objects
            player.user = updated_users[user_id]
        else:
            # slower case, requires a separate query for each updated user
            player.user.refresh_from_db()
