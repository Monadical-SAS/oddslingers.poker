import os
import logging
import json

from datetime import timedelta

from django.views import View
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.password_validation import validate_password
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.db.models import Q, QuerySet
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.urls import reverse
from django.utils import timezone
from django.utils.safestring import mark_safe
from allauth.account.utils import complete_signup
from allauth.account.models import EmailAddress
from allauth.account.views import ConfirmEmailView

from oddslingers.models import User
from oddslingers.tasks import send_signup_email, send_chips_email, track_analytics_event
from oddslingers.utils import (sanitize_html, require_login,
                          camelcase_to_capwords)
from oddslingers.mutations import execute_mutations

from banker.utils import (
    deposits, transfer_history,
    table_transfer_history, freezeout_transfer_history
)
from banker.mutations import buy_chips, transfer_chips
from banker.models import BalanceTransfer
from banker.deprecated import sell_chips

from poker.level_utils import update_levels, earned_chips
from poker.constants import (
    Action, Event, AnimationEvent, SEASONS,
    CASH_GAME_BBS, TOURNEY_BUYIN_AMTS,
    N_BB_TO_NEXT_LEVEL, TOURNEY_BUYIN_TIMES
)
from poker.views.utils import get_view_format_tables
from poker.bot_personalities import PERSONALITIES, DEFAULT_BIO

from rewards.constants import get_badge_icon
from rewards.mutations import reward_signup_badges
from rewards.models import Badge

from ui.views.leaderboard import load_leaderboard_cache

from .base_views import PublicReactView

logger = logging.getLogger('root')


CHIP_BUY_DELAY = timedelta(hours=1)

# We dont want people getting a username like "Bet" or "dealer"
BANNED_USERNAMES = {
    'dealer', 'button', 'cashier', 'banker', 'oddslingers', 'support',
    'raise', 'anon', 'anonymous', 'undefined', 'null', 'nan',
    'infinity', 'admin', 'administrator', 'smith', 'username',
    'password', 'won', 'lost', 'system', 'beta', 'prod', 'dev', 'poker'
} | {
    str(e).lower() for e in Action
} | {
    str(e).lower() for e in Event
} | {
    str(e).lower() for e in AnimationEvent
} | {
    botname for botname in PERSONALITIES
}
ALLOWED_USERNAME_SYMBOLS = '-_.'
MAX_USERNAME_LEN = 15


def safe_next_url(next_url: str) -> str:
    # send them to the homepage if no next is specified
    next_url = next_url or '/'
    # dont allow outside redirects like https://attacker.com,
    #   //attacker.com or ftp://attacker.com
    if next_url.startswith('//') or not next_url.startswith('/'):
        next_url = '/'

    return next_url

def validate_username(username: str):
    if '@' in username:
        raise ValidationError(
            'Username cannot contain @ symbol to avoid confusion '
            'with emails.'
        )
    if not (2 < len(username) <= MAX_USERNAME_LEN):
        raise ValidationError(
            'Username must be between 3 and '
            f'{MAX_USERNAME_LEN} characters long.'
        )
    # reserved or confusing word
    if username.lower() in BANNED_USERNAMES:
        raise ValidationError(
            'That username is not allowed because it could cause '
            'confusion for players.'
        )
    # only letters, nums, -, or _
    if not all(char.isalnum() or char in ALLOWED_USERNAME_SYMBOLS
               for char in username):
        raise ValidationError(
            'Username can only contain characters a-Z 0-9 - and _.'
        )
    # has characters other than symbols
    if len(username) == sum(username.count(s)
                            for s in ALLOWED_USERNAME_SYMBOLS):
        raise ValidationError(
            "Username must contain at least one character "
            "that isn't a symbol."
        )
    return True

username_validators = [validate_username]


def get_profile_pictures() -> list:
    directory_in_str = os.path.join(
        settings.BASE_DIR,
        'static/images/profile_pictures/'
    )

    return [filename for filename in os.listdir(directory_in_str)\
            if not filename[0] == '.']


class Logout(View):
    def get(self, request):
        next_url = safe_next_url(
            request.GET.get('next', reverse('Login'))
        )

        if request.user.is_authenticated:
            logout(request)

        return redirect(next_url)


class Login(View):
    template = 'ui/login.html'

    def get(self, request):
        next_url = safe_next_url(request.GET.get('next'))

        if request.user.is_authenticated:
            return redirect(next_url)

        return render(request, self.template, {
            'next': next_url,
            'SIGNUP_BONUS': settings.SIGNUP_BONUS,
        })

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        next_url = safe_next_url(request.POST.get('next'))

        if request.user.is_authenticated:
            return redirect(next_url)

        if not (username and password):
            return render(request, self.template, {
                'login_errors': 'Missing username or password.',
                'next': next_url,
                'SIGNUP_BONUS': settings.SIGNUP_BONUS,
            })

        user = authenticate(username=username, password=password)
        if not user:
            track_analytics_event.send(username, 'login_attempt')
            return render(request, self.template, {
                'login_errors': (
                    'Incorrect username or password. \n If you don\'t '
                    'have an account, use the form on the right to '
                    'sign up.'
                ),
                'next': next_url,
                'SIGNUP_BONUS': settings.SIGNUP_BONUS,
            })

        track_analytics_event.send(user.username, 'login')
        mutations, _ = update_levels(user)
        execute_mutations(mutations)

        login(request, user)
        return redirect(next_url)


class Signup(View):
    template = 'ui/signup.html'

    def get(self, request):
        next_url = safe_next_url(request.GET.get('next'))

        # they're already logged in
        if request.user.is_authenticated:
            return redirect(next_url)

        return render(request, self.template, {
            'next': next_url,
            'SIGNUP_BONUS': settings.SIGNUP_BONUS,
        })

    def post(self, request):
        username = request.POST.get('username')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        email = request.POST.get('email')
        next_url = safe_next_url(request.POST.get('next'))

        # they're already logged in
        if request.user.is_authenticated:
            return redirect(next_url)

        # they tried to log in using the signup page
        user = authenticate(username=username, password=password)
        if user:
            login(request, user)
            return redirect(next_url)

        error = validate_signup_form(username, password, password2, email)
        if error:
            return render(request, self.template, {
                'signup_errors': error,
                'username': username,
                'email': email,
                'next': next_url,
                'SIGNUP_BONUS': settings.SIGNUP_BONUS,
            })

        # create a new user account and log them in
        user = User.objects.create_user(
            username= username,
            email=email or '',
            password=password
        )
        user.backend = settings.AUTHENTICATION_BACKENDS[0]
        user.save()

        # give them some free chips to start out with
        execute_mutations(
            buy_chips(user, settings.SIGNUP_BONUS, notes="Signup bonus")
        )

        # award them the signup-related badges
        execute_mutations(
            reward_signup_badges(user, dict(request.POST))
        )

        mutations, _ = update_levels(user)
        execute_mutations(mutations)

        send_signup_email.send(user.username)
        track_analytics_event.send(user.username, 'signup')

        return complete_signup(
            request,
            user,
            settings.EMAIL_VERIFICATION,
            next_url
        )


class ChangeTheme(View):

    def post(self, request):
        curr_cookie = request.COOKIES.get('theme')
        cookie = 'dark'
        if curr_cookie == 'dark':
            cookie = 'light'

        response = HttpResponse(status=200)
        response.set_cookie('theme', cookie)
        return response


def validate_signup_form(username, password, password2, email):
    # they're missing a username or password
    if not (username and password):
        return 'Missing username or password.'

    if username in ('cowpig', 'squash'):
        # oddslingers manage create_superuser
        return 'Hah, nice try. You can only create these users from the CLI.'

    # they're missing an email address
    if (not settings.DEBUG) and not email:
        return 'Missing an email address.'

    # re-typed password dont match
    if (not settings.DEBUG) and (not password == password2):
        return 'Passwords do not match.'

    # their username choice is invalid
    try:
        for validator in username_validators:
            validator(username)
    except ValidationError as e:
        return e.message

    # user already exists with that username
    if User.objects.filter(username__iexact=username).exists():
        return mark_safe(
            'That username is already taken, try a different username.\n'
            'Or, log in <a href="/accounts/login/">here</a> if you already have an account.'
        )

    # user already exists with that email
    if User.objects.filter(email=email).exists() or EmailAddress.objects.filter(email=email).exists():
        return mark_safe(
            'That email is already in use with a different account.\n'
            'Did you mean to <a href="/accounts/login/">log in</a> to an existing account?'
        )

    # check the password validity
    user = User(username=username, email=(email or ''))
    try:
        if (not settings.DEBUG) and len(password) < 8:
            raise ValidationError('The password is not long enough.')
        validate_password(password, user=user)
    except ValidationError as e:
        errs = ', '.join(e.messages)
        msg = f'Try another password, that one is not valid. {errs}'
        return msg

    return None

class EmailChips(View):
    template = 'ui/claim_chips.html'

    def get(self, request, transaction_id=None):
        if not request.user.is_authenticated:
            return redirect('Signup')

        if not transaction_id:
            return redirect('Home')

        try:
            xfer = BalanceTransfer.objects.get(id=transaction_id)
        except (BalanceTransfer.DoesNotExist,
                BalanceTransfer.MultipleObjectsReturned):
            return redirect('Home')

        try:
            notes = json.loads(xfer.notes)
        except json.JSONDecodeError:
            return redirect('Home')

        conditions = (
            'claimed' in notes,
            'dst_email' in notes,
            not notes['claimed'],
            request.user.has_email(notes['dst_email']),
        )
        if not all(conditions):
            return redirect('Home')

        execute_mutations(
            buy_chips(
                request.user,
                xfer.amt,
                notes=json.dumps({'src_username': xfer.source.username})
            )
        )

        notes['claimed'] = True
        xfer.notes = json.dumps(notes)
        xfer.save()

        msg = f'claimed {xfer.amt} chips via email invitation from {xfer.source.username}'
        track_analytics_event.send(request.user.username, msg)

        return render(request, self.template, {
            'sender': xfer.source.username,
            'amount': xfer.amt,
        })

class ConfirmEmail(ConfirmEmailView):
    @require_login
    def get(self, request, key=None):
        already_verified = request.user.has_verified_email
        response = super().get(request, key)
        if not already_verified and request.user.has_verified_email:
            execute_mutations(
                buy_chips(
                    request.user,
                    settings.EMAIL_VERIFIED_BONUS,
                    'Free chips for verifying your email address'
                )
            )
        return response

class UserProfile(PublicReactView):
    title = 'User Profile'
    component = 'pages/user.js'
    custom_stylesheet = 'user.css'

    def get(self, request, username=None):
        if not username:
            if request.user.is_authenticated:
                return redirect('UserProfile', username=request.user.username)
            else:
                return redirect('Leaderboard')
        try:
            self.user = User.objects.get(username=username)
        except User.DoesNotExist:
            safe_query = sanitize_html(username, strip=True, allow_safe=False)
            return redirect(f'{reverse("Leaderboard")}?search={safe_query}')
        return super(UserProfile, self).get(request, username)

    def props(self, request, username):
        user = self.user

        user_info = user.attrs(
            'id',
            'short_id',
            'username',
            'first_name',
            'last_name',
            'bio',
            'is_active',
            'is_staff',
            'is_robot',
            'profile_image',
        )

        if user.is_robot:
            personality = PERSONALITIES[user.username]
            user_info.update({
                'profile_image': '/static/images/bender.png',
                'bio': personality['profile'].get('bio') or DEFAULT_BIO,
                'personality': personality['profile']
            })

        user_badges = Badge.objects\
                           .current_season()\
                           .filter(user=user)\
                           .exclude(name__icontains='week')\
                           .exclude(name__icontains='season')

        extra_badges = Badge.objects\
                            .filter(user=user)\
                            .filter(Q(name='genesis')
                                    | Q(name='fearless_leader'))

        user_badges = (user_badges | extra_badges).order_by('-created')
        badges_info = {}
        for badge in user_badges:
            if badge.name not in badges_info:
                badges_filter = user_badges.filter(name=badge.name)
                human_title = camelcase_to_capwords(badge.name)
                badges_info[badge.name] = {
                    'type': 'reward',
                    'subtype': badge.name,
                    'bsStyle': 'warning',
                    # 'created': min(b.created for b in badges_filter),
                    'ts': max(b.created for b in badges_filter),
                    'title': f'{human_title} x{badges_filter.count()}',
                    'description': f"{badge.description}.",
                    'icon': get_badge_icon(badge.name),
                }


        ldboard_badges = Badge.objects\
                              .filter(user=user)\
                              .filter(Q(name__icontains='week')
                                      | Q(name__icontains='season'))\
                              .order_by('-created')
        ldbd_badges_info = {}
        for badge in ldboard_badges:
            human_title = camelcase_to_capwords(badge.name)
            ldbd_badges_info[badge.short_id] = {
                'type': 'reward',
                'subtype': badge.name,
                'bsStyle': 'warning',
                # 'created': min(b.created for b in badges_filter),
                'ts': badge.created ,
                'title': human_title,
                'description': f"{badge.description}.",
                'icon': get_badge_icon(badge.name),
            }

        profile_pictures = get_profile_pictures()

        deposits = list(recent_deposits(user))
        if len(deposits) > 0:
            last_deposit_diff = (timezone.now() - deposits[-1].timestamp)
            seconds_remaining = (
                CHIP_BUY_DELAY.total_seconds()
                - int(last_deposit_diff.total_seconds())
            )
        else:
            seconds_remaining = 0

        table_filter = {'seated': True}

        # if viewer is viewing their own profile, give them extra information
        if user == request.user:

            user_info.update(user.attrs(
                'email',
                'date_joined',
                'last_login',
                'is_superuser',
                'chips_in_play',
                'has_verified_email',
            ))
            user_info['is_me'] = True
            user_info['balance'] = user.userbalance().balance
            user_info['levels_constants'] = {
                'cash_game_bbs': CASH_GAME_BBS,
                'tourney_buyin_amts': TOURNEY_BUYIN_AMTS,
                'n_bb_to_next_level': N_BB_TO_NEXT_LEVEL,
                'tourney_buyin_times': TOURNEY_BUYIN_TIMES,
            }
            user_info['bonus_constants'] = {
                'free_chips_bonus': settings.FREE_CHIPS_BONUS,
                'email_verified_bonus': settings.EMAIL_VERIFIED_BONUS,
            }
            user_info['past_seasons'] = season_history(user)

            user_earned_chips = earned_chips(user)
            user_public_chips_in_play = user.public_chips_in_play
            user_info['earned_chips'] = user_earned_chips + user_public_chips_in_play
            mutations, _ = update_levels(user, user_earned_chips, user_public_chips_in_play)
            execute_mutations(mutations)

            user_info.update(user.attrs(
                'cashtables_level',
                'tournaments_level',
            ))

            last_info = request.session.get('last_info')
            request.session.update({'last_info': json.dumps({
                'user_info': user_info,
                'badges_info': badges_info,
            }, default=str)})

            user_info['new_achievements'] = new_achievements(
                json.loads(last_info),
                user_info,
                badges_info
            ) if last_info else None

        else:
            active = timezone.now() - timedelta(minutes=5)
            table_filter['table__modified__gt'] = active

        tables = [
            player.table for player in
            user.player_set.filter(**table_filter).only('table')
        ]
        tables_info = get_view_format_tables(tables, user) if tables else None

        return {
            'profile_user': user_info,
            'friends': [],
            'streams': [],
            'tables': tables_info,
            'badges': badges_info,
            'leaderboard_badges': ldbd_badges_info,
            'profile_pictures': profile_pictures,
            'wait_to_deposit': seconds_remaining,
        }

    @require_login
    def post(self, request, username):

        AVAILABLE_TYPES = (
            'BUY_CHIPS',
            'SEND_CHIPS',
            'TRANSFER_HISTORY',
            'LEVELS_PROGRESS'
        )
        assert request.POST.get('type') in AVAILABLE_TYPES, (
            'Invalid User Profile action attempted.'
        )
        if request.POST['type'] == 'BUY_CHIPS':
            return JsonResponse(give_bonus_chips(request.user))

        elif request.POST['type'] == 'SEND_CHIPS':
            to_user = request.POST['to_user'].strip()
            amount = request.POST['amount'].strip()
            return JsonResponse(
                send_chips_to_user(request.user, to_user, amount)
            )
        elif request.POST['type'] == 'TRANSFER_HISTORY':
            return JsonResponse(get_transfers(request.user))
        elif request.POST['type'] == 'LEVELS_PROGRESS':
            return JsonResponse(levels_progress(request.user))

def levels_progress(user: User) -> dict:
    bonus = {}
    tables = {}
    tournaments = {}

    table_transfers = table_transfer_history(user)
    if table_transfers:
        tables = tables_progress(user, table_transfers)

    freezeout_transfers = freezeout_transfer_history(user)
    if freezeout_transfers:
        tournaments = freezeout_progress(user, freezeout_transfers)

    bonus_transfers = deposits(user)
    if bonus_transfers:
        bonus = bonus_progress(user, bonus_transfers)

    return {
        'success': True,
        'badges': bonus,
        'tables': tables,
        'tournaments': tournaments,
    }

def tables_progress(user: User, table_transfers: QuerySet) -> dict:
    tables_data = {}
    table_ids = []
    for table_transfer in table_transfers:
        if table_transfer.source_type.name == 'user':
            table = table_transfer.dest
            amount = -table_transfer.amt
        else:
            table = table_transfer.source
            amount = table_transfer.amt

        if table.is_private:
            continue

        bb_idx = str(int(table.bb))
        if bb_idx not in tables_data:
            tables_data[bb_idx] = {
                'earnings': 0,
                'hands': 0,
                'sb': int(table.sb)
            }
        tables_data[bb_idx]['earnings'] += amount

        if table.id not in table_ids:
            table_ids.append(table.id)
            table_player = user.player_set.filter(table_id=table.id)
            if table_player and len(table_player) == 1:
                tables_data[bb_idx]['hands'] += table_player[0].n_hands_played

    return tables_data

def freezeout_progress(user: User, freezeout_transfers: QuerySet) -> dict:
    tourneys_data = {}
    for freezeout_transfer in freezeout_transfers:
        if freezeout_transfer.source_type.name == 'user':
            freezeout = freezeout_transfer.dest
            amount = -freezeout_transfer.amt
        else:
            freezeout = freezeout_transfer.source
            amount = freezeout_transfer.amt

        if freezeout.is_private:
            continue

        buyin_idx = str(int(freezeout.buyin_amt))
        if buyin_idx not in tourneys_data:
            tourneys_data[buyin_idx] = {'earnings':0}
        tourneys_data[buyin_idx]['earnings'] += amount

    return tourneys_data

def bonus_progress(user: User, bonus_transfers: QuerySet) -> int:
    deposits = 0
    for bonus_transfer in bonus_transfers:
        deposits += bonus_transfer.amt
    return deposits

def get_transfers(user: User) -> dict:
    transfers = transfer_history(user)
    return {
        'success': True,
        'transfers': [
            get_transfer_data(user, transfer)
            for transfer in transfers
        ]
    }

def get_transfer_data(user: User, transfer: BalanceTransfer) -> dict:
    if transfer.source_type.name == 'user' and transfer.source == user:
        t_type = 'debit'
    else:
        t_type = 'credit'

    t_name = transfer.source_type.name
    if transfer.source_type.name == 'user':
        t_name = transfer.dest_type.name

    if t_type == 'debit':
        if transfer.dest == None:
            t_label = transfer.dest_type.name
            t_path = None
        elif transfer.dest_type.name == 'user':
            t_label = transfer.dest.username
            t_path = f'/user/{transfer.dest.username}'
        elif transfer.dest_type.name in ('poker table', 'freezeout'):
            t_label = transfer.dest.name
            t_path = transfer.dest.path
        else:
            try:
                json_notes = json.loads(transfer.notes)
                user = User.objects.only('username').get(
                    email=json_notes['dst_email']
                )
                t_label = user.username
                t_path = f'/user/{user.username}'
            except (json.JSONDecodeError,
                    KeyError,
                    User.DoesNotExist,
                    User.MultipleObjectsReturned):
                t_label = transfer.dest_type.name
                t_path = None
    else:
        if transfer.source == None:
            t_label = transfer.source_type.name
            t_path = None
        elif transfer.source_type.name == 'user':
            t_label = transfer.source.username
            t_path = f'/user/{transfer.source.username}'
        elif transfer.source_type.name in ('poker table', 'freezeout'):
            t_label = transfer.source.name
            t_path = transfer.source.path
        else:
            try:
                json_notes = json.loads(transfer.notes)
                t_label = json_notes['src_username']
                t_path = f"/user/{json_notes['src_username']}"
            except (json.JSONDecodeError, KeyError):
                t_label = transfer.source_type.name
                t_path = None

    return {
        'type': t_type,
        'name': t_name,
        'label': t_label,
        'amt': transfer.amt,
        'notes': transfer.notes,
        'path': t_path,
        'timestamp': transfer.timestamp,
    }

def send_chips_to_user(user: User, to_user: User, amount: int) -> dict:
    assert to_user and amount

    if not user.has_verified_email:
        return {
            'success': False,
            'details': 'You must verify your email before sending chips.'
        }

    try:
        amount = int(amount)
        assert 0 < amount <= user.userbalance().balance
    except (ValueError, AssertionError):
        return {
            'success': False,
            'details': 'Invalid amount. Chips must be a whole number between 1 and your total balance.'
        }

    try:
        validate_email(to_user)
        is_email = True
    except ValidationError:
        is_email = False


    try:
        key = 'email' if is_email else 'username'
        to_user = User.objects.get(**{key: to_user})
    except User.DoesNotExist:
        if is_email and settings.ALLOW_SENDING_CHIPS_BY_EMAIL:
            send_chips_via_email(user, to_user, amount)
            return {
                'success': True,
                'quantity': amount,
                'balance': user.userbalance().balance
            }
        else:
            return {
                'success': False,
                'details': 'Recipient not found. Check the username'
            }

    if to_user.is_robot:
        return {
            'success': False,
            'details': f'{to_user.username} is rich enough already'
        }

    if to_user.username == user.username:
        return {
            'success': False,
            'details': 'You cannot send chips to yourself'
        }

    execute_mutations(
        transfer_chips(user, to_user, amount)
    )

    track_analytics_event.send(
        user.username,
        f'transferred ㆔{amount} chips to {to_user.username}'
    )

    return {
        'success': True,
        'quantity': amount,
        'balance': user.userbalance().balance,
    }

def give_bonus_chips(user: User) -> dict:
    if recent_deposits(user).count() > 0:
        return {
            'success': False,
            'details': 'You wait to make another deposit!',
        }

    execute_mutations(
        buy_chips(user, settings.FREE_CHIPS_BONUS, notes="Free chips")
    )

    track_analytics_event.send(
        user.username,
        f'collected {settings.FREE_CHIPS_BONUS} free chips'
    )

    return {
        'success': True,
        'quantity': settings.FREE_CHIPS_BONUS,
        'balance': user.userbalance().balance,
    }

def recent_deposits(user: User) -> QuerySet:
    # Note: this will include initial free chips deposit given to new signups
    recent = timezone.now() - CHIP_BUY_DELAY
    return deposits(user, start_date=recent)


def send_chips_via_email(user, dst_email, amount):
    notes = {
        'dst_email': dst_email,
        'claimed': False,
    }
    xfers = []
    for obj in sell_chips(user, amount, json.dumps(notes)):
        if isinstance(obj, BalanceTransfer):
            xfers += [obj]
        obj.save()
    if len(xfers) != 1:
        raise ValidationError(
            'Inconsistent number of transactions when sending chips to email'
        )

    next_url = reverse('EmailChips', args=[str(xfers[0].id)])
    send_chips_email.send(dst_email, user.username, amount, next_url)

    msg = f'sent {amount} chips via email invitation to {dst_email}'
    track_analytics_event.send(user.username, msg)


def season_history(user: User) -> dict:
    season_history = dict()
    cached_data = load_leaderboard_cache()

    for season in range(settings.CURRENT_SEASON + 1):
        _, end = SEASONS[season]

        if season == settings.CURRENT_SEASON:
            # TODO: make this fast enough to run on every pageload
            # top_users = top_users_in_season(settings.CURRENT_SEASON)
            top_users = []
            user_data = list(filter(
                lambda usr: usr[1].username == user.username,
                enumerate(top_users)
            ))
            end = 'ongoing'
        else:
            season_data = cached_data['seasons'][season]
            user_data = list(filter(
                lambda usr: usr['username'] == user.username,
                season_data
            ))
            end = f"{end.strftime('%b %d, %Y')}"

        if len(user_data) > 1:
            raise ValidationError(
                f'More than one register found in cached leaderboard\
                for user {user.username} in season {season}: {user_data}'
            )
        user_data = user_data[0] if user_data else []
        season_history[season] = get_user_data(end_time=end,
                                               user_data=user_data)
    return season_history


def get_user_data(end_time, user_data) -> dict:
    data = {}
    if user_data:
        if isinstance(user_data, tuple):
            ranking = user_data[0]
            winnings = user_data[1].recent_winnings
        else:
            ranking = user_data['ranking']
            winnings = user_data['winnings']
        data = {
            'end': end_time,
            'winnings': winnings,
            'ranking': ranking + 1,
        }

    else:
        data = {
            'end': end_time,
            'winnings': '0',
            'ranking': 'unranked'
        }

    return data

def new_achievements(last_info: dict,
                     user_info: dict,
                     badges_info: dict) -> dict:
    lvl_types = [
        'cashtables_level',
        'tournaments_level',
    ]
    new_levels = {}
    for lvl_type in lvl_types:
        if user_info.get(lvl_type) > last_info['user_info'].get(lvl_type):
            new_levels.update({lvl_type: {
                'old': last_info['user_info'].get(lvl_type),
                'new': user_info.get(lvl_type),
            }})

    new_badges = {}
    for badge_name in badges_info.keys():
        last_badge = last_info['badges_info'].get(badge_name)
        if last_badge:
            last_badge_dt = timezone.datetime.strptime(
                last_badge.get('ts'),
                '%Y-%m-%d %H:%M:%S.%f+00:00'
            ).replace(tzinfo=timezone.utc)
            badge_dt = badges_info.get(badge_name).get('ts')

            if badge_dt > last_badge_dt:
                new_badges.update({
                    badge_name: badges_info.get(badge_name).get('description')
                })
        else:
            new_badges.update({
                badge_name: badges_info.get(badge_name).get('description')
            })

    new_stuff = {}
    if new_levels:
        new_stuff['levels'] = new_levels
    if new_badges:
        new_stuff['badges'] = new_badges

    return new_stuff if new_stuff else None
