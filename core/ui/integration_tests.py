"""
Live ui integration tests to direct at a running django server.

./manage.py integration_test ui''')
"""

import os
import unittest
import requests

from django.conf import settings
from django.urls import reverse

from ui.views.base_views import BaseView
from ui.urls import urlpatterns


BASE_URL = os.environ.get('ODDSLINGERS_URL', 'http://127.0.0.1:8000')
WS_BASE_URL = os.environ.get('ODDSLINGERS_WS_URL', BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://').replace(':443', '').replace(':80', ''))
VERIFY_SSL = os.environ.get('SERVER_TEST_VERIFY_SSL', 'True') == 'True'
TIMEOUT = int(os.environ.get('SERVER_TEST_TIMEOUT', '5'))
LOAD_FACTOR = int(os.environ.get('SERVER_TEST_LOAD_FACTOR', '1'))
TARGET = 'prod' if VERIFY_SSL else 'dev'

### Behavior Tests

class TestBasics(unittest.TestCase):
    def test_all_urls_load(self):
        """make sure all simple urls in ui.urls load with a 200 code"""

        for pattern in urlpatterns:
            try:
                url = BASE_URL + reverse(pattern.name)
            except Exception:
                # URL requires extra arguments to reverse
                continue

            resp = requests.get(url, timeout=TIMEOUT, verify=VERIFY_SSL)

            # print('Got {} {} ({} bytes)'.format(resp.status_code, url.ljust(45), len(resp.content)))

            # Make sure all RedirectViews return a 200, or 300 redirect response
            if hasattr(pattern.callback, 'view_class'):
                assert resp.status_code == 200 or 300 <= resp.status_code < 400, 'RedirectView failed to return a redirect status code.'

            # Make sure all BaseView views return a valid 200 response
            if hasattr(pattern.callback, 'view_class') and isinstance(pattern.callback.view_class, BaseView):
                assert b'<html>' in resp.content
                assert resp.status_code == 200

        # print('All urls in ui.urls return expected responses.')

    def test_git_sha_matches_local_sha(self):
        """make sure our tests match up with the version of the code we are testing"""

        resp = requests.get(BASE_URL + '/?props_json=1', timeout=TIMEOUT, verify=VERIFY_SSL).json()

        assert resp['GIT_SHA'] == settings.GIT_SHA, (
            ('The host you are testing {0} is running a different version of the codebase from your integration tests ({1} vs {2}).\n  '
             'Is a stale version getting cached, or are you on a different branch from the target host?\n  '
             ' (runserver must be fully restarted in order for the GIT_SHA to reflect changes').format(
                BASE_URL,
                resp['GIT_SHA'],
                settings.GIT_SHA,
            )
        )

        # print('Git SHA on server {} matches git SHA of tests {}.'.format(resp['GIT_SHA'], settings.GIT_SHA))


### Load Tests

class TestRequestLoad(unittest.TestCase):
    """Load-test the django request system.  Hits:
        - staticfiles: django-provided staticfile system, or nginx depending on the host's setup
        - get requests: on non-websocket ReactPublicView pages
        - homepage: get the full homepage template render (with no socket connections)
    """

    def setUp(self):
        # must be imported after TestBasics runs because gevent.monkey_patch breaks requests.get('https://*') on python3.6
        # move this to the top once this issue is actually fixed https://github.com/gevent/gevent/issues/903  (make sure to test it!!!)
        import grequests
        global grequests

    def test_staticfile_load(self):
        """make our webserver can handle a decent static file load"""

        if TARGET != 'prod':
            # print('Skipping staticfile test for devserver, comment out this check to test it anyway.')
            return

        # easier workload and longer timeouts for single-threaded devserver
        if TARGET == 'prod':
            num_requests = LOAD_FACTOR * 100
            timeout = 3
        else:
            num_requests = LOAD_FACTOR * 20
            timeout = 2
        url = BASE_URL + '/static/images/chips.png'

        # concurrently fetch an image 100 times
        responses = grequests.imap(
            grequests.get(
                url,
                timeout=timeout,
                verify=VERIFY_SSL,
            )
            for _ in range(num_requests)
        )

        assert all(resp.status_code == 200 for resp in responses), \
            'Chips image failed to respond in {} seconds when {} requests were sent simultaneously.'.format(timeout, num_requests)

        # print('\nGot {} concurrent responses for {}'.format(num_requests, url))

    def test_staticpage_load(self):
        """make sure django can handle a decent static page request load"""

        if TARGET == 'prod':
            num_requests = LOAD_FACTOR * 40
            timeout = 4
        else:
            num_requests = LOAD_FACTOR * 15
            timeout = 3
        url = BASE_URL + '/about/'

        responses = grequests.imap(
            grequests.get(
                url,
                timeout=timeout,
                verify=VERIFY_SSL,
            )
            for _ in range(num_requests)
        )

        assert all(resp.status_code == 200 for resp in responses), \
            'About page failed to respond in {} seconds when {} requests were sent simultaneously.'.format(timeout, num_requests)

        # print('\nGot {}  concurrent responses for {}'.format(num_requests, url))


    def test_homepage_load(self):
        """make sure django can handle a decent complex page request load"""

        if TARGET == 'prod':
            num_requests = LOAD_FACTOR * 20
            timeout = 6
        else:
            num_requests = LOAD_FACTOR * 10
            timeout = 4
        url = BASE_URL + '/'

        responses = grequests.imap(
            grequests.get(
                url,
                timeout=timeout,
                verify=VERIFY_SSL,
            )
            for _ in range(num_requests)
        )

        assert all(resp.status_code == 200 for resp in responses), \
            'Homepage failed to respond in {} seconds when {} requests were sent simultaneously.'.format(timeout, num_requests)

        # print('\nGot {}  concurrent responses for {}'.format(num_requests, url))


# TODO: write django Client view tests for login/signup/logout/profile view
