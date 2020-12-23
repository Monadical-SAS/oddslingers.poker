"""UI testing helpers and utilites"""

from channels.test import ChannelTestCase, WSClient

from django.utils import timezone
from django.urls import reverse
from django.conf import settings
from django.http import HttpRequest
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser

from oddslingers.utils import to_json_str
from oddslingers.mutations import execute_mutations

from sockets.models import Socket

from banker.mutations import buy_chips



class FrontendTest(ChannelTestCase):
    """
    A base test class which provides functions for interacting w/ the
    backend via mock websocket & http connections.  Logs all
    transmitted messages in self.http_to_backend, self.http_to_frontend
    self.ws_to_backend, self.ws_to_frontend
    """

    def setUp(self, url,
                    setup_user=True,
                    setup_http=True,
                    setup_ws=True):
        super().setUp()
        self.url = url

        # TODO: refactor this flag messyness

        if setup_user:
            self.user = self.setup_user('testuser')

        if setup_http:
            self.http_to_frontend = []
            self.http_to_backend =[]
            self.http = self.setup_http()
            self.initial_http_response = self.make_initial_http_request()

        if setup_ws:
            self.ws_to_frontend = []
            self.ws_to_backend = []
            self.sent_seq_num = 0
            self.recv_seq_num = 0
            self.ws = self.setup_ws()
            self.initial_ws_response = self.connect_ws()

    def tearDown(self):
        super().tearDown()
        self.teardown_user()

    def dump_frontend_log(self, filename=None, notes=None):
        """
        dump a replayable log of the test up to the current point in time
        """

        filename = filename or f'{self.__class__.__name__}_dump.json'
        table_dump = {
            'notes': notes,
            'settings': {
                'DEBUG': settings.DEBUG,
                'GIT_SHA': settings.GIT_SHA,
            },
            'user': self.user if self.user.is_authenticated else None,
            'http_to_backend': self.http_to_backend,    # aka requests
            'http_to_frontend': self.http_to_frontend,  # aka responses
            'ws_to_backend': self.ws_to_backend,
            'ws_to_frontend': self.ws_to_frontend,
            'time': {
                'server_time': timezone.now().timestamp() * 1000,
            }
        }

        with open(filename, 'w', encoding='utf-8') as f:
            f.write(to_json_str(table_dump, indent=4))

        print(f'[√] {self.__class__} dumped frontend log to: {filename}')

    ### Page Methods
    def setup_user(self, username=None):
        """overrside this to make requests as a specific self.user"""

        if username is None:
            return AnonymousUser()
        else:
            User = get_user_model()
            return User.objects.create_user(
                username=username,
                email='',
                password='batteryhorsecorrectstaple',
            )

    def teardown_user(self):
        if self.user and self.user.id:
            self.user.delete()

    ### HTTP Methods
    def setup_http(self):
        """setup a django Client() and get the initial page's props"""

        http = Client()
        if self.user.is_authenticated:
            http.force_login(self.user)

        return http

    def make_initial_http_request(self):
        # get initial page props
        return self.request({
            'url': self.url + '?props_json=1',
            'method': 'GET',
            'params': {},
        })

    def request(self, request: dict=None):
        """make an HTTP request to the backend, returns an HTTPResponse"""

        request = request or {}
        uname = self.user.username if self.user.is_authenticated else None
        request.update({
            'url': request.get('url', self.url),
            'method': request.get('method', 'GET'),
            'params': request.get('params', {}),
            'username': uname,
        })

        if request['method'] == 'GET':
            response = self.http.get(request['url'], request['params'])
        elif request['method'] == 'POST':
            response = self.http.post(request['url'], request['params'])
        elif request['method'] == 'PATCH':
            response = self.http.post(request['url'], request['params'])
        else:
            msg = 'Invalid request, expected: GET/POST/PATCH'
            raise NotImplementedError(msg)

        response_json = {
            'class': response.__class__.__name__,
            'status_code': response.status_code,
            'content': response.content,
            'url': getattr(response, 'url', None),
        }

        try:
            response_json['json'] = response.json()
            del response_json['content']
        except ValueError:
            pass

        self.http_to_backend.append(request)
        self.http_to_frontend.append(response_json)
        return response

    ### Websocket Methods
    def setup_ws(self):
        """
        setup a channels WSClient() connected to the handler for self.url
        """

        # setup websocket connection for our page
        ws = WSClient()
        if self.user.is_authenticated:
            ws.force_login(self.user)

        return ws

    def connect_ws(self) -> dict:
        """open a simulated WSClient websocket connection to the backend"""

        try:
            self.ws.send_and_consume('websocket.connect', {'path': self.url})
            self.ws_to_backend.append({
                'type': 'websocket.connect',
                'TIMESTAMP': str(timezone.now().timestamp() * 1000),
                'SEQ_NUM': self.sent_seq_num,
            })
            self.sent_seq_num += 1
            return self.receive()
        except AssertionError:
            # there is no handler for websocket.connect on this url
            pass

    def disconnect_ws(self):
        """send a clean WSClient disconnect to the backend handler"""
        try:
            handler = self.ws.send_and_consume('websocket.disconnect',
                                               {'path': self.url})
            self.ws_to_backend.append({
                'type': 'websocket.disconnect',
                'TIMESTAMP': str(timezone.now().timestamp() * 1000),
                'SEQ_NUM': self.sent_seq_num,
            })
            self.sent_seq_num += 1
            return handler
        except AssertionError:
            # there is no handler for websocket.disconnect on this url
            pass

    def send(self, action: dict):
        """
        send a ws msg from the frontend to the backend, returns a Handler
        """
        action.update({
            'TIMESTAMP': str(timezone.now().timestamp() * 1000),
            'SEQ_NUM': self.sent_seq_num,
        })
        self.sent_seq_num += 1

        handler = self.ws.send_and_consume('websocket.receive', {
            'path': self.url,
            'text': to_json_str(action),
        })
        self.ws_to_backend.append(action)
        return handler

    def receive(self) -> dict:
        """receive a json message from the backend sent to the frontend"""

        msg_to_frontend = self.ws.receive()
        self.recv_seq_num += 1
        if msg_to_frontend:
            msg_to_frontend.update({
                'SEQ_NUM': self.recv_seq_num,
            })
            self.ws_to_frontend.append(msg_to_frontend)
            return msg_to_frontend
        return None


class MockRequest(HttpRequest):
    """Mock of a Django request, with url name and absolute_uri overriden"""

    def __init__(self, client=None, user_defaults=None):
        super().__init__()
        client = client or Client()
        # TODO: a comment explaining this line, and also < 80 chars
        self.resolver_match = type('resolver_match', (), {'url_name': 'test_url'})()

        def build_absolute_uri():
            return 'http://oddslingers.com/TEST_URL'

        self.build_absolute_uri = build_absolute_uri
        User = get_user_model()
        self.user = User.objects.create_user(
            username='test_user',
            email='',
            password='correcthorsebatterystaple',
            **(user_defaults or {}),
        )
        self.session = client.session
        execute_mutations(
            buy_chips(self.user, 10000)
        )


class SimpleViewTest(TestCase):
    """
    View method testing (http requests and view methods only)
    Use FrontendTest instead if you need websocket and http testing.

    Inherit from this test to create a test that checks View
    functionality against a mocked request

    Usage:
        class MyViewTest(ViewTest):
            VIEW_CLASS = MyView   # specify the view class you want to test

            def test_context(self):
                # self.view, self.request, self.user are automatically
                #   provided for convenience

                assert 'user' self.view.get_context(self.request)
    """
    VIEW_CLASS = None
    _VIEW = None
    _USER = None
    _REQUEST = None

    @property
    def url(self):
        return reverse(self.VIEW_CLASS.__name__)

    @property
    def view(self):
        self._VIEW = self._VIEW or self.VIEW_CLASS()
        return self._VIEW

    @property
    def user(self):
        User = get_user_model()
        self._USER = self._USER or User.objects.create_user(
            username='test_user',
            email='',
            password='correcthorsebatterystaple',
        )
        execute_mutations(
            buy_chips(self._USER, 10000)
        )
        return self._USER

    @property
    def request(self):
        # make sure self._USER == self._REQUEST.user, and avoid
        #   creating 2 different users
        self.client = Client()
        if not self._REQUEST:
            self._REQUEST = MockRequest(self.client)
            if self._USER:
                self._REQUEST.user = self._USER
            else:
                self._USER = self._REQUEST.user
        return self._REQUEST

    def tearDown(self):
        User = get_user_model()
        User.objects.all().delete()
        Socket.objects.all().delete()
