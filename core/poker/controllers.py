import logging
import traceback

from typing import Type, List, Dict, Tuple, Union, Optional

from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.db import transaction

from oddslingers.utils import (
    autocast, rotated, get_next_filename, timezone, to_json_str,
    secure_random_number,
)

from sockets.models import Socket

from poker import rankings
from poker.accessors import PokerAccessor, accessor_type_for_table
from poker.constants import (
    Event, Action, NEW_HAND_STR, NL_HOLDEM, PL_OMAHA, NL_BOUNTY,
    SIDE_EFFECT_SUBJ, ANIMATION_DELAYS,
    NUM_HOLECARDS, PlayingState, BLINDS_SCHEDULE,
    HANDS_TO_INCREASE_BLINDS, SIDEBET_ACTIONS, VISIBLE_ACTIONS
)
from poker.handhistory import HandHistoryLog, DBLog, fmt_eventline
from poker.megaphone import broadcast_to_sockets
from poker.models import PokerTable, Player, ChangeList, Freezeout
from poker.subscribers import (
    Subscriber, NotificationSubscriber, ChatSubscriber,
    LogSubscriber, AnimationSubscriber, BankerSubscriber,
    TableStatsSubscriber, TournamentResultsSubscriber,
    TournamentChatSubscriber, LevelSubscriber, AnalyticsEventSubscriber,
)
from oddslingers.subscribers import UserStatsSubscriber
from rewards.subscribers import BadgeSubscriber  # noqa
from sidebets.subscribers import SidebetSubscriber

logger = logging.getLogger('poker')

EventSubject = Union[PokerTable, Player, Freezeout, str]
EventArgs = Dict[str, Union[str, Decimal, Optional[int]]]
EventTuple = Tuple[EventSubject, Event, EventArgs]
EventList = List[EventTuple]

ActionTuple = Tuple[Player, Action, Dict]
ActionList = List[ActionTuple]

# TODO: have all function that dispatch return (this or an EventList)
DispatchRecord = Tuple[ActionList, EventList]


class GameController:
    """
        Base class for all Game Controllers.
        Provides dispatch and step function stub
    """

    # you must set these in the __init__ when you inherit from GameController
    accessor: PokerAccessor = None
    log: HandHistoryLog = None
    subscribers: List[Subscriber] = None

    # this should be set statically (according to the controller type)
    #   to something from poker.constants
    expected_tabletype: str = None
    verbose: bool = False

    def __init__(self, *args, **kwargs):
        # stubs are here to allow mypy to know the subclasses have these funcs
        raise NotImplementedError('__init__ must be defined by a subclass.')

    @property
    def table(self) -> PokerTable:
        return self.accessor.table

    def check_tabletype(self):
        assert self.table.table_type == self.expected_tabletype, \
                f'Expected a table of type {self.expected_tabletype} '\
                f'but got {self.table.table_type}'

    def describe(self, print_me=True):
        return self.accessor.describe(print_me)

    def dump_for_test(self, hand=None, fn_pattern='hh_',
                      notes=None, path=None):
        """hh filenames are hh_XXX.json, where XXX are ordered digits"""

        path = path or settings.DEBUG_DUMP_DIR
        new_fn = get_next_filename(path, fn_pattern, '.json')

        if hand is None:
            self.log.save_to_file(new_fn,
                                  player='all',
                                  current_hand_only=True,
                                  indent=True,
                                  notes=notes)

        elif hand == 'all':
            self.log.save_to_file(new_fn,
                                  player='all',
                                  indent=True,
                                  notes=notes)
        elif isinstance(hand, int):
            if hand == -1:
                hand = self.table.hand_number - 1
            self.log.save_to_file(new_fn,
                                  player='all',
                                  hand_gte=hand,
                                  hand_lt=hand+1,
                                  indent=True,
                                  notes=notes)
        else:
            raise ValueError(f'Invalid hand provided: {hand}')

    def debug_filedump(self, error_msg, filename=None):
        notes = to_json_str({
            'error_msg': error_msg,
            'callstack': list(traceback.format_stack()),
            'table': self.table.attrs(),
            'players': [player.attrs() for player in self.accessor.players],
        })
        if filename:
            self.log.save_to_file(filename, player='all', notes=notes)
        else:
            self.dump_for_test(hand='all', notes=notes)

    def dispatch_timing_reset(self, *args, **kwargs):
        raise NotImplementedError(
            'dispatch_timing_reset must be defined by a subclass.'
        )

    def join_table(self, *args, **kwargs):
        raise NotImplementedError('join_table must be defined by a subclass.')

    def step(self, *args, **kwargs):
        raise NotImplementedError('step must be defined by a subclass.')

    def dispatch(self, action_name: str, **kwargs) -> None:
        # print('dispatching', action_name, 'args:', kwargs)
        self._start_dispatch_timestamp = timezone.now().timestamp()
        should_broadcast = False
        broadcast_only_to_player = None

        if action_name.lower() in ('noop', 'latency_test'):
            pass
        elif action_name.lower() == 'join_table':
            self.join_table(**kwargs)
            should_broadcast = self.broadcast
        elif '_sidebet' in action_name.lower():
            should_broadcast = self.broadcast
            self.sidebet_dispatch(action_name, **kwargs)
        else:
            should_broadcast = self.broadcast
            plyr, public = self.player_dispatch(action_name, **kwargs)
            broadcast_only_to_player = None if public else plyr

        self.step()
        self.commit(should_broadcast, broadcast_only_to_player)

        self._end_dispatch_timestamp = timezone.now().timestamp()

        if action_name.lower() == 'latency_test':
            self.test_latency(kwargs)

    def player_dispatch(self, action_name, **kwargs) -> Tuple[Player, bool]:
        player = self.accessor.player_by_player_id(kwargs['player_id'])

        try:
            action = Action.from_str(action_name)
        except KeyError:
            raise InvalidAction(
                f'No Action with this name exists: {action_name}'
            )

        avail_acts = self.accessor.available_actions(player)
        if action not in avail_acts:
            msg = f'Tried to dispatch @{player}: [{action_name}]: {kwargs} '\
                  f'but it is not one of the available actions: {avail_acts}'
            raise RejectedAction(msg)

        # get the controller function for this action
        subevent_generator = getattr(self, action_name.lower(), None)

        assert subevent_generator is not None, \
                f'Got unrecognized action: {action_name}'

        try:
            events = subevent_generator(**kwargs)
        except Exception as err:
            msg = f'{err} at subevent_generator for with '\
                  f'@{player}: [{action_name}]: {kwargs}'
            raise type(err)(msg).with_traceback(err.__traceback__)

        self.log.write_action(action_name, **kwargs)
        self.internal_dispatch(events)

        # 2nd arg tells broadcast whether to broadcast to the whole table
        return player, action in VISIBLE_ACTIONS

    def sidebet_dispatch(self, action_name, **kwargs):
        user = self.accessor.user_by_id(kwargs['user_id'])

        try:
            action = Action.from_str(action_name)
        except KeyError:

            raise InvalidAction(
                f'No Action with this name exists: {action_name}'
            )

        assert action in SIDEBET_ACTIONS, \
                f'got non sidebet action: {action_name}'

        # get the controller function for this action
        subevent_generator = getattr(self, action_name.lower(), None)

        assert subevent_generator is not None, \
                f'Got unrecognized action: {action_name}'

        try:
            events = subevent_generator(**kwargs)
        except Exception as err:
            msg = f'{err} at subevent_generator for with '\
                  f'@{user}: [{action_name}]: {kwargs}'
            raise type(err)(msg).with_traceback(err.__traceback__)

        self.log.write_action(action_name, **kwargs)
        self.internal_dispatch(events)

    def internal_dispatch(self, events: EventList) -> None:
        # print('dispatching events:', events)
        for subj, event, kwargs in events:
            try:
                changes: ChangeList = []
                if subj == SIDE_EFFECT_SUBJ:
                    if event in (Event.NEW_HAND,
                                 Event.CHAT,
                                 Event.NOTIFICATION,
                                 Event.NEW_STREET,
                                 Event.CREATE_TRANSFER,
                                 Event.SHOWDOWN_COMPLETE,
                                 Event.CREATE_SIDEBET,
                                 Event.CLOSE_SIDEBET,):
                        # used by subscribers
                        pass
                    else:
                        raise ValueError(f'Event {event} not specified '
                                          'for SIDE_EFFECT_SUBJ')

                else:
                    assert isinstance(subj, (PokerTable, Player, Freezeout))  # for mypy
                    changes = subj.dispatch(event, **kwargs)

                if self.verbose:
                    print(f"writef: @{subj} [{event}] {kwargs}")
                    self.accessor.describe()

                # TODO: remove BadgeSubscriber dependency on LogSubscriber
                #   and then remove this check
                logsub_first = False
                for sub in self.subscribers:
                    if isinstance(sub, LogSubscriber):
                        logsub_first = True
                    elif isinstance(sub, BadgeSubscriber) and not logsub_first:
                        msg = 'Cannot dispatch to BadgeSubscriber before '\
                              'LogSubscriber because of BadgeSubscriber '\
                              'dependency on the HandHistoryLog.'
                        raise Exception(msg)
                    sub.dispatch(subj, event, changes=changes, **kwargs)

            except Exception as err:
                msg = f'{err} at dispatch with: @{subj}: [{event}] {kwargs}'
                raise type(err)(msg).with_traceback(err.__traceback__)

    def commit(self, broadcast=True, broadcast_only_to_player=None) -> None:
        with transaction.atomic():
            self.accessor.commit()

            for sub in self.subscribers:
                if isinstance(sub, LogSubscriber):
                    assert self.log is sub.log, \
                        'if the sub.log and self.log are different, '\
                        'then events and actions are being logged to '\
                        'different places (and only events are saved)'
                sub.commit()

        if broadcast:
            broadcast_to_sockets(self.accessor,
                                self.subscribers,
                                broadcast_only_to_player)


class HoldemController(GameController):
    expected_tabletype = NL_HOLDEM

    def __init__(self,
                 table: PokerTable,
                 players: List[Player]=None,
                 log: HandHistoryLog=None,
                 subscribers: List[Subscriber]=None,
                 verbose: bool=False,
                 broadcast: bool=True):

        self.accessor = accessor_type_for_table(table)(table, players)
        self.log = log if log is not None else DBLog(self.accessor)

        # smartly get the DB log if it's not passed
        self.subscribers = subscribers if subscribers is not None else [
            NotificationSubscriber(self.accessor),
            ChatSubscriber(self.accessor),
            AnimationSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
            LogSubscriber(self.log),
            BadgeSubscriber(self.accessor, self.log),
            SidebetSubscriber(self.accessor),
            LevelSubscriber(self.accessor),
            TableStatsSubscriber(self.accessor),
            UserStatsSubscriber(self.accessor),
            AnalyticsEventSubscriber(self.accessor),
        ]

        self.broadcast = broadcast
        self.verbose = verbose

        if verbose:
            print(f'initialized {self.__class__.__name__} with table {table}')
            print('players:')
            print('name\tstack\twagers\tuncollected')
            for p in self.accessor.players:
                print(f'{p.username[:5]}\t{p.stack:<5}\t{p.wagers}\t'
                      f'{p.uncollected_bets}')

        self.check_tabletype()

    ###########################################################################
    # PLAYER API

    # synchronous-only actions
    @autocast
    def bet(self, player_id: str, amt: Decimal, **kwargs) -> EventList:
        amt = self.accessor.round_wager(amt)
        player = self.accessor.player_by_player_id(player_id)
        if (amt > player.stack
                or (amt < self.table.bb and amt != player.stack)):
            raise InvalidAction('Invalid bet amount')
        all_in = player.stack_available - amt == 0
        return [
            (player, Event.BET, {'amt': amt, 'all_in': all_in}),
            *self.timing_events(player, Action.BET)
        ]

    @autocast
    def raise_to(self, player_id: str, amt: Decimal, **kwargs) -> EventList:
        amt = self.accessor.round_wager(amt)
        player = self.accessor.player_by_player_id(player_id)
        min_amt = self.accessor.min_bet_amt()

        if (amt > player.stack_available
                or (amt < min_amt and amt != player.stack_available)):
            raise InvalidAction('Invalid raise amount')
        all_in = player.stack_available - amt == 0
        return [
            (player, Event.RAISE_TO, {'amt': amt, 'all_in': all_in}),
            *self.timing_events(player, Action.RAISE_TO)
        ]

    @autocast
    def call(self, player_id: str, **kwargs) -> EventList:
        player = self.accessor.player_by_player_id(player_id)
        amt_to_call = self.accessor.call_amt(player)
        all_in = player.stack_available - amt_to_call == 0

        return [
            (player, Event.CALL, {'amt': amt_to_call, 'all_in': all_in}),
            *self.timing_events(player, Action.CALL)
        ]

    @autocast
    def check(self, player_id: str, **kwargs) -> EventList:
        player = self.accessor.player_by_player_id(player_id)
        return [
            (player, Event.CHECK, {}),
            *self.timing_events(player, Action.CHECK)
        ]

    @autocast
    def fold(self, player_id: str,
                   sit_out: bool=False,
                   show_cards: bool=False,
                   **kwargs) -> EventList:
        player = self.accessor.player_by_player_id(player_id)
        event_kwargs = {}
        if show_cards:
            event_kwargs = {'show_cards': True, 'cards': player.cards}
        if sit_out:
            return [
                (player, Event.FOLD, event_kwargs),
                (player, Event.SIT_OUT, {}),
                *self.timing_events(player, Action.FOLD)
            ]
        return [
            (player, Event.FOLD, event_kwargs),
            *self.timing_events(player, Action.FOLD)
        ]

    # actions available out of sync
    @autocast
    def buy(self, player_id: str, amt: Decimal, **kwargs) -> EventList:
        amt = self.accessor.round_wager(amt)
        player = self.accessor.player_by_player_id(player_id)

        if not self.accessor.is_legal_buyin(player, amt):
            msg = 'Invalid buyin amount'
            return [(SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                'player': player,
                'notification_type': 'rebuy_notification',
                'msg': msg,
            })]

        if not self.accessor.player_has_balance(player, amt):
            msg = f"Tried to buy in for {amt} but not enough chips available."
            return [(SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                'player': player,
                'notification_type': 'rebuy_notification',
                'msg': msg,
            })]

        return [
            (SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                    'player': player,
                    'notification_type': 'rebuy_notification',
                    'msg': f'Buyin of {amt} will be given at end of hand.'}),
            (player, Event.BUY, {'amt': amt})
        ]

    @autocast
    def take_seat(self, player_id: str, position: int, **kwargs) -> EventList:
        # in most cases, use join_table instead because this requires
        #   that a player object already exist for this table, and
        #   join_table will apply user options such as sit_behaviour
        player = self.accessor.player_by_player_id(player_id)
        sit_event = (player, Event.TAKE_SEAT, {"position": position})
        if player.seated:
            if player.playing_state != PlayingState.LEAVE_SEAT_PENDING:
                raise InvalidAction('Player is already sitting at the table')
            return [sit_event]

        table = self.table
        player_at_pos = self.accessor.players_at_position(position,
                                                          active_only=True)
        if (position > table.num_seats - 1
            or player_at_pos is not None):
            raise InvalidAction('Invalid position')

        if player.stack or player.user and player.user.default_buyin:
            # if a player was sitting before, they must buy in for the same
            #   stack they had before
            amt = player.stack or player.user.default_buyin * table.bb

            if not self.accessor.player_has_balance(player, amt):
                msg = f'Player {player.username} tried to buy in for '\
                      f"{amt} but doesn't have enough chips available."
                raise InvalidAction(msg)

            transfer = (SIDE_EFFECT_SUBJ, Event.CREATE_TRANSFER, {
                'src': player.user,
                'dst': self.table,
                'amt': amt,
                'notes': fmt_eventline(subj=player.username,
                                       event=Event.TAKE_SEAT,
                                       args={'amt': amt}),
            })
            return [sit_event, transfer]
        return [sit_event]

    @autocast
    def leave_seat(self, player_id: str, **kwargs) -> EventList:
        events = []
        player = self.accessor.player_by_player_id(player_id)

        if not player.seated:
            raise InvalidAction('Received leave_seat event for player '
                                'that is not seated')

        events.append((player, Event.LEAVE_SEAT, {}))
        if player.is_sitting_out():
            return self.player_leave_table(player)
        else:
            events.append((SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                'player': player,
                'notification_type': 'leave_seat',
                'msg': 'You will leave the seat at end of hand'
            }))

        return events

    @autocast
    def sit_in(self, player_id: str, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        if not player.stack >= self.accessor.min_amt_to_play(player):
            raise InvalidAction('Player needs more chips to play.')
        return [(player, Event.SIT_IN, {})]

    @autocast
    def sit_out(self, player_id: str, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        return [(player, Event.SIT_OUT, {})]

    @autocast
    def sit_in_at_blinds(self, player_id: str, set_to: bool, **kwargs):
        player = self.accessor.player_by_player_id(player_id)

        if player.playing_state == PlayingState.SIT_IN_AT_BLINDS_PENDING:
            if set_to:
                raise InvalidAction('Player will already sit in at blinds')
        elif player.playing_state in (
                PlayingState.SITTING_OUT,
                PlayingState.SIT_IN_PENDING,
                PlayingState.LEAVE_SEAT_PENDING):
            if not set_to:
                raise InvalidAction('Player was not going to sit in at blinds')
        else:
            raise InvalidAction('Player is not sitting out.')

        return [(player, Event.SIT_IN_AT_BLINDS, {'set_to': set_to})]

    @autocast
    def sit_out_at_blinds(self, player_id: str, set_to: bool, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        if player.playing_state not in (
                PlayingState.SITTING_IN,
                PlayingState.SIT_OUT_PENDING,
                PlayingState.LEAVE_SEAT_PENDING):
            raise InvalidAction('Player is already sitting out.')
        return [(player, Event.SIT_OUT_AT_BLINDS, {'set_to': set_to})]

    @autocast
    def set_auto_rebuy(self, player_id: str, amt: Decimal, **kwargs):
        player = self.accessor.player_by_player_id(player_id)

        amt_is_zero = amt == 0
        if not self.accessor.is_legal_buyin(None, amt) and not amt_is_zero:
            raise InvalidAction('Invalid auto-rebuy amount.')

        if amt:
            msg = f'Auto-rebuy has been set to {amt}.'
        else:
            msg = 'Auto-rebuy is off.'
        return [
            (SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                'player': player,
                'notification_type': 'rebuy_notification',
                'msg': msg
            }),
            (player, Event.SET_AUTO_REBUY, {'amt': amt}),
        ]

    @autocast
    def set_preset_checkfold(self, player_id: str, set_to: bool, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        return [(player, Event.SET_PRESET_CHECKFOLD, {'set_to': set_to})]

    @autocast
    def set_preset_check(self, player_id: str, set_to: bool, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        return [(player, Event.SET_PRESET_CHECK, {'set_to': set_to})]

    @autocast
    def set_preset_call(self, player_id: str, set_to: Decimal, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        call_amt = self.accessor.call_amt(player)
        if set_to not in [call_amt, 0]:
            raise RejectedAction(f'Tried to preset a call for {set_to} '\
                             f'when call_amt was {call_amt}')
        return [(player, Event.SET_PRESET_CALL, {'set_to': set_to})]

    ###################
    # Utility player action functions
    def dispatch_kick_inactive_players(self):
        if self.accessor.table.is_tutorial:
            return

        players_to_kick = self.accessor.players_to_kick()
        if players_to_kick:
            for player in players_to_kick:
                self.player_dispatch("LEAVE_SEAT", player_id=player.id)
                if not player.is_robot:
                    msg = f'{player.username} was bumped for inactivity'
                    self.internal_dispatch([self._dealer_msg_event(msg)])
                self.step()
            self.commit()

    def dispatch_player_leave_table(self, player: Player, broadcast=True):
        self.player_dispatch('LEAVE_SEAT', player_id=player.id)
        self.step()
        self.commit(broadcast=broadcast)

    ##################
    # internal-use utility functions
    def player_disconnect(self, player: Player):
        # print(player, 'disconnected')
        self.internal_dispatch([(player, Event.SIT_OUT, {})])

    def player_close_table(self, player: Player):
        self.internal_dispatch([(player, Event.LEAVE_SEAT, {})])

    def player_leave_table(self, player: Player):
        return [
            (player, Event.LEAVE_SEAT, {'immediate': True}),
            (SIDE_EFFECT_SUBJ, Event.CREATE_TRANSFER, {
                'src': self.table,
                'dst': player.user,
                'amt': player.stack,
                'notes': fmt_eventline(subj=player.username,
                                       event=Event.LEAVE_SEAT,
                                       args={'amt': player.stack}),
            }),
        ]

    def create_sidebet(self, player_id, user_id, amt, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        user = self.accessor.user_by_id(user_id)
        return [
            (SIDE_EFFECT_SUBJ, Event.CREATE_SIDEBET, {
                'player': player,
                'user': user,
                'amt': amt
            })
        ]

    def close_sidebet(self, user_id, player_id, **kwargs):
        user = self.accessor.user_by_id(user_id)
        player = self.accessor.player_by_player_id(player_id)
        sidebets = self.accessor.user_sidebets_for_player(user, player)
        return [
            (SIDE_EFFECT_SUBJ, Event.CLOSE_SIDEBET, {
                'sidebets': sidebets
            })
        ]

    # note: this is a special method
    #   - it is called with a user_id instead of a player_id
    #   - a new player object is added to the accessor
    #   - transactions are created during rebuy_updates_for_player
    @autocast
    def join_table(self, user_id: str, buyin_amt: Decimal=None,
                   position: int=None, **kwargs):
        ''' the story of join_table:
            1. a player object needs to be retrieved or created for the user
            2. TAKE_SEAT is dispatched for that player
                note: SIT_IN_AT_BLINDS is set to True
            3. BUY is dispatched for that user
            4. rebuy_updates reflects the BUY amount in the player's stack
        '''

        # Setup position
        has_sidebets = self.accessor.user_has_active_sidebets(user_id,
                                                              self.table.id)
        if has_sidebets:
            user = self.accessor.user_by_id(user_id)
            self.internal_dispatch([
                (SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                    'spectator': user,
                    'notification_type': 'failed_join_table',
                    'msg': f'You cannot join a table with active sidebets.',
                }),
            ])
            self.broadcast = True
            return None

        positions_taken = [p.position for p in self.accessor.seated_players()]
        positions_available = [
            i for i in range(self.table.num_seats)
            if i not in positions_taken
        ]
        if len(positions_available) < 1:
            raise InvalidAction("Table is full.")
        if position is None:
            random_idx = secure_random_number(max_num=len(positions_available))
            position = positions_available[random_idx]
        elif position not in positions_available:
            raise InvalidAction("That seat is already taken.")

        # Setup Player object
        player = self.accessor.player_by_user_id(user_id)
        if player is not None:
            if player.seated:
                raise InvalidAction("Player is already seated at this table.")
        else:
            user = self.accessor.user_by_id(user_id)
            player = Player(
                user=user,
                table=self.table,
            )

            self.accessor.players.append(player)

        # Setup initial buyin
        rebuy_amount = player.user.auto_rebuy_in_bbs * self.table.bb
        is_rebuy_set = self.accessor.is_legal_buyin(None, rebuy_amount)
        has_balance = self.accessor.player_has_balance(player, rebuy_amount)

        if is_rebuy_set and has_balance:
            buyin_amt_check = rebuy_amount
        else:
            buyin_amt_check = self.accessor.table.min_buyin

        if not buyin_amt or buyin_amt < buyin_amt_check:
            buyin_amt = buyin_amt_check

        # Setup auto rebuys
        set_rebuy_actions = ()
        if is_rebuy_set:
            set_rebuy_actions = self.set_auto_rebuy(player.id, rebuy_amount)

        # Dispatch the initial take-seat events
        self._check_join_table_buyin(player, buyin_amt)
        self.internal_dispatch([
            (player, Event.TAKE_SEAT, {'position': position}),
            *self._player_sitting_behaviour_event(player),
            *set_rebuy_actions,
        ])
        self.log.write_action(Action.TAKE_SEAT, player.id,
                              buyin_amt=buyin_amt,
                              position=position,
                              username=player.username,
                              stack=player.stack,
                              owes_sb=player.owes_sb,
                              owes_bb=player.owes_bb,
                              playing_state=player.playing_state,
                              auto_rebuy=player.auto_rebuy,
                              orbits_sitting_out=player.orbits_sitting_out,)

        # Dispatch the initial join table buyin event
        self._dispatch_join_table_buyin(player, buyin_amt)

        return player

    def _player_sitting_behaviour_event(self, player):
        '''
        player's state when join_table is called will be
        SITTING_OUT by default
        '''
        if not player.user:
            return []
        if player.user.sit_behaviour == PlayingState.SIT_IN_AT_BLINDS_PENDING:
            return [(player, Event.SIT_IN_AT_BLINDS, {'set_to': True})]
        if player.user.sit_behaviour == PlayingState.SIT_IN_PENDING:
            return [(player, Event.SIT_IN, {})]
        if player.user.sit_behaviour == PlayingState.SITTING_OUT:
            return []

    def _dispatch_join_table_buyin(self, player, buyin_amt):
        if player.stack:
            buyin_amt = max(player.stack, buyin_amt)
            self.internal_dispatch([
                (player, Event.UPDATE_STACK, {'reset_stack': True})
            ])
        self.internal_dispatch([(player, Event.BUY, {'amt': buyin_amt})])
        self.internal_dispatch(self.rebuy_updates_for_player(player))

    def test_latency(self, initial_message: dict):
        # TODO: remove this from controller
        """respond to the given socket id with the current timestamp"""
        end_time = timezone.now().timestamp()
        total_time = end_time - initial_message['RECV_TIMESTAMP']
        dispatch_time = self._end_dispatch_timestamp - self._start_dispatch_timestamp
        try:
            socket = Socket.objects.get(id=initial_message['socket_id'])
            socket.send_action(
                'SERVER_LATENCY',
                total_time=total_time*1000,
                dispatch_time=dispatch_time*1000,
                queued_time=(total_time - dispatch_time)*1000)
        except Socket.DoesNotExist:
            # user left halfway through a latency test
            pass

    def _check_join_table_buyin(self, player: Player, buyin_amt: Decimal):
        no_funds = lambda m: not self.accessor.player_has_balance(player, m)
        if no_funds(player.stack):
            msg = f'Player left table and must buy in for'\
                  f'previous amount, but lacks the balance.'
            raise InvalidAction(msg)
        if buyin_amt and no_funds(buyin_amt):
            msg = f"Player tried to buy in but didn't have enough chips"
            raise InvalidAction(msg)

    #########################################
    # timing utility functions
    def timed_dispatch(self, internal_only=False):
        '''should be called regularly to see if players need to be timed out'''
        player = self.accessor.next_to_act()
        table = self.table

        if player is not None:
            assert table.last_action_timestamp, \
                'Table has no last action timestamp, so timed events \
                cant be started.'

            # if next player is out of time
            if self.accessor.is_out_of_time(player):
                # print(player, 'ran out of time.')
                self.internal_dispatch(self.out_of_time_msg(player))
                self.dispatch('FOLD', player_id=player.id, sit_out=True)
                return True

        return False

    def out_of_time_msg(self, player: Player):
        msg = f"{player.username} ran out of time and folded."
        return [self._dealer_msg_event(msg)]

    def timing_events(self, player: Player, action_type: Action) -> EventList:
        is_robot = {'is_robot': player.is_robot}
        events = [(self.table, Event.RECORD_ACTION, is_robot)]

        time_elapsed = self.accessor.seconds_since_last_action()
        time_allowed = self.accessor.seconds_to_act()
        if time_elapsed is not None and time_elapsed > time_allowed:
            secs = (time_allowed + player.timebank_remaining) - time_elapsed

            if secs < -2:
                testing_or_mock = settings.IS_TESTING or player.is_mock
                if not testing_or_mock:
                    warning = 'Over two seconds have passed after '\
                              'player has already run out of time.'
                    logger.warning(warning)
                    # self.dump_for_test(hand='all', notes=warning,
                    #                fn_pattern='timebug_')

            new_timebank = max(secs - time_elapsed,
                                self.table.min_timebank)

            events.append((
                    player, Event.SET_TIMEBANK, {'set_to': new_timebank}))

        return events

    def dispatch_timing_reset(self):
        self.internal_dispatch([(self.table, Event.RECORD_ACTION, {})])
        self.commit(broadcast=True)

    def bump_inactive_humans(self):
        if self.table.is_tutorial:
            return []

        five_mins = timedelta(minutes=5)
        table = self.accessor.table
        assert timezone.now() - table.last_action_timestamp > five_mins, \
                "Called bump_inactive_humans on a recently-used table..."
        bumped_plyrs = []
        while True:
            plyr = self.accessor.next_to_act()
            if not plyr:
                break
            if plyr.user.is_robot:
                break
            msg = f"{plyr.username} ran out of time and folded."
            self.internal_dispatch([self._dealer_msg_event(msg)])
            self.player_dispatch('FOLD', player_id=plyr.id, sit_out=True)
            self.step()

        for plyr in self.accessor.seated_players():
            if not plyr.is_active() and not plyr.user.is_robot:
                msg = f"{plyr.username} was booted due to inactivity."
                self.internal_dispatch([self._dealer_msg_event(msg)])
                self.player_dispatch('LEAVE_SEAT', player_id=plyr.id)
                bumped_plyrs.append(plyr)
                self.step()

        return bumped_plyrs

    ##########################################################################
    # Bot-specific
    def dispatch_sit_in_for_bots(self):
        '''
        note that this is a no-op unless there are bots sitting out
        that could be sitting in and playing, in which case it will
        behave like a dispatch
        '''
        confused_bots = self.accessor.bots_who_should_sit_in()
        if confused_bots:
            for bot in confused_bots:
                self.player_dispatch('SIT_IN', player_id=bot.id)

            self.step()
            self.commit()

    ##########################################################################
    # INTERNAL LOGIC

    # TODO: change this to a DispatchRecord
    def step(self, end_hand_stop=False) -> ActionList:
        '''
        order of internal step calls:
        - setup_hand()
        - < wait for players to act -- mandatory >
        - deal_flop()
        - < wait for players to act >
        - deal_turn()
        - < wait for players to act >
        - deal_river()
        - < wait for players to act >
        - end_hand()
        setup_hand(), the first wait for players, and end_hand()
        are always called.
        the rest depend on whether there's action left in the hand
        '''
        next_to_act = self.accessor.next_to_act()
        if next_to_act is None:
            if self.accessor.is_predeal():
                self.setup_hand()
                return []
            elif self.accessor.is_river_or_end():
                if not end_hand_stop:
                    self.end_hand()
                    return self.step(end_hand_stop)
                return []
            elif self.accessor.is_turn():
                self.deal_river()
                return self.step(end_hand_stop)
            elif self.accessor.is_flop():
                self.deal_turn()
                return self.step(end_hand_stop)
            elif self.accessor.is_preflop():
                self.deal_flop()
                return self.step(end_hand_stop)
            else:
                # if settings.DEBUG:
                #     import ipdb; ipdb.set_trace()
                raise Exception('Reached impossible game state for: '\
                               f'{self.accessor.next_to_act()}')

        else:
            preset_action = self.preset_player_action(next_to_act)
            if preset_action:
                self.player_dispatch(preset_action, player_id=next_to_act.id)
                return [
                    (next_to_act, preset_action, {}),
                    *self.step(end_hand_stop)
                ]
            return []

    def setup_hand(self, mocked_blinds=None, mocked_deck_str=None):
        '''
        beginning of hand non-side-effect events:
            prepare_hand
                BUY / UPDATE_STACK
                SIT_OUT / LEAVE_SEAT
                SET_TIMEBANK
                SET_BLIND_POS (special case--lock btn when only 1 player)
                SIT_IN / SIT_OUT (given blinds)
                RESET
            sit_in_pending_and_move_blinds
                OWE_SB / OWE_BB
                SIT_IN (special case--new round)
                ADD_ORBIT_SITTING_OUT / LEAVE_SEAT
                SET_BLIND_POS
            shuffle_and_start_new_hand
                SHUFFLE
                -> NEW_HAND (side-effect; snapshots state) <-
            post_and_deal
                ANTE / POST / POST_DEAD
                DEAL

        note that mocked_blinds and mocked_deck_str can only be used in
            replayers or in testing
        '''
        should_start = self.prepare_hand()
        if should_start:
            self.internal_dispatch(
                self.sit_in_pending_and_move_blinds(mocked_blinds)
            )
            self.internal_dispatch(
                self.shuffle_and_start_new_hand(mocked_deck_str)
            )
            self.internal_dispatch(self.post_and_deal())
            self.step()

    def shuffle_and_start_new_hand(self, mocked_deck_str=None):
        if mocked_deck_str:
            self.assert_testing_or_mock()
            shuffle_kwargs = {'deck_str': mocked_deck_str,}
        else:
            shuffle_kwargs = {}
        return [
            (self.accessor.table, Event.SHUFFLE, shuffle_kwargs),
            (SIDE_EFFECT_SUBJ, Event.NEW_HAND, {}),
        ]

    def assert_testing_or_mock(self):
        assert self.table.is_mock or settings.IS_TESTING,\
                'this method should be used for replaying or testing only'

    def prepare_hand(self):
        self.internal_dispatch(self.rebuy_checks())
        self.internal_dispatch(self.rebuy_updates())

        active_player_wagers = sum(
            p.wagers for p in self.accessor.players_who_can_play()
            if p.last_action != Event.SIT_IN
        )
        if active_player_wagers != 0:
            # if settings.DEBUG:
            #     import ipdb; ipdb.set_trace()
            raise Exception('Tried setup_hand while there is dirty '\
                            'state from a previous hand.')

        self.internal_dispatch(self.queued_sitouts_and_boot_empty_stacks())

        # if btn is locked is false, we need to lock it, otherwise
        #   we're done; can't start a game
        if (not self.accessor.enough_players_to_play()
                and (self.accessor.btn_is_locked()
                     or self.accessor.nobody_can_play())
                and not len(self.accessor.players_with_pending_actions())):
            return False

        self.internal_dispatch(self.add_time_to_timebanks())

        if not self.sitting_updates_and_enough_players_check():
            return False

        self.internal_dispatch(self.reset_for_new_hand())

        return True

    def sitting_updates_and_enough_players_check(self):
        if not self.check_enough_players():
            return False

        # if it's a new round, move_blinds resets sitting in/out
        #   otherwise, we do it here.
        if not self.accessor.is_new_round():
            self.internal_dispatch(self.set_sitting_given_blinds())

        if not self.check_enough_players():
            return False

        return True

    def check_enough_players(self):
        if not self.accessor.enough_players_to_play():
            msg = "Not enough players to start a new hand."
            self.internal_dispatch(self.lock_btn_to_active_player())
            self.internal_dispatch(self.all_pending_sitting_actions())
            clears = self.table_and_player_stack_and_action_clears()
            self.internal_dispatch(clears)
            self.internal_dispatch([self._dealer_msg_event(msg)])
            return False

        return True

    def post_and_deal(self):
        return self.post_blinds() + self.deal_starting_hands()

    def deal_flop(self):
        events = self.reset_for_new_street()
        events += self.deal_to_board(3)
        self.internal_dispatch(events)
        flop_str = ', '.join(c.pretty() for c in self.table.board)
        msg = f'FLOP: {flop_str}'
        self.internal_dispatch([self._dealer_msg_event(msg)])

    def deal_turn(self):
        table = self.table
        events = self.reset_for_new_street()
        events += self.deal_to_board(1)
        self.internal_dispatch(events)
        flop_str = ', '.join(c.pretty() for c in table.board[:3])
        turn_str = table.board[3].pretty()
        msg = f'TURN: {flop_str}, [{turn_str}]'
        self.internal_dispatch([self._dealer_msg_event(msg)])

    def deal_river(self):
        table = self.table
        events = self.reset_for_new_street()
        events += self.deal_to_board(1)
        self.internal_dispatch(events)
        flop_and_turn = ', '.join(c.pretty() for c in table.board[:4])
        river_str = table.board[4].pretty()
        msg = f'RIVER: {flop_and_turn}, [{river_str}]'
        self.internal_dispatch([self._dealer_msg_event(msg)])

    def end_hand(self):
        self.internal_dispatch(self.return_uncalled_bets())

        # triggers frontend chips-move-in animation
        showdown_events = [
            (SIDE_EFFECT_SUBJ, Event.NEW_STREET, {})
        ] + self.wins_and_losses()

        # There is now an edge case where this is not true:
        #   only bb is posted, and folds around to the bb.
        # TODO: consider putting this check back in with an edge case
        #   conditional
        # win_events = {event for _subj, event, _args in showdown_events}
        # if Event.WIN not in win_events:
        #     self.dump_for_test()
        #     if settings.DEBUG:
        #         import ipdb; ipdb.set_trace()
        #     raise Exception('WIN event was not in showdown events'\
        #                                             ' at end_hand')

        winsum = sum(
            arg['amt']
            for _, e, arg in showdown_events
            if e == Event.WIN
        )
        if winsum != self.accessor.current_pot():
            self.dump_for_test()
            # if settings.DEBUG:
            #     import ipdb; ipdb.set_trace()
            raise Exception('WIN amounts do not add up to final pot '
                            'size at end_hand')

        showdown_events += [(SIDE_EFFECT_SUBJ, Event.SHOWDOWN_COMPLETE, {})]
        self.internal_dispatch(showdown_events)

        status_clears = self.player_stack_and_action_clears()
        self.internal_dispatch(status_clears)

        # sit in players who had to wait another hand
        # self.internal_dispatch([
        #     (player, Event.SIT_IN, {'immediate': True})
        #     for player in self.accessor.seated_players()
        #     if player.playing_state == PlayingState.SIT_IN_PENDING
        # ])
        self.internal_dispatch(self.final_end_hand_events())

    def final_end_hand_events(self):
        return [
            *self.rebuy_notifications(),
            *(
                (plyr, Event.END_HAND, {})
                for plyr in self.accessor.active_players()
            ),
            (self.table, Event.END_HAND, {}),
        ]

    def preset_player_action(self, next_to_act):
        if next_to_act.playing_state == PlayingState.LEAVE_SEAT_PENDING:
            return 'FOLD'

        avail_acts = self.accessor.available_actions(next_to_act)
        assert sum((
            next_to_act.preset_checkfold,
            next_to_act.preset_check,
            bool(next_to_act.preset_call),
        )) < 2, 'a maximum of one preset action should ever be set at a time'

        if next_to_act.preset_checkfold:
            if Action.CHECK in avail_acts:
                return 'CHECK'

            elif Action.FOLD in avail_acts:
                return 'FOLD'

        elif next_to_act.preset_check and Action.CHECK in avail_acts:
            return 'CHECK'

        elif next_to_act.preset_call and \
             next_to_act.preset_call  == self.accessor.call_amt(next_to_act):
            return 'CALL'

        return None

    def reset_for_new_hand(self) -> EventList:
        assert self.accessor.enough_players_to_play(), \
                    "Not enough players to start hand."

        events = self.table_and_player_stack_and_action_clears()
        events.append(self._dealer_msg_event(NEW_HAND_STR))

        return events

    def add_time_to_timebanks(self) -> EventList:
        events = []
        table = self.table
        if table.hand_number % 10 == 0:
            for p in self.accessor.active_players():
                if p.timebank_remaining < table.max_timebank:
                    inc = table.seconds_per_action_increment
                    n_seconds = min(
                            table.max_timebank,
                            p.timebank_remaining + inc)
                    events.append(
                        (p, Event.SET_TIMEBANK, {'set_to': n_seconds})
                    )
        return events

    def reset_sit_in_pending_players(self,
                                     next_btn_idx,
                                     next_bb_idx) -> EventList:
        must_wait = self.accessor.must_wait_to_sit_in_players(
            next_btn_idx,
            next_bb_idx
        )
        events = []
        for plyr in self.accessor.seated_players():
            if plyr in must_wait:
                events.append((SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                    'player': plyr,
                    'notification_type': 'wait_to_sit_in',
                    'msg': 'Players cannot join the game between the btn '\
                           'and the bb. You will have to wait another '\
                           'hand to play.'
                }))
            elif plyr.playing_state == PlayingState.SIT_IN_PENDING:
                events.append((plyr, Event.SIT_IN, {'immediate': True}))
                events.append((plyr, Event.RESET, {}))

        return events

    def player_stack_and_action_clears(self) -> EventList:
        # when players are sat in, we handle their resets then
        return [
            (plyr, Event.RESET, {})
            for plyr in self.accessor.active_players()
            if plyr.playing_state != PlayingState.SIT_IN_PENDING
        ]

    def table_and_player_stack_and_action_clears(self) -> EventList:
        # table NEW_HAND event must always come after all resets, or the
        #   HHLog will be corrupt
        return [
            *self.player_stack_and_action_clears(),
             (self.table, Event.RESET, {})
        ]

    def all_pending_sitting_actions(self):
        events = []
        for plyr in self.accessor.seated_players():
            if plyr.playing_state == PlayingState.SIT_OUT_PENDING:
                events.append((plyr, Event.SIT_OUT, {'immediate': True}))
            elif plyr.playing_state == PlayingState.SIT_IN_PENDING:
                events.append((plyr, Event.SIT_IN, {'immediate': True}))
            elif plyr.playing_state == PlayingState.LEAVE_SEAT_PENDING:
                events += self.player_leave_table(plyr)
        return events

    def rebuy_notifications(self):
        # for player in self.accessor.active_players():
        #     if player.stack < self.table.min_buyin and not player.auto_rebuy:
        #         return [(SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
        #             'player': player,
        #             'notification_type': 'rebuy_notification',
        #             'msg': 'Note: you are close to running out of '
        #                    'chips and have auto-rebuy disabled!'
        #         })]
        return []

    def rebuy_checks(self):
        events = []
        for player in self.accessor.players:
            if player.pending_rebuy:
                #import ipdb; ipdb.set_trace()
                is_legal_buyin = self.accessor.is_legal_buyin(
                    player,
                    player.pending_rebuy,
                    include_pending_rebuy=False
                )
                if not is_legal_buyin:
                    amt_dict = {'amt': -player.pending_rebuy}
                    events.append((player, Event.BUY, amt_dict))
                    events.append((SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                        'player': player,
                        'notification_type': 'failed_rebuy',
                        'msg': f'Invalid buyin amount: '\
                                f'{player.pending_rebuy}'}))

            elif player.auto_rebuy and player.auto_rebuy > player.stack:
                amt_adjusted = player.auto_rebuy - player.stack

                if self.accessor.is_legal_buyin(player, amt_adjusted):
                    events.append((player, Event.BUY, {'amt': amt_adjusted}))

        return events

    def rebuy_updates(self):
        events = []
        for p in self.accessor.players:
            events += self.rebuy_updates_for_player(p)

        return events

    def rebuy_updates_for_player(self, player):
        amt = player.pending_rebuy or 0

        if amt == 0:
            return []

        elif self.accessor.player_has_balance(player, amt):
            msg = f'{player.username} added {int(amt)} chips.'
            return [
                (player, Event.UPDATE_STACK, {}),
                (self._dealer_msg_event(msg)),
                (SIDE_EFFECT_SUBJ, Event.CREATE_TRANSFER, {
                    'src': player.user,
                    'dst': self.table,
                    'amt': amt,
                    'notes': fmt_eventline(subj=player.username,
                                           event=Event.BUY,
                                           args={'amt': amt}),
                }),
            ]

        else:
            return [
                (SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                    'player': player,
                    'notification_type': 'failed_rebuy',
                    'msg': f'Buyin for {amt} failed; insufficient funds.',
                }),
                (player, Event.BUY, {'amt': -player.pending_rebuy})
            ]

    def reset_for_new_street(self):
        chip_returns = self.return_uncalled_bets()

        players = self.accessor.active_players()

        new_street_side_effect = [(SIDE_EFFECT_SUBJ, Event.NEW_STREET, {})]
        new_street_events = [
            (p, Event.NEW_STREET, {})
            for p in players
            if p.last_action is not None or p.uncollected_bets
        ]

        return chip_returns + new_street_side_effect + new_street_events

    def return_uncalled_bets(self):
        # import ipdb; ipdb.set_trace()
        seated = self.accessor.seated_players()

        largest_wager = max(seated, key=lambda plyr: plyr.wagers).wagers
        largest_wager_plyrs = [
            plyr for plyr in seated
            if plyr.wagers == largest_wager
        ]

        if len(largest_wager_plyrs) == 1:
            largest_wager_plyr = largest_wager_plyrs[0]
            plyrs_with_less = [
                plyr for plyr in seated
                if plyr != largest_wager_plyr
            ]
            next_largest_wager = max(plyr.wagers for plyr in plyrs_with_less)

            diff = largest_wager - next_largest_wager

            return [(largest_wager_plyr, Event.RETURN_CHIPS, {'amt': diff})]

        return []

    def sit_in_pending_and_move_blinds(self, mocked_blinds=None):
        table = self.table

        if mocked_blinds:
            self.assert_testing_or_mock()
            positions = mocked_blinds
            events = []
        elif (self.accessor.is_first_hand()
                or self.accessor.is_effectively_new_game_edgecase()):
            btn_idx = self.accessor.btn_idx_for_new_hand()

            positions = self.positions_from_locked_btn(btn_idx)
            events = [
                *self.new_hand_blinds_owed(),
                *self.new_round_sitting_events(),
            ]

        elif self.accessor.btn_is_locked():
            positions = self.positions_from_locked_btn(table.btn_idx)
            events = [
                *self.new_hand_blinds_owed(),
                *self.new_round_sitting_events()
            ]

        else:
            events, positions = self.standard_blind_rotation(table.sb_idx,
                                                             table.bb_idx)

        return [
            *events,
            *self.reset_sit_in_pending_players(
                positions['btn_pos'],
                positions['bb_pos']
            ),
            (table, Event.SET_BLIND_POS, positions),
        ]

    def new_round_sitting_events(self):
        output = []
        for player in self.accessor.seated_players():
            if (self.accessor.can_play(player)
                    and player.playing_state != PlayingState.SITTING_IN):
                output += [
                    (player, Event.SIT_IN, {'immediate': True}),
                    (player, Event.RESET, {}),
                ]
        return output

    def standard_blind_rotation(self, curr_sb_idx, curr_bb_idx):
        acc = self.accessor
        events = []

        next_bb, skipped_bb_positions = acc.next_bb_location_info(curr_bb_idx)

        events += self.bb_owers_from_positions(skipped_bb_positions)
        events += self.orbit_bumps_for_skipped_positions(skipped_bb_positions)

        next_sb, skipped_sb_positions = acc.next_sb_location_info(curr_sb_idx,
                                                                  next_bb)
        events += self.sb_owers_from_positions(skipped_sb_positions,
                                               skipped_bb_positions)

        # next_sb is overwritten in the hu case
        next_btn, next_sb = acc.btn_sb_locations(next_sb,
                                                    next_bb,
                                                    curr_bb_idx)

        return events, {
            'btn_pos': next_btn,
            'sb_pos': next_sb,
            'bb_pos': next_bb
        }

    def positions_from_locked_btn(self, btn_idx):
        actives = self.accessor.players_who_can_play()
        if len(actives) == 1:
            # if settings.DEBUG:
            # import ipdb; ipdb.set_trace()
            raise Exception(
                'Impossible Gamestate: positions_from_locked_btn '\
                'got active_players=1'
            )

        actives = self.accessor.players_who_can_play()

        assert len([p for p in actives if p.position == btn_idx]) == 1, \
                'Sanity check fail: no player sitting at the locked '\
                'button position. Hint: this could happen if '\
                'lock_btn_to_active_player() is called, then that '\
                'player stands, and there is some way a game starts '\
                'without a player sitting in and having the same '\
                'method called for that player: is there another way '\
                'a game might start?'

        if len(actives) == 2:
            other_position = [
                p.position for p in actives
                if p.position != btn_idx
            ].pop()

            return {
                'btn_pos': btn_idx,
                'sb_pos': btn_idx,
                'bb_pos': other_position
            }

        else:
            btn_player = [p for p in actives if p.position == btn_idx].pop()
            actives = list(rotated(actives, actives.index(btn_player)))

            return {
                'btn_pos': btn_idx,
                'sb_pos': actives[1].position,
                'bb_pos': actives[2].position
            }

    def new_hand_blinds_owed(self):
        players = self.accessor.seated_players()

        events = [
            (p, Event.OWE_SB, {'owes': False})
            for p in players
            if p.owes_sb
        ]

        actives = [p for p in players if self.accessor.can_play(p)]
        events += [
            (p, Event.OWE_BB, {'owes': False})
            for p in actives
            if p.owes_bb
        ]

        inactives = [p for p in players if not self.accessor.can_play(p)]
        events += [
            (p, Event.OWE_BB, {'owes': True})
            for p in inactives
            if not p.owes_bb
        ]

        return events

    def orbit_bumps_for_skipped_positions(self, skipped_positions):
        events = []
        if self.accessor.table.is_tutorial:
            return []
        for pos in skipped_positions:
            plyr = self.accessor.players_at_position(pos,
                                                     include_unseated=False)
            if plyr is not None:
                if self.accessor.should_bump_for_orbits_out(plyr):
                    events.append(self._dealer_msg_event(
                        f'{plyr.username} was bumped from the table '
                         'for sitting out too long'
                    ))
                    events += self.player_leave_table(plyr)
                else:
                    events.append((plyr, Event.ADD_ORBIT_SITTING_OUT, {}))
        return events

    def bb_owers_from_positions(self, skipped_positions):
        return [
            (plyr, Event.OWE_BB, {'owes': True})
            for pos in skipped_positions
                for plyr in self.accessor.players_at_position(pos,
                                                        include_unseated=True)
            if not plyr.owes_bb
        ]

    def sb_owers_from_positions(self, skipped_positions,
                                      skipped_bb_positions):
        return [
            (plyr, Event.OWE_SB, {'owes': True})
            for pos in skipped_positions
            if pos not in skipped_bb_positions
                for plyr in self.accessor.players_at_position(
                        pos,
                        include_unseated=True
                    )
                if not (plyr.owes_bb or plyr.owes_sb)
        ]

    def post_blinds(self):
        events = []
        table = self.table

        # btn_player = self.accessor.players_at_position(table.btn_idx,
        #                                                active_only=True)
        # msg = f'{btn_player.username} is the BTN'
        # events.append(self._dealer_msg_event(msg))

        sb_player = self.accessor.players_at_position(table.sb_idx,
                                                      active_only=True)
        bb_player = self.accessor.players_at_position(table.bb_idx,
                                                      active_only=True)
        assert bb_player is not None, "move_blinds is probably broken."

        active_players = self.accessor.active_players(table.sb_idx or 0)

        for player in active_players:
            player_stack = player.stack

            if table.ante:
                # TODO: player stacks have to be updated after ante
                #   because they might be all-in
                raise NotImplementedError()
                ante_amt = min(player_stack, table.ante)
                events.append((player, Event.ANTE, {'amt': ante_amt}))

            if player is bb_player:
                msg = f'{player.username} posted {table.bb} for BB'
                events.append(self._dealer_msg_event(msg))
                amt_dict = {'amt': min(player_stack, table.bb)}
                events.append((bb_player, Event.POST, amt_dict))
                events += self.forgive_debt(player, bb=True)

            else:
                if player.owes_bb:
                    blind_amt = min(player_stack, table.bb)
                    player_stack -= blind_amt
                    msg = f'{player.username} posted {table.bb} for BB '\
                           '(out of position)'
                    events.append(self._dealer_msg_event(msg))
                    events.append((player, Event.POST, {'amt': blind_amt}))
                    events += self.forgive_debt(player, bb=True)

                if player is sb_player:
                    msg = f'{player.username} posted {table.sb} for SB'
                    events.append(self._dealer_msg_event(msg))
                    amt_dict = {'amt': min(player_stack, table.sb)}
                    events.append((sb_player, Event.POST, amt_dict))
                    events += self.forgive_debt(player, bb=False)
                elif player.owes_sb:
                    msg = f'{player.username} posted {table.sb} for a dead SB'
                    events.append(self._dealer_msg_event(msg))
                    amt_dict = {'amt': min(player_stack, table.sb)}
                    events.append((player, Event.POST_DEAD, amt_dict))
                    events += self.forgive_debt(player, bb=False)

        return events

    def forgive_debt(self, player, bb=True):
        if player.owes_bb and bb:
            return [(player, Event.OWE_BB, {'owes': False})]
        elif player.owes_sb and not bb:
            return [(player, Event.OWE_SB, {'owes': False})]

        return []

    def lock_btn_to_active_player(self):
        who_can_play = self.accessor.players_who_can_play()
        if len(who_can_play) == 1:
            btn_pos = who_can_play.pop().position
            return [(self.table, Event.SET_BLIND_POS, {
                'btn_pos': btn_pos,
                'sb_pos': None,
                'bb_pos': None
            })]

        elif len(who_can_play) == 0:
            return []

        else:
            raise Exception('lock_btn_to_active_player() was called '\
                            'when there were enough players to start a game')

    def queued_sitouts_and_boot_empty_stacks(self):
        events = []
        players = self.accessor.active_players()

        for player in players:
            if player.playing_state == PlayingState.SIT_OUT_PENDING:
                # print('acting on queued sit_out for player', player)
                events.append((player, Event.RESET, {}))
                events.append((player, Event.SIT_OUT, {'immediate': True}))
            elif player.playing_state == PlayingState.LEAVE_SEAT_PENDING:
                events.append((player, Event.RESET, {}))
                events += self.player_leave_table(player)
            elif player.stack == 0:
                msg = f'{player.username} needs more chips to play'
                events.append(self._dealer_msg_event(msg))
                events.append((player, Event.RESET, {}))
                events.append((player, Event.SIT_OUT, {'immediate': True}))

        return events

    def set_sitting_given_blinds(self, last_bb_checked=None):
        # always call with last_bb_checked should=None--it is used for
        #   recursive calls only

        assert not self.accessor.is_first_hand(), \
            'on first hand, all playing_states should reset and blinds '\
            'should be randomly assigned instead of calling this function.'

        if last_bb_checked is None:
            bb_pos = (self.table.bb_idx + 1) \
                        % self.table.num_seats
        else:
            bb_pos = (last_bb_checked + 1) % self.table.num_seats
            if bb_pos == self.table.bb_idx:
                # base case 3: wrapped around the table and sat everyone out
                return []

        player = self.accessor.players_at_position(bb_pos)

        if not player:
            return self.set_sitting_given_blinds(bb_pos)

        if player.is_sitting_out():
            if player.playing_state == PlayingState.SIT_IN_AT_BLINDS_PENDING:
                # base case 1: player is sitting out but wants to play now
                return [
                    (player, Event.RESET, {}),
                    (player, Event.SIT_IN, {'immediate': True}),
                ]
            else:
                return self.set_sitting_given_blinds(bb_pos)
        else:
            if player.sit_out_at_blinds:
                # print('sitting out at blinds:', player)
                return [
                    (player, Event.RESET, {}),
                    (player, Event.SIT_OUT, {'immediate': True}),
                    *self.set_sitting_given_blinds(bb_pos),
                ]
            else:
                # base case 2: player is sitting in & playing
                return []

    def deal_starting_hands(self):
        table = self.table
        events = []
        first_to_act = self.accessor.first_to_act_pos()
        n_holecards = NUM_HOLECARDS[self.table.table_type]
        players = self.accessor.active_players(rotate=first_to_act)
        n_cards_dealt = len(players) * n_holecards
        cards_to_deal = table.cards_to_deal(n_cards_dealt)
        # reverse because we need to pop them in the order they're provided
        cards_to_deal.reverse()
        events = [
            (player, Event.DEAL, {'card': cards_to_deal.pop()})
            for _ in range(n_holecards)
                for player in players
        ]
        # print('deals')
        # print('\n'.join(f'{event[0]} {event[2]["card"]}' for event in events))
        for player in players:
            msg = f'{player.username} ({player.stack_available}) was '\
                   'dealt two cards'
            events.append(self._dealer_msg_event(msg))
        events.append((table, Event.POP_CARDS, {'n_cards': n_cards_dealt}))
        # TODO: delay countdown by # deals * 0.5s
        return events

    def deal_to_board(self, n_cards):
        cards_to_deal = self.table.cards_to_deal(n_cards)
        events = [
            (self.table, Event.DEAL, {'card': card})
            for card in cards_to_deal
        ]
        events.append((self.table,
                       Event.POP_CARDS,
                       {'n_cards': n_cards}))
        return events

    def showdown_win_events(self, showdown_winnings_for_pot):
        return [
            (plyr, Event.WIN, win_kwargs)
            for plyr, win_kwargs in showdown_winnings_for_pot.items()
        ]

    def reveal_hands(self, winning_players, show_msg=True):
        events = []

        players = self.accessor.players_in_acting_order()
        raisers = [p.position for p in players
                   if p.last_action in (Event.BET, Event.RAISE_TO)]
        rotate = raisers[-1] if raisers else None

        showdown_players = self.accessor.showdown_players(rotate)
        # this player always reveal
        players_and_events = [(showdown_players[0], 'reveal')]

        # this offset is to keep the last reveal player index
        last_reveal_ofs = 0
        for index in range(len(showdown_players) - 1):
            player1 = showdown_players[index + 1]
            player2 = players_and_events[-1 - last_reveal_ofs][0]
            # if win a sidepot or has better hand than the last reveal, reveal
            is_winner = player1 in winning_players
            if is_winner or self.accessor.has_gte_hand(player1, player2):
                players_and_events.append((player1, 'reveal'))
                last_reveal_ofs = 0
            else:
                # else muck, and keep the last reveal index
                players_and_events.append((player1, 'muck'))
                last_reveal_ofs += 1

        for plyr, event in players_and_events:
            if event == 'reveal':
                cards_str = ', '.join(c.pretty() for c in plyr.cards)
                hand_name = cards_str
                if show_msg:
                    hand = self.accessor.player_hand(plyr)
                    hand_name = rankings.hand_to_name(hand)
                events.append((plyr, Event.REVEAL_HAND, {
                    'player_id': plyr.id,
                    'cards': plyr.cards,
                    'description': hand_name
                }))
                if show_msg:
                    msg = f'{plyr.username} has {cards_str} ({hand_name})'
                    events.append(self._dealer_msg_event(msg))
            else:
                events.append((plyr, Event.MUCK, {'player_id': plyr.id}))
                msg = f'{plyr.username} mucked'
                events.append(self._dealer_msg_event(msg))

        return events

    def wins_and_losses(self):
        all_pots = self.accessor.sidepot_summary()
        players = self.accessor.showdown_players()

        if len(players) == 1:
            # this is the case where everyone folded
            return self.no_showdown_wins_and_losses(players, all_pots)
        else:
            return self.showdown_wins_and_losses(players, all_pots)

    def no_showdown_wins_and_losses(self, players, all_pots):
        pot_name = lambda i: f'sidepot {i}' if i else 'the main pot'

        winner = players.pop()
        output = []
        delay = ANIMATION_DELAYS[Event.WIN]
        cards_msg = ""

        if winner.user and not winner.user.muck_after_winning:
            output = self.reveal_hands([winner], show_msg=False)
            event_kwargs = output[0][2]
            cards_msg = f" with {event_kwargs['description']}"
            delay += ANIMATION_DELAYS[Event.REVEAL_HAND]

        for i, (amt, _) in enumerate(all_pots):
            output.append(
                (winner, Event.WIN, {
                    'amt': amt,
                    'pot_id': i,
                    'showdown': False,
                })
            )
            output.append(self._dealer_msg_event(
                f'{winner.username} won {amt} from {pot_name(i)}{cards_msg}',
                speaker='winner_info'
            ))
        return output + [
            (self.table, Event.DELAY_COUNTDOWN, {
                'n_seconds': delay
            })
        ]

    def showdown_wins_and_losses(self, players, all_pots):
        pot_name = lambda i: f'sidepot {i}' if i else 'the main pot'

        showdown_winnings = [
            self.accessor.showdown_winnings_for_pot(pot_summary, i)
            for i, pot_summary in enumerate(all_pots)
        ]

        showdown_win_events_nested = [
            self.showdown_win_events(showdown_winnings_for_pot)
            for showdown_winnings_for_pot in showdown_winnings
        ]
        # flattens the list of lists of win events
        showdown_win_events = [
            win_event
            for win_events in showdown_win_events_nested
                for win_event in win_events
        ]

        winning_players = {p for p, _, _ in showdown_win_events}
        reveal_events = self.reveal_hands(winning_players)

        reveals = {
            plyr: args['description']
            for plyr, event, args in reveal_events
            if event == Event.REVEAL_HAND
        }

        win_summary_events = []
        for i, summary in enumerate(showdown_winnings):
            plyrs = summary.keys()
            a_winner = next(iter(plyrs))
            amt = summary[a_winner]['amt']
            if len(plyrs) > 1:
                for plyr in plyrs:
                    reveal_plyr = reveals[plyr]
                    reveal_winner = reveals[a_winner]
                    assert reveal_plyr == reveal_winner, \
                        'sanity check fail: split pot with different hands'

                plyrs_str = ', '.join(plyr.username for plyr in plyrs)
                msg = f'{plyrs_str} split {pot_name(i)} with '\
                      f'{reveals[a_winner]} for {amt // len(players)} '\
                      'chips each'

            else:
                msg = f'{a_winner.username} won {pot_name(i)} with '\
                      f'{reveals[a_winner]} for {amt} chips'

            win_summary_events.append(
                self._dealer_msg_event(msg, speaker='winner_info')
            )

        num_reveals = len([e for e in reveal_events
                           if e[1] == Event.REVEAL_HAND])
        reveal_delays = ANIMATION_DELAYS[Event.REVEAL_HAND] * num_reveals
        win_delays = ANIMATION_DELAYS[Event.WIN] * len(showdown_win_events)
        secs = {'n_seconds': win_delays + reveal_delays}
        delay_event = [(self.table, Event.DELAY_COUNTDOWN, secs)]

        return reveal_events + showdown_win_events \
             + delay_event + win_summary_events

    def _dealer_msg_event(self, msg, speaker=None):
        return SIDE_EFFECT_SUBJ, Event.CHAT, {
            'speaker': speaker or 'Dealer',
            'msg': msg,
        }


class BountyController(HoldemController):
    expected_tabletype = NL_BOUNTY

    def final_end_hand_events(self):
        if self.accessor.table.bounty_flag:
            return [
                (self.table, Event.SET_BOUNTY_FLAG, {'set_to': False}),
                *super().final_end_hand_events()
            ]
        return super().final_end_hand_events()

    def end_hand(self):
        if not self.forced_flip():
            super().end_hand()

    def bounty_showdown_sequence(self, winner):
        potsize = self.accessor.current_pot()
        all_pots = self.accessor.sidepot_summary()
        winner_msg = f'{winner.username} won {potsize} without '\
                     f'showdown and had {winner.cards}. Bounty '\
                     f'hand! Everyone else is now forced to flip '\
                     f'for {winner.stack + potsize}!'

        return [
            (SIDE_EFFECT_SUBJ, Event.NEW_STREET, {}),
            (winner, Event.BOUNTY_WIN, {'player_id': winner.id,
                                        'cards': winner.cards}),
            *self.no_showdown_wins_and_losses([winner], all_pots),
            (self._dealer_msg_event(winner_msg, speaker='winner_info')),
            *self.table_and_player_stack_and_action_clears(),
            (self.table, Event.SHUFFLE, {}),
            (self.table, Event.SET_BOUNTY_FLAG, {'set_to': True}),
        ]

    def bounty_deal(self, winner):
        return [
            *self.deal_starting_hands(),
            (SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                'notification_type': 'bounty',
                'msg': f'{winner.username} won a bounty; you are '
                       f'forced to flip for their stack',
            }),
        ]

    def bounty_call_sequence(self, winner):
        actives = self.accessor.active_players()
        assert min(player.stack for player in actives) > 0, \
                'Sanity check fail: player is at zero chips without '\
                'having gone all-in.'
        return [
            (player, Event.CALL, {
                'amt': self.accessor.bounty_call_amt(player, winner),
                'all_in': True
            })
            for player in actives if player != winner
        ]

    def mocked_forced_flip(self, deck_str=None):
        self.assert_testing_or_mock()
        if self.accessor.there_is_bounty_win():
            winner = self.accessor.showdown_players()[0]
            self.internal_dispatch(self.bounty_showdown_sequence(winner))

            if deck_str:
                self.table.deck_str = deck_str

            self.internal_dispatch(self.bounty_deal(winner))
            self.internal_dispatch(self.bounty_call_sequence(winner))
            return True
        return False

    def forced_flip(self):
        if self.accessor.there_is_bounty_win():
            winner = self.accessor.showdown_players()[0]
            self.internal_dispatch(self.bounty_showdown_sequence(winner))
            self.internal_dispatch(self.bounty_deal(winner))
            self.internal_dispatch(self.bounty_call_sequence(winner))
            return True
        return False


class OmahaController(HoldemController):
    expected_tabletype = PL_OMAHA
    @autocast
    def bet(self, player_id: str, amt: Decimal, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        pot_bet = self.accessor.pot_raise_size()

        if amt > player.stack or amt > pot_bet \
                or (amt < self.table.bb and amt != player.stack):
            raise ValueError('Invalid bet amount')
        all_in = player.stack_available - amt == 0

        return [
            (player, Event.BET, {'amt': amt, 'all_in': all_in}),
            *self.timing_events(player, Action.RAISE_TO)
        ]

    @autocast
    def raise_to(self, player_id: str, amt: Decimal, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        min_amt = self.accessor.min_bet_amt()
        max_amt = self.accessor.pot_raise_size()

        if amt > player.stack_available or (amt < min_amt \
                and amt != player.stack_available) or amt > max_amt:
            raise ValueError('Invalid raise amount')
        all_in = player.stack_available - amt == 0

        return [
            (player, Event.RAISE_TO, {'amt': amt, 'all_in': all_in}),
            *self.timing_events(player, Action.RAISE_TO)
        ]


class FreezeoutController(GameController):
    def __init__(self, table, players=None, log=None, subscribers=None,
                 verbose=False, broadcast=True):
        super().__init__(
            table, players=players, log=log, subscribers=subscribers,
            verbose=verbose, broadcast=broadcast
        )
        tourney_subscribers = subscribers if subscribers is not None else [
            TournamentResultsSubscriber(self.accessor),
            TournamentChatSubscriber(self.accessor),
            NotificationSubscriber(self.accessor),
            AnimationSubscriber(self.accessor),
            BankerSubscriber(self.accessor),
            LogSubscriber(self.log),
            BadgeSubscriber(self.accessor, self.log),
            TableStatsSubscriber(self.accessor),
            UserStatsSubscriber(self.accessor),
            LevelSubscriber(self.accessor),
            AnalyticsEventSubscriber(self.accessor),
        ]
        self.subscribers = tourney_subscribers

    def buy(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def sit(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def stand(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def sit_in_at_blinds(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def sit_out_at_blinds(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def join_table(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def set_auto_rebuy(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    def leave_seat(self, *args, **kwargs):
        raise InvalidAction("Not possible in a freezeout")

    @autocast
    def bet(self, player_id: str, amt: Decimal, **kwargs):
        super_events = super().bet(player_id, amt, **kwargs)
        sit_back_event = self._sit_back_or_invalid(player_id)
        return [*sit_back_event, *super_events]

    @autocast
    def raise_to(self, player_id: str, amt: Decimal, **kwargs):
        super_events = super().raise_to(player_id, amt, **kwargs)
        sit_back_event = self._sit_back_or_invalid(player_id)
        return [*sit_back_event, *super_events]

    @autocast
    def check(self, player_id: str, **kwargs):
        super_events = super().check(player_id, **kwargs)
        sit_back_event = self._sit_back_or_invalid(player_id)
        return [*sit_back_event, *super_events]

    @autocast
    def call(self, player_id: str, **kwargs):
        super_events = super().call(player_id, **kwargs)
        sit_back_event = self._sit_back_or_invalid(player_id)
        return [*sit_back_event, *super_events]

    def _sit_back_or_invalid(self, player_id: str, **kwargs):
        player = self.accessor.player_by_player_id(player_id)
        if player.playing_state == PlayingState.TOURNEY_SITTING_OUT:
            return [(player, Event.SIT_IN, {})]
        return []

    @autocast
    def sit_in(self, player_id: str, **kwargs):
        # no need to check for min buyin in freezeout
        player = self.accessor.player_by_player_id(player_id)
        return [(player, Event.SIT_IN, {})]

    def reset_sit_in_pending_players(self, next_btn_idx, next_bb_idx):
        return []

    def rebuy_checks(self):
        return []

    def rebuy_updates(self):
        return []

    def rebuy_notifications(self):
        return []

    def bb_owers_from_positions(self, skipped_positions):
        return []

    def sb_owers_from_positions(self, skipped_positions,
                                      skipped_bb_positions):
        return []

    def preset_player_action(self, next_to_act):
        if next_to_act.playing_state == PlayingState.TOURNEY_SITTING_OUT:
            if self.accessor.is_acting_first(next_to_act):
                return None
            # print("FOLDING")
            return 'FOLD'
        else:
            return super().preset_player_action(next_to_act)

    def queued_sitouts_and_boot_empty_stacks(self):
        events = []

        for plyr in self.accessor.seated_players():
            if plyr.stack == 0:
                msg = f'{plyr.username} was eliminated.'
                events.append(self._dealer_msg_event(msg))
                events.append((plyr, Event.LEAVE_SEAT, {'immediate': True}))

                players_except_kicked = [
                    seated_plyr
                    for seated_plyr in self.accessor.seated_players()
                    if seated_plyr != plyr
                ]
                for p in players_except_kicked:
                    events.append((SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                        'player': p,
                        'notification_type': 'player_eliminated',
                        'msg': msg
                    }))

        return events

    def sitting_updates_and_enough_players_check(self):
        tournament = self.table.tournament

        if self.accessor.tournament_is_over():
            events = []
            plyrs = self.accessor.seated_players()
            winner = plyrs[0]

            events.append((tournament, Event.FINISH_TOURNAMENT, {
                'winner': winner
            }))
            entrants_count = tournament.entrants.count()
            tourney_prize = entrants_count * tournament.buyin_amt
            events.append((SIDE_EFFECT_SUBJ, Event.CREATE_TRANSFER, {
                'src': tournament,
                'dst': winner.user,
                'amt': tourney_prize,
                'notes': fmt_eventline(subj=winner.user.username,
                                       event=Event.FINISH_TOURNAMENT,
                                       args={'amt': tourney_prize}),
            }))
            # Unfreezing chips for the winner
            events.append((winner, Event.LEAVE_SEAT, {
                'immediate': True
            }))

            msg = f'{winner.username} has won the tournament.'
            events.append(self._dealer_msg_event(msg))

            self.internal_dispatch(events)
            return False

        return True

    def reset_for_new_hand(self):
        events = self.table_and_player_stack_and_action_clears()
        blind_sched_idx = min(
            self.accessor.table.hand_number // HANDS_TO_INCREASE_BLINDS,
            len(BLINDS_SCHEDULE)
        )
        sb, bb = BLINDS_SCHEDULE[blind_sched_idx]

        if sb != self.accessor.table.sb:
            events.append(
                (self.accessor.table, Event.SET_BLINDS, {'sb': sb, 'bb': bb})
            )
            msg = f'Blinds going up to {int(sb)}/{int(bb)}'
            events.append(self._dealer_msg_event(msg))
            for plyr in self.accessor.seated_players():
                events.append((SIDE_EFFECT_SUBJ, Event.NOTIFICATION, {
                    'player': plyr,
                    'notification_type': 'blinds_going_up',
                    'msg': msg
                }))

        events.append(self._dealer_msg_event(NEW_HAND_STR))

        return events

    def orbit_bumps_for_skipped_positions(self, skipped_positions):
        # never bump players from tournament tables
        return []

    def out_of_time_msg(self, player):
        return []


class HoldemFreezeoutController(FreezeoutController, HoldemController):
    pass


class OmahaFreezeoutController(FreezeoutController, OmahaController):
    pass


class BountyFreezeoutController(FreezeoutController, BountyController):
    pass


def controller_type_for_table(table: PokerTable) -> Type[GameController]:
    if table.table_type == NL_HOLDEM and table.tournament is None:
        return HoldemController

    if table.table_type == NL_HOLDEM and table.tournament is not None:
        return HoldemFreezeoutController

    if table.table_type == PL_OMAHA and table.tournament is None:
        return OmahaController

    if table.table_type == PL_OMAHA and table.tournament is not None:
        return OmahaFreezeoutController

    if table.table_type == NL_BOUNTY and table.tournament is None:
        return BountyController

    if table.table_type == NL_BOUNTY and table.tournament is not None:
        return BountyFreezeoutController


def controller_for_table(table: PokerTable,
                         *args, **kwargs) -> GameController:
    return controller_type_for_table(table)(table, *args, **kwargs)


class InvalidAction(ValueError):
    pass


class RejectedAction(InvalidAction):
    pass
