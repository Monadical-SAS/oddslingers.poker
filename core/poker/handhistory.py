from operator import itemgetter
from collections import defaultdict, OrderedDict

from django.utils import timezone
from django.conf import settings

from oddslingers.utils import json_strptime, ExtendedEncoder, to_json_str

from poker.constants import (Event, TABLE_SUBJECT_REPR, SIDE_EFFECT_SUBJ,
                             PLAYER_API)
from poker.models import (Player, PokerTable, HandHistory, HandHistoryEvent,
                          HandHistoryAction, SideEffectSubject)

# important assumptions made by the JSON and DBLogs:
#   - The END_HAND event will be called once per hand, and everything
#       that comes after it can be considered part of the next hand
#   - The state of the game does does not need to be serialized until
#       the NEW_HAND event is dispatched


class HandHistoryLog:
    def write_action(self, action, player_id=None, **kwargs):
        desc = 'This should store a record of an action being taken '\
               'by a player.'
        raise NotImplementedError(desc)

    def write_event(self, subj, event, **event_args):
        desc = 'This should write an event to the current log'
        raise NotImplementedError(desc)

    def get_log(self, player=None, notes=None, hand_gte=None, hand_lt=None,
                ts_gte=None, ts_lt=None, current_hand_only=False):
        ''' format:
        {
            'release': <git_commit_hash>,
            'accessed': <ts>,
            'notes': <str>,
            'hands': [
                {
                    'ts': <ts>,
                    'table': <json>,
                    'players': <json>,
                    'events': [<json>, ... ],
                    'actions': [<json>, ... ],
                },
                ...
            ]
        }
        '''
        desc = 'Should return a filtered json-serializable '\
               'representation of the log'
        raise NotImplementedError(desc)

    def current_hand_log(self, player=None, notes=None):
        desc = 'Should return the same as '\
               'get_log(hand_gte=self.current_hand.hand_number)'
        raise NotImplementedError(desc)

    def readable_log(self, player=None, notes=None, hand_gte=None, hand_lt=None,
                     ts_gte=None, ts_lt=None, current_hand_only=False,
                     stringify=True):
        desc = 'Should be a human-readable version of get_log'
        raise NotImplementedError(desc)

    def save_to_file(self, filename, player=None, notes=None,
                            hand_gte=None, hand_lt=None,
                            ts_gte=None, ts_lt=None,
                            current_hand_only=False, indent=False):
        raise NotImplementedError('Should save a json-serialized log to file')

    def frontend_log(player, hand_gte, hand_lt):
        ''' format:
        [
            {
                'hand_number': <hand_number (int)>,
                'summary': <human-readable hand history summary (str)>,
            } for hand in self.get_log(...)['hands']
        ]

        should use hand_history_to_frontend_dict()
        '''
        raise NotImplementedError('Should return hand history for frontend')

    def commit(self):
        raise NotImplementedError('Should commit the log to db if necessary.')

    @staticmethod
    def game_state_json(table, players):
        return ExtendedEncoder.convert_for_json({
            'table': {
                'id': table.id,
                'name': table.name,
                'ante': table.ante,
                'min_buyin': table.min_buyin,
                'max_buyin': table.max_buyin,
                'num_seats': table.num_seats,
                'sb': table.sb,
                'bb': table.bb,
                'btn_idx': table.btn_idx,
                'sb_idx': table.sb_idx,
                'bb_idx': table.bb_idx,
                'board_str': table.board_str,
                'deck_str': table.deck_str,
                'precision': table.precision,
                'hand_number': table.hand_number,
                'table_type': table.table_type,
            },
            'players': [{
                'id': plyr.id,
                'username': plyr.username,
                'stack': plyr.stack,
                'playing_state': plyr.playing_state,
                'position': plyr.position,
                'owes_sb': plyr.owes_sb,
                'owes_bb': plyr.owes_bb,
                'sit_out_at_blinds': plyr.sit_out_at_blinds,
                'auto_rebuy': plyr.auto_rebuy,
                'orbits_sitting_out': plyr.orbits_sitting_out
            } for plyr in players]
        })

    @staticmethod
    def filter_cards(event_line, player):
        if event_line['event'] == 'DEAL' and player != 'all':
            if player is None or player.username != event_line['subj']:
                # to crash in case the data format changes
                assert len(event_line['args'].keys()) == 1
                return {**event_line, 'args': {'card': '?'}}

        return event_line

    @staticmethod
    def frontend_event_filter(events):
        include = [e.name for e in PLAYER_API] + ['CHAT', 'WIN']
        return [e for e in events if e['event'].upper() in include]

    @staticmethod
    def hand_history_to_frontend_dict(hand):
        table = hand['table']
        output = {
            'title': 'Summary for hand #{hand_number} at table "{name}"'
                     .format(**table),
            'table_info': '({sb}/{bb} {num_seats}-max {table_type})'
                          .format(**table),
            'history': []

        }
        for event_line in hand['events']:
            event = event_line['event']
            subj = event_line['subj']
            args = event_line['args']

            if event == 'CHAT':
                if args['msg'] != '====NEW HAND====':
                    output['history'].append(args['msg'])
            elif event in ('FOLD', 'CHECK', 'CALL'):
                output['history'].append(f'{subj} {event.lower()}ed')
            elif event in ('BET', 'ANTE'):
                if event == 'BET':
                    past_tense = 'bet'
                elif event == 'ANTE':
                    past_tense = 'anted'
                msg = f'{subj} {past_tense} {args["amt"]} chips'
                output['history'].append(msg)
            elif event == 'RAISE_TO':
                msg = f'{subj} raised to {args["amt"]} chips'
                output['history'].append(msg)
            # elif event == 'UPDATE_STACK':
            #     output['history'].append(f'{subj} added {args["amt"]} chips')

        return output


class MultiLog(HandHistoryLog):
    """for testing only"""
    def __init__(self, logs):
        self.logs = logs

    def write_action(self, action, **kwargs):
        for log in self.logs:
            log.write_action(action, **kwargs)

    def write_event(self, subj, event, **kwargs):
        for log in self.logs:
            log.write_event(subj, event, **kwargs)

    def get_log(self, player=None, notes=None, hand_gte=None,
                      hand_lt=None, ts_gte=None, ts_lt=None,
                      current_hand_only=False):
        raise NotImplementedError('Call get_log on a child log.')

    def current_hand_log(self, player=None, notes=None):
        raise NotImplementedError('Call current_hand_log on a child log.')

    def readable_log(self, player=None, notes=None,
                            hand_gte=None, hand_lt=None,
                            ts_gte=None, ts_lt=None,
                            current_hand_only=False, stringify=True):
        raise NotImplementedError('Call readable_log on a child log.')

    def save_to_file(self, filename, player=None, notes=None,
                            hand_gte=None, hand_lt=None,
                            ts_gte=None, ts_lt=None,
                            current_hand_only=False, indent=False):
        raise NotImplementedError('Call save_to_file on a child log.')

    def commit(self):
        for log in self.logs:
            log.commit()


class JSONLog(HandHistoryLog):
    def __init__(self, accessor):
        self.accessor = accessor
        self.hands = []

    def _init_hand(self):
        self.hands.append({
            'ts': ExtendedEncoder.convert_for_json(timezone.now()),
            'table': None,
            'players': None,
            'actions': [],
            'events': [],
        })

    def current_hand(self):
        return self.hands[-1]

    def _check_serialized_state(self):
        if not self.hands:
            self._init_hand()

        if self.current_hand()['table'] is None:
            self._serialize_starting_state()

    def _serialize_starting_state(self):
        if not self.hands:
            msg = 'JSONLog._serialize_starting_state was called '\
                  'before _init_hand'
            raise RuntimeError(msg)

        self.current_hand().update({
            **self.game_state_json(self.accessor.table,
                                   self.accessor.seated_players()),
        })

    def write_event(self, subj, event, **event_args):
        if not self.hands:
            self._init_hand()

        self._write_event(subj, event, **event_args)

        if event == Event.END_HAND and isinstance(subj, PokerTable):
            self._init_hand()
        elif event == Event.NEW_HAND:
            self._serialize_starting_state()

    def _write_event(self, subj, event, **event_args):
        if isinstance(subj, Player):
            subj = str(subj.username)
        elif isinstance(subj, PokerTable):
            subj = TABLE_SUBJECT_REPR
        elif not subj == SIDE_EFFECT_SUBJ:
            raise ValueError(f'Tried to log an event with subj {subj} '\
                             f'of type {type(subj)}')

        self.current_hand()['events'].append({
            'ts': ExtendedEncoder.convert_for_json(timezone.now()),
            'subj': subj,
            'event': str(event),
            'args': ExtendedEncoder.convert_for_json(event_args),
        })

    def write_action(self, action, player_id, **kwargs):
        subj = self.accessor.player_by_player_id(player_id).username
        self.current_hand()['actions'].append({
            'ts': ExtendedEncoder.convert_for_json(timezone.now()),
            'action': str(action),
            'subj': subj,
            'args': ExtendedEncoder.convert_for_json(kwargs),
        })

    def _convert_hand(self, hh, player):
        return {
            **self._add_gamestate_if_unserialized(hh),
            'events': [
                self.filter_cards(line, player)
                for line in hh['events']
            ],
        }

    def _add_gamestate_if_unserialized(self, hh):
        if hh is None or 'table' not in hh:
            raise Exception(
                'Empty hh passed into _add_gamestate_if_unserialized():'
                f'{hh}'
            )

        # This can happen between END_HAND and NEW_HAND events
        if hh['table'] is None:
            return {
                **hh,
                **self.game_state_json(self.accessor.table,
                                       self.accessor.seated_players())
            }

        return hh

    def _log_metadata(self, notes):
        return {
            'release': settings.GIT_SHA,
            'accessed': timezone.now(),
            'notes': notes,
        }

    def _filter_hands(self, hhs, hand_gte=None, hand_lt=None, ts_gte=None,
                      ts_lt=None):
        tsf_gte = lambda hh: (ts_gte is None
                              or json_strptime(hh['ts']) >= ts_gte)

        tsf_lt = lambda hh: (ts_lt is None
                             or json_strptime(hh['ts']) < ts_lt)

        hf_gte = lambda hh: (hand_gte is None
                             or hh['table']['hand_number'] >= hand_gte)

        hf_lt = lambda hh: (hand_lt is None
                            or hh['table']['hand_number'] < hand_lt)

        return [
            hh for hh in hhs
            if tsf_gte(hh) and tsf_lt(hh) and hf_gte(hh) and hf_lt(hh)
        ]

    def get_log(self, player=None, notes=None, hand_gte=None, hand_lt=None,
                      ts_gte=None, ts_lt=None, current_hand_only=False):
        if current_hand_only:
            return self.current_hand_log(player, notes)

        return {
            **self._log_metadata(notes),
            'hands': [
                self._convert_hand(hh, player)
                for hh in self._filter_hands(self.hands, hand_gte, hand_lt,
                                             ts_gte, ts_lt)
            ]
        }

    def current_hand_log(self, player=None, notes=None):
        return {
            **self._log_metadata(notes),
            'hands': [
                self._convert_hand(self.current_hand(), player)
            ] if self.hands else [],
        }

    def describe(self, for_player=None,
                       current_hand=False,
                       filtered=True,
                       print_me=True):
        # 'filtered' interpolates actions with dealer messages
        #   into one eventlist, and removes the rest
        if current_hand:
            log = self.current_hand_log(player=for_player)
        else:
            log = self.get_log(player=for_player)

        log['hands'] = [
            fmt_hand(hand, for_player=for_player, filtered=filtered)
            for hand in log['hands']
        ]
        out = to_json_str(log, indent=2, unicode_escape=True)

        if print_me:
            print(out)
        else:
            return out

    def save_to_file(self, filename, player='all', notes=None, hand_gte=None,
                     hand_lt=None, ts_gte=None, current_hand_only=False,
                     indent=False):
        if current_hand_only:
            log = self.current_hand_log(player=player, notes=notes)
        else:
            log = self.get_log(player=player, notes=notes, hand_gte=hand_gte,
                               hand_lt=hand_lt, ts_gte=ts_gte)

        # import ipdb; ipdb.set_trace()
        with open(filename, 'w') as f:
            f.write(to_json_str(log, indent=4 if indent else 0))

    def frontend_log(self, player, hand_gte, hand_lt):
        log = self.get_log(player=player, hand_gte=hand_gte, hand_lt=hand_lt)
        return [
            {
                'hand_number': hand['table']['hand_number'],
                'summary': HandHistoryLog.hand_history_to_frontend_dict(hand),
            }
            for hand in log['hands']
        ]

    def commit(self):
        self._check_serialized_state()


class DBLog(JSONLog):
    def __init__(self, accessor):
        self.accessor = accessor
        self.objects_to_save = []

        try:
            self.hands = [
                HandHistory.objects.get(
                    table_id=self.accessor.table.id,
                    hand_number=self.accessor.table.hand_number,
                )
            ]
        except HandHistory.DoesNotExist:
            try:
                self.hands = [
                    HandHistory.objects.filter(table_id=self.accessor.table.id)\
                                       .latest('hand_number')
                ]
            except HandHistory.DoesNotExist:
                self.hands = []

    def _init_hand(self):
        table = self.accessor.table
        new_hh = HandHistory(table=table, hand_number=table.hand_number)
        self.objects_to_save.append(new_hh)
        self.hands.append(new_hh)

    def _check_serialized_state(self, force=False):
        if not self.hands:
            self._init_hand()

        if force or self.current_hand().table_json is None:
            self._serialize_starting_state()

    def _serialize_starting_state(self):
        game_state = self.game_state_json(self.accessor.table,
                                          self.accessor.seated_players())
        this_hand = self.current_hand()

        # print('==========================================================')
        # print('serilaizing hand history:')
        # print(game_state)
        # print('accessor currently has players:')
        # print([p.__json__() for p in self.accessor.players])
        # print('current table state:')
        # print(self.accessor.table.__json__())

        this_hand.table_json = game_state['table']
        this_hand.players_json = game_state['players']

        if this_hand not in self.objects_to_save:
            self.objects_to_save.append(this_hand)

    def _write_event(self, subj, event, **args):
        if subj == SIDE_EFFECT_SUBJ:
            subj = SideEffectSubject.load()

        self.objects_to_save.append(
            HandHistoryEvent(
                hand_history=self.current_hand(),
                subject=subj,
                event=event.name,
                args=ExtendedEncoder.convert_for_json(args),
            )
        )

    def write_action(self, action, player_id=None, **args):
        assert player_id is not None, 'Received an action without a player_id'

        player = self.accessor.player_by_player_id(player_id)
        self.objects_to_save.append(HandHistoryAction(
            hand_history=self.current_hand(),
            subject=player,
            action=str(action),
            args=ExtendedEncoder.convert_for_json(args),
        ))

    def _unsaved_hands(self, hand_gte=None, hand_lt=None,
                       ts_gte=None, ts_lt=None, current_hand_only=False):
        if current_hand_only:
            hand_gte = self.current_hand().hand_number

        get_ts = lambda x: x.timestamp if x.timestamp else timezone.now()

        ts_filter = lambda thing: (
                ((not ts_gte) or get_ts(thing) >= ts_gte)
                and
                ((not ts_lt) or (get_ts(thing) < ts_lt))
        )

        hn_filter = lambda hand_number: (
            ((not hand_gte) or (hand_number >= hand_gte))
            and
            ((not hand_lt) or (hand_number < hand_lt))
        )

        line_filter = lambda line: (
            hn_filter(line.hand_history.hand_number) and ts_filter(line)
        )

        unsaved = defaultdict(lambda: {
            'actions': [],
            'events': [],
        })

        for obj in self.objects_to_save:
            if isinstance(obj, HandHistory):
                if hn_filter(obj.hand_number):
                    hand_number = obj.hand_number
                    unsaved[hand_number] = {
                        **unsaved[hand_number],
                        'ts': obj.timestamp,
                        'table': obj.table_json,
                        'players': obj.players_json,
                    }
            elif line_filter(obj):
                hand_number = obj.hand_history.hand_number
                if isinstance(obj, HandHistoryAction):
                    unsaved[hand_number]['actions'].append(obj.__json__())
                else:
                    unsaved[hand_number]['events'].append(obj.__json__())

        return unsaved

    def _merge_unsaved(self, hands, hand_gte=None, hand_lt=None,
                       ts_gte=None, ts_lt=None, current_hand_only=False):
        unsaved_hands = self._unsaved_hands(
            hand_gte, hand_lt, ts_gte, ts_lt, current_hand_only
        )

        output = []
        for hand in hands:
            if hand['table']['hand_number'] in unsaved_hands:
                unsaved_hand = unsaved_hands.pop(hand['table']['hand_number'])

                output.append(self._add_gamestate_if_unserialized({
                    **hand,
                    **unsaved_hand,
                    'actions': hand['actions'] + unsaved_hand['actions'],
                    'events': hand['events'] + unsaved_hand['events'],
                }))

                assert (
                    ((not hand['actions']) or (not unsaved_hand['actions']))
                    or
                    (hand['actions'][-1]['ts']
                     <= unsaved_hand['actions'][0]['ts'])
                ), "Broken assumption: unsaved action predates saved action"
                assert (
                    ((not hand['events']) or (not unsaved_hand['events']))
                    or
                    (hand['events'][-1]['ts']
                     <= unsaved_hand['events'][0]['ts'])
                ), "Broken assumption: unsaved event predates saved event"

            else:
                output.append(hand)

        for hand_number in sorted(unsaved_hands.keys()):
            output.append(unsaved_hands[hand_number])

        for hh in output:
            if 'table' not in hh:
                print(hh)
                print(self.objects_to_save)
                raise Exception('Broken hh detected')

        return output

    def _timestamp_filter_args(self, ts_gte, ts_lt):
        args = {}
        if ts_gte:
            args['timestamp__gte'] = ts_gte
        if ts_lt:
            args['timestamp__lt'] = ts_lt
        return args

    def get_log(self, player=None, notes=None, hand_gte=None, hand_lt=None,
                      ts_gte=None, ts_lt=None, current_hand_only=False):
        if not self.hands:
            hands = []
        else:
            ts_filt_args = self._timestamp_filter_args(ts_gte, ts_lt)

            if current_hand_only:
                hands = [self.current_hand().filtered_json(**ts_filt_args)]

            else:
                hh_filter_args = {'table_id': self.accessor.table.id}
                if hand_gte:
                    hh_filter_args['hand_number__gte'] = hand_gte
                if hand_lt:
                    hh_filter_args['hand_number__lt'] = hand_lt


                hh_filter_args = {**hh_filter_args, **ts_filt_args}

                hands = [
                    hand.filtered_json(**ts_filt_args)
                    for hand in HandHistory.objects\
                            .filter(**hh_filter_args, **ts_filt_args)\
                            .select_related()\
                            .order_by('hand_number')
                ]

            hands = ExtendedEncoder.convert_for_json(hands)
            hands = self._merge_unsaved(
                hands, hand_gte, hand_lt, ts_gte, ts_lt, current_hand_only
            )

        return {
            **self._log_metadata(notes),
            'hands': [self._convert_hand(hh, player) for hh in hands]
        }

    def current_hand_log(self, player=None, notes=None):
        return self.get_log(
            player=player, notes=notes, current_hand_only=True
        )

    def commit(self):
        self._check_serialized_state()
        # if (len(self.current_hand().players_json)
        #             != len(self.accessor.seated_players())):
        #     print(self.current_hand().players_json)
        #     print(self.accessor.seated_players())
        for obj in self.objects_to_save:
            # if isinstance(obj, HandHistory):
            #     print(f'saving HandHistory with players:\n{obj.players_json}')
            if (isinstance(obj, HandHistoryEvent)
                    or isinstance(obj, HandHistoryAction)):
                # relation's ID must be manually attached, since the \
                #   HandHistory object doesn't get assigned an ID until
                #   it's been committed to the database
                obj.hand_history_id = obj.hand_history.id
            obj.save()
        self.objects_to_save = []

def fmt_hand(hand_json, filtered=True, for_player=None):
    od = OrderedDict(fmt_table(hand_json['table']))
    od['ts'] = hand_json['ts']
    od['players'] = [fmt_player(plyr) for plyr in hand_json['players']]
    if filtered:
        combined = sorted(
            hand_json['actions'] + hand_json['events'],
            key=itemgetter('ts')
        )
        od['filtered_eventlist'] = fmt_eventlist(
            combined,
            filtered=filtered,
            for_player=for_player
        )
    else:
        od['events'] = fmt_eventlist(
            hand_json['events'],
            filtered=False,
            for_player=for_player,
        )
        od['actions'] = fmt_eventlist(hand_json['actions'], filtered=False)

    return od

def fmt_eventlist(lst, filtered=True, for_player=None):
    if filtered:
        # The controller pushes dealer chat for:
        # reveal, update_stack, deal, post, blinds,
        include = ['CHAT', 'WIN']
        lst = [
            line for line in lst
            if 'action' in line or line['event'] in include
        ]

    return [fmt_eventline(for_player=for_player, **line) for line in lst]

def fmt_eventline(for_player=None, **line):
    if 'event' in line:
        line = HandHistoryLog.filter_cards(line, for_player)
        fmtted = '@{subj:<16} [{event:^12}] {args}'.format(**line)
    else:
        fmtted = '@{subj:<16} [{action:^12}] {args}'.format(**line)

    if 'ts' in line:
        return f"{line['ts']}: {fmtted}"

    return fmtted


def fmt_player(plyr_json):
    fmt = '{position} ({stack}): {username} <{playing_state}>'
    return fmt.format(**plyr_json)

def fmt_table(table_json):
    table_fmtstr = '{name}: {num_seats}-max {sb}/{bb} {table_type}'
    return {
        table_fmtstr.format(**table_json): {
            k: v
            for k, v in table_json.items()
            if k not in ('name', 'num_seats', 'sb', 'bb', 'table_type')
        }
    }
