import os
import operator

from uuid import UUID

# from django.core.cache import cache
from django.conf import settings
from django.shortcuts import redirect

from oddslingers.utils import sanitize_html, require_staff, to_json_str  # noqa

from poker.models import PokerTable
from poker.tablebeat import stop_tablebeat
from poker.replayer import ActionReplayer
from poker.game_utils import fuzzy_get_game
from poker.subscribers import AnimationSubscriber

from support.models import SupportTicket
from support.artifacts import (
    read_frontend_log,
    read_hand_history,
    # read_notes,
    # read_traceback,
    # read_user_info,
    # read_table_info,
    # read_tablebeat_info,
    # read_botbeat_info
)

from ui.views.base_views import BaseView, ReactView


class TableDebuggerList(BaseView):
    title = 'TableDebuggerList'
    template = 'poker/debugger_list.html'
    login_required = True

    @require_staff(redirect_url='Tables', allow_debug=True)
    def get(self, request):
        self.context = {
            'tables': (
                (table.short_id, table.name)
                for table in (PokerTable.objects
                                        .filter(is_mock=False)
                                        .only('id', 'name')
                                        .order_by('-modified'))
            ),
            'replayers': (
                (table.short_id, table.name)
                for table in (PokerTable.objects
                                        .filter(is_mock=True)
                                        .only('id', 'name')
                                        .order_by('-modified'))
            ),
        }
        return super().get(request)


def get_replayer_by_id(id, hand_number=-1, action_idx=0, session_id=None):
    """contstuct an ActionReplayer from a given table id"""

    try:
        controller = fuzzy_get_game(id)
        table = controller.table
    except KeyError:
        return None

    if not table.is_mock:
        # pause heartbeat when debugging a live table
        stop_tablebeat(table)
        table.sockets.send_action('ERROR',
                details='Stopped game temporarily for debugging purposes.')
    # TODO: handle fetching the proper replayer for a mock table

    hand_number = -1 if hand_number is None else int(hand_number)

    return ActionReplayer.from_table(table, action_idx, hand_number,
                                     session_id=session_id,
                                     subscriber_types=[AnimationSubscriber])


def get_replayer_by_filename(filename,
                             hand_number=-1,
                             action_idx=0,
                             session_id=None):
    """construct an ActionReplayer from a given handhistory filename"""

    hand_number = -1 if hand_number is None else int(hand_number)
    action_idx = 0 if action_idx is None else int(action_idx)

    dump_path = os.path.join(settings.BASE_DIR, 'poker',
                             'tests', 'data', filename)

    return ActionReplayer.from_file(open(dump_path, 'r'),
                                    hand_number,
                                    action_idx,
                                    subscriber_types=[AnimationSubscriber],
                                    session_id=session_id)

def is_invalid_debugger_path(table, hand_number, action_idx):
    """
    check if a hand_number and action_id are valid for a given replayer table
    """

    # redirect to most recent hand number/event idx if not specified
    if hand_number is None or action_idx is None:
        return True

    # if they go to a future hand that doesnt exist yet,
    #   take them to the most recent one
    hand_number, action_idx = int(hand_number), int(action_idx)
    if hand_number > table.hand_number:
        return True

    assert 0 <= hand_number <= table.hand_number and 0 <= action_idx, \
            'Hand number or action_idx out of range.'
    return False


def get_replayer_by_path(id_or_filename,
                         hand_number=None,
                         action_idx=None,
                         session_id=None):
    """given a table id or handhistory filename, get an ActionReplayer"""
    # print('get_replayer_by_path', hand_number, action_idx)
    replayer = get_replayer_by_id(id_or_filename,
                                  hand_number,
                                  action_idx,
                                  session_id)
    if not replayer:
        replayer = get_replayer_by_filename(id_or_filename,
                                            hand_number,
                                            action_idx,
                                            session_id)
    return replayer


class BackendDebugger(ReactView):
    title = 'Backend Debugger Ticket'
    component = 'pages/debugger.js'
    template = 'ui/debug.html'

    @require_staff(redirect_url='Tables', allow_debug=True)
    def get(self, request, **kwargs):

        ticket_id = kwargs.get('ticket_id')
        hand_number = int(request.GET.get('hand_number', 0))
        action_idx = request.GET.get('action_idx', 0)
        try:
            qs = SupportTicket.objects
            if isinstance(ticket_id, UUID):
                self.ticket = qs.get(id=ticket_id)
            else:
                self.ticket = qs.get(id__startswith=ticket_id)
        except SupportTicket.DoesNotExist:
            return redirect('/tables')

        # cache_key = f'backend-debugger-log-:{self.ticket.id}'
        json_log = read_hand_history(self.ticket)
        # if json_log is None:
        #     json_log = read_hand_history(self.ticket)
        #     cache.set(cache_key, json_log)

        if action_idx and int(action_idx):
            self.replayer = ActionReplayer(json_log=json_log,
                                           hand_number=hand_number,
                                           action_idx=int(action_idx) - 1,
                                           subscriber_types=[AnimationSubscriber])
        else:
            self.replayer = ActionReplayer(json_log=json_log,
                                           hand_number=hand_number,
                                           action_idx=int(action_idx),
                                           subscriber_types=[AnimationSubscriber])


        if not self.replayer:
            # prevent reflected XSS in url
            sanitized = sanitize_html(
                self.ticket.table.id, strip=True, allow_safe=False
            )
            return redirect(f'/tables/?search={sanitized}')

        table = self.replayer.controller.table

        props = '?props_json=1' if request.GET.get('props_json') else ''

        # redirect to full path if path is missing some info
        if is_invalid_debugger_path(table, hand_number, action_idx):
            hand_number = table.hand_number
            action_idx = action_idx or 0
            props = f'{props}&action_idx={action_idx}&hand_number={hand_number}'
            path = f'/support/{self.ticket.short_id}/bdebugger{props}'

            return redirect(path)

        elif int(action_idx) > 0:
            try:
                # import ipdb; ipdb.set_trace()
                self.replayer.step_forward()
            except StopIteration:
                # import ipdb; ipdb.set_trace()
                if int(hand_number) + 1 < len(self.replayer.hands):
                    hand_number = int(hand_number) + 1
                    action_idx = 1
                else:
                    action_idx = int(action_idx) - 1

                props = f'{props}&action_idx={action_idx}&hand_number={hand_number}'
                path = f'/support/{self.ticket.short_id}/bdebugger{props}'

                return redirect(path)

        username = None
        gamestate = self.replayer.gamestate_json(username)
        gamestate['ticket_id'] = self.ticket.short_id
        gamestate['hand_number'] = hand_number
        gamestate['action_idx'] = action_idx
        self.props = {
            'gamestate': gamestate
        }

        # print('self.props:')
        # print(to_json_str(self.props, indent=4))

        return super().get(request)


class FrontendDebugger(ReactView):
    title = 'Frontend Debugger Ticket'
    component = 'pages/debugger.js'
    template = 'ui/debug.html'
    ticket = None

    def _get_gamestate(self, op, gs_list, idx):
        gamestate = []
        while True:
            try:
                gamestate = gs_list[idx]
            except IndexError:
                break
            if gamestate['type'] == 'UPDATE_GAMESTATE':
                break
            idx = op(idx, 1)

        gamestate['idx'] = idx
        gamestate['ticket_id'] = self.ticket.short_id
        gamestate['debugger'] = 'FrontendDebugger'
        return gamestate

    def get_next_gamestate(self, messages_received, idx):
        return self._get_gamestate(operator.add, messages_received, idx)

    def get_prev_gamestate(self, messages_received, idx):
        return self._get_gamestate(operator.sub, messages_received, idx)

    @require_staff(redirect_url='Tables', allow_debug=True)
    def get(self, request, ticket_id=None):
        return super().get(request, ticket_id)

    def props(self, request, ticket_id=None):
        try:
            qs = SupportTicket.objects
            if isinstance(ticket_id, UUID):
                self.ticket = qs.get(id=ticket_id)
            else:
                self.ticket = qs.get(id__startswith=ticket_id)
        except SupportTicket.DoesNotExist:
            return {}

        frontend_log = read_frontend_log(self.ticket)
        if frontend_log:
            idx = int(request.GET.get('message_idx') or 0)
            messages_received = frontend_log['ws_to_frontend']
            operation = request.GET.get('op')

            if operation == 'sub':
                return {
                    'gamestate': self.get_prev_gamestate(messages_received, idx)
                }
            else:
                return {
                    'gamestate': self.get_next_gamestate(messages_received, idx)
                }
        else:
            return {}


# class FrontendDebuggerTicket(PublicReactView):
#     title = 'Frontend Debugger Ticket'
#     component = 'pages/debugger-main.js'
#     ticket = None

#     def get(self, request, ticket_id=None, idx=None):

#         if idx is None:
#             return redirect('')
#         try:
#             self.ticket = SupportTicket.objects.get(id=ticket_id)
#         except SupportTicket.DoesNotExist:
#             pass

#         return super().get(request, ticket_id, idx)

#     def props(self, request, **kwargs):

#         if self.ticket is None:
#             return {}

#         return {

#         }
