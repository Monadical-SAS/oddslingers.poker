import logging

from datetime import timedelta, datetime
from decimal import Decimal
from typing import Optional, Union, Tuple, Iterable, List

from django.db import models
from django.db.models import Prefetch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.postgres.fields import JSONField
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from django.utils.functional import cached_property

from oddslingers.utils import autocast, DEBUG_ONLY, ExtendedEncoder
from oddslingers.model_utils import BaseModel, DispatchHandlerModel

from sockets.models import Socket

from poker.cards import Card, Deck
from poker.constants import (
    TABLE_TYPES, Event, NL_HOLDEM, TABLE_SUBJECT_REPR, Action,
    SIDE_EFFECT_SUBJ, PLAYER_API, PlayingState, HIDE_TABLES_AFTER_N_HANDS,
    TournamentStatus
)
from poker.bot_personalities import PERSONALITIES

logger = logging.getLogger('poker')

ChangeKey = str
ChangeVal = Union[Deck, Decimal, str, int, bool, list, Event, PlayingState]
Change = Tuple[ChangeKey, ChangeVal]
ChangeList = Iterable[Change]


class ChatHistory(BaseModel):
    def get_chat(self):
        return ChatLine.objects.filter(chat_history=self).order_by('id')

    def get_last_100(self) -> models.QuerySet:
        lines = ChatLine.objects.filter(chat_history=self)
        return lines.order_by('-timestamp')[:100][::-1]


class ChatLine(models.Model):
    id = models.AutoField(primary_key=True)

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    chat_history = models.ForeignKey(ChatHistory, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.DO_NOTHING,
                             null=True)

    # TODO: decide what the max chars in a username should be
    speaker = models.CharField(max_length=20)
    message = models.CharField(max_length=1000)

    class Meta:
        unique_together = (('chat_history', 'timestamp', 'user'),)
        index_together = (('chat_history', 'timestamp'),)

    def __json__(self) -> dict:
        return {
            'timestamp': self.timestamp and self.timestamp.timestamp(),
            'user': self.user,
            'speaker': self.speaker,
            'message': self.message,
        }

    def __repr__(self):
        return f'({self.timestamp}) {self.speaker}: {self.message}'

    def __str__(self):
        return f'({self.timestamp}) {self.speaker}: {self.message}'


class PokerTournamentQuerySet(models.QuerySet):
    def create_tournament(self, name: str, **defaults):
        tournament = self.create(name=name, **defaults)
        tournament.chat.save()
        tournament.save()
        return tournament


class PokerTournament(BaseModel, DispatchHandlerModel):
    objects = PokerTournamentQuerySet.as_manager()

    name = models.CharField(max_length=256, default='Tournament', unique=True)

    game_variant = models.CharField(
        max_length=10,
        choices=TABLE_TYPES,
        default=NL_HOLDEM,
    )
    entrants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='tournaments',
        related_query_name='tournament'
    )
    buyin_amt = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        default=5000
    )
    status = models.IntegerField(
        choices=[
            (tstatus.value, tstatus.name)
            for tstatus in TournamentStatus
        ],
        default=TournamentStatus.PENDING.value
    )
    start_time = models.DateTimeField(null=True, blank=True)
    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL
    )
    tournament_admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        related_name='tournament_admin',
        on_delete=models.SET_NULL
    )
    modified = models.DateTimeField(auto_now=True)
    chat_history = models.OneToOneField(
        ChatHistory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )
    is_private = models.BooleanField(default=False)

    @property
    def path(self) -> str:
        return f'/tournament/{self.short_id}/'

    @property
    def table_path(self) -> Optional[str]:
        table = self.pokertable_set.first()
        return table and table.path

    @property
    def chat(self) -> ChatHistory:
        if self.chat_history is None:
            self.chat_history = ChatHistory()
        return self.chat_history

    @property
    def variant(self) -> str:
        """the human readable table type, e.g. No Limit Hold'em"""
        return dict(TABLE_TYPES).get(self.game_variant, 'Poker')

    @property
    def zulip_topic(self):
        return f'{self.name} ({self.short_id})'

    def mark_as_started(self):
        self.status = TournamentStatus.STARTED.value
        self.save()

    def get_entrants(self) -> List[dict]:
        return [
            entrant.attrs('id', 'username', 'profile_image', 'is_robot')
            for entrant in self.entrants.all()
        ]

    def on_finish_tournament(self, **kwargs) -> ChangeList:
        return (
            ('status', TournamentStatus.FINISHED.value,),
        )

    def get_results(self) -> List[dict]:
        results = self.results.order_by('placement')
        return [result.__json__() for result in results]

    def on_cancel(self):
        refunds = [
            TournamentResult(
                user=entrant,
                placement=0,
                payout_amt=self.buyin_amt,
                tournament=self
            )
            for entrant in self.entrants.all()
        ]

        self.status = TournamentStatus.CANCELED.value

        return [
            self,
            *refunds,
        ]

    def __json__(self) -> dict:
        return {
            'id': str(self.id),
            'path': self.path,
            'name': self.name,
            'buyin_amt': self.buyin_amt,
            'game_variant': self.game_variant,
            'status': self.get_status_display()
        }


class Freezeout(PokerTournament):
    max_entrants = models.IntegerField(null=False, default=6)

    def __json__(self) -> dict:
        return {
            **super().__json__(),
            'max_entrants': self.max_entrants
        }


class TournamentResult(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=False,
        on_delete=models.CASCADE
    )
    tournament = models.ForeignKey(
        PokerTournament,
        null=False,
        related_name='results',
        related_query_name='result',
        on_delete=models.CASCADE
    )
    placement = models.IntegerField()
    payout_amt = models.DecimalField(max_digits=20, decimal_places=2)

    def __json__(self) -> dict:
        return {
            'user': self.user.username,
            'placement': self.placement,
            'payout_amt': self.payout_amt
        }


class PokerTableQuerySet(models.QuerySet):
    def with_players(self) -> models.QuerySet:
        """prefetch player objects and their usernames with the table"""
        return self.prefetch_related(
            'player_set',
            Prefetch(
                'player_set__user',
                queryset=get_user_model().objects.all()
                                         .only('username', 'is_robot'),
            )
        )

    def with_handhistory(self) -> models.QuerySet:
        return self.prefetch_related('handhistory_set')

    def with_stats(self) -> models.QuerySet:
        return self.prefetch_related('stats')

    def with_sidebets(self) -> models.QuerySet:
        from sidebets.models import Sidebet

        return self.prefetch_related(
            'sidebet_set',
            Prefetch(
                'sidebet_set',
                queryset=Sidebet.objects.exclude(status='closed'),
            ),
        )

    def with_chathistory(self) -> models.QuerySet:
        return self.prefetch_related('chat_history')

    def create_table(self, name: str, **defaults) -> 'PokerTable':
        table = self.create(name=name, **defaults)
        PokerTableStats.objects.get_or_create(table=table)
        table.chat.save()
        table.save()
        return table


class PokerTable(BaseModel, DispatchHandlerModel):
    objects = PokerTableQuerySet.as_manager()

    name = models.CharField(max_length=128, default='Homepage Table',
                            unique=False, db_index=True)

    is_archived = models.BooleanField(default=False)

    tournament = models.ForeignKey(
        Freezeout,
        null=True,
        on_delete=models.SET_NULL
    )
    is_mock = models.BooleanField(default=False)

    created = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        on_delete=models.SET_NULL
    )
    modified = models.DateTimeField(auto_now=True, db_index=True)

    table_type = models.CharField(
        max_length=10,
        choices=TABLE_TYPES,
        default=NL_HOLDEM,
    )

    # table settings fields
    min_buyin = models.DecimalField(max_digits=20, decimal_places=2,
                                    null=False, default=100)
    max_buyin = models.DecimalField(max_digits=20, decimal_places=2,
                                    null=False, default=400)
    num_seats = models.IntegerField(default=6)

    # blinds fields
    ante = models.DecimalField(max_digits=20, decimal_places=2,
                               null=True, blank=True)
    sb = models.DecimalField(max_digits=20, decimal_places=2,
                             default=1, null=True)
    bb = models.DecimalField(max_digits=20, decimal_places=2,
                             default=2, null=True)

    btn_idx = models.IntegerField(null=True, blank=True)
    sb_idx = models.IntegerField(null=True, blank=True)
    bb_idx = models.IntegerField(null=True, blank=True)

    # card fields
    deck_str = models.CharField(max_length=312, null=True, blank=True)
    board_str = models.CharField(max_length=256, null=True, blank=True)

    # number of decimal places we want to use to keep track of chip fractions
    precision = models.IntegerField(default=0)

    # hand history
    hand_number = models.IntegerField(default=0)

    seconds_per_action_base = models.IntegerField(default=15)
    seconds_per_action_increment = models.IntegerField(default=5)
    min_timebank = models.IntegerField(default=5)
    max_timebank = models.IntegerField(default=60)

    # these fields are modified by `RECORD_ACTION`, which is produced
    #   by the `timing_events` helper function on the controller
    last_action_timestamp = models.DateTimeField(auto_now_add=True)
    last_human_action_timestamp = models.DateTimeField(null=True)

    chat_history = models.OneToOneField(
        ChatHistory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL
    )

    bounty_flag = models.BooleanField(default=False)
    sidebets_enabled = models.BooleanField(default=False)
    is_tutorial = models.BooleanField(default=False)
    is_private = models.BooleanField(default=False)

    @property
    def chat(self) -> ChatHistory:
        if self.chat_history is None:
            self.chat_history = ChatHistory()
        return self.chat_history

    @property
    def path(self) -> str:
        return f'/table/{self.short_id}/'

    @property
    def sockets(self) -> models.QuerySet:
        return Socket.objects.filter(path=self.path)

    @property
    def deck(self) -> Deck:
        if not self.deck_str:
            return Deck()
        return Deck(self.deck_str.split(','))

    @deck.setter
    def deck(self, deck_obj: Deck):
        assert isinstance(deck_obj, Deck), \
            'The passed deck is not a Deck object'
        self.deck_str = ','.join(deck_obj.to_list())

    @property
    def last_action(self) -> Optional[Event]:
        if not self.last_action_int:
            return None
        return Event(self.last_action_int)

    @last_action.setter
    def last_action(self, event: Event):
        if event is None:
            self.last_action_int = event
        else:
            self.last_action_int = Event.value

    @property
    def board(self) -> List[Card]:
        if not self.board_str:
            return []
        return [Card(c) for c in self.board_str.split(',')]

    @board.setter
    def board(self, board_list: List[Card]):
        assert hasattr(board_list, '__iter__'), \
            'The passed board_list is not an iterable'
        board_list = [str(c) for c in board_list]
        self.board_str = ','.join(board_list)

    def cards_to_deal(self, n_cards) -> List[Card]:
        deck = Deck(self.deck_str.split(','))
        return [deck.deal() for _ in range(n_cards)]

    @property
    def variant(self) -> str:
        """the human readable table type, e.g. No Limit Hold'em"""
        return dict(TABLE_TYPES).get(self.table_type, 'Poker')

    # properties used for table selection
    @property
    def is_new(self) -> bool:
        return self.created_by_id is None\
               and self.hand_number < HIDE_TABLES_AFTER_N_HANDS

    @property
    def is_stale(self) -> bool:
        one_hour_ago = timezone.now() - timedelta(minutes=60)
        return self.modified < one_hour_ago

    @property
    def zulip_topic(self) -> str:
        return f'{self.name} ({self.short_id})'

    @cached_property
    def last_human_activity(self) -> Optional['datetime']:
        try:
            return HandHistoryAction.objects.filter(
                                        hand_history__table_id=self.id,
                                        subject__user__is_robot=False)\
                                    .only('timestamp')\
                                    .latest('timestamp')\
                                    .timestamp
        except HandHistoryAction.DoesNotExist:
            return None

    @cached_property
    def hotness_level(self) -> int:
        """table "hotness rating" on a scale of 0=dead, to 5=poppin"""

        # TODO: make this a more advanced metric combining activity level,
        # blind size, stack size, number of spectators, etc...

        last_activity = self.modified
        if last_activity is None:
            return 0
        elif last_activity > (timezone.now() - timedelta(minutes=3)):
            return 5
        elif last_activity > (timezone.now() - timedelta(minutes=5)):
            return 4
        elif last_activity > (timezone.now() - timedelta(minutes=10)):
            return 3
        elif last_activity > (timezone.now() - timedelta(minutes=60)):
            return 2
        elif last_activity > (timezone.now() - timedelta(days=1)):
            return 1
        return 0

    def __str__(self) -> str:
        return f'{self.variant}:{self.name or self.short_id}'

    def __repr__(self) -> str:
        plyrs = ', '.join(player.username for player in self.player_set.all())
        return f'<{self.name or self.short_id} [{plyrs}]>'

    def __json__(self, *attrs) -> dict:
        return {
            **self.attrs(
                'id',
                'short_id',
                'name',
                'path',
                'table_type',
                'variant',
                'ante',
                'min_buyin',
                'max_buyin',
                'num_seats',
                'sb',
                'bb',
                'hand_number',
                'created',
                'tournament_id',
                'hotness_level',
                'sidebets_enabled'
            ),
            'str': str(self),
            'player_ids': self.player_set.values('id'),
            'players': [str(player) for player in self.player_set.all()],
            **(self.attrs(*attrs) if attrs else {}),
        }

    ##########
    # Events
    @autocast
    def on_set_blind_pos(self, btn_pos: Optional[Decimal],
                               sb_pos: Optional[Decimal],
                               bb_pos: Optional[Decimal]) -> ChangeList:
        return (
            ('btn_idx', btn_pos),
            ('sb_idx', sb_pos),
            ('bb_idx', bb_pos),
        )

    @autocast
    def on_set_blinds(self, sb: Optional[Decimal] = None,
                            bb: Optional[Decimal] = None,
                            ante: Optional[Decimal] = None) -> ChangeList:
        return (
            ('sb', sb if sb is not None else self.sb),
            ('bb', bb if bb is not None else self.bb),
            ('ante', ante if ante is not None else self.ante),
        )

    @autocast
    def on_shuffle(self, deck_str: Optional[str] = None) -> ChangeList:
        if deck_str is None:
            return (('deck', Deck()),)
        else:
            return (('deck_str', deck_str),)

    @autocast
    def on_pop_cards(self, n_cards: int) -> ChangeList:
        deck = self.deck
        popped_cards = [deck.deal() for _ in range(n_cards)]  # noqa
        # print("POPPING CARDS:", popped_cards)
        return (('deck', deck),)

    # used for setting flop/turn/river
    @autocast
    def on_deal(self, card: Card) -> ChangeList:
        board = self.board
        board.append(card)
        return (('board', board), *self.on_record_action())

    def on_reset(self) -> ChangeList:
        return (
            ('deck_str', ''),
            *self.on_record_action(),
            ('board', []),
        )

    def on_end_hand(self) -> ChangeList:
        return (
            ('hand_number', self.hand_number + 1),
        )

    def on_record_action(self, is_robot: bool=True) -> ChangeList:
        if (not self.last_action_timestamp
                or self.last_action_timestamp < timezone.now()):
            if not is_robot:
                return (
                    ('last_action_timestamp', timezone.now()),
                    ('last_human_action_timestamp', timezone.now()),
                )
            return (('last_action_timestamp', timezone.now()),)
        return ()

    def on_delay_countdown(self, n_seconds: int) -> ChangeList:
        changes = self.on_record_action()
        if changes:
            ts = changes[0][1]
        else:
            ts = self.last_action_timestamp

        new_timestamp = ts + timezone.timedelta(seconds=n_seconds)

        return (('last_action_timestamp', new_timestamp),)

    def on_set_bounty_flag(self, set_to: bool) -> ChangeList:
        return (('bounty_flag', set_to),)

    def on_create_transaction(self) -> ChangeList:
        return ()

    def on_log(self, *args, **kwargs) -> ChangeList:
        return ()

    @property
    @DEBUG_ONLY
    def controller(self):
        from poker.controllers import controller_for_table
        return controller_for_table(self)

    @property
    @DEBUG_ONLY
    def accessor(self):
        return self.controller.accessor

    @property
    @DEBUG_ONLY
    def seated_players(self):
        return self.accessor.seated_players()

    @property
    @DEBUG_ONLY
    def active_players(self):
        return self.accessor.active_players()

    @DEBUG_ONLY
    def kick_player(self, username):
        from .heartbeat_utils import queue_tablebeat_dispatch
        from .tablebeat import tablebeat_pid

        player = self.accessor.table.player_set.get(user__username=username)
        if tablebeat_pid(self):
            queue_tablebeat_dispatch(self.id, {
                'type': 'LEAVE_SEAT',
                'player_id': str(player.id),
            })
            queue_tablebeat_dispatch(self.id, {
                'type': 'PLAYER_CLOSE_TABLE',
                'player_id': str(player.id),
            })
        else:
            self.controller.dispatch(
                'LEAVE_SEAT',
                player_id=str(player.id),
            )
            self.controller.dispatch(
                'PLAYER_CLOSE_TABLE',
                player_id=str(player.id),
            )

    @DEBUG_ONLY
    def god_chat(self, msg, speaker='god', user=None):
        # TODO: make this queue a real, persisted chat message
        return self.table.sockets.send_action(
            'UPDATE_GAMESTATE', chat=[{
                'message': msg,
                'speaker': speaker,
                'timestamp': timezone.now(),
                'user': user.id if user else None,
            }]
        )

    @DEBUG_ONLY
    def flush_and_broadcast(self):
        return self.accessor.flush_and_broadcast()

    @DEBUG_ONLY
    def pid(self):
        from poker.tablebeat import tablebeat_pid
        return tablebeat_pid(self)

    @DEBUG_ONLY
    def start_tablebeat(self):
        from poker.tablebeat import start_tablebeat
        return start_tablebeat(self)

    @DEBUG_ONLY
    def stop_tablebeat(self):
        from poker.tablebeat import stop_tablebeat
        return stop_tablebeat(self)

    @staticmethod
    @DEBUG_ONLY
    def new_game(name='New Table', defaults=None, num_bots=0):
        from poker.game_utils import make_game
        return make_game(name=name, defaults=defaults, num_bots=num_bots)

    @DEBUG_ONLY
    def dump_for_test(self, *args, **kwargs):
        return self.controller.dump_for_test(hand='all', *args, **kwargs)


class MockPokerTable(PokerTable):
    def save(self, *args, **kwargs):
        assert self.is_mock
        super().save(*args, **kwargs)


class PlayerManager(models.Manager):
    def get_queryset(self):
        """Always attach usernames to players"""
        return super().get_queryset().prefetch_related(
            Prefetch(
                'user',
                queryset=get_user_model().objects.all()
                                         .only('username', 'is_robot')
            )
        )


class Player(BaseModel, DispatchHandlerModel):
    objects = PlayerManager()
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.DO_NOTHING,
                             null=True)

    ### money info
    # total stack available to bet with
    stack = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    # wagers represents the total chips put into the pot during a hand
    wagers = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    # uncollected_bets represents the total chips put into the pot this street
    uncollected_bets = models.DecimalField(max_digits=20,
                                           decimal_places=2,
                                           default=0)
    dead_money = models.DecimalField(max_digits=20,
                                     decimal_places=2,
                                     default=0)

    ### table info
    table = models.ForeignKey(PokerTable, on_delete=models.CASCADE)
    # numeric position at table
    # if position = None, player has not chosen a seat yet or
    #   has been unseated
    position = models.IntegerField(null=True)
    # whether or not they are at the table currently
    # seated = True implies position = an integer, not null

    # on_leave_seat and on_take_seat
    seated = models.BooleanField(default=False)

    # means they are still occupying seat but not currently dealt in
    # sitting out has value implies position also has integer value
    # sitting out null implies player is not seated at table
    #   (position also null)

    playing_state_int = models.IntegerField(
        choices=[(state.value, state.name) for state in PlayingState],
        null=True
    )
    sit_out_at_blinds = models.BooleanField(default=False)

    mock_name = models.CharField(max_length=64, null=True, blank=True)

    owes_sb = models.BooleanField(default=False)
    owes_bb = models.BooleanField(default=False)

    auto_rebuy = models.DecimalField(max_digits=20,
                                     decimal_places=2,
                                     null=True)
    pending_rebuy = models.DecimalField(max_digits=20,
                                        decimal_places=2,
                                        default=0)

    preset_checkfold = models.BooleanField(default=False)
    preset_check = models.BooleanField(default=False)
    preset_call = models.DecimalField(
        max_digits=20,
        decimal_places=2,
        null=True
    )
    orbits_sitting_out = models.IntegerField(default=0)

    # cards
    cards_str = models.CharField(max_length=256, null=False, default='')

    last_action_int = models.IntegerField(
        choices=[(e.value, e.name) for e in PLAYER_API],
        null=True
    )
    last_action_timestamp = models.DateTimeField(default=timezone.now)

    timebank_remaining = models.IntegerField(default=0)

    created = models.DateTimeField(auto_now_add=True)
    modified = models.DateTimeField(auto_now=True, db_index=True)

    n_hands_played = models.IntegerField(default=0)

    class Meta:
        unique_together = (('table', 'user'),)
        index_together = (('table', 'user'),)

    def dispatch(self, event, **kwargs):
        if event in PLAYER_API:
            self.last_action_timestamp = timezone.now()
        return super().dispatch(event, **kwargs)

    def __str__(self):
        return self.username

    def __repr__(self):
        return f'<@{self.position}:{self.username} ({self.stack})>'

    def __json__(self):
        return {
            **self.attrs(
                'id',
                'short_id',
                'user_id',
                'table_id',
                'username',
            ),
            'str': str(self),
            'user': str(self.user) if self.user_id else None,
            'table': str(self.table) if self.table_id else None,
        }

    @property
    def sockets(self) -> models.QuerySet:
        return Socket.objects.filter(path=self.table.path,
                                     user_id=self.user_id)

    @cached_property
    def username(self) -> str:
        assert (not self.mock_name) != (not self.user), (
            'Illegal to have both self.user and self.mock_name')
        if self.mock_name is None:
            return self.user.username
        return self.mock_name

    @property
    def last_action(self) -> Event:
        if not self.last_action_int:
            return None
        return Event(self.last_action_int)

    @last_action.setter
    def last_action(self, event: Optional[Event]):
        if event is None:
            self.last_action_int = event
        else:
            self.last_action_int = event.value

    @property
    def playing_state(self) -> Optional[PlayingState]:
        if not self.playing_state_int:
            return None
        return PlayingState(self.playing_state_int)

    @playing_state.setter
    def playing_state(self, playing_state: Optional[PlayingState]):
        if playing_state is None:
            self.playing_state_int = playing_state
        else:
            self.playing_state_int = playing_state.value

    @property
    def cards(self) -> List[Card]:
        if not self.cards_str:
            return []
        return [Card(c) for c in self.cards_str.split(',')]

    @cards.setter
    def cards(self, cards_list: List[Card]):
        assert hasattr(cards_list, '__iter__'), \
                'The passed cards_list is not an iterable'
        self.cards_str = ','.join(str(c) for c in cards_list)

    def is_active(self) -> bool:
        return self.seated and not self.is_sitting_out()

    def is_sitting_out(self) -> bool:
        return self.playing_state in (
            PlayingState.SIT_IN_AT_BLINDS_PENDING,
            PlayingState.SITTING_OUT,
            PlayingState.SIT_IN_PENDING,
        )

    @property
    def stack_available(self) -> Decimal:
        return self.stack + self.uncollected_bets

    def total_contributed(self) -> Decimal:
        return self.wagers + self.dead_money

    @autocast
    def check_amt(self, amt: Decimal):
        if amt > self.stack:
            raise ValueError('Cannot wager more than stack')

    @property
    def is_mock(self) -> bool:
        return self.mock_name is not None

    @property
    def is_robot(self) -> bool:
        if not self.user:
            return self.username in PERSONALITIES.keys()

        return self.user.is_robot

    def is_all_in(self) -> bool:
        return self.self.stack == 0 and self.wagers != 0

    ##########
    # event helpers
    def clear_presets(self) -> ChangeList:
        return (
            (preset, None if preset == 'preset_call' else False)
            for preset in ('preset_checkfold', 'preset_check', 'preset_call')
            if getattr(self, preset)
        )

    def clear_active_last_actions(self) -> ChangeList:
        active_acts = (Event.CALL, Event.RAISE_TO, Event.BET, Event.CHECK)
        if self.last_action in active_acts:
            return (('last_action', None),)
        return ()

    def _assert_no_inhand_state(self):
        assert not (self.cards
                    or self.wagers
                    or self.dead_money
                    or self.uncollected_bets), \
            '{} still has in-hand state; cannot leave the hand!'.format(self)

    ##########
    # events
    @autocast
    def on_owe_bb(self, owes: bool) -> ChangeList:
        return (('owes_bb', owes),)

    @autocast
    def on_owe_sb(self, owes: bool) -> ChangeList:
        return (('owes_sb', owes),)

    def on_reset(self) -> ChangeList:
        return (
            ('cards', []),
            ('wagers', 0),
            ('dead_money', 0),
            ('uncollected_bets', 0),
            ('orbits_since_sitting_out', 0),
            ('last_action', None),
            *self.clear_presets(),
        )

    def on_new_street(self) -> ChangeList:
        return (
            ('uncollected_bets', 0),
            *self.clear_presets(),
            *self.clear_active_last_actions(),
        )

    def on_end_hand(self) -> ChangeList:
        return (('n_hands_played', self.n_hands_played + 1),)

    ####################################################################
    # FIX ME
    @autocast
    def on_take_seat(self, position: int) -> ChangeList:
        if self.playing_state == PlayingState.LEAVE_SEAT_PENDING:
            return (('playing_state', PlayingState.SITTING_IN),)
        elif self.seated:
            raise Exception('Tried to take_seat when already seated')
        else:
            if self.playing_state is None:
                playing_state = PlayingState.SITTING_OUT
            else:
                playing_state = self.playing_state
            return (
                ('owes_bb', True),
                ('seated', True),
                ('position', position),
                ('orbits_sitting_out', 0),
                ('playing_state', playing_state),
            )

    def on_leave_seat(self, immediate: bool=False) -> ChangeList:
        if immediate:
            self._assert_no_inhand_state()
            return (
                ('seated', False),
                ('playing_state', None),
            )
        else:
            if self.sit_out_at_blinds:
                return (
                    ('sit_out_at_blinds', False),
                    ('playing_state', PlayingState.LEAVE_SEAT_PENDING),
                )
            return (
                ('playing_state', PlayingState.LEAVE_SEAT_PENDING),
            )

    def on_sit_in(self, immediate: bool=False) -> ChangeList:
        if self.table.tournament is not None:
            if self.cards:
                return (
                    ('last_action', None),
                    ('playing_state', PlayingState.SITTING_IN),
                )
            return (
                ('last_action', Event.FOLD),
                ('playing_state', PlayingState.SITTING_IN),
            )

        if immediate:
            return (
                ('last_action', Event.SIT_IN),
                ('playing_state', PlayingState.SITTING_IN),
            )
        elif self.playing_state == PlayingState.SIT_OUT_PENDING:
            # cancels a sit_out request; player will be set to folded
            return (('playing_state', PlayingState.SITTING_IN),)
        elif self.playing_state in (
                PlayingState.SIT_IN_AT_BLINDS_PENDING,
                PlayingState.SITTING_OUT):
            return (
                ('playing_state', PlayingState.SIT_IN_PENDING),
            )
        else:
            state = str(self.playing_state)
            raise ValueError(f'Cannot SIT_IN if playing_state is {state}')

    def on_sit_out(self, immediate: bool=False) -> ChangeList:
        if self.table.tournament is not None:
            return (
                ('last_action', Event.SIT_OUT),
                ('playing_state', PlayingState.TOURNEY_SITTING_OUT),
            )

        # if SIT_IN_PENDING, cancels the SIT_IN
        if immediate or self.playing_state == PlayingState.SIT_IN_PENDING:
            self._assert_no_inhand_state()
            if self.sit_out_at_blinds:
                return (
                    ('sit_out_at_blinds', False),
                    ('playing_state', PlayingState.SITTING_OUT),
                )
            return (('playing_state', PlayingState.SITTING_OUT),)
        else:
            if self.sit_out_at_blinds:
                return (
                    ('sit_out_at_blinds', False),
                    ('playing_state', PlayingState.SIT_OUT_PENDING),
                )
            return (('playing_state', PlayingState.SIT_OUT_PENDING),)

    @autocast
    def on_sit_in_at_blinds(self, set_to: bool) -> ChangeList:
        if set_to is True:
            return (('playing_state', PlayingState.SIT_IN_AT_BLINDS_PENDING),)
        else:
            return (('playing_state', PlayingState.SITTING_OUT),)

    @autocast
    def on_sit_out_at_blinds(self, set_to: bool) -> ChangeList:
        if self.playing_state in (
                PlayingState.SIT_OUT_PENDING,
                PlayingState.LEAVE_SEAT_PENDING):
            return (
                ('playing_state', PlayingState.SITTING_IN),
                ('sit_out_at_blinds', set_to),
            )
        return (
            ('sit_out_at_blinds', set_to),
        )

    ##################################################################

    @autocast
    def on_deal(self, card: Card) -> ChangeList:
        cards = self.cards
        cards.append(card)
        return (
            ('cards', cards),
            ('orbits_sitting_out', 0),
        )

    @autocast
    def on_ante(self, amt: Decimal) -> ChangeList:
        self.check_amt(amt)

        return (
            ('wagers', self.wagers + amt),
            ('stack', self.stack - amt),
        )

    @autocast
    def on_post_dead(self, amt: Decimal) -> ChangeList:
        self.check_amt(amt)
        return (
            ('dead_money', self.dead_money + amt),
            ('stack', self.stack - amt),
        )

    @autocast
    def on_bet(self, amt: Decimal, all_in: bool=False) -> ChangeList:
        self.check_amt(amt)

        return (
            ('uncollected_bets', amt),
            ('wagers', self.wagers + amt),
            ('stack', self.stack - amt),
            ('last_action', Event.BET),
            *self.clear_presets()
        )

    @autocast
    def on_call(self, amt: Decimal, all_in: bool=False) -> ChangeList:
        amt_adjusted = amt - self.uncollected_bets

        if amt_adjusted >= self.stack:
            amt_adjusted = self.stack

        return (
            ('wagers', self.wagers + amt_adjusted),
            ('stack', self.stack - amt_adjusted),
            ('uncollected_bets', amt),
            ('last_action', Event.CALL),
            *self.clear_presets()
        )

    @autocast
    def on_raise_to(self, amt: Decimal, all_in: bool=False) -> ChangeList:
        amt_adjusted = amt - self.uncollected_bets
        self.check_amt(amt_adjusted)

        diff = amt - self.uncollected_bets

        return (
            ('wagers', self.wagers + diff),
            ('stack', self.stack - diff),
            ('uncollected_bets', amt),
            ('last_action', Event.RAISE_TO),
            *self.clear_presets()
        )

    @autocast
    def on_post(self, amt: Decimal) -> ChangeList:
        self.check_amt(amt)

        return (
            ('wagers', self.wagers + amt),
            ('stack', self.stack - amt),
            ('uncollected_bets', self.uncollected_bets + amt),
            ('last_action', Event.POST),
        )

    def on_fold(self, show_cards: bool = False, cards=None) -> ChangeList:
        return (
            ('last_action', Event.FOLD),
            ('cards', []),
            *self.clear_presets()
        )

    def on_check(self) -> ChangeList:
        return (
            ('last_action', Event.CHECK),
            *self.clear_presets()
        )

    @autocast
    def on_buy(self, amt: Decimal) -> ChangeList:
        return (('pending_rebuy', self.pending_rebuy + amt),)

    @autocast
    def on_update_stack(self, reset_stack: bool=False) -> ChangeList:
        to_amt = 0 if reset_stack else self.stack + self.pending_rebuy
        return (
            ('stack', to_amt),
            ('pending_rebuy', 0),
            ('wagers', 0),
            ('uncollected_bets', 0),
        )

    @autocast
    def on_win(self, amt: Decimal,
               pot_id=None, showdown=None, winning_hand=None) -> ChangeList:
        # pot_id, showdown, and winning_hand are used elsewhere,
        #   and can be ignored here
        return (('stack', self.stack + amt),)

    @autocast
    def on_set_auto_rebuy(self, amt: Decimal) -> ChangeList:
        # set to zero to turn this off
        return (('auto_rebuy', amt),)

    def on_add_orbit_sitting_out(self) -> ChangeList:
        return (('orbits_sitting_out', self.orbits_sitting_out + 1),)

    @autocast
    def on_set_timebank(self, set_to: int) -> ChangeList:
        return (('timebank_remaining', set_to),)

    def on_reveal_hand(self, **kwargs) -> ChangeList:
        # this event signals animations in the front end
        return ()

    def on_bounty_win(self, **kwargs) -> ChangeList:
        # this event signals animations in the front end
        return ()

    def on_muck(self, **kwargs) -> ChangeList:
        return (('cards', []),)

    @autocast
    def on_return_chips(self, amt: Decimal) -> ChangeList:
        return (
            ('uncollected_bets', self.uncollected_bets - amt),
            ('wagers', self.wagers - amt),
            ('stack', self.stack + amt),
        )

    @autocast
    def on_set_preset_checkfold(self, set_to: bool) -> ChangeList:
        return (
            *self.clear_presets(),
            ('preset_checkfold', set_to),
        )

    @autocast
    def on_set_preset_check(self, set_to: bool) -> ChangeList:
        return (
            *self.clear_presets(),
            ('preset_check', set_to),
        )

    @autocast
    def on_set_preset_call(self, set_to: Decimal) -> ChangeList:
        return (
            *self.clear_presets(),
            ('preset_call', set_to),
        )


class MockPlayer(Player):
    def save(self, *args, **kwargs):
        assert self.is_mock
        super().save(*args, **kwargs)


class SideEffectSubject(BaseModel):
    ID = '11' * 16
    id = models.UUIDField(primary_key=True, default=ID, editable=False)

    def __str__(self):
        return SIDE_EFFECT_SUBJ

    def __repr__(self):
        return f'<{SIDE_EFFECT_SUBJ}> model'

    def save(self, *args, **kwargs):
        # make sure the ID they are trying to save matches the singleton's
        #   only allowed ID
        if str(self.id) != str(self.ID):
            raise ValueError('This is intended to be a singleton.')

        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create()
        return obj


class HandHistory(models.Model):
    id = models.AutoField(primary_key=True)
    timestamp = models.DateTimeField(auto_now=True)

    table = models.ForeignKey(PokerTable, on_delete=models.CASCADE)
    hand_number = models.IntegerField(default=0, db_index=True)

    table_json = JSONField(null=True)
    players_json = JSONField(null=True)

    class Meta:
        unique_together = (('table', 'hand_number'), ('table', 'timestamp'))
        index_together = (('table', 'hand_number'))

    def events(self):
        return self.handhistoryevent_set.all()

    def actions(self):
        return self.handhistoryaction_set.all()

    def filtered_json(self, *filter_args, **filter_kwargs) -> dict:
        actions = self.handhistoryaction_set\
                    .filter(*filter_args, **filter_kwargs)\
                    .select_related('subject')\
                    .order_by('id')
        events = self.handhistoryevent_set\
                    .filter(*filter_args, **filter_kwargs)\
                    .select_related('subject_type')\
                    .prefetch_related('subject')\
                    .order_by('id')
        return {
            'ts': self.timestamp,
            'table': self.table_json,
            'players': self.players_json,
            'actions': [a.__json__() for a in actions],
            'events': [e.__json__() for e in events],
        }

    def __repr__(self) -> str:
        return self.__str__()

    def __str__(self) -> str:
        tbl_name = self.table.name
        return f'<HandHistory #{self.id} at {tbl_name}.{self.hand_number}>'


class HandHistoryEvent(models.Model):
    id = models.AutoField(primary_key=True)
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE)

    timestamp = models.DateTimeField(auto_now=True)
    subject_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    subject_id = models.UUIDField()
    subject = GenericForeignKey('subject_type', 'subject_id')
    event = models.CharField(
        choices=((e.name, e.name) for e in Event),
        max_length=64,
        null=True
    )
    args = JSONField()

    def subject_name(self):
        if self.subject_type.model_class() in (Player, MockPlayer):
            return str(self.subject.username)
        elif self.subject_type.model_class() in (PokerTable, MockPokerTable):
            return TABLE_SUBJECT_REPR
        elif self.subject_type.model_class() == SideEffectSubject:
            return str(self.subject)
        else:
            msg = f"Tried to log a subj of type {self.subject_type}"
            raise ValueError(msg)

    def get_ts(self) -> datetime:
        return self.timestamp if self.timestamp else timezone.now()

    def __json__(self) -> dict:
        return {
            'ts': ExtendedEncoder.convert_for_json(self.get_ts()),
            'subj': self.subject_name(),
            'event': str(self.event),
            'args': self.args,
        }

    def __repr__(self):
        return f'<{self.__str__(with_tbl=True)}>'

    def __str__(self, with_ts=False, with_tbl=False):
        output_str = f'@{self.subject_name()} [{self.event}] {self.args}'

        if with_tbl:
            hh = self.hand_history
            prefix = f'{hh.table.name}.{hh.hand_number}'
            output_str = f'{prefix} {output_str}'

        if with_ts:
            if self.timestamp:
                ts_str = ExtendedEncoder.convert_for_json(self.timestamp)
            else:
                ts_str = 'unsaved'
            output_str = f'{ts_str} {output_str}'

        return output_str


class HandHistoryAction(models.Model):
    id = models.AutoField(primary_key=True)
    hand_history = models.ForeignKey(HandHistory, on_delete=models.CASCADE)

    timestamp = models.DateTimeField(auto_now=True)
    subject = models.ForeignKey(Player, on_delete=models.CASCADE)
    action = models.CharField(
        choices=((a.name, a.name) for a in Action),
        max_length=64,
        null=True
    )
    args = JSONField()

    class Meta:
        unique_together = (('hand_history', 'timestamp'),)

    def get_ts(self) -> datetime:
        return self.timestamp if self.timestamp else timezone.now()

    def __json__(self) -> dict:
        return {
            'ts': ExtendedEncoder.convert_for_json(self.get_ts()),
            'subj': self.subject.username,
            'action': str(self.action),
            'args': self.args,
        }

    def __repr__(self) -> str:
        return f'<{self.__str__(with_tbl=True)}>'

    def __str__(self, with_ts=False, with_tbl=False) -> str:
        output_str = f'@{self.subject.username} [{self.action}] {self.args}'

        if with_tbl:
            hh = self.hand_history
            prefix = f'{hh.table.name}.{hh.hand_number}'
            output_str = f'{prefix} {output_str}'

        if with_ts:
            if self.timestamp:
                ts_str = ExtendedEncoder.convert_for_json(self.timestamp)
            else:
                ts_str = 'unsaved'
            output_str = f'{ts_str} {output_str}'

        return output_str


class PokerTableStats(BaseModel):
    table = models.OneToOneField(
        PokerTable,
        on_delete=models.CASCADE,
        related_name='stats'
    )
    players_per_flop_pct = models.DecimalField(
        default=0,
        max_digits=20,
        decimal_places=2,
        null=True
    )
    avg_pot = models.DecimalField(
        default=0,
        max_digits=20,
        decimal_places=2,
        null=True
    )
    avg_stack = models.DecimalField(
        default=0,
        max_digits=20,
        decimal_places=2,
        null=True
    )
    hands_per_hour = models.DecimalField(
        default=0,
        max_digits=20,
        decimal_places=2,
        null=True
    )
    num_samples = models.IntegerField(default=0)

    def __json__(self, *attrs) -> dict:
        return self.attrs(
            'players_per_flop_pct',
            'avg_pot',
            'avg_stack',
            'hands_per_hour',
            'num_samples',
            *attrs,
        )

