import os
import json
import logging
import traceback


from shutil import copyfile
from typing import Union, Optional, List

from django.conf import settings
from django.contrib.auth import get_user_model

from oddslingers.utils import to_json_str
from poker.models import PokerTable
from poker.replayer import EventReplayer
from poker.controllers import controller_for_table

from .models import SupportTicket


User = get_user_model()

# Filenames inside <settings.SUPPORT_TICKET_DIR>/<incident_id/<filename>
SETTINGS_INFO_PATH = 'settings.json'
TRACEBACK_PATH = 'traceback.txt'
USER_INFO_PATH = 'user.json'
TABLE_INFO_PATH = 'table.json'
NOTES_PATH = 'notes.txt'
TABLEBEAT_INFO_PATH = 'tablebeat_info.json'
BOTBEAT_INFO_PATH = 'botbeat_info.json'
FRONTEND_LOG_PATH = 'frontend_log.json'
CURRENT_HAND_HISTORY_PATH = 'current_hand.json'
FULL_HAND_HISTORY_PATH = 'hand_history.json'
SOCKET_IO_LOG_PATH = 'socket_io_{0}_{1}.log'
TABLEBEAT_LOG_PATH = 'tablebeat_{0}.log'
BOTBEAT_LOG_PATH = 'botbeat.log'
COMMUNICATION_LOG_PATH = 'communication.txt'

# Mute ticket creation console messages when running tests
if settings.IS_TESTING:
    class FakeLogger:
        def warning(self, *args, **kwargs):
            pass
        def error(self, *args, **kwargs):
            pass
        def exception(self, *args, **kwargs):
            pass
    logger = FakeLogger()
else:
    logger = logging.getLogger('root')


def copy_file(ticket: SupportTicket, path: str, artifact_path: str):
    """Collect a file into the support ticket dir from the filsystem"""
    try:
        copyfile(path, os.path.join(ticket.dir, artifact_path))
    except FileNotFoundError as e:
        logger.warning(
            "Support ticket tried to collect a file that doesn't exist",
            extra={
                'ticket_id': ticket.id,
                'path': path,
                'artifact_path': artifact_path,
                'exception': f'{e.__class__.__name__}: {e}',
            },
        )
        if settings.DEBUG:
            print(path, artifact_path)


def save_artifact(ticket: SupportTicket,
                  path: str,
                  content: Union[str, dict],
                  mode: str='w+'):
    """Save str or json blob into a given path in the support ticket's dir"""
    # In the future we may want to log the saved artifacts to the DB or upload
    # them to other locations, this is the place to do that

    ticket.create_dir()
    artifact_path = os.path.join(ticket.dir, path)

    with open(artifact_path, mode) as f:
        if isinstance(content, dict):
            f.write(to_json_str(content, indent=4))
            f.write('\n')
        else:
            f.write(f'{content}\n')

def read_artifact(ticket: SupportTicket, path: str) -> Optional[Union[str, dict]]:
    """load a given tickets str or json artifact and return as dict or str"""
    artifact_path = os.path.join(ticket.dir, path)

    if not os.path.exists(artifact_path):
        return None

    with open(artifact_path, 'r') as f:
        if path.endswith('.json'):
            return json.load(f)
        else:
            return f.read().strip() or None


### Environment
def save_settings_info(ticket: SupportTicket):
    settings_info = {
        'DEBUG': settings.DEBUG,
        'ODDSLINGERS_ENV': settings.ODDSLINGERS_ENV,
        'GIT_SHA': settings.GIT_SHA,
        'DJANGO_USER': settings.DJANGO_USER,
        'PID': settings.PID,
        'DEFAULT_HOST': settings.DEFAULT_HOST,
        'ENABLE_DRAMATIQ': settings.ENABLE_DRAMATIQ,
        'POKER_AI_STUPID': settings.POKER_AI_STUPID,
        'POKER_AI_INSTANT': settings.POKER_AI_INSTANT,
        'POKER_PAUSE_ON_EXCEPTION': settings.POKER_PAUSE_ON_EXCEPTION,
        'POKER_PAUSE_ON_REPORT_BUG': settings.POKER_PAUSE_ON_REPORT_BUG,
        'STATUS_LINE': settings.STATUS_LINE,
    }
    save_artifact(ticket, SETTINGS_INFO_PATH, settings_info)

def read_settings_info(ticket: SupportTicket) -> Optional[dict]:
    settings_info = read_artifact(ticket, SETTINGS_INFO_PATH)
    if settings_info is None: return None

    # needed to tell mypy env is always dict
    assert isinstance(settings_info, dict)
    return settings_info



### Notes
def save_notes(ticket: SupportTicket, notes: str):
    save_artifact(ticket, NOTES_PATH, notes)

def read_notes(ticket: SupportTicket) -> Optional[str]:
    notes = read_artifact(ticket, NOTES_PATH)
    if notes is None: return None

    # needed to tell mypy notes are always str
    assert isinstance(notes, str)
    return notes



### Traceback
def save_traceback(ticket: SupportTicket, exc: Exception, tb: str=None):
    tb = tb or traceback.format_exc()
    save_artifact(
        ticket,
        TRACEBACK_PATH,
        f'{exc.__class__.__name__}: {exc}\n\n{tb}'
    )

def read_traceback(ticket: SupportTicket) -> Optional[str]:
    tb = read_artifact(ticket, TRACEBACK_PATH)
    if tb is None: return None

    # needed to tell mypy tb is always str
    assert isinstance(tb, str)
    return tb


### User Info

def save_user_info(ticket: SupportTicket, user: User=None):
    if user:
        user_info = {
            **user.__json__('chips_in_play', 'email'),
            'balance': user.userbalance().balance
        }
        save_artifact(ticket, USER_INFO_PATH, user_info)
    else:
        save_artifact(ticket, USER_INFO_PATH, {
            'username': None,
            'id': None,
            'is_anonymous': True,
        })

def read_user_info(ticket: SupportTicket) -> Optional[dict]:
    user_info = read_artifact(ticket, USER_INFO_PATH)
    if user_info is None: return None

    # to tell mypy info is always dict
    assert isinstance(user_info, dict)
    return user_info



### Table Info
def save_table_info(ticket: SupportTicket, table: PokerTable):
    save_artifact(ticket, TABLE_INFO_PATH, table.__json__(
        'deck_str',
        'board_str',
    ))

def read_table_info(ticket: SupportTicket) -> Optional[dict]:
    table_info = read_artifact(ticket, TABLE_INFO_PATH)
    if table_info is None: return None

    # to tell mypy info is always dict
    assert isinstance(table_info, dict)
    return table_info



### Tablebeat Info
def assemble_tablebeat_info(table: PokerTable, queued_message: dict=None) -> dict:
    from poker.tablebeat import tablebeat_pid
    try:
        controller = controller_for_table(table)
        next_to_act = controller.accessor.next_to_act()
    except Exception:
        next_to_act = None

    return {
        'table_id': table.id,
        'table_ts': table.modified,
        'tablebeat_pid': tablebeat_pid(table),
        'queued_message': queued_message,
        'table_hand_number': table.hand_number,
        'next_to_act': next_to_act,
    }

def save_tablebeat_info(ticket: SupportTicket, tablebeat_info: dict):
    save_artifact(ticket, TABLEBEAT_INFO_PATH, tablebeat_info)

def read_tablebeat_info(ticket: SupportTicket) -> Optional[dict]:
    tablebeat_info = read_artifact(ticket, TABLEBEAT_INFO_PATH)
    if tablebeat_info is None: return None

    # to tell mypy info is always dict
    assert isinstance(tablebeat_info, dict)
    return tablebeat_info



### Botbeat info
def assemble_botbeat_info(queued_tables: List[PokerTable],
                          failing_table: PokerTable,
                          stupid: bool) -> dict:
    from poker.tablebeat import tablebeat_pid
    from poker.botbeat import botbeat_pid

    return {
        'stupid_bots': stupid,
        'botbeat_pid': botbeat_pid(),
        'queued_tables': queued_tables,
        'table_name': failing_table.name if failing_table else None,
        'table_id': failing_table.id if failing_table else None,
        'tablebeat_pid': (
            tablebeat_pid(failing_table) if failing_table else None
        ),
    }

def save_botbeat_info(ticket: SupportTicket, botbeat_info: dict):
    save_artifact(ticket, BOTBEAT_INFO_PATH, botbeat_info)

def read_botbeat_info(ticket: SupportTicket) -> Optional[dict]:
    botbeat_info = read_artifact(ticket, BOTBEAT_INFO_PATH)
    if botbeat_info is None: return None

    # to tell mypy info is always dict
    assert isinstance(botbeat_info, dict)
    return botbeat_info


### Hand History
def save_hand_history(ticket: SupportTicket, table: PokerTable):
    controller = controller_for_table(table)
    current_hand_path = os.path.join(ticket.dir, CURRENT_HAND_HISTORY_PATH)
    full_hand_history_path = os.path.join(ticket.dir, FULL_HAND_HISTORY_PATH)

    controller.log.save_to_file(current_hand_path,
                                'all',
                                current_hand_only=True)
    controller.log.save_to_file(full_hand_history_path,
                                'all',
                                current_hand_only=False)


def read_hand_history(ticket: SupportTicket) -> Optional[dict]:
    hand_history = read_artifact(ticket, FULL_HAND_HISTORY_PATH)
    if hand_history is None: return None

    # to tell mypy hhlog is always dict
    assert isinstance(hand_history, dict)
    return hand_history

def read_hh_to_replayer(ticket: SupportTicket,
                        fast_forward=False) -> EventReplayer:
    hhlog_json = read_hand_history(ticket)
    assert hhlog_json is not None

    replayer = EventReplayer(hhlog_json)

    if fast_forward:
        while True:
            try:
                replayer.step_forward()
            except StopIteration:
                break

    return replayer



### Frontend Log
def save_frontend_log(ticket: SupportTicket, frontend_log: dict):
    save_artifact(ticket, FRONTEND_LOG_PATH, frontend_log)

def read_frontend_log(ticket: SupportTicket) -> Optional[dict]:
    frontend_log = read_artifact(ticket, FRONTEND_LOG_PATH)
    if frontend_log is None: return None

    # to tell mypy log is always dict
    assert isinstance(frontend_log, dict)
    return frontend_log


### Socket IO Log
def save_socket_log(ticket: SupportTicket, socket_path: str):
    path = '-'.join(socket_path.split('/')[1:-1])

    src = settings.SOCKET_IO_LOG.format(path, 'in')
    artifact_path = SOCKET_IO_LOG_PATH.format(path, 'in')
    copy_file(ticket, src, artifact_path)

    # src = settings.SOCKET_IO_LOG.format(path, 'out')
    # artifact_path = SOCKET_IO_LOG_PATH.format(path, 'out')
    # copy_file(ticket, src, artifact_path)


### Tablebeat Log
def save_tablebeat_log(ticket: SupportTicket, table: PokerTable):
    src_path = settings.TABLEBEAT_LOG.format(table.short_id)
    artifact_path = TABLEBEAT_LOG_PATH.format(table.short_id)
    copy_file(ticket, src_path, artifact_path)

### Botbeat Log
def save_botbeat_log(ticket: SupportTicket):
    copy_file(ticket, settings.BOTBEAT_LOG, BOTBEAT_LOG_PATH)


### Communication Log (log of reports sent to humans and 3rd party services)
def save_communication_log(ticket: SupportTicket, message: dict):
    save_artifact(ticket, COMMUNICATION_LOG_PATH, message, 'a+')

def read_communication_log(ticket: SupportTicket) -> List[dict]:
    comms_strs = read_artifact(ticket, COMMUNICATION_LOG_PATH)
    assert comms_strs is None or isinstance(comms_strs, str)

    if not comms_strs:
        return []

    # comms_str is a list of (indented) json objects as strs, so we split them
    # into separate json blobs and parse individually
    return [
        json.loads(comm + '}')
        for comm in comms_strs.split('\n}')
        if comm.strip()
    ]
