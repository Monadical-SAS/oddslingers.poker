import json

from collections import OrderedDict
from decimal import Decimal
from uuid import uuid4

from django.core.cache import cache
from django.db import transaction

from poker.accessors import accessor_type_for_table
from poker.handhistory import DBLog, fmt_hand
from poker.controllers import controller_for_table
from poker.constants import (
    Event, TABLE_SUBJECT_REPR, PlayingState, PLAYER_API,
    SIDE_EFFECT_SUBJ, NL_BOUNTY, PLAYER_REFRESH_FIELDS, TABLE_REFRESH_FIELDS
)
from poker.models import MockPokerTable, MockPlayer, Player, HandHistory
from poker.megaphone import gamestate_json
from poker.subscribers import LogSubscriber

from oddslingers.utils import DoesNothing, to_json_str


class HandHistoryReplayer:
    def __init__(self, json_log,
                       hand_idx=None,
                       hand_number=None,
                       session_id=None,
                       subscriber_types=None,
                       logging=False):

        if 'release' in json_log.keys():
            self.__release__ = json_log['release']
            # accessed == created timestamp
            self.__accessed__ = json_log['accessed']
            self.__notes__ = json_log['notes']
            try:
                self.__notes__ = json.loads(self.__notes__)
            except (json.decoder.JSONDecodeError, TypeError):
                pass
        else:
            # deprecated log format
            self.__release__ = "none specified"
            self.__accessed__ = "unspecified"
            self.__notes__ = "deprecated log format w/o metadata"

        self.hands = json_log['hands']

        self.subscriber_types = subscriber_types

        self.table = None
        self.players = None
        self.controller = None
        self.logging = logging

        if session_id is not None:
            self.session_id = session_id
        else:
            self.session_id = str(uuid4()).split('-')[0]

        if hand_idx is None and hand_number is None:
            hand_idx = -1
        if hand_number is not None:
            assert hand_idx is None
            self.skip_to_hand_number(hand_number)

        if hand_idx is not None:
            assert hand_number is None
            self.skip_to_hand_idx(hand_idx)

    @property
    def accessor(self):
        return self.controller.accessor

    def skip_to_hand_idx(self, hand_idx):
        self.hand_idx = hand_idx
        self.reset_to_hand(self.current_hand())

    def skip_to_hand_number(self, hand_number):
        for i, hand in enumerate(self.hands):
            if hand['table']['hand_number'] == hand_number:
                self.hand_idx = i
                self.reset_to_hand(self.current_hand())
                return

        raise ValueError(f'Hand number {hand_number} did not appear in hand history')

    def reset_to_hand(self, hand_history):
        if isinstance(hand_history, int):
            msg = 'Got int instead of hand_history. Did you mean '\
                  'skip_to_hand_idx() or skip_to_hand_number()?'
            raise ValueError(msg)
        self.delete()

        table_dict = hand_history['table'].copy()
        table_name = f'Replayer-{table_dict.pop("name")}-{self.session_id}'
        table_dict['is_mock'] = True
        table_dict.pop('id')
        player_dicts = hand_history['players']

        with transaction.atomic():
            self.table, _ = MockPokerTable.objects.update_or_create(
                name=table_name,
                defaults=table_dict
            )
            self.players = []

            for player_dict in player_dicts:
                player = self._mock_player_from_dict(player_dict)
                self.players.append(player)

            self.players += self._takeseat_players(hand_history, self.players)

        self.controller = controller_for_table(
                                self.table,
                                self.players,
                                subscribers=[],
                                log=DoesNothing(),
                                verbose=False,
                                broadcast=False)

        self.commit()
        # necessary because strings from json need to be cast to decimal
        self.refresh_from_db()

        if self.subscriber_types:
            self.controller.subscribers = [
                sub(self.accessor)
                for sub in self.subscriber_types
            ]

        if self.logging:
            self.controller.log = DBLog(self.accessor)
            self.controller.subscribers.append(
                LogSubscriber(self.controller.log)
            )

        # need this hack to avoid calling .balance on None
        #   because MockPlayer objects have no user
        def mocked_player_has_balance(player, amt):
            # TODO: get this working; see BadStartingStackTest in test_hands
            return True
            return any([
                evnt for evnt in self.events
                if evnt['event'] == 'CREATE_TRANSFER'
                    and evnt['args']['src']['str'] == player.username
                    and evnt['args']['amt'] == amt
            ]) if self.events else True

        self.accessor.player_has_balance = mocked_player_has_balance


    def _mock_player_from_dict(self, player_dict, seated=True):
        kwargs = {
            k: v for k, v in player_dict.items()
            if k not in ('id', 'user')
        }

        # buyin_amt is here because join_table uses it. take_seat
        #   should never be called directly and doesn't actually have
        #   the buyin_amt param. see self.dispatch_current_action and
        #   controller.join_table for more
        if 'buyin_amt' in kwargs:
            kwargs.pop('buyin_amt')

        playing_state = PlayingState.from_str(kwargs.pop('playing_state'))
        kwargs['playing_state_int'] = playing_state.value

        plyr_name = kwargs.pop('username')
        kwargs['seated'] = seated
        player, _ = MockPlayer.objects.update_or_create(
                                            table_id=self.table.id,
                                            mock_name=plyr_name,
                                            defaults=kwargs)
        player.table = self.table
        player.refresh_from_db(fields=PLAYER_REFRESH_FIELDS)
        return player

    def _takeseat_players(self, hand_history, loaded_players):
        '''
            controller.join_table adds parameters necessary to add a
            new player to the list of accessor players whenever it is
            called

            Without this, trying to replay a take_seat action would
            crash the replayer if the player joined before the most
            recent reset_to serialized list of players
        '''
        if not 'actions' in hand_history:
            return []

        loaded_usernames = [plyr.username for plyr in loaded_players]
        # note: username being here implies it was a join_table
        #   because normally that's not a parameter.
        #   note that the frontend passes in 'USERNAME' in caps
        #   for regular TAKE_SEAT events, which will be correctly
        #   filtered here.
        return [
            self._mock_player_from_dict(action['args'], seated=False)
            for action in hand_history['actions']
            if action['action'].lower() == 'take_seat'
                and 'username' in action['args']
                and action['args'].get('username') not in loaded_usernames
        ]

    def current_hand(self):
        return self.hands[self.hand_idx]

    def skip_to_end_of_hand(self):
        while True:
            try:
                self.step_forward()
            except StopIteration:
                break

    def skip_to_last_hand(self):
        self.hand_idx = len(self.hands) - 1
        self.reset_to_hand(self.current_hand())

    def skip_to_end_of_hh(self):
        self.skip_to_last_hand()
        self.skip_to_end_of_hand()

    def step_forward(self):
        raise NotImplementedError(
                'This should move forward one Event or Action in the HH')

    def step_back(self):
        raise NotImplementedError(
                'This should move back one Event or Action in the HH')

    def next_hand(self):
        self.hand_idx += 1
        try:
            self.reset_to_hand(self.current_hand())
        except IndexError:
            raise StopIteration('Reached the last hand.')

    def prev_hand(self):
        if self.hand_idx == 0:
            raise StopIteration('Already at the beginning of HH')

        self.hand_idx -= 1
        self.reset_to_hand(self.current_hand())

    def refresh_from_db(self):
        self.table.refresh_from_db(fields=TABLE_REFRESH_FIELDS)
        for player in self.players:
            player.refresh_from_db(fields=PLAYER_REFRESH_FIELDS)

    def commit(self):
        if self.controller:
            self.controller.commit(broadcast=False)

    def delete(self):
        if self.players:
            for player in self.players:
                player.delete()
        if self.logging:
            HandHistory.objects.filter(table=self.table).delete()
        if self.table is not None:
            self.table.delete()

    def gamestate_json(self, username):
        if username is None:
            player = None
        elif username == 'all':
            player = username
        else:
            player = self.accessor.player_by_username(username)

        return gamestate_json(self.accessor,
                              player,
                              self.controller.subscribers)

    def details(self):
        od = OrderedDict()
        od['class'] = self.__class__.__name__
        od['session_id'] = self.session_id
        od['# hands'] = len(self.hands)
        od['hand_idx'] = self.hand_idx

        if isinstance(self, ActionReplayer):
            od['# actions'] = len(self.current_hand()['actions'])
            od['action_idx'] = self.action_idx
        elif isinstance(self, EventReplayer):
            od['# events'] = len(self.current_hand()['events'])
            od['event_idx'] = self.event_idx

        if hasattr(self, '__notes__'):
            if isinstance(self.__notes__, dict):
                # e.g. tracebacks will be printed correctly
                od['notes'] = to_json_str(
                    self.__notes__,
                    indent=2,
                    unicode_escape=True,
                ).replace('\n', '\n\t')
            else:
                od['notes'] = str(self.__notes__)

        return od

    @property
    def actions(self):
        return self.current_hand()['actions']

    @property
    def events(self):
        return self.current_hand()['events']

    def describe(self, print_me=True):
        details_strs = (
            f'{key}: {value}'
            for key, value in self.details().items()
        )
        fmtted_details = '\n'.join(details_strs)

        out = f'{fmtted_details}'\
               '\nCURRENT STATE:\n'\
              f'{self.accessor.describe(print_me=False)}'

        if print_me:
            print(out)
        else:
            return out

    def describe_log(self, print_me=True, indent=2, filtered=True):
        log = self.original_log()
        log['hands'] = [
            fmt_hand(hand, filtered=filtered, for_player='all')
            for hand in self.hands
        ]
        out = to_json_str(log, indent=indent, unicode_escape=True)
        if print_me:
            print(out)
        else:
            return out

    def describe_hand(self, print_me=True, indent=2, filtered=True):
        curr_hand = fmt_hand(
            self.current_hand(),
            filtered=filtered,
            for_player='all'
        )
        curr_hand_str = to_json_str(
            curr_hand,
            indent=indent,
            unicode_escape=True
        )
        out = f'current hand:\n{curr_hand_str}\n'\
              f'hand_idx {self.hand_idx} of {len(self.hands)}\n'\
              f"hand_number {self.current_hand()['table']['hand_number']}"\
              f" (ranging {self.hands[0]['table']['hand_number']}"\
              f" to {self.hands[-1]['table']['hand_number']})"

        if print_me:
            print(out)
        else:
            return out

    def original_log(self):
        return {
            'release': getattr(self, '__release__', None),
            'accessed': getattr(self, '__accessed__', None),
            'notes': getattr(self, '__notes__', None),
            'hands': self.hands,
        }

    def debug_filedump(self, filename):
        '''
        For cases where we no longer have access to the json log
        that the replayer was constructed from, this reconstructs it
        and dumps it to file.
        '''
        with open(filename, 'w') as f:
            json.dump(self.original_log(), f, indent=4)

    @classmethod
    def from_table(cls,
                   table,
                   hand_idx=None,
                   hand_number=None,
                   subscriber_types=None,
                   session_id=None,
                   logging=False):
        # print('creating replayer @:/', hand_idx, '/', event_idx, '/',
        #        session_id)
        cache_key = f'{cls.__name__}-log-:{table.id}:{table.modified}'
        json_log = cache.get(cache_key)
        if json_log is None:
            AccessorType = accessor_type_for_table(table)
            log = DBLog(AccessorType(table))
            json_log = log.get_log(player='all')
            cache.set(cache_key, json_log)

        # print('got json_log from db:')
        # print(to_json_str(json_log))
        return cls(
            json_log=json_log,
            hand_idx=hand_idx,
            hand_number=hand_number,
            subscriber_types=subscriber_types,
            session_id=session_id,
            logging=logging
        )

    @classmethod
    def from_file(cls,
                  file,
                  hand_idx=None,
                  hand_number=None,
                  subscriber_types=None,
                  session_id=None,
                  logging=False):
        # print('creating replayer @:/', hand_idx, '/', event_idx, '/',
        #        session_id)
        if isinstance(file, str):
            with open(file) as open_file:
                return cls.from_file(
                    file=open_file,
                    hand_idx=hand_idx,
                    hand_number=hand_number,
                    subscriber_types=subscriber_types,
                    session_id=session_id,
                    logging=logging,
                )

        replayer = cls(
            json_log=json.load(file),
            hand_idx=hand_idx,
            hand_number=hand_number,
            subscriber_types=subscriber_types,
            session_id=session_id,
            logging=logging
        )
        replayer.file = file
        return replayer


class EventReplayer(HandHistoryReplayer):
    def __init__(self, json_log,
                       hand_idx=None,
                       hand_number=None,
                       event_idx=0,
                       subscriber_types=None,
                       session_id=None,
                       logging=False):

        super().__init__(json_log,
                         hand_idx=hand_idx,
                         hand_number=hand_number,
                         subscriber_types=subscriber_types,
                         session_id=session_id,
                         logging=logging)
        self._skip_to_event(event_idx)

    def reset_to_hand(self, hand_history):
        self.event_idx = 0
        super().reset_to_hand(hand_history)
        self.go_to_next_nonskip_event()

    def go_to_next_nonskip_event(self, backwards=False):
        try:
            while self._is_skip_event(self.current_event()):
                if backwards:
                    self.event_idx -= 1
                else:
                    self.event_idx += 1
        except IndexError:
            raise StopIteration('Reached the last Event.')

    def current_event(self):
        return self.current_hand()['events'][self.event_idx]

    def deserialize_event(self, event_dict):
        if event_dict['subj'] == TABLE_SUBJECT_REPR:
            subj = self.table
        elif event_dict['subj'] == SIDE_EFFECT_SUBJ:
            subj = SIDE_EFFECT_SUBJ
        else:
            subj = self.accessor.player_by_username(
                event_dict['subj']
            )

        event = Event.from_str(event_dict['event'])
        args = event_dict['args']

        return (subj, event, args)

    def dispatch_event(self, event):
        subj, event, args = self.deserialize_event(event)

        if isinstance(subj, Player) and event in PLAYER_API:
            args['player_id'] = subj.id
            self.controller.player_dispatch(str(event), **args)
        else:
            self.controller.internal_dispatch(((subj, event, args),))

    def dispatch_events(self, events):
        for event in events:
            self.dispatch_event(event)

    def _is_skip_event(self, event):
        event_str = event['event'].upper()
        # ignore these because they mess with state handled by the serialized
        #   players object
        return event_str in (
            'TAKE_SEAT', 'LEAVE_SEAT', 'BUY', 'SIT_IN', 'SHUFFLE',
            'SIT_OUT', 'UPDATE_STACK', 'RESET', 'OWE_BB', 'OWE_SB',
        )

    def _skip_to_event(self, idx):
        self.reset_to_hand(self.current_hand())
        for event in self.current_hand()['events'][:idx]:
            if not self._is_skip_event(event):
                self.dispatch_event(event)
        self.event_idx = idx
        self.go_to_next_nonskip_event()

    def step_forward(self):
        # import ipdb; ipdb.set_trace()
        self.dispatch_event(self.current_event())
        self.event_idx += 1
        self.go_to_next_nonskip_event()

    def step_back(self):
        if self.event_idx == 0:
            raise IndexError('Already at the beginning of the hand.')

        self.event_idx -= 1
        self.go_to_next_nonskip_event(backwards=True)
        # must replay the hand from the beginning
        self._skip_to_event(self.event_idx)


class ActionReplayer(EventReplayer):
    def __init__(self, json_log,
                       hand_idx=None,
                       hand_number=None,
                       event_idx=0,
                       action_idx=0,
                       subscriber_types=None,
                       session_id=None,
                       verbose=False,
                       logging=False):

        self.verbose = verbose
        super().__init__(json_log,
                         hand_idx=hand_idx,
                         hand_number=hand_number,
                         event_idx=event_idx,
                         subscriber_types=subscriber_types,
                         session_id=session_id,
                         logging=logging)
        self._skip_to_action(action_idx)

    def reset_to_hand(self, hand_history):
        self.action_idx = 0
        super().reset_to_hand(hand_history)
        '''
            beginning of hand events:
                prepare_hand
                    BUY / UPDATE_STACK
                    SIT_OUT / LEAVE_SEAT
                    SET_TIMEBANK
                    SET_BLIND_POS (special case--lock btn when only 1 player)
                    SIT_IN / SIT_OUT
                    RESET
                start_hand
                    OWE_SB / OWE_BB
                    SIT_IN (special case--new round)
                    ADD_ORBIT_SITTING_OUT / LEAVE_SEAT
                    SET_BLIND_POS
                    SIT_OUT (special case--player couldn't post)
                        NEW_HAND (side_effect subj; snapshots state)
                    ANTE / POST / POST_DEAD
                    DEAL
        '''

        self.controller.setup_hand(
            mocked_deck_str=self.current_hand()['table']['deck_str'],
            mocked_blinds={
                'btn_pos': self.current_hand()['table']['btn_idx'],
                'sb_pos': self.current_hand()['table']['sb_idx'],
                'bb_pos': self.current_hand()['table']['bb_idx'],
            }
        )
        self.commit()

        if self._player_sits_in_to_start_new_hand_edgecase():
            # resetting to a hand brings us to the START_HAND event
            #   which occurs after the SIT_IN action in this edgecase
            self.action_idx = 1

        if self.verbose:
            hand_number = self.controller.table.hand_number
            print(f'\t ====Reset to hand #{hand_number}====')
            self.accessor.describe(True)

    def current_action(self):
        return self.current_hand()['actions'][self.action_idx]

    def dispatch_current_action(self, multi_hand=True):
        action = self.current_action()
        self.dispatch_action(action)

        self._bounty_flip_check()

        preset_actions = self.controller.step(end_hand_stop=True)
        self.action_idx += 1
        # skip over the actions that were dispatched by step()
        for subj, action, _ in preset_actions:
            curr_action = self.current_action()
            assert curr_action['action'].lower() == action.lower()
            assert curr_action['subj'] == subj.username
            self.action_idx += 1

        if multi_hand and self.accessor.hand_is_over():
            self.next_hand_without_reset()

    def dispatch_action(self, action):
        act_name = action['action'].lower()
        subj = self.accessor.player_by_username(action['subj'])

        dispatch_buyin = False
        if act_name == 'take_seat' and not subj.seated:
            dispatch_buyin = True

        if self.verbose:
            self.print_action(subj, act_name, **action['args'])

        # try:
        self.controller.player_dispatch(act_name,
                                        player_id=subj.id,
                                        **action['args'])
        # except Exception as e:
        #     print(e)
        #     import ipdb; ipdb.set_trace()
        #     pass

        if (self.action_idx == 0
                and act_name == 'sit_in'
                and self._player_sits_in_to_start_new_hand_edgecase()):
            deck_str = self.current_hand()['table']['deck_str']
            self.controller.setup_hand(mocked_deck_str=deck_str)

        # see HoldemController.join_table() -- this is called automatically
        #   by the join_table helper method
        if dispatch_buyin:
            self.controller._dispatch_join_table_buyin(
                subj, Decimal(action['args']['buyin_amt'])
            )

    def _bounty_flip_check(self):
        acc = self.accessor
        if acc.table.table_type != NL_BOUNTY:
            return
        if self.accessor.there_is_bounty_win():
            flip_idx = None
            for i, event in enumerate(self.current_hand()['events']):
                if event['event'] == 'BOUNTY_WIN':
                    flip_idx = i
            post_flip_events = self.current_hand()['events'][flip_idx:]
            flip_deck = ','.join([
                event['args']['card'] for event in post_flip_events
                if event['event'] == 'DEAL'
            ])
            assert flip_deck, "No bounty DEAL events found in event history"
            self.controller.mocked_forced_flip(deck_str=flip_deck)

    def _skip_to_action(self, idx):
        self.action_idx = 0
        self.reset_to_hand(self.current_hand())
        n_actions = len(self.current_hand()['actions'])

        if idx < 0:
            idx = n_actions - idx

        while self.action_idx < idx:
            self.dispatch_current_action()

    def step_forward(self, multi_hand=True):
        try:
            # this mutates action_idx. in most cases it is incremented
            #   by one, except when a new hand is reached in multi_hand
            #   or when multiple actions are dispatched at once because
            #   preset_action(s) are dispatched by `step`
            self.dispatch_current_action(multi_hand)

            if self.verbose:
                print(f'replayer gamestate:')
                self.accessor.describe(True)

            if self.subscriber_types:
                # need to call commit() on the controller so that subscribers
                #   prepare for a gamestate broadcast
                self.commit()

        except IndexError:
            raise StopIteration('Reached the last action')

    def step_back(self):
        if self.action_idx == 0:
            raise IndexError('Already at the beginning of the hand.')
        self._skip_to_action(self.action_idx - 1)

    def is_last_hand(self):
        return self.current_hand() == self.hands[-1]

    def next_hand_without_reset(self):
        if not self.accessor.hand_is_over():
            raise ValueError('Need to reach end of hand to continue.')

        if self.is_last_hand():
            raise StopIteration('Reached the last hand in HandHistory')

        if self.verbose:
            print(f'--> Reached the end of hand number '\
                  f'{self.controller.table.hand_number} '\
                  f'at idx {self.hand_idx}')
            self.accessor.describe(True)

        self.controller.end_hand()
        self.hand_idx += 1
        self.action_idx = 0

        self.players += self._takeseat_players(
            self.current_hand(),
            self.players
        )

        deck_str = self.current_hand()['table']['deck_str']
        # self.hand_idx -= 1
        self.controller.setup_hand(mocked_deck_str=deck_str)
        # self.hand_idx += 1

        if self.verbose:
            print(f'--> Starting new hand: '\
                  f'{self.controller.table.hand_number} '\
                  f'at idx {self.hand_idx}')
            self.accessor.describe(True)

        # make sure our changes match what happened in the hand_history
        for player_dict in self.current_hand()['players']:
            username = player_dict['username']
            player = self.accessor.player_by_username(username)

            starting_stack = player.stack_available + player.dead_money
            assert starting_stack == Decimal(player_dict['stack'])

            if not self._player_sits_in_to_start_new_hand_edgecase(player):
                playing_state = str(player.playing_state)
                assert playing_state == player_dict['playing_state']

        # for event in self.current_hand()['events']:
        #     if event in ('BUY')

    def _player_sits_in_to_start_new_hand_edgecase(self, for_player=None):
        # this covers an edgecase where a new hand doesn't start
        #   until a given player sits in; which breaks assumptions
        #   in hand

        if not self.current_hand()['actions']:
            return False

        first_action = self.current_hand()['actions'][0]

        sit_in_actions = ('SIT_IN', 'SIT_IN_AT_BLINDS', 'TAKE_SEAT')
        if not first_action['action'].upper() in sit_in_actions:
            return False

        if for_player and first_action['subj'] != for_player.username:
            return False

        event_idx_for_act = 0
        event_idx_for_new_hand = 0
        for i, event in enumerate(self.current_hand()['events']):
            is_act = (
                event['event'].lower() == first_action['action'].lower()
                and event['subj'].lower() == first_action['subj'].lower()
            )
            if is_act:
                event_idx_for_act = i

            is_new_hand = event['event'].lower() == 'new_hand'
            if is_new_hand:
                event_idx_for_new_hand = i

        assert event_idx_for_act is not None, \
                "Failed to find a corresponding Event for the first Action"

        return event_idx_for_act < event_idx_for_new_hand


    def print_action(self, subj, action, **kwargs):
        print('*   *   *')
        print(f'Dispatching #{self.action_idx}({subj}, {action})')
        print(f'with kwargs {kwargs}')


# class ReplaySubscriber(Subscriber):
#     # TODO: use this to follow along w/Events in the ActionReplayer
#     #   and check for differences between recorded Events and events
#     #   produced by the controller
#     def __init__(self, accessor):
#         self.reset()

#     def reset(self):
#         self.events = []

#     def dispatch(self, subj, event, changes=None, **kwargs):
#         if subj != SIDE_EFFECT_SUBJ:
#             self.events.append({
#                 str(event)})

#     def commit(self):
#         self.reset()

#     def updates_for_broadcast(self, player=None, spectator=None):
#         return {}
