import logging

from typing import Optional
from importlib import import_module

from user_sessions.templatetags.user_sessions import device

from django.db import models
from django.db.models import SET_NULL, QuerySet, Sum
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.auth.models import AbstractUser, UserManager
from django.contrib.sessions.models import Session
from django.contrib.gis.geoip2 import GeoIP2
from django.utils.functional import cached_property
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.conf import settings

from banker.models import BalanceTransfer

from poker.constants import (
    TAKE_SEAT_BEHAVIOURS, PlayingState,
    CASH_GAME_BBS, TOURNEY_BUYIN_AMTS,
    N_BB_TO_NEXT_LEVEL, TOURNEY_BUYIN_TIMES,
    THRESHOLD_BB_EMAIL_VERIFIED
)

from oddslingers.managers import SeasonRegularManager

from .utils import DEBUG_ONLY, ANSI
from .model_utils import BaseModel


logger = logging.getLogger('sessions')
SessionStore = import_module(settings.SESSION_ENGINE).SessionStore


class CaseInsensitiveUserManager(UserManager):
    def get_by_natural_key(self, username):
        return self.get(username__iexact=username)

    def create_user(self, *args, **kwargs):
        user = super().create_user(*args, **kwargs)
        UserStats.objects.create_for_current_season(user=user)
        UserBalance.objects.create_for_current_season(user=user)
        return user


class User(AbstractUser, BaseModel):
    objects = CaseInsensitiveUserManager()

    # id = models.UUIDField
    # username
    # password
    # email
    # first_name
    # last_name
    # is_active
    # is_staff
    # is_superuser
    # last_login
    # date_joined

    is_robot = models.BooleanField(default=False)
    default_buyin = models.IntegerField(default=200)

    # not always the same as date_joined
    created = models.DateTimeField(auto_now_add=True)
    # not always the same as last_login, used for cache invalidation
    modified = models.DateTimeField(auto_now=True)
    profile_picture = models.CharField(max_length=64, blank=True, null=True)
    bio = models.CharField(max_length=255, blank=True, null=True)

    muted_sounds = models.BooleanField(default=False)
    sit_behaviour_int = models.IntegerField(
        default=PlayingState.SITTING_OUT.value,
        choices=[(state.value, state.name) for state in TAKE_SEAT_BEHAVIOURS],
    )
    four_color_deck = models.BooleanField(default=True)
    auto_rebuy_in_bbs = models.IntegerField(default=0)
    show_dealer_msgs = models.BooleanField(default=True)
    show_win_msgs = models.BooleanField(default=True)
    show_chat_msgs = models.BooleanField(default=True)
    show_spectator_msgs = models.BooleanField(default=True)
    show_chat_bubbles = models.BooleanField(default=True)
    show_playbyplay = models.BooleanField(default=True)
    light_theme = models.BooleanField(default=True)
    keyboard_shortcuts = models.BooleanField(default=False)
    muck_after_winning = models.BooleanField(default=True)

    def __str__(self):
        return self.username or self.short_id

    def __repr__(self):
        inactive = (' (inactive)', '')[self.is_active]
        staff = ('', ' (staff)', ' (admin)')[self.is_staff + self.is_superuser]
        return f'<User:{self.username}{inactive}{staff}>'

    def __json__(self, *attrs):
        return {
            **self.attrs(
                'id',
                'email',
                'username',
                'first_name',
                'last_name',
                'date_joined',
                'profile_picture',
                'is_active',
                'is_staff',
                'is_superuser',
                'is_authenticated',
                'profile_picture',
                'muted_sounds',
                'four_color_deck',
                'show_dealer_msgs',
                'show_win_msgs',
                'show_chat_msgs',
                'show_spectator_msgs',
                'show_chat_bubbles',
                'show_playbyplay',
                'auto_rebuy_in_bbs',
                'light_theme',
                'keyboard_shortcuts',
                'muck_after_winning',
                'cashtables_level',
                'tournaments_level',
                'has_verified_email',
            ),
            'str': str(self),
            'sit_behaviour': self.get_sit_behaviour_int_display(),
            **(self.attrs(*attrs) if attrs else {}),
        }

    @property
    def sit_behaviour(self) -> PlayingState:
        if not self.sit_behaviour_int:
            return None
        return PlayingState(self.sit_behaviour_int)

    @sit_behaviour.setter
    def sit_behaviour(self, sit_behaviour):
        if sit_behaviour is None:
            self.sit_behaviour_int = sit_behaviour
        else:
            self.sit_behaviour_int = sit_behaviour.value

    @property
    def profile_image(self) -> str:
        picture = self.profile_picture or 'images/chip.png'
        return f'/static/{picture}'

    @property
    def chips_in_play(self) -> float:
        return self.player_set.filter(seated=True)\
                              .aggregate(Sum('stack'))['stack__sum'] or 0

    @property
    def public_chips_in_play(self) -> float:
        return self.player_set.filter(seated=True, table__is_private=False)\
                              .aggregate(Sum('stack'))['stack__sum'] or 0

    @property
    def has_active_sidebets(self) -> bool:
        return self.sidebet_set.filter(status='active').exists()

    @property
    def has_verified_email(self):
        return self.emailaddress_set.filter(verified=True).exists()

    @cached_property
    def hands_played(self) -> int:
        return (
            self.player_set.aggregate(hands=Sum('n_hands_played'))['hands']
            or 0
        )

    @cached_property
    def games_level(self):
        return self.userstats().games_level

    @cached_property
    def games_level_number(self):
        return CASH_GAME_BBS.index(self.cashtables_level) + 1

    @property
    def cashtables_level(self):
        cash_lvl = self.games_level / N_BB_TO_NEXT_LEVEL
        return max(
            (lvl for lvl in CASH_GAME_BBS if lvl <= cash_lvl),
            default=CASH_GAME_BBS[0]
        )

    @property
    def tournaments_level(self):
        tourney_lvl = self.games_level / TOURNEY_BUYIN_TIMES
        return max(
            (lvl for lvl in TOURNEY_BUYIN_AMTS if lvl <= tourney_lvl),
            default=TOURNEY_BUYIN_AMTS[0]
        )

    @property
    def last_url(self) -> Optional[str]:
        try:
            return self.usersession_set\
                       .only('last_url')\
                       .latest('last_activity')\
                       .last_url
        except (UserSession.DoesNotExist, AttributeError):
            return None

    @property
    def last_activity(self):
        try:
            return self.usersession_set\
                       .only('last_activity')\
                       .latest('last_activity')\
                       .last_activity
        except (UserSession.DoesNotExist, AttributeError):
            return None

    def badge_count(self, season=settings.CURRENT_SEASON) -> int:
        return self.badge_set.filter(season=season).count()

    def userbalance(self):
        return self.userbalance_set.current_season().get()

    def userstats(self):
        return self.userstats_set.current_season().get()

    def can_access_table(self, table_bb: int) -> bool:
        if self.cashtables_level < table_bb:
            return False

        if table_bb >= THRESHOLD_BB_EMAIL_VERIFIED:
            return self.has_verified_email

        return True

    def can_access_tourney(self, buyin_amt: int) -> bool:
        return self.tournaments_level >= buyin_amt

    def has_email(self, email: str) -> bool:
        conditions = (
            self.email == email,
            self.emailaddress_set.filter(email=email).exists()
        )
        return any(conditions)

    sent_transfers = GenericRelation(
        BalanceTransfer,
        content_type_field='source_type',
        object_id_field='source_id',
    )

    recv_transfers = GenericRelation(
        BalanceTransfer,
        content_type_field='dest_type',
        object_id_field='dest_id',
    )

    @DEBUG_ONLY
    @property
    def transfers(self) -> QuerySet:
        """all transfers coming from or going two this user"""
        all_transfer_ids = (
            set(self.sent_transfers.values_list('id'))
          | set(self.recv_transfers.values_list('id'))
        )
        return BalanceTransfer.objects.current_season()\
                                      .filter(id__in=all_transfer_ids)


class UserSession(BaseModel):
    session = models.OneToOneField(Session, on_delete=SET_NULL, null=True)
    user = models.ForeignKey(
        User,
        blank=True,
        null=True,
        on_delete=models.CASCADE
    )

    ip = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=256, blank=True, null=True)

    expire_date = models.DateTimeField(blank=True, null=True)
    login_date = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    last_url = models.URLField(max_length=256, blank=True, null=True)

    def __str__(self) -> str:
        deets = f'({self.device} {self.ip}) @ {self.last_url}'
        return f'{self.user.username} {deets}'

    def __repr__(self) -> str:
        return f'<UserSession:{str(self)}>'

    def __json__(self, *attrs) -> dict:
        return {
            **self.attrs(
                'user_id',
                'session_id',
                'ip',
                'user_agent',
                'login_date',
                'last_activity',
                'expire_date',
                'device',
                'location',
            ),
            'str': str(self),
            **(self.attrs(*attrs) if attrs else {}),
        }

    @classmethod
    def update_from_request(cls, request, user=None):
        if (getattr(request, 'path', None) is None or
            getattr(request, 'session', None) is None):
            # if request is not a real request for some reason, skip
            # e.g. testing a FakeRequest generated by channels.test.WSClient
            return

        if not request.session.session_key:
            # In very special cases a request may not have a valid session:
            #  - tests using a MockRequest
            #  - manually created request objects
            #  - sessions hijacked by admins using django-hijack
            return None

        if not hasattr(request, 'user'):
            # when testing with django.test.Client client.force_login(user)
            # creates a bare request which doesn't get passed through the
            # SessionMiddleware (which is what attaches request.user)
            assert user, (
                'User must be passed manually when not attached to request')
        else:
            if user:
                assert request.user == user, (
                    'If request.user is present, it must match the '
                    'user passed in'
                )
            user = request.user

        assert user.is_authenticated, \
                'Cannot create session for anonymous user'

        expire_date = None
        session = list(Session.objects.filter(pk=request.session.session_key))
        if session:
            expire_date = session[0].expire_date

        user_session, created = cls.objects.update_or_create(
            user=user,
            session_id=request.session.session_key,
            defaults={
                'expire_date': expire_date,
                'ip': request.META.get('REMOTE_ADDR', '')[:63] or None,
                'user_agent': \
                    request.META.get('HTTP_USER_AGENT', '')[:255] \
                    or None,
                'last_url': request.path[:255],
            }
        )
        return user_session

    @property
    def socket_set(self) -> QuerySet:
        return self.session.socket_set

    @cached_property
    def username(self) -> Optional[str]:
        return self.user.username if self.user else None

    @cached_property
    def device(self) -> str:
        return device(self.user_agent) if self.user_agent else 'Unknown'

    @cached_property
    def location_json(self) -> Optional[dict]:
        try:
            g = GeoIP2()
            g.country('8.8.8.8')
        except Exception as e:
            if settings.DEBUG:
                print('{lightyellow}[X] No GeoIP2 data available, make \
                        sure GeoLite2-City.mmdb is present in \
                        settings.GEOIP_DIR{reset}'.format(**ANSI))
                print(e)
            else:
                msg = 'Missing or invalid GeoIP2 database in \
                       settings.GEOIP_path'
                logger.warning(msg, extra={
                    'exception': e,
                    'db_path': settings.GEOIP_DIR,
                })
            return None

        if not self.ip or not g or self.ip == '127.0.0.1':
            return None

        try:
            return g.city(self.ip)
        except Exception:
            return None

    @cached_property
    def location(self) -> Optional[str]:
        if self.ip == '127.0.0.1':
            return "There's no place like home"

        json = self.location_json
        if not json:
            return None

        return ', '.join(
            json[key]
            for key in ('city', 'region', 'country_name')
            if json[key]
        ) or 'Unknown'

    @cached_property
    def session_store(self) -> Optional[SessionStore]:
        """
        use this for writes instead of self.session, as it properly updates
        both the Session and cached session used by sessions.cached_db
        """
        if self.session_id:
            return SessionStore(session_key=self.session_id)
        return None

    def end(self, request=None) -> None:
        """Log out and delete the user's sockets and active HTTP sessions"""

        if request:
            request.session.flush()
        if self.session:
            self.session.socket_set.all().delete()
            self.session_store.delete()
            self.session.delete()
        self.delete()


class UserBalance(BaseModel):
    objects = SeasonRegularManager()

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    season = models.IntegerField(default=0)

    def __str__(self) -> str:
        return f'{self.user.username} ({self.balance})'

    def __repr__(self) -> str:
        return f'<UserBalance: {self.user.username} ({self.balance})>'

    class Meta:
        unique_together = (('user', 'season'),)
        index_together = (('user', 'season'),)


class UserStats(BaseModel):
    objects = SeasonRegularManager()

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    hands_played = models.IntegerField(default=0)
    season = models.IntegerField(default=0)

    games_level = models.PositiveIntegerField(
        default=max(
            CASH_GAME_BBS[0] * N_BB_TO_NEXT_LEVEL,
            TOURNEY_BUYIN_AMTS[0] * TOURNEY_BUYIN_TIMES,
        ),
    )

    def __repr__(self):
        return f'<UserStats: {self.user.username}>'

    class Meta:
        unique_together = (('user', 'season'),)
        index_together = (('user', 'season'),)


def user_logged_in_handler(sender, request, user, **kwargs):
    UserSession.update_from_request(request, user)


def user_logged_out_handler(sender, request, user, **kwargs):
    sessions = UserSession.objects.filter(
        session_id=request.session.session_key,
        user_id=user.id,
    )
    for user_session in sessions:
        user_session.end()


user_logged_in.connect(user_logged_in_handler)
user_logged_out.connect(user_logged_out_handler)
