"""
Poker and general integration tests.

./manage.py integration_test poker''')
"""

import os
import unittest
import requests

from django.urls import reverse

from sockets.models import ROUTING_KEY, HELLO_TYPE, GOT_HELLO_TYPE
from sockets.integration_tests import (connect_socket, send_action, 
                                       recv_json, recv_all_json)


BASE_URL = os.environ.get('ODDSLINGERS_URL', 'http://127.0.0.1:8000')
WS_BASE_URL = os.environ.get('ODDSLINGERS_WS_URL', 
                             BASE_URL.replace('https://', 'wss://')\
                             .replace(':443', '')\
                             .replace(':80', ''))
VERIFY_SSL = os.environ.get('SERVER_TEST_VERIFY_SSL', 'True') == 'True'
TIMEOUT = int(os.environ.get('SERVER_TEST_TIMEOUT', 2))
LOAD_FACTOR = int(os.environ.get('SERVER_TEST_LOAD_FACTOR', 1))

# 0 is equivalent to ssl.CERT_NONE
WS_OPTS = {} if VERIFY_SSL else {'sslopt': {'cert_reqs': 0}}


### Integration Tests

class FullIntegrationTest(unittest.TestCase):
    user_settings = {
        'password': 'tCuq2;L{"Q-*xKmz6oy', 
        'player': None, 
        'socket': None,
    }
    users = [
        {'username': 'testuser1', **user_settings},
        {'username': 'testuser2', **user_settings},
        {'username': 'testuser3', **user_settings},
        {'username': 'testuser4', **user_settings},
        {'username': 'testuser5', **user_settings},
    ]
    table = {
        'table_type': 'NLHE',
        'sb': 1,
        'bb': 2,
        'num_bots': 0,
    }

    def test_01_user_signs_up(self):
        """test user signup via the /accounts/signup/ page"""

        signup_url = BASE_URL + reverse('Signup')
        print('\n' + signup_url)

        for user in self.users:
            # Sign the User up
            signup_page = requests.get(signup_url, verify=VERIFY_SSL)
            assert signup_page.ok, \
                    f'Failed to get signup page at {signup_url}'

            post_data = {
                'csrfmiddlewaretoken': signup_page.cookies['csrftoken'],
                'username': user['username'],
                'password': user['password'],
            }
            signup_response = requests.post(
                signup_url, 
                post_data, 
                cookies=signup_page.cookies, 
                verify=VERIFY_SSL, 
                allow_redirects=False
            )

            assert signup_response.ok
            print(f'Signed user {user["username"]} up '\
                  f'({signup_response.status_code} => '\
                  f'{signup_response.headers["Location"]})')

    def test_02_user_logs_in(self):
        """Test user login via the /accounts/login/ page"""

        login_url = BASE_URL + reverse('Login')
        print('\n' + login_url)

        for user in self.users:
            # Log the User in
            login_page = requests.get(login_url, verify=VERIFY_SSL)
            assert login_page.ok, f'Failed to get login page at {login_url}'

            post_data = {
                'csrfmiddlewaretoken': login_page.cookies['csrftoken'],
                'username': user['username'],
                'password': user['password'],
            }
            login_response = requests.post(
                login_url, 
                post_data, 
                cookies=login_page.cookies, 
                verify=VERIFY_SSL, 
                allow_redirects=False
            )

            assert login_response.ok
            assert login_response.cookies, \
                    f'Failed to get authentication cookie for logged '\
                    f'in user {user["username"]}\n{login_response.cookies}'

            user['cookies'] = login_response.cookies
            print(f'Logged user {user["username"]} in '\
                  f'({login_response.status_code} => '\
                  f'{login_response.headers["Location"]})')


    def test_03_user_gets_user_profile(self):
        """Test user profile fetch via /user/username/ page"""

        user_url = reverse("UserProfile", args=("USERNAME",))
        profile_url = f'{BASE_URL}{user_url}?props_json=1'
        print('\n' + profile_url)

        for user in self.users:
            assert 'cookies' in user and 'sessionid' in user['cookies'], \
                    'Previous test failed to run, no logged-in session '\
                   f'for user {user["username"]}.'
            # Get the user's profile page
            prof_url = profile_url.replace('USERNAME', user['username'])
            
            profile_response = requests.get(
                prof_url,
                cookies=user['cookies'],
                verify=VERIFY_SSL,
            )

            resp_json = profile_response.json()


            assert profile_response.ok and resp_json, \
                    f'Failed to get user profile page for '\
                    f'{user["username"]} at {prof_url}'

            assert 'user' in resp_json and resp_json['user'], \
                    f'Missing logged-in user info for current '\
                    f'user in response {user["username"]}\n'\
                    f'{user["cookies"]}\n'\
                    f'{profile_response.cookies}'

            assert 'email' in resp_json['profile_user'], \
                    f'Failed to get public profile data for user '\
                    f'{user["username"]} at {prof_url}\n'\
                    f'{user["cookies"]}\n'\
                    f'{resp_json}'

            # Update our representation of the user with their profile data
            user.update(resp_json['user'])

            print(f'Got user {user["username"]} profile page '\
                  f'({profile_response.status_code})')


    def test_04_user_makes_table(self):
        """Test user creating a table on the tables page"""

        user = self.users[0]
        assert 'date_joined' in user, \
                'Previous test failed, missing logged-in user data.'

        tables_page_url = BASE_URL + reverse('Tables')
        print('\n' + tables_page_url)

        table_args = {
            **self.table,
            'csrfmiddlewaretoken': user['cookies']['csrftoken'],
        }

        table_response = requests.post(
            tables_page_url,
            table_args,
            cookies=user['cookies'],
            verify=VERIFY_SSL,
        )

        assert table_response.ok and 'path' in table_response.json(), \
                f'Failed to create new table at {table_response.url} '\
                f'({table_response.status_code})\n{table_args}'

        path = table_response.json()['path']
        short_id = path.split('/')[-2]

        assert path and '/' in path and short_id, \
                f'Failed to parse table short_id "{short_id}" '\
                f'from path "{path}"'

        self.table.update({
            'path': path,
            'short_id': short_id,
        })
        print(f'Created new table {path}')


    def test_05_users_connect_to_table(self):
        """
        Test users getting a table page and connecting to the table 
        via websockets
        """

        assert 'path' in self.table and self.table['path'], \
                'Previous test failed to run, missing path on self.table'

        table_url = BASE_URL + self.table['path'] + '?props_json=1'
        table_ws_url = WS_BASE_URL + self.table['path']
        print('\n' + table_url)

        for user in self.users:
            table_response = requests.get(
                table_url, 
                cookies=user['cookies'], 
                verify=VERIFY_SSL
            )
            resp_json = table_response.json()

            assert table_response.ok and 'gamestate' in resp_json, \
                    f'Failed to get gamestate when requesting table '\
                    f'{table_url} ({table_response.status_code})\n'\
                    f'{resp_json}'

            socket = connect_socket(
                table_ws_url,
                cookie=user['cookies']['sessionid'],
                **WS_OPTS,
            )

            response = recv_json(socket, timeout=3)
            assert (response[ROUTING_KEY] == 'SET_GAMESTATE' 
                        and 'table' in response and 'players' in response), \
                     'Failed to get initial SET_GAMESTATE message when '\
                    f'landing on table.\n{response}'

            # clear buffer so next message is expected response
            recv_all_json(socket, timeout=1)  

            self.table.update(response['table'])

            send_action(socket, HELLO_TYPE)
            response = recv_json(socket, timeout=3)

            assert response and response[ROUTING_KEY] == GOT_HELLO_TYPE, \
                    f'{user["username"]} failed to get a GOT_HELLO '\
                    f'back from the table\n{response}'

            user['socket'] = socket

            print(f'Connected user {user["username"]} to table '\
                  f'{self.table["path"]}')

    def test_06_users_sitting_down(self):
        """Test users sitting down at the table via websocket action"""

        pass
        # first user who creates the table is always sat out till others join
        for user in self.users[1:]:
            socket = user['socket']
            assert socket, \
                    f'Previous test failed. \(No socket was set up for \
                      user {user["username"]})'

            # clear buffer so next message is expected response
            recv_all_json(socket, timeout=1)  

            send_action(socket, 'JOIN_TABLE')
            response = recv_json(socket, timeout=3)

            assert response and response[ROUTING_KEY] == 'UPDATE_GAMESTATE', \
                    f'{user["username"]} failed to get an UPDATE_GAMESTATE '\
                    f'response after trying JOIN_TABLE\n{response}'

            for player in response['players'].values():
                if player['username'] == user['username']:
                    break
            else:
                assert False, \
                        f'{user["username"]} was not in the tables '\
                        f'players after trying JOIN_TABLE\n{response}'

                assert not player['sitting_out'], \
                        f'{user["username"]} is on the table, but is '\
                        f'still sat out after trying JOIN_TABLE\n{player}'

            user['player'] = player
            self.table.update(response['table'])

        print(f'{player["username"]} sat in to table {self.table["name"]}')


    def test_07_players_acting(self):
        """Test players sending poker actions to the table"""
        pass

    def test_08_players_timing_out(self):
        """Test players getting autofolded due to inactivity"""
        pass

    def test_09_players_leaving(self):
        """Test players sitting out and cashing out of a table"""
        pass

    # TODO: cleanup test users & table so as not to pollute production data
