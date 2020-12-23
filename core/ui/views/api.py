import logging
import json
import shutil
import os

from django.contrib.gis.geoip2 import GeoIP2
from django.http import QueryDict
from django.conf import settings
from django.http import FileResponse

from oddslingers.utils import ANSI, sanitize_html
from oddslingers.tasks import send_invite_email
from oddslingers.mutations import execute_mutations

from ui.views.accounts import get_profile_pictures

from rewards.mutations import award_badge, reward_attempted_xss, reward_swearing

from linky.views import create_link

from poker.constants import TAKE_SEAT_BEHAVIOURS, PlayingState
from poker.models import PokerTable
from poker.game_utils import fuzzy_get_table

from .base_views import APIView

logger = logging.getLogger('poker')

### Helpers



def user_session_summary(request, only_active=True) -> dict:
    user = request.user
    try:
        g = GeoIP2()
        g.country('8.8.8.8')
    except Exception as e:
        if settings.DEBUG:
            print('{lightyellow}[X] No GeoIP2 data available, make sure GeoLite2-City.mmdb is present in settings.GEOIP_DIR{reset}'.format(**ANSI))
            print(e)
        else:
            logger.warning('Missing or invalid GeoIP2 database in settings.GEOIP_path', extra={
                'exception': e,
                'db_path': settings.GEOIP_DIR,
            })
        g = None

    def get_location(ip):
        if ip == '127.0.0.1':
            return 'Localhost'
        elif not ip or not g:
            return None
        try:
            return '{city}, {region}, {country_name}'.format(**g.city(ip))
        except Exception:
            return None

    sessions = user.usersession_set.all()

    sessions = sessions.order_by('-last_activity')

    execute_mutations(
        award_badge(user=user, name='security_minded', max_times=1)
    )

    return [
        {
            'current': request.session.session_key == session.session_id,
            **session.attrs(
                'session_id',
                'ip',
                'device',
                'location',
                'user_agent',
                'login_date',
                'last_activity',
            )
        }
        for session in sessions
    ]


### Views

class User(APIView):
    def user_data(self, request):
        return {
            'user': request.user.attrs(
                'id',
                'username',
                'is_staff',
            ),
        }

    def get(self, request):
        if not request.user.is_authenticated:
            return self.respond(errors=['You must be logged in to get user info.'])

        return self.respond(self.user_data(request))

    def patch(self, request):
        user = request.user
        if not user.is_authenticated:
            return self.respond(errors=['You must be logged in to change user info.'])

        try:
            PATCH = json.loads(request.body)
        except json.JSONDecodeError:
            PATCH = QueryDict(request.body)

        execute_mutations([
            *reward_attempted_xss(user, PATCH),
            *reward_swearing(user, PATCH)
        ])

        user = self.add_data_to_user(user, PATCH)

        user.save()
        if 'bio' in PATCH:
            execute_mutations(
                award_badge(user, 'hello_world', max_times=1)
            )

        return self.respond(self.user_data(request))

    def add_data_to_user(self, user, PATCH):
        modified_user = user

        if 'picture' in PATCH:
            assert PATCH["picture"] in get_profile_pictures(), 'Invalid profile picture choice.'
            modified_user.profile_picture = f'images/profile_pictures/{PATCH["picture"]}'
        elif 'bio' in PATCH:
            safe_text = sanitize_html(PATCH['bio'], strip=True, allow_safe=False)
            modified_user.bio = safe_text[:255]
        elif 'muted_sounds' in PATCH:
            modified_user.muted_sounds = bool(PATCH['muted_sounds'])
        elif 'show_dealer_msgs' in PATCH:
            modified_user.show_dealer_msgs = bool(PATCH['show_dealer_msgs'])
        elif 'show_win_msgs' in PATCH:
            modified_user.show_win_msgs = bool(PATCH['show_win_msgs'])
        elif 'show_chat_msgs' in PATCH:
            modified_user.show_chat_msgs = bool(PATCH['show_chat_msgs'])
        elif 'show_spectator_msgs' in PATCH:
            modified_user.show_spectator_msgs = bool(PATCH['show_spectator_msgs'])
        elif 'show_chat_bubbles' in PATCH:
            modified_user.show_chat_bubbles = bool(PATCH['show_chat_bubbles'])
        elif 'auto_rebuy_in_bbs' in PATCH:
            modified_user.auto_rebuy_in_bbs = int(PATCH['auto_rebuy_in_bbs'])
        elif 'four_color_deck' in PATCH:
            modified_user.four_color_deck = bool(PATCH['four_color_deck'])
        elif 'keyboard_shortcuts' in PATCH:
            modified_user.keyboard_shortcuts = bool(PATCH['keyboard_shortcuts'])
        elif 'show_playbyplay' in PATCH:
            modified_user.show_playbyplay = bool(PATCH['show_playbyplay'])
        elif 'sit_behaviour' in PATCH:
            option = PATCH['sit_behaviour'].upper()
            allowed_options = [bhv.name for bhv in TAKE_SEAT_BEHAVIOURS]
            assert option in allowed_options, 'Invalid choice!'
            modified_user.sit_behaviour = PlayingState.from_str(option)
        elif 'light_theme' in PATCH:
            modified_user.light_theme = bool(PATCH['light_theme'])
        elif 'muck_after_winning' in PATCH:
            modified_user.muck_after_winning = bool(PATCH['muck_after_winning'])
        else:
            raise Exception("User API: That's not a valid key to patch")
        return modified_user


class UserBalance(APIView):
    def get(self, request):
        if not request.user.is_authenticated:
            return self.respond(errors=['You must be logged in to get user balance.'])

        return self.respond({
            'balance': request.user.userbalance().balance,
            'level': request.user.cashtables_level,
        })


class UserSessions(APIView):
    def get(self, request):
        resp = {
            'sessions': [],
            'is_authenticated': bool(request.user.is_authenticated),
        }

        if request.user.is_authenticated:
            resp['sessions'] = user_session_summary(request)

        return self.respond(resp)

    def delete(self, request):
        if not request.user.is_authenticated:
            return self.respond(errors=['You must be logged in to delete sessions.'])

        ids = request.GET.getlist('session_id')
        if not ids or not ids[0]:
            return self.respond(errors=['You must specify a session_id to delete, or pass "all".'])

        if ids[0] == 'all':
            sessions = request.user.usersession_set.all()
        else:
            sessions = request.user.usersession_set.filter(session_id__in=ids)

        count = 0
        for sesh in sessions:
            sesh.end()
            count += 1

        return self.respond({'deleted': count})

class URLShortener(APIView):
    def post(self, request):
        user = request.user if request.user.is_authenticated else None
        return self.respond({
                'linky': create_link(
                    viewname=request.POST.get('viewname'),
                    kwargs={'id':request.POST.get('id')},
                    user=user
                )
            })

class TableInvite(APIView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated:
            return self.respond(errors=['You must be logged in to invite.'])

        execute_mutations(
            reward_attempted_xss(user, request.POST)
        )

        email = request.POST.get('email').strip()
        table_id = request.POST.get('table_id').strip()

        assert email and table_id, 'Missing required email or table_id'
        assert '@' in email and '.' in email, 'Invalid email'

        try:
            table = PokerTable.objects.only("id").get(id=table_id)
        except PokerTable.DoesNotExist:
            raise Exception("Table API: Table does not exist")

        send_invite_email.send(email, user.username, table.path)

        return self.respond()


class SupportTicketDownload(APIView):
    def get(self, request, ticket_id):
        user = request.user
        if not user.is_authenticated:
            return self.respond(errors=['You must be logged in.'])

        if not (user.is_staff or user.is_superuser):
            return self.respond(errors=['You must have superpowers for this.'])

        # Create zip file in /tmp/incident_<id>.zip
        dest_file = f'/tmp/incident_{ticket_id}'
        src_dir = os.path.join(settings.SUPPORT_TICKET_DIR, ticket_id)
        try:
            shutil.make_archive(dest_file, 'zip', src_dir)
        except FileNotFoundError:
            return self.respond(errors=['Ticket artifacts not found'])

        # Return zip file
        response = FileResponse(open(f'{dest_file}.zip', 'rb'))
        response['Content-Disposition'] = 'attachment; filename=incident_%s.zip' % str(ticket_id)
        self.dest_path = os.path.join('/tmp', f'incident_{ticket_id}.zip')
        return response

    def after_response(self, request=None, response=None):
        super().after_response(request=request, response=response)

        os.remove(self.dest_path)


class TableArchive(APIView):
    def post(self, request):
        user = request.user
        if not user.is_authenticated or not user.is_superuser:
            return self.respond(errors=['You do not have permission to modify tables.'])

        table = fuzzy_get_table(request.POST.get('id'))
        table.is_archived = True
        table.save()
        return self.respond()
