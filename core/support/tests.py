import os
import json
import shutil
import traceback
import logging

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.conf import settings

from poker.constants import NL_HOLDEM
from poker.game_utils import make_bot_game
from poker.tests.test_log import assert_equivalent_game_states

from .models import SupportTicket, TicketSource
from .artifacts import (
    USER_INFO_PATH,
    NOTES_PATH,
    TRACEBACK_PATH,
    save_settings_info,
    read_settings_info,
    save_user_info,
    read_user_info,
    read_table_info,
    save_notes,
    read_notes,
    save_traceback,
    read_traceback,
    read_tablebeat_info,
    read_botbeat_info,
    read_hh_to_replayer,
    read_frontend_log,
    read_communication_log,
)
from .incidents import (
    ticket_from_tablebeat_exception,
    ticket_from_botbeat_exception,
    ticket_from_table_report_bug,
    ticket_from_support_page,
    report_ticket,
)

logger = logging.getLogger('none')


class BaseSupportTest(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='testuser1',
            email='',
            password='asfdljka12345',
        )

    def tearDown(self):
        for ticket in SupportTicket.objects.all():
            prod_or_beta = settings.ODDSLINGERS_ENV in ('PROD', 'BETA')
            if prod_or_beta or not settings.DEBUG:
                # don't run this on prod or beta, as it may dangerously
                # delete any tickets that share a short id with test db tickets
                shutil.rmtree(ticket.dir)

            ticket.delete()
        self.user.delete()


class BasePokerSupportTest(BaseSupportTest):
    def setUp(self):
        super().setUp()

        self.controller = make_bot_game(2, NL_HOLDEM)
        self.table = self.controller.accessor.table

    def tearDown(self):
        self.table.player_set.all().delete()
        self.table.delete()


class IncidentTest(BaseSupportTest):
    def test_basic_incident_creation(self):
        notes = 'Testing support ticket creation'
        e = ValueError(
            'Test ValueError raised by support.tests.BasicIncidentTest'
        )

        try:
            raise e
        except ValueError as exc:
            tb = traceback.format_exc()

            ticket = SupportTicket.objects.create(
                subject=notes,
                source=TicketSource.ADMIN,
                reported_by=self.user,
            )

            save_settings_info(ticket)
            save_user_info(ticket, self.user)
            save_notes(ticket, notes)
            save_traceback(ticket, exc, tb)
            report_ticket(ticket)

        assert os.path.exists(ticket.dir), 'Ticket dir was not created'

        assert read_settings_info(ticket).get('PID') == settings.PID

        # test basic artifact writing and reading
        with open(os.path.join(ticket.dir, USER_INFO_PATH), 'r') as f:
            user_info = json.load(f)
            assert user_info == read_user_info(ticket)
            assert ticket.reported_by == self.user
            assert user_info.get('username') == self.user.username

        with open(os.path.join(ticket.dir, NOTES_PATH), 'r') as f:
            assert notes in f.read() and notes in read_notes(ticket)

        with open(os.path.join(ticket.dir, TRACEBACK_PATH), 'r') as f:
            exc_content = f.read()
            assert e.__class__.__name__ in exc_content, (
                f'Exception class not present in {ticket.dir}/{TRACEBACK_PATH}'
            )
            assert str(e) in exc_content, (
                f'Exception str not present in {ticket.dir}/{TRACEBACK_PATH}'
            )
            assert tb in exc_content, (
                f'Traceback not present in {ticket.dir}/{TRACEBACK_PATH}'
            )

        communication_logs = read_communication_log(ticket)
        assert len(communication_logs) >= 2, (
            'Fewer than 3 communication logs found (did a ticket report fail?)')

        assert all(comm.get('ts') for comm in communication_logs)

    def test_support_page(self):
        """test support page request -> SupportTicket creation process"""

        subject = 'Test request subject abcdef'
        details = 'This is a body for a support request from the support page'
        ticket = ticket_from_support_page(subject, details, self.user)

        assert subject in ticket.subject
        assert ticket.source == TicketSource.SUPPORT_PAGE
        assert details in read_notes(ticket)
        assert read_settings_info(ticket).get('PID') == settings.PID
        assert read_user_info(ticket).get('username') == self.user.username


class PokerIncidentTest(BasePokerSupportTest):
    def test_tablebeat_exception(self):
        """test tablebeat exception -> SupportTicket creation process"""

        e = Exception('Test tablebeat exception')
        e.table_id = self.table.id
        tb = 'Fake test traceback 123...\na\nb\nc'

        tablebeat_info = {
            'table_id': self.table.id,
            'table_ts': self.table.modified,
            'tablebeat_pid': 12345,
            'queued_message': {'player_id': 'abc12543', 'action': 'FOLD'},
            'table_hand_number': self.table.hand_number,
            'next_to_act': self.controller.accessor.next_to_act(),
        }
        ticket = ticket_from_tablebeat_exception(
            self.table,
            e,
            tb,
            tablebeat_info,
        )

        assert 'Tablebeat exception' in ticket.subject
        assert ticket.table == self.table
        assert ticket.source == TicketSource.TABLEBEAT_EXC
        assert read_user_info(ticket) is None
        assert str(e) in ticket.subject
        assert str(e) in read_traceback(ticket)
        assert tb in read_traceback(ticket)
        assert read_settings_info(ticket).get('PID') == settings.PID

        queued_tablebeat_msg = tablebeat_info['queued_message']
        reported_msg = read_tablebeat_info(ticket)['queued_message']
        assert queued_tablebeat_msg == reported_msg

        assert read_table_info(ticket)['hand_number'] == self.table.hand_number

        replayer = read_hh_to_replayer(ticket, fast_forward=True)
        assert_equivalent_game_states(
            self.controller.accessor,
            replayer.controller.accessor,
        )


    def test_botbeat_exception(self):
        """test botbeat exception -> SupportTicket creation process"""

        e = Exception('Test botbeat exception')
        e.table_id = self.table.id
        tb = 'Fake test traceback 223...\na\nb\nc'

        botbeat_info = {
            'stupid_bots': True,
            'botbeat_pid': 22345,
            'queued_tables': ['abcedfg1', 'badsfw2'],
            'table_name': self.table.name,
            'table_id': self.table.id,
            'tablebeat_pid': 32345,
        }
        ticket = ticket_from_botbeat_exception(
            self.table,
            e,
            tb,
            botbeat_info,
        )

        assert 'Botbeat exception' in ticket.subject
        assert ticket.table == self.table
        assert ticket.source == TicketSource.BOTBEAT_EXC
        assert read_user_info(ticket) is None
        assert str(e) in ticket.subject
        assert str(e) in read_traceback(ticket)
        assert tb in read_traceback(ticket)
        assert read_settings_info(ticket).get('PID') == settings.PID

        botbeat_table_queue = botbeat_info['queued_tables']
        reported_queue = read_botbeat_info(ticket)['queued_tables']
        assert botbeat_table_queue == reported_queue

        assert read_table_info(ticket)['hand_number'] == self.table.hand_number

        replayer = read_hh_to_replayer(ticket, fast_forward=True)
        assert_equivalent_game_states(
            self.controller.accessor,
            replayer.controller.accessor,
        )

    def test_table_report_bug(self):
        """test table report bug -> SupportTicket creation process"""

        frontend_log = {
            'notes': 'User inputted some notes here',
            'user': {'username': self.user.username},
            'url': self.table.path,
        }

        ticket = ticket_from_table_report_bug(
            self.table,
            frontend_log['notes'],
            frontend_log,
            self.user,
        )

        assert read_settings_info(ticket).get('PID') == settings.PID
        assert ticket.table == self.table
        assert ticket.source == TicketSource.TABLE_REPORT_BUG
        assert frontend_log['notes'] in read_notes(ticket)

        bug_report_user = read_user_info(ticket).get('username')
        assert bug_report_user == self.user.username

        reported_hand_number = read_table_info(ticket).get('hand_number')
        assert reported_hand_number == self.table.hand_number

        assert read_frontend_log(ticket) == frontend_log

        replayer = read_hh_to_replayer(ticket, fast_forward=True)
        assert_equivalent_game_states(
            self.controller.accessor,
            replayer.controller.accessor,
        )
