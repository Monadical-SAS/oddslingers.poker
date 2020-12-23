import traceback
import logging

from typing import Tuple

from django.conf import settings
from django.utils import timezone
from django.contrib.sessions.models import Session
from channels.generic.websockets import JsonWebsocketConsumer

from oddslingers.utils import ANSI, debug_print_io, log_io_message
from oddslingers.models import UserSession
from .models import Socket
from .constants import (
    PING_RESPONSE_TYPE,
    HELLO_TYPE,
    GOT_HELLO_TYPE,
    RECONNECT_TYPE,
    TIME_SYNC_TYPE,
    ROUTING_KEY,
)

logger = logging.getLogger('sockets')


class RoutedSocketHandler(JsonWebsocketConsumer):
    """All the methods and attributes available to every websocket request"""

    ### Properties used to set up JsonWebsocketConsumer behavior

    # by default, dont require user to be logged in to get messages
    login_required: bool = False
    # guess the user from the http connection header, and attach
    #   it to all messages
    http_user_and_session: bool = True
    socket: Socket = None

    # add shared handlers you want every websocket to have here:
    routes: Tuple[Tuple[str, str], ...] = (
        # the first parameter is a string for exact matching
        #   against the incoming type key
        # the second parameter is either a function, the string
        #   name of the handler function on self
        # e.g. ('GET_TABLE', 'on_get_table')
        (PING_RESPONSE_TYPE, 'on_ping'),
        (HELLO_TYPE, 'on_hello'),
        (TIME_SYNC_TYPE, 'on_time_sync'),
    )

    def setup_session(self, extra: dict=None):
        """initialize the socket DB model which persists the socket info"""
        extra = extra or {}
        if self.message.http_session:
            session_key = self.message.http_session.session_key
            extra['session_id'] = session_key

        self.socket, created = Socket.objects.update_or_create(
            channel_name=self.reply_channel.name,
            defaults={
                'user': self.user,
                'path': self.path,
                'active': True,
                'last_ping': timezone.now(),
                **extra,
            },
        )

    @property
    def reply_channel(self):
        return self.message.reply_channel

    @property
    def view_name(self):
        return self.__class__.__name__

    @property
    def user(self):
        if not self.message.user.is_authenticated:
            return None
        return self.message.user

    def connect(self, message: dict=None, initialize: bool=True):
        """called when the socket connects
           (non-blocking, runs in parallel thread to receive)
        """
        ip_header = [
            header[1] for header in message.get('headers', [])
            if header[0] == b'x-real-ip'
        ]
        fallback_ip = message.get('client', [None])[0]
        user_ip = ip_header[0] if ip_header else fallback_ip
        user_ip = user_ip.strip() if user_ip else None

        if isinstance(user_ip, bytes):
            user_ip = user_ip.decode()

        self.setup_session({'user_ip': user_ip})
        if initialize:
            # must send an empty reply immediately to open the channel
            # otherwise initial socket HANDSHAKE is never finished
            self.socket.reply_channel.send({'accept': True})

    def disconnect(self, message, **kwargs):
        """called when the socket disconnects
           (non-blocking, runs in parallel thread to receive)
        """
        self.setup_session()
        user_ip = self.socket.user_ip
        created = self.socket.created
        last_ping = self.socket.last_ping
        now = timezone.now()
        self.socket.delete()

        disconnect_code = message.content.get('code')

        if disconnect_code == 1006:
            details = {
                'code': disconnect_code,
                'path': message.content['path'],
                'socket_age': str(last_ping - created),
                'time_since_last_ping': str(now - last_ping),
                'user_id': self.user.id if self.user else None,
                'user_ip': user_ip,
                'username': self.user.username if self.user else 'anon',
                'email': self.user.email if self.user else None,
            }
            print(
                f'{ANSI["red"]}[!] Dropped websocket connection!'
                f'{ANSI["reset"]}'
            )
            if settings.DEBUG:
                print('\n'.join(f'{k}: {v}' for k, v in details.items()))
            else:
                logger.warning(
                    ('Dropped websocket due to bad network, '
                     'nginx restart, or overloaded server.'),
                    extra=details,
                )

    def send_action(self, action_type: str, **kwargs):
        """
        send a websocket action with the given type and args to the user
        """
        self.setup_session()
        self.socket.send_action(action_type=action_type, **kwargs)

    def check_authentication(self, content=None):
        """ensure the user is authorized for the given websocket message"""

        if self.login_required and not self.message.user.is_authenticated:
            # User needs to reconnect to access sesion data (happens
            #   when redis sessions table is erased)
            self.send_action(
                RECONNECT_TYPE,
                details='No session was attached to socket, '\
                        'the frontend should try reconnecting.'
            )
            return False
        return True

    def match_handler(self, content):
        """find the handler function for a given json websocket message"""
        action_type = content.get(ROUTING_KEY)

        # run through route patterns looking for a match to handle the msg
        for pattern, handler in reversed(self.routes):
            # if pattern is a compiled regex, try matching it
            if hasattr(pattern, 'match') and pattern.match(action_type):
                return handler
            # if pattern is just a str, check for exact match
            if action_type == pattern:
                return handler

        return None

    def call_handler(self, handler, content):
        """call the handler function with a given json websocket message"""
        try:
            if handler:
                self.log_message(out=False, content=content, unknown=False)

                if hasattr(handler, '__call__'):
                    # if handler is a function already, call it
                    handler(self, content)
                else:
                    # otherwise fetch the function on self with the
                    #   handler's name
                    handler_func = getattr(self, handler, None)
                    assert handler_func, \
                            f'No handler function with name {handler} exists'
                    handler_func(content)
            else:
                self.default_route(content)
        except Exception as e:
            if settings.DEBUG and not settings.IS_TESTING:
                # if backend exception occurs, send over websocket for display
                stacktrace = traceback.format_exc()
                self.send_action(
                    'ERROR',
                    success=False,
                    errors=[repr(e)],
                    details=stacktrace,
                )
                print(stacktrace)
            elif not settings.DEBUG or settings.IS_TESTING:
                self.send_action(
                    'ERROR',
                    success=False,
                    details=repr(e),
                    errors=[
                        'An error occured while processing your request, '
                        'please contact support or try again.'
                    ],
                )
            if not settings.DEBUG and not settings.IS_TESTING:
                logger.exception(e, extra={
                        'user': self.user.attrs(
                            'id', 'username', 'email', 'first_name',
                            'last_name', 'date_joined', 'is_staff',
                            'is_active'
                        )
                        if self.user else None
                    },
                )

    def receive(self, content: dict, **kwargs):
        """pass parsed json message to appropriate handler in self.routes"""

        self.setup_session()

        if not self.check_authentication(content):
            return None

        assert 'USER_ID' not in content and 'USERNAME' not in content, (
            'Reserved keys USER_ID and USERNAME cannot be used in the top-level'
            'of socket messages.')

        content['USER_ID'] = self.user.id if self.user else None
        content['USERNAME'] = self.user.username if self.user else None
        log_io_message(self.socket, direction='in', content=content)

        handler = self.match_handler(content)
        self.call_handler(handler, content)

    def default_route(self, content: dict):
        """default handler for messages that dont match any route patterns"""
        self.log_message(out=False, content=content, unknown=True)
        self.send_action(
            'ERROR',
            details=f'Unknown action: {content.get(ROUTING_KEY)}'
        )
        # logger.warning(f'Unrecognized websocket msg: {content}')

    def on_hello(self, content: dict):
        """
        respond to websocket initial HELLO, confirms connection
        and round-trip-time
        """
        self.send_action(
            GOT_HELLO_TYPE,
            user_id=self.user.id if self.user else None,
            path=self.path,
            # last_ping=self.socket.last_ping,
            # user_ip=self.socket.user_ip,
        )

        if self.message.http_session:
            session_key = self.message.http_session.session_key
            session = (Session.objects
                              .filter(pk=session_key)
                              .only('expire_date').last())
            user_session = (UserSession.objects
                                       .filter(session_id=session_key)
                                       .only('id')
                                       .last())
            if user_session and session:
                user_session.expire_date = session.expire_date
                user_session.save()
            else:
                if settings.DEBUG:
                    pass
                else:
                    # Can be caused by bad django restart and/or
                    #   bad redis session data
                    raise Exception(
                        'Missing a Session for a currently active user'
                    )

        # when the user refreshes/loads a page
        # confirm any other sockets they own on the same page are active
        self.socket.cleanup_stale()

    def on_ping(self, content: dict):
        """
        when the frontend responds to a ping, confirm that their
        socket is still alive
        """
        pass

    def on_time_sync(self, content: dict):
        """
        when we get a request to synchronize time, send back an empty message
        """
        self.send_action(TIME_SYNC_TYPE)

    def log_message(self, out=True, content=None, unknown=False):
        """
        log pretty websocket messages to console for easy flow
        debugging
        """
        debug_print_io(out=out, content=content, unknown=unknown)
