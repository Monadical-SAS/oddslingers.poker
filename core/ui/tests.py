"""UI integration tests"""

import uuid
from decimal import Decimal

from django.conf import settings
from django.urls import reverse

from oddslingers.models import UserSession, User
from oddslingers.mutations import execute_mutations

from poker.models import PokerTable, Player, Freezeout
from poker.constants import TournamentStatus, TOURNEY_BUYIN_AMTS
from poker.game_utils import get_or_create_bot_user, get_n_random_bot_names

from sockets.router import SocketRouter

from banker.utils import balance
from banker.mutations import buy_chips, create_transfer

from .views.base_views import BaseView, PublicReactView
from .views.pages import Table, Sidebet, TournamentSummary
from .views.tables import Tables
from .views.leaderboard import Leaderboard, save_leaderboard_cache
from .views.accounts import UserProfile
from .test_utils import MockRequest, SimpleViewTest, FrontendTest


### Test Helpers

class StubPageForIntegrationTests(PublicReactView):
    """
    simple empty page served on dev & production to allow for easy
    integration tests & websocket load tests
    """
    url_pattern = r'^/?_test/$'
    socket = SocketRouter()
    props = {
        'body': ('This page is meant for robots only, click back in '
                 'your browser to return to the last page you were on.')
    }


### Base View Tests

class TestBaseView(SimpleViewTest):
    VIEW_CLASS = BaseView

    def test_base_template_default(self):
        """sanity check to make sure the default template is well-defined"""
        assert self.view.template == 'ui/base.html'

    def test_get_returns_httpresponse(self):
        """sanity check to make get() properly returns an HttpResponse"""
        # intentionally brittle, think carefully before changing response types
        assert self.view.get(self.request).__class__.__name__ in (
            'HttpResponse', 'HttpResponseWithCallback')

    def test_base_context(self):
        """make sure the basic required attrs are in the template context"""
        context = self.view.get_context(self.request)
        assert 'DEBUG' in context and context['DEBUG'] == settings.DEBUG
        assert 'user' in context and context['user']['username'] == 'test_user'
        assert context['user']['is_authenticated']

    def test_context_assembling(self):
        """
        test the proper compliation of context from the base_context and
        context property
        """
        self.view.context = {'test_context': 1}
        assert 'test_context' in self.view.get_context(self.request)


class TestPublicReactView(SimpleViewTest):
    VIEW_CLASS = PublicReactView

    def test_basics(self):
        TestBaseView.test_base_context(self)
        TestBaseView.test_get_returns_httpresponse(self)

    def test_base_template_default(self):
        assert self.view.template == 'ui/react_base.html'

    def test_base_props(self):
        """make sure the basic required attrs are in the props dict"""
        props = self.view.get_props(self.request)

        expected_fields = ('url_name', 'url', 'domain', 'view', 'user')
        assert all(field in props for field in expected_fields)
        assert props['user']['username'] == self.user.username

    def test_props_assembling(self):
        """
        test the proper compliation of props from the base_props
        and props property
        """
        self.view.props = {'test_prop': 1}
        props = self.view.get_props(self.request)

        assert props['test_prop'] == 1

    def test_hotloading_props_json(self):
        """test fetching only props json via get by using /url/?props_json=1"""
        req = MockRequest()
        req.GET = {'props_json': 1}

        assert self.view.get(req).__class__.__name__ == 'JsonResponse'


class TestTable(SimpleViewTest):
    VIEW_CLASS = Table

    def setUp(self):
        super().setUp()
        self.table = PokerTable.objects.create_table(name='Test Table')

    def test_no_table_found(self):
        """if table url 404s, go to table search page with query"""
        homepage_resp = self.view.get(self.request, id='abcd')

        assert homepage_resp.__class__.__name__ == 'HttpResponseRedirect'
        assert homepage_resp.url == '/tables/?search=abcd'

    def test_gamestate_in_props(self):
        """if table s found, make sure gamestate is served"""
        assert 'gamestate' in self.view.get_props(self.request,
                                                  id=self.table.id,
                                                  autostart_tablebeat=False)

    def test_fuzzy_redirect(self):
        """make sure fuzzy table urls redirect to the canonical table path"""
        homepage_resp = self.view.get(self.request,
                                      id=str(self.table.id),
                                      autostart_tablebeat=False)

        assert homepage_resp.__class__.__name__ == 'HttpResponseRedirect'
        assert homepage_resp.url == '/table/{}/'.format(self.table.short_id)

    def tearDown(self):
        super().tearDown()
        PokerTable.objects.all().delete()
        Player.objects.all().delete()


class TestTables(SimpleViewTest):
    VIEW_CLASS = Tables

    def setUp(self):
        self.table = PokerTable.objects.create(name='Test Table 1')
        self.table2 = PokerTable.objects.create(name='Test Table 2')
        self.table3 = PokerTable.objects.create(name='ABCDEFGHIJKLM')
        self.tournament = Freezeout.objects.create(name="Test Tourney")

    def test_successful_create_table(self):
        request = MockRequest()
        table_name = 'JJJJJJJJJJ'
        request.POST = {
            'sb': 1,
            'bb': 2,
            'table_name': table_name,
            'num_seats': 4,
            'num_bots': 0,
            'table_type': 'PLO',
            'min_buyin': 400,
        }

        resp = self.view.post(request, autostart_tablebeat=False)
        assert resp.__class__.__name__ == 'JsonResponse'
        assert b'"path":' in resp.content
        created_table = PokerTable.objects.filter(name=table_name).first()
        assert created_table
        assert created_table.sb == request.POST['sb']
        assert created_table.bb == request.POST['bb']
        assert created_table.num_seats == request.POST['num_seats']
        assert created_table.table_type == request.POST['table_type']
        assert created_table.min_buyin == request.POST['min_buyin']
        assert created_table.created_by == request.user
        assert created_table.max_buyin == Decimal(200 * request.POST['bb'])
        assert Player.objects.filter(table=created_table, user__is_robot=True)\
                             .count() == request.POST['num_bots']

    def test_create_private_table(self):
        request = MockRequest()
        table_name = 'JJJJJJJJJJ'
        request.POST = {
            'table_name': table_name,
            'sb': 1,
            'bb': 2,
            'num_seats': 4,
            'num_bots': 2,
            'is_private': 'true'
        }

        resp = self.view.post(request, autostart_tablebeat=False)
        assert resp.__class__.__name__ == 'JsonResponse'
        assert b'"path":' in resp.content
        created_table = PokerTable.objects.filter(name=table_name).first()
        assert created_table
        assert created_table.is_private

    def test_create_table_with_already_exist_table_name(self):
        request = MockRequest()
        table_name = 'Test Table 1'
        request.POST = {
            'table_name': table_name,
            'sb': 1,
            'bb': 2,
            'num_bots': 3,
        }

        assert PokerTable.objects.filter(name=table_name).count() == 1
        resp = self.view.post(request, autostart_tablebeat=False)
        assert resp.__class__.__name__ == 'JsonResponse'
        assert b'"path":' in resp.content
        assert PokerTable.objects.filter(name=table_name).count() == 1
        assert PokerTable.objects.filter(name=f'{table_name} #1').exists()
        resp = self.view.post(request, autostart_tablebeat=False)
        assert PokerTable.objects.filter(name=table_name).count() == 1
        assert PokerTable.objects.filter(name=f'{table_name} #2').exists()
        request.POST['table_name'] = self.tournament.name
        resp = self.view.post(request, autostart_tablebeat=False)
        assert PokerTable.objects.filter(name=table_name).count() == 1
        assert PokerTable.objects.filter(name=f'{table_name} #1').exists()

    def test_create_plo_table_with_sb_bigger_than_one_and_bots(self):
        request = MockRequest()
        table_name = 'JJJJJJJJJJ'
        request.POST = {
            'table_name': table_name,
            'sb': 12,
            'bb': 24,
            'num_seats': 4,
            'num_bots': 2,
            'table_type': 'PLO',
            'min_buyin': 400,
        }

        with self.assertRaisesMessage(
            AssertionError,
            "Can't add bots to PLO games with blinds bigger than 1/2"
        ):
            self.view.post(request, autostart_tablebeat=False)

    def test_successful_create_tournament(self):
        request = MockRequest()
        tourney_name = 'JJJJJJJJJJ'
        request.POST = {
            'table_name': tourney_name,
            'sb': 12,
            'bb': 24,
            'num_seats': 4,
            'table_type': 'PLO',
            'is_tournament': 'true',
            'is_private': 'false',
        }
        execute_mutations(
            buy_chips(request.user, 15000)
        )
        request.user.userbalance().refresh_from_db()

        resp = self.view.post(request, autostart_tablebeat=False)
        assert resp.__class__.__name__ == 'JsonResponse'
        assert b'"path":' in resp.content
        created_tournament = Freezeout.objects\
                                      .filter(name=tourney_name)\
                                      .first()
        assert created_tournament
        assert created_tournament.max_entrants == request.POST['num_seats']
        assert created_tournament.game_variant == request.POST['table_type']
        assert created_tournament.buyin_amt == TOURNEY_BUYIN_AMTS[0]
        assert created_tournament.tournament_admin == request.user
        assert created_tournament.created_by == request.user
        assert not created_tournament.is_private

    def test_create_tournament_with_already_exist_table_name(self):
        request = MockRequest()
        tourney_name = 'Test Tourney'
        request.POST = {
            'table_name': tourney_name,
            'sb': 24,
            'bb': 48,
            'is_tournament': 'true'
        }
        execute_mutations(
            buy_chips(request.user, 15000)
        )
        request.user.userbalance().refresh_from_db()

        assert Freezeout.objects.filter(name=tourney_name).count() == 1
        resp = self.view.post(request, autostart_tablebeat=False)
        assert resp.__class__.__name__ == 'JsonResponse'
        assert b'"path":' in resp.content
        assert Freezeout.objects.filter(name=tourney_name).count() == 1
        assert Freezeout.objects.filter(name=f'{tourney_name} #1').exists()
        resp = self.view.post(request, autostart_tablebeat=False)
        assert Freezeout.objects.filter(name=tourney_name).count() == 1
        assert Freezeout.objects.filter(name=f'{tourney_name} #2').exists()
        request.POST['table_name'] = self.table.name
        resp = self.view.post(request, autostart_tablebeat=False)
        assert Freezeout.objects.filter(name=tourney_name).count() == 1
        assert Freezeout.objects.filter(name=f'{tourney_name} #1').exists()

    def test_create_private_tournament(self):
        request = MockRequest()
        tourney_name = 'JJJJJJJJJJ'
        request.POST = {
            'table_name': tourney_name,
            'sb': 12,
            'bb': 24,
            'num_seats': 4,
            'is_private': 'true',
            'is_tournament': 'true',
        }
        execute_mutations(
            buy_chips(request.user, 15000)
        )
        request.user.userbalance().refresh_from_db()

        resp = self.view.post(request, autostart_tablebeat=False)
        assert resp.__class__.__name__ == 'JsonResponse'
        assert b'"path":' in resp.content
        created_tournament = Freezeout.objects\
                                      .filter(name=tourney_name)\
                                      .first()
        assert created_tournament
        assert created_tournament.is_private

    def tearDown(self):
        super().tearDown()
        PokerTable.objects.all().delete()
        Player.objects.all().delete()


class TestSidebet(SimpleViewTest):
    VIEW_CLASS = Sidebet

    def test_bets_in_props(self):
        view_props = self.view.get_props(self.request)
        assert 'bets' in view_props


class TestLeaderboard(SimpleViewTest):
    VIEW_CLASS = Leaderboard

    def setUp(self):
        self.test_user = User.objects.create_user(username='testuser1')
        self.test_user2 = User.objects.create_user(username='testuser2')
        self.test_user3 = User.objects.create_user(username='abcdefghij')
        self.table = PokerTable.objects.create_table(name='Test Table')

    def test_no_user_results(self):
        self.request.GET = {'search': 'blahblahblah'}
        self.view.get(self.request)

        resp_props = self.view.props(self.request)
        assert len(resp_props['current_top']) == 0

    def test_multiple_user_results(self):
        self.request.GET = {'search': 'testuser'}
        self.view.get(self.request)

        resp_props = self.view.props(self.request)
        assert len(resp_props['current_top']) == 2

    def test_save_cache(self):
        execute_mutations(
            create_transfer(self.table, self.user, 10000)
        )
        save_leaderboard_cache()


### Page View Tests (Page Integration Tests)
class TestUserProfile(SimpleViewTest):
    VIEW_CLASS = UserProfile

    def setUp(self):
        self.test_table = PokerTable.objects.create_table(name='Test Table 1')
        self.test_user = User.objects.create_user(
            username='testarudo',
            password='love',
            email='heart@happy.joy'
        )
        self.test_player = Player.objects.create(
            table=self.test_table,
            user=self.test_user,
            position=0,
            seated=False,
        )

    def test_active_tables(self):
        self.view.get(self.request, username=self.test_user.username)
        props = self.view.get_props(
            self.request,
            username=self.test_user.username
        )
        assert props['tables'] == None

        self.test_player.seated = True
        self.test_player.save()
        props = self.view.get_props(
            self.request,
            username=self.test_user.username
        )
        assert len(props['tables']) == 1
        assert props['tables'][0]['id'] == str(self.test_table.id)

    def tearDown(self):
        super().tearDown()
        PokerTable.objects.all().delete()
        Player.objects.all().delete()


class TestAbout(FrontendTest):
    def setUp(self):
        url = reverse('About')
        super().setUp(url)

    def test_real_client_get(self):
        response = self.request()

        assert response.status_code == 200
        assert response.context.get('user')
        assert response.context['user']['id']


class TestHomepage(FrontendTest):
    def setUp(self):
        url = reverse('Home')
        super().setUp(url)

    def test_basics(self):
        response = self.request()
        assert response.__class__.__name__ in (
            'HttpResponse', 'HttpResponseWithCallback'
        )

        props = response.context['props']
        assert 'user' in response.context
        assert 'user' in props
        assert self.user.id == props['user']['id']

        assert 'gamestate' in props
        assert 'table' in props['gamestate']
        assert props['gamestate']['table']['id']
        assert 'players' in props['gamestate']

        # Confirm user_logged_in_handler fired to create UserSession
        assert UserSession.objects.filter(
            user_id=self.user.id,
            session_id=self.http.session.session_key,
        ).exists()

    def tearDown(self):
        PokerTable.objects.all().delete()
        Player.objects.all().delete()
        super().tearDown()


class TestTournamentSummary(SimpleViewTest):
    VIEW_CLASS = TournamentSummary

    def setUp(self):
        super().setUp()
        self.tournament = Freezeout.objects\
                                   .create_tournament(name='Test tourney 1')

    def test_no_tournament_found(self):
        """if table url 404s, go to table search page with query"""
        id = str(uuid.uuid4())
        homepage_resp = self.view.get(self.request, id=id)

        assert homepage_resp.__class__.__name__ == 'HttpResponseRedirect'
        assert homepage_resp.url == f'/tables/?search={id}'

    def test_fuzzy_redirect(self):
        """make sure fuzzy table urls redirect to the canonical table path"""
        homepage_resp = self.view.get(self.request,
                                      id=str(self.tournament.id))

        assert homepage_resp.__class__.__name__ == 'HttpResponseRedirect'
        assert homepage_resp.url == f'/tournament/{self.tournament.short_id}/'

    def tearDown(self):
        super().tearDown()
        PokerTable.objects.all().delete()
        Freezeout.objects.all().delete()
        Player.objects.all().delete()


class TestTournamentSummaryActions(FrontendTest):
    def setUp(self, *args, **kwargs):
        self.tournament = Freezeout.objects.create_tournament(
            name='Test tourney 1',
            buyin_amt=TOURNEY_BUYIN_AMTS[0],
        )
        url = self.tournament.path
        super().setUp(url, *args, **kwargs)

    def _create_random_bot(self):
        bot_name = get_n_random_bot_names(self.tournament, 1)[0]
        return get_or_create_bot_user(bot_name)

    def test_on_join_tournament(self):
        """Test on_join_tournament method of the view"""
        execute_mutations(buy_chips(
            self.user,
            self.tournament.buyin_amt + Decimal(1000)
        ))
        self.user.userbalance().refresh_from_db()
        prev_user_balance = self.user.userbalance().balance
        prev_tourney_balance = balance(self.tournament)

        assert self.tournament.entrants.count() == 0
        self.send({'type': 'JOIN_TOURNAMENT'})

        self.user.userbalance().refresh_from_db()
        assert self.tournament.entrants.count() == 1
        assert not self.tournament.entrants.first().is_robot
        assert self.user.userbalance().balance == prev_user_balance - \
            self.tournament.buyin_amt
        assert balance(self.tournament) == prev_tourney_balance + \
            self.tournament.buyin_amt

    def test_on_join_tournament_without_chips(self):
        """Test for joining a tournament without balance"""
        assert not self.tournament.entrants.exists()
        self.send({'type': 'JOIN_TOURNAMENT'})
        assert not self.tournament.entrants.exists()

    def test_add_bot_to_tournament(self):
        """Test adding a bot to the tournament"""
        assert self.tournament.entrants.count() == 0
        self.send({'type': 'JOIN_TOURNAMENT', 'robot': True})

        assert self.tournament.entrants.count() == 1
        assert self.tournament.entrants.first().is_robot

    def test_on_leave_tournament(self):
        """Test on_leave_tournament method of the view"""
        self.tournament.entrants.add(self.user)

        assert self.tournament.entrants.count() == 1
        prev_user_balance = self.user.userbalance().balance
        prev_tourney_balance = balance(self.tournament)
        self.send({'type': 'LEAVE_TOURNAMENT'})
        self.user.userbalance().refresh_from_db()
        assert self.tournament.entrants.count() == 0
        assert self.user.userbalance().balance == prev_user_balance + \
            self.tournament.buyin_amt
        assert balance(self.tournament) == prev_tourney_balance - \
            self.tournament.buyin_amt

    def test_correct_admin_change(self):
        """Test the admin is correctly changed to another user"""
        self.tournament.entrants.add(self.user)
        new_user = User.objects.create_user(username='new_user')
        self.tournament.entrants.add(new_user)
        robot = self._create_random_bot()
        self.tournament.entrants.add(robot)
        self.tournament.tournament_admin = self.user
        self.tournament.save()

        assert self.tournament.entrants.count() == 3
        self.send({'type': 'LEAVE_TOURNAMENT'})
        self.tournament.refresh_from_db()
        assert self.tournament.entrants.count() == 2
        assert self.tournament.tournament_admin == new_user


    def test_no_bot_is_admin(self):
        """Test when we leave a tournament and there are no human player but
        bots, the admin is None"""
        self.tournament.entrants.add(self.user)
        robot = self._create_random_bot()
        self.tournament.entrants.add(robot)

        assert self.tournament.entrants.count() == 2
        self.send({'type': 'LEAVE_TOURNAMENT'})
        assert self.tournament.entrants.count() == 1
        assert self.tournament.tournament_admin is None

    def test_kick_player(self):
        """ Test on_leave_tournament method when a player is being kicked"""
        self.tournament.entrants.add(self.user)
        self.tournament.tournament_admin = self.user
        self.tournament.save()
        user2kick = User.objects.create_user(username='trumpy')
        self.tournament.entrants.add(user2kick)

        assert self.tournament.entrants.count() == 2
        self.send({
            'type': 'LEAVE_TOURNAMENT',
            'kicked_user': user2kick.username
        })
        assert self.tournament.entrants.count() == 1
        assert self.tournament.entrants.first() == self.user

    def test_only_admins_can_kick(self):
        """Test that when kicking a player only an admin could do so"""
        self.tournament.entrants.add(self.user)
        user2kick = User.objects.create_user(username='trumpy')
        self.tournament.entrants.add(user2kick)

        assert self.tournament.entrants.count() == 2
        self.send({
            'type': 'LEAVE_TOURNAMENT',
            'kicked_user': user2kick.username
        })
        assert self.tournament.entrants.count() == 2
        assert user2kick in self.tournament.entrants.all()

    def test_kick_bot_from_tournament(self):
        """Test on_leave_tournament method when a BOT is being kicked"""
        self.tournament.entrants.add(self.user)
        self.tournament.tournament_admin = self.user
        self.tournament.save()
        robot = self._create_random_bot()
        self.tournament.entrants.add(robot)

        assert self.tournament.entrants.count() == 2
        self.send({
            'type': 'LEAVE_TOURNAMENT',
            'kicked_user': robot.username
        })
        assert self.tournament.entrants.count() == 1
        assert self.tournament.entrants.first() == self.user

    def test_tournament_doesnt_start_with_just_bots(self):
        """ Test that a full tournament doesn't starts if it's all bots"""
        self.tournament.max_entrants = 1
        self.tournament.save()

        assert self.tournament.pokertable_set.count() == 0
        assert self.user.player_set.count() == 0
        assert self.tournament.status == TournamentStatus.PENDING.value
        self.send({'type': 'JOIN_TOURNAMENT', 'robot': True})
        assert self.tournament.pokertable_set.count() == 0
        assert self.user.player_set.count() == 0
        self.tournament.refresh_from_db()
        assert self.tournament.status == TournamentStatus.PENDING.value

    def test_start_tournament(self):
        """Testing if the tournament starts it is filled"""
        self.tournament.max_entrants = 1
        self.tournament.save()
        execute_mutations(buy_chips(
            self.user,
            self.tournament.buyin_amt + Decimal(1000)
        ))
        assert self.tournament.pokertable_set.count() == 0
        assert self.user.player_set.count() == 0
        assert self.tournament.status == TournamentStatus.PENDING.value
        self.send({'type': 'JOIN_TOURNAMENT'})
        assert self.tournament.pokertable_set.count() == 1
        assert self.user.player_set.count() == 1
        self.tournament.refresh_from_db()
        assert self.tournament.status == TournamentStatus.STARTED.value

    def tearDown(self):
        super().tearDown()
        PokerTable.objects.all().delete()
        Freezeout.objects.all().delete()
        Player.objects.all().delete()


class TestFAQ(FrontendTest):
    def setUp(self):
        url = reverse('FAQ')
        super().setUp(url)

    def test_real_client_get(self):
        response = self.request()

        assert response.status_code == 200
        assert response.context.get('user')
        assert response.context['user']['id']


class TestLearn(FrontendTest):
    def setUp(self):
        url = reverse('Learn')
        super().setUp(url)

    def tearDown(self):
        super().tearDown()
        PokerTable.objects.all().delete()

    def test_real_client_get(self):
        response = self.request()

        assert response.status_code == 200
        assert response.context.get('user')
        assert response.context['user']['id']
        assert PokerTable.objects.filter(
            is_tutorial=True,
            is_archived=False,
            name__icontains=self.user.username
        ).exists()

    def test_with_an_archived_tutorial(self):
        tutorial = PokerTable.objects.get(
            name=f'Tutorial: {self.user.username}',
            is_tutorial=True
        )
        tutorial.is_archived = True
        tutorial.save()

        response = self.request()

        assert response.status_code == 200
        assert PokerTable.objects.filter(
            is_tutorial=True,
            is_archived=False,
            name=f'Tutorial: {self.user.username} 1'
        )
