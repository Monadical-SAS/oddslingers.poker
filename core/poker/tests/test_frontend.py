"""Test poker view+handlers via mock websocket & http requests"""

# import os
# import json
# from decimal import Decimal

# from django.urls import reverse

# from ui.test_utils import FrontendTest
# from banker.mutations import buy_chips
# from sockets.constants import ROUTING_KEY as TYPE

# from ..constants import Action, HH_TEST_PATH
# from ..replayer import ActionReplayer
# from ..game_utils import make_game
# from ..controllers import controller_for_table
# from ..models import PokerTable
# from ..tablebeat import start_tablebeat
# from ..mutations import execute_mutations


# ### Poker handler test helpers

# class PokerFrontendTest(FrontendTest):
#     """Tests a poker handler. User is logged in but not a player."""

#     def setUp(self, *args, **kwargs):
#         controller = self.setup_game()
#         accessor = controller.accessor
#         self.table_id = accessor.table.id
#         self.short_id = accessor.table.short_id

#         url = accessor.table.path
#         super().setUp(url, *args, **kwargs)

#     def setup_game(self):
#         table_params = {
#             'num_seats': 6,
#             'sb': 1,
#             'bb': 2,
#         }
#         ctrl = make_game(
#             'Test Table',
#             table_params,
#             num_bots=4,
#         )
#         start_tablebeat(ctrl.table)
#         return ctrl

#     def get_controller(self):
#         table = PokerTable.objects.get(id=self.table_id)
#         return controller_for_table(table)

#     def tearDown(self):
#         accessor = self.get_controller().accessor

#         for player in accessor.players:
#             player.delete()
#             player.user.delete()
#         accessor.table.delete()

#         super().tearDown()


# class PlayerTest(PokerFrontendTest):
#     """User is logged-in and is a player at self.table"""

#     def setUp(self):
#         self.user = self.setup_user(username='test_user')
#         execute_mutations(
#           buy_chips(self.user, 10000)
#         )

#         super().setUp(setup_user=False)

#         self.player = self.setup_player()

#     def setup_player(self):
#         self.send({TYPE: 'JOIN_TABLE'})
#         response = self.receive()
#         assert response.get('privado'), (
#             'Response to JOIN_TABLE was not a private gamestate')

#         return self.user.player_set.get(
#             table_id=self.get_controller().table.id,
#         )


# ### Test behavior of poker handler with various auth levels
# class SpectatorBasicsTest(PokerFrontendTest):
#     """Ensure game spectators cant perform player actions"""

#     def test_unauthorized_message(self):
#         """make sure AnonymousUser actions are rejected"""

#         handler = self.send({TYPE: 'BET', 'amt': '1000000'})
#         assert handler.player is None
#         assert handler.table.id == self.get_controller()\
#                                                 .accessor\
#                                                 .table\
#                                                 .id

#         response = self.receive()
#         assert response and response.get(TYPE) == 'ERROR'

#     def test_table_hello(self):
#         """make sure the HELLO call/response process works"""

#         self.send({TYPE: 'HELLO'})
#         response = self.receive()
#         assert response and response.get(TYPE) == 'GOT_HELLO'

#     def test_force_action(self):
#         """make sure FORCE_ACTION isn't publicly accessable"""

#         self.send({TYPE: 'FORCE_ACTION', 'action': 'FOLD'})
#         response = self.receive()
#         assert response and response.get(TYPE) == 'ERROR'


# class AnonBasicsTest(SpectatorBasicsTest):
#     """Ensure non-logged-in users behave the same as logged-in spectators"""

#     is_authenticated = False


# class PlayerBasicsTest(PlayerTest):
#     """Ensure logged-in table players actions are accepted"""

#     def test_set_auto_rebuy(self):
#         """make sure Player actions like set_auto_rebuy are accepted"""

#         # make sure the handler correclty identified us
#         handler = self.send({
#             'type': Action.SET_AUTO_REBUY,
#             'amt': '100',
#         })
#         assert handler.player.id == self.player.id
#         assert handler.table.id == self.get_controller()\
#                                                 .accessor\
#                                                 .table\
#                                                 .id

#         # make sure we got the auto rebuy confirmation notification
#         response = self.receive()
#         assert response.get(TYPE) != 'ERROR' and response['notifications']
#         assert response['notifications'][0]['type'] == 'rebuy_notification'

#     def test_sit_in_immediately(self):
#         """make sure the Player can sit in"""
#         self.send({TYPE: Action.SIT_IN})
#         response = self.receive()

#         assert response['privado'] and response['animations']

#         snapto = response['animations'][0]
#         player_id = str(self.player.id)

#         assert snapto['type'] == 'SNAPTO'
#         assert not snapto['value']['players'][player_id]['sit_in_at_blinds']
#         assert snapto['value']['players'][player_id]['sit_in_next_hand']


# class TestFrontendFromHH(FrontendTest):
#     def setUp(self):
#         filename = os.path.join(HH_TEST_PATH, 'blinds_wrong.json')
#         with open(filename, 'r') as f:
#             hh = json.load(f)

#         self.replayer = ActionReplayer(hh)
#         self.replayer.step_forward()
#         self.table = self.replayer.controller.table
#         url = self.table.path

#         super().setUp(url)

#     def tearDown(self):
#         self.replayer.delete()
#         super().tearDown()

#     def test_basics(self):
#         response = self.request()
#         assert response.status_code == 200
#         props = response.context['props']
#         assert 'gamestate' in props
#         assert 'table' in props['gamestate']
#         assert props['gamestate']['table']['id'] == str(self.table.id)


# class TestFrontendDebugger(FrontendTest):
#     def setUp(self):
#         filename = "a_few_hands"
#         extension = ".json"
#         file = os.path.join(HH_TEST_PATH, f'{filename}{extension}')
#         with open(file, 'r') as f:
#             hh = json.load(f)

#         self.user = self.setup_user("username")
#         self.user.is_staff = True
#         self.user.save()
#         self.replayer = ActionReplayer(hh)
#         self.table = self.replayer.controller.table
#         url = self.getUrl(filename)

#         super().setUp(url, setup_user=False)

#     def tearDown(self):
#         self.replayer.delete()
#         super().tearDown()


# class TestFrontendDebuggerRedirect(TestFrontendDebugger):

#     def getUrl(self, filename):
#         return reverse('TableDebugger', kwargs={"file_or_id": filename})

#     def test_redirect(self):
#         response = self.request()
#         assert response.status_code == 302
#         assert response.url == "/debugger/a_few_hands/8/0/"


# class TestFrontendDebuggerView(TestFrontendDebugger):

#     def setUp(self):
#         self.hand_number = 8
#         self.action_idx = 0
#         super().setUp()

#     def getUrl(self, filename):
#         return reverse('TableDebugger',
#                         kwargs={
#                             "file_or_id": filename,
#                             "hand_number": self.hand_number,
#                             "action_idx": self.action_idx,
#                             "username": None
#                         })

#     def test_response(self):
#         response = self.request()
#         assert response.status_code == 200

#         props = response.context['props']
#         assert 'gamestate' in props

#         gamestate = props['gamestate']
#         assert 'table' in gamestate

#     def test_gamestate(self):
#         response = self.request()
#         gamestate = response.context['props']['gamestate']
#         # Reset hand replayer to current gamestate
#         self.replayer.skip_to_hand_number(self.hand_number)

#         assert "players" in gamestate
#         gamestate_players = gamestate["players"].values()
#         players = self.replayer.controller.accessor.players
#         assert len(gamestate_players) == len(players)

#         for player in players:
#             # Get the players with the username
#             gs_players = list(filter(
#                 lambda p: p['username'] == player.username,
#                 gamestate_players,
#             ))
#             # Only one player
#             assert len(gs_players) == 1

#             gs_player = gs_players[0]

#             assert gs_player['username'] == player.username
#             assert Decimal(gs_player['stack']['amt']) == player.stack
#             assert Decimal(gs_player['uncollected_bets']['amt']) == \
#                    player.uncollected_bets
#             assert gs_player['position'] == player.position
