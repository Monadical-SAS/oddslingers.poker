"""
    Shortcut for setting env config and calling ./manage.py test
    module.integration_tests
"""

import os
import unittest

from django.core.management.base import BaseCommand
from django.conf import settings

from .utils import split_hoststr, host_type, module_type

DEFAULT_TEST_TARGET = 'http://127.0.0.1:8000'


def get_evn_setup(host):
    # Integration test target url
    target = host or os.environ.get('ODDSLINGERS_URL', DEFAULT_TEST_TARGET)
    protocol, host, port = split_hoststr(target)
    ws_protocol = 'wss' if protocol == 'https' else 'ws'

    # Check whether this is a devserver with a self-signed cert or production
    if '.com' in host:
        VERIFY_SSL = True  # always verify ssl cert when testing production
    else:
        VERIFY_SSL = False

        # when testing deverser with self-signed cert, patch requests to stop
        #   noisy complaints (it's not practical to have 400+ lines of warnings
        #   obscure useful output during a load test)
        import requests
        from requests.packages.urllib3.exceptions import InsecureRequestWarning
        requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # standard ports dont need to be added to url string
    if str(port) in ('80', '443'):
        port_str = ''
    else:
        port_str = f':{port}'

    return {
        'ODDSLINGERS_URL': f'{protocol}://{host}{port_str}',
        'ODDSLINGERS_WS_URL': f'{ws_protocol}://{host}{port_str}',
        'SERVER_TEST_VERIFY_SSL': str(VERIFY_SSL),
        'SERVER_TEST_TIMEOUT': os.environ.get('SERVER_TEST_TIMEOUT', '10'),
        'SERVER_TEST_LOAD_FACTOR': os.environ.get('SERVER_TEST_LOAD_FACTOR', '1'),
    }


class Command(BaseCommand):
    help = 'Run the integration tests for a specified [module] on '\
           'a specified -h [host]\n(equivalent to ./manage.py test '\
           'module.integration_tests)'

    def add_arguments(self, parser):
        parser.add_argument('module', nargs='*', type=module_type, default=None)
        parser.add_argument('-H', '--host',
                            type=host_type,
                            required=False,
                            default=DEFAULT_TEST_TARGET)
        parser.add_argument('-f', '--failfast',
                            action='store_true',
                            dest='failfast',
                            default=False)


    def handle(self, *args, **options):
        modules = options['module']
        host = options['host']
        failfast = options['failfast']

        # set environment variables that integration tests use for config
        os.environ.update(get_evn_setup(host))

        # if no module is specified, run all integration_tests.py in
        #   INSTALLED_APPS
        if not modules:
            for app in settings.INSTALLED_APPS:
                try:
                    exec(f'import {app}.integration_tests')
                    modules.append(app)
                except:
                    pass

        # run each suite of integration_tests
        failures = []
        for module in modules:
            suite = unittest.TestLoader().discover(
                module + '.integration_tests',
                pattern='integration_tests.py'
            )
            if suite.countTestCases():
                result = unittest.TextTestRunner(failfast=failfast).run(suite)
                failures.extend(result.failures)

                # failfast
                if failfast and result.failures:
                    print(f'Tests interrupted due to failure in "{module}" '
                          f'out of [{", ".join(modules)}].')
                    print('\n'.join(str(f) for f in result.failures))
                    raise SystemExit(1)

        if failures:
            print('\n'.join(str(f) for f in result.failures))
            raise SystemExit(1)
