import logging

from decimal import Decimal
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.utils import timezone

from oddslingers.utils import (rotated, ExtendedEncoder, idx_dict,
                          autocast, decimal_floor, fnv_hash,
                          secure_random_number)

from poker.bot_personalities import bot_personality, DEFAULT_BIO
from poker.constants import (
    Event, Action, NL_HOLDEM, PL_OMAHA, NL_BOUNTY,
    FOLD_OR_TOGGLE_PENDING, PlayingState, TOURNEY_AUTOFOLD_DELAY,
    NUM_HOLECARDS, ACTIVE_PLAYSTATES, BOUNTY_HANDS,
    BOUNTY_TOURNEY_BBS_TO_CALL, BUMP_AFTER_INACTIVE_MINS,
    MAX_ORBITS_SITTING_OUT
)
from poker.hand_ranges import hand_to_description
from poker.models import Player
from poker.rankings import (best_hand_from_cards, best_hand_using_holecards,
                            hand_sortkey)
from poker.megaphone import player_sockets

from sidebets.models import Sidebet

from banker.utils import balance


logger = logging.getLogger('poker')


def filter_nonactors(players):
    return [
        plyr for plyr in players
        if (
            plyr.playing_state in ACTIVE_PLAYSTATES
            and plyr.cards
        )
    ]


class PokerAccessor:
    def __init__(self, table, players=None):
        self.table = table
        # smartly load players into memory if they aren't passed
        self.players = players or list(table.player_set.all())

        # used by the BankerSubscriber
        self.pending_transfers = []

    def commit(self):
        if self.table.tournament:
            self.table.tournament.save()

        self.table.save()

        for player in self.players:
            player.save()

    def gamestate(self, convert=False):
        output = {
            'table_json': self.table_json(),
            'private_jsons': {player.id: self.private_player_json(player)
             for player in self.seated_players()},
            'public_json': self.players_json(),
        }
        if convert:
            return ExtendedEncoder.convert_for_json(output)
        return output

    def players_json(self, for_player=None):
        # WARNING: for_player returns info private to that player
        if for_player == 'all':
            private = lambda player: True
        else:
            private = lambda player: player == for_player

        return {
            player.id: self.player_json(player, private=private(player))
            for player in self.seated_players()
        }

    def table_json(self):
        next_actor = self.next_to_act()
        if self.table.created_by:
            created_by = self.table.created_by.username
        else:
            created_by = 'OddSlingers'

        return {
            'id': str(self.table.id),
            'short_id': str(self.table.short_id),
            'name': self.table.name,
            'path': self.table.path,
            'variant': self.table.variant,
            'sb': self.table.sb or 0,
            'bb': self.table.bb or 0,
            'board': idx_dict({'card': card}
                              for card in self.table.board or ()),
            'btn_idx': self.table.btn_idx,
            'num_seats': self.table.num_seats,
            'available_seats': (self.table.num_seats
                                - len(self.seated_players())),
            'hand_number': self.table.hand_number,
            'total_pot': self.current_pot(),
            'sidepot_summary': self.frontend_sidepot_summary(),
            'to_act_id': str(next_actor.id) if next_actor else None,
            'seconds_to_act': self.seconds_to_act(),
            'last_action_timestamp': self.table.last_action_timestamp,
            'min_buyin': self.table.min_buyin,
            'max_buyin': self.table.max_buyin,
            'created_by': created_by,
            'sidebets_enabled': self.table.sidebets_enabled,
            'is_private': self.table.is_private,
            'tournament': (
                self.table.tournament and self.table.tournament.__json__()
            )
        }

    def player_json(self, player, private=False):
        is_autofolding = str(player.playing_state) == 'TOURNEY_SITTING_OUT'
        output = {
            'id': str(player.id),
            'short_id': player.short_id,
            'username': player.username,
            'user_id': player.user_id,
            'stack': {'amt': player.stack or 0},
            'position': player.position,
            'sitting_out': player.is_sitting_out(),
            'uncollected_bets': {'amt': player.uncollected_bets or 0},
            'is_active': player.is_active(),
            'last_action': str(Event(player.last_action_int))
                           if player.last_action_int
                           else None,
            'is_all_in': bool(self.is_all_in(player)),
            # TODO: remove this and add it as an OR case to 'sitting_out'
            'is_autofolding': is_autofolding,
            # 'balance': self.get_balance(player),
            'cards': idx_dict({'card': '?'} for card in player.cards or ()),
            'timebank': player.timebank_remaining,
        }

        if private:
            output.update(self.private_player_json(player))

        if player.user and player.user.is_robot:
            output.update(self.bot_player_json(player))
        return output

    def private_player_json(self, player):
        to_act_events = {
            'min_bet': min(self.min_bet_amt(), player.stack_available),
        } if player == self.next_to_act() else {
            'min_bet': None,
        }
        will_act_events = {
            'amt_to_call': self.call_amt(player, diff=True),
        } if self.will_act_this_round(player) else {
            'amt_to_call': None,
        }
        return {
            'pending_rebuy': player.pending_rebuy,
            'auto_rebuy': player.auto_rebuy,
            'preset_call': player.preset_call,
            'preset_check': player.preset_check,
            'preset_checkfold': player.preset_checkfold,
            'playing_state': str(player.playing_state),
            'logged_in': player.user and player.user.is_authenticated,
            'cards': idx_dict({'card': card} for card in player.cards or ()),
            'available_actions': [
                str(e) for e in self.available_actions(player.id)
            ],
            'legal_min_buyin': self.legal_min_buyin(player),
            'legal_max_buyin': self.legal_max_buyin(player),
            **self.sitting_checkboxes(player),
            **to_act_events,
            **will_act_events,
        }

    def bot_player_json(self, player):
        personality = bot_personality(player.user.username)
        profile = personality.get('profile', {})
        return {
            'is_robot': True,
            'profile_image': '/static/images/bender.png',
            'bio': profile.get('bio') or DEFAULT_BIO,
            'personality_preflop': profile.get('preflop'),
            'personality_postflop':  profile.get('postflop'),
        }

    def sitting_checkboxes(self, player):
        state = player.playing_state
        return {
            'sit_in_at_blinds': state == PlayingState.SIT_IN_AT_BLINDS_PENDING,
            'sit_in_next_hand': state == PlayingState.SIT_IN_PENDING,
        } if player.is_sitting_out() else {
            'sit_out_at_blinds': player.sit_out_at_blinds,
            'sit_out_next_hand': state == PlayingState.SIT_OUT_PENDING,
        }

    def get_balance(self, player):
        if player.user:
            total_balance = balance(player.user, self.table)
            for xfer in self.pending_transfers:
                if player.user.id == xfer.dest_id:
                    total_balance += xfer.amt
                elif player.user.id == xfer.source_id:
                    total_balance -= xfer.amt

            return total_balance + player.stack
        else:
            return 'robot dollars'

    def player_contributions(self, exclude_uncollected_bets=True):
        return [
            pot for pot, ppl in self.sidepot_summary(exclude_uncollected_bets)
        ]

    def _filter_active_players(self):
        return [plyr for plyr in self.players if plyr.is_active()]

    def players_to_kick(self):
        # TODO: human players who are sitting in alone but inactive
        #   (no open socket connections) should also get kicked
        return [
            *self.inactive_humans(),
            *self.bored_robots(),
        ]

    def is_bored(self, robot):
        # each robot's brain is programmed to get bored at a unique hand
        #   (so they don't just all get up at the same time)
        return fnv_hash(robot.username) % 40 == self.table.hand_number % 40

    def bored_robots(self):
        # robots never get bored before the 500th hand
        #   nor when they're teaching
        if self.table.hand_number < 500 or self.table.is_tutorial:
            return []

        # they also take at least a minute to get bored
        just_now = timezone.now() - timedelta(minutes=1)
        last_human = self.table.last_human_action_timestamp
        if last_human and last_human > just_now:
            return []

        seated_plyrs = self.seated_players()

        # robots never get bored around these fascinating skinbags
        if len([plyr for plyr in seated_plyrs if not plyr.is_robot]):
            return []

        # but lonely robots get bored quickly
        robot_alone = len(seated_plyrs) == 1 and seated_plyrs[0].is_robot
        if robot_alone:
            return seated_plyrs

        return [
            robot for robot in seated_plyrs
            if (robot.is_robot
                and self.is_bored(robot)
                and not robot.sit_out_at_blinds
                and robot.playing_state == PlayingState.SITTING_IN)
        ]

    def inactive_humans(self):
        if self.table.is_tutorial:
            return []
        time_ago = timezone.now() - timedelta(minutes=BUMP_AFTER_INACTIVE_MINS)

        seated_plyrs = self.seated_players()

        # bump a signle human if they are inactive and disconnected
        if len(seated_plyrs) == 1:
            return [
                plyr for plyr in seated_plyrs
                if not plyr.is_robot
                    and plyr.last_action_timestamp < time_ago
                    and not player_sockets(plyr)
            ]

        return [
            plyr for plyr in seated_plyrs
            if not plyr.is_robot
                and plyr.playing_state == PlayingState.SITTING_OUT
                and plyr.last_action_timestamp < time_ago
        ]

    def should_bump_for_orbits_out(self, player):
        if self.table.is_tutorial:
            return False

        if player.orbits_sitting_out < MAX_ORBITS_SITTING_OUT:
            return False

        return not player.is_active()

    def seated_players(self):
        players = []
        for pos in range(self.table.num_seats):
            plyr = self.players_at_position(
                pos,
                active_only=False,
                include_unseated=False
            )
            if plyr:
                players.append(plyr)
        return players

    def seated_humans(self):
        return [
            plyr for plyr in self.players
            if not plyr.is_robot and plyr.seated
        ]

    def active_players(self, rotate=None,
                             include_pending_at_idx=None):
        if rotate is None:
            rotate = self.first_to_act_pos() or 0

        player_idxs = rotated(list(range(self.table.num_seats)), rotate)

        if include_pending_at_idx is not None:
            players = []
            for i in player_idxs:
                plyr = self.players_at_position(i)
                if (i == include_pending_at_idx
                        and self.player_is_active_or_pending(plyr)):
                    players.append(plyr)
                elif plyr is not None and plyr.is_active():
                    players.append(plyr)
        else:
            players = [
                self.players_at_position(i, active_only=True)
                for i in player_idxs
            ]

        return [plyr for plyr in players if plyr is not None]

        return players

    def showdown_players(self, rotate=None):
        return filter_nonactors(self.active_players(rotate))

    def predeal_active_players(self):
        return [
            plyr for plyr in self.seated_players()
            if plyr.playing_state in ACTIVE_PLAYSTATES
            and plyr.last_action != Event.FOLD
        ]

    def players_with_pending_actions(self):
        return [
            plyr for plyr in self.seated_players()
            if plyr.playing_state in (
                PlayingState.SIT_IN_PENDING,
                PlayingState.SIT_OUT_PENDING,
                PlayingState.LEAVE_SEAT_PENDING,
            )
        ]

    def players_at_position(self, position: int,
                                  active_only=False,
                                  include_unseated=False):
        """
        returns a single player at the position, or a list if more than
        one player
        """
        players = [plyr for plyr in self.players if plyr.position == position]

        if active_only:
            active = [plyr for plyr in players if plyr.is_active()]
            assert len(active) <= 1, \
                'Sanity check fail: more than one player active at '\
                'a position'
            return active.pop() if active else None
        elif not include_unseated:
            seated = [plyr for plyr in players if plyr.seated]
            assert len(seated) <= 1, \
                'Sanity check fail: more than one player seated at '\
                'a position'
            return seated.pop() if seated else None

        return players

    def winners(self, showdown_players):
        losers = list(showdown_players)
        handrank = lambda plyr: hand_sortkey(self.player_hand(plyr))
        losers.sort(key=handrank)
        table_winners = [losers.pop()]
        winning_handrank = handrank(table_winners[0])

        while losers and handrank(losers[-1]) == winning_handrank:
            table_winners.append(losers.pop())

        return table_winners

    def showdown_winnings_for_pot(self, pot_summary, pot_id):
        potsize, pot_contributors = pot_summary

        showdown_players = self.showdown_players()
        players_to_pay = self.winners(p for p in pot_contributors
                                       if p in showdown_players)

        n_winners = Decimal(len(players_to_pay))
        payout_size = self.round_wager(Decimal(potsize) / n_winners)
        prec = self.table.precision
        smallest_chip = round(Decimal(10**(-prec)), prec)
        n_extra_chips = (potsize - (payout_size * n_winners)) / smallest_chip

        output = {}

        # showdown_players() is being used here because we want to
        #   award pots in position order (and players_to_pay is unordered)
        #   pot_id is used in the frontend, and the 'showdown' annotation
        #   is used by the rewards system (which showdown_set calculates)

        showdown_set = set(showdown_players).intersection(pot_contributors)
        n_paid = 0
        for plyr in showdown_players:
            if plyr in players_to_pay:
                amt_won = payout_size
                if n_paid < n_extra_chips:
                    amt_won += smallest_chip

                output[plyr] = {
                    'amt': amt_won,
                    'pot_id': pot_id,
                    'showdown': len(showdown_set) > 1,
                }
                if output[plyr]['showdown']:
                    output[plyr]['winning_hand'] = self.player_hand(plyr)

                n_paid += 1

        return output

    @autocast
    def round_wager(self, wager: Decimal):
        prec = self.table.precision
        return decimal_floor(wager, prec)

    def can_play(self, player):
        playing = player.playing_state  in (
            PlayingState.SITTING_IN,
            PlayingState.SIT_OUT_PENDING,
            PlayingState.TOURNEY_SITTING_OUT,
            PlayingState.LEAVE_SEAT_PENDING,
        )
        ready_to_play = (
            player.stack >= self.min_amt_to_play(player)
            and player.playing_state in (
                PlayingState.SIT_IN_AT_BLINDS_PENDING,
                PlayingState.SIT_IN_PENDING,
            )
        )
        return playing or ready_to_play

    def min_amt_to_play(self, player):
        amt = Decimal(0)
        if self.table.bb:
            amt += Decimal(self.table.bb)
        if self.table.sb:
            amt += int(player.owes_sb) * Decimal(self.table.sb)
        if self.table.ante:
            amt += Decimal(self.table.ante)
        return amt

    def enough_players_to_play(self):
        return len(self.players_who_can_play()) > 1

    def nobody_can_play(self):
        return len(self.players_who_can_play()) == 0

    def players_who_can_play(self):
        return [p for p in self.seated_players() if self.can_play(p)]

    def available_actions(self, player):
        if not isinstance(player, Player):
            player = self.player_by_player_id(player)
        if not player:
            # print(player, [str(p.id) for p in self.players])
            raise ValueError(f'No player with id {player}')
        assert player.table == self.table, \
            'available_actions() called on accessor for a player '\
            'belonging to a different table'

        if not player.seated:
            # note: This should not be dispatched directly to join table!
            #   use the controller's join_table() helper method instead
            return self._unseated_actions()

        actions = [
            *self._always_available_actions(player),
            *self._sitting_toggle_actions(player),
        ]

        if player.is_sitting_out():
            return actions

        return actions + self._sitting_in_actions(player)

    def _unseated_actions(self):
        return [Action.TAKE_SEAT]

    def _always_available_actions(self, player):
        # LEAVE_SEAT can be called at any time
        return [Action.LEAVE_SEAT] + self._buy_actions(player)

    def _buy_actions(self, player):
        actions = [Action.SET_AUTO_REBUY]

        if player.stack + player.pending_rebuy < self.table.max_buyin:
           actions.append(Action.BUY)

        return actions

    def _sitting_toggle_actions(self, player):
        if player.playing_state == PlayingState.LEAVE_SEAT_PENDING:
            # TAKE_SEAT is used to cancel a LEAVE_SEAT
            # SIT_OUT_AT_BLINDS will also cancel
            #   note, possibly surprising: cancels even if set_to is false
            return [
                Action.TAKE_SEAT,
                Action.SIT_OUT_AT_BLINDS,
            ]

        if player.playing_state == PlayingState.SITTING_OUT:
            if player.stack >= self.min_amt_to_play(player):
                return [
                    Action.SIT_IN,
                    Action.SIT_IN_AT_BLINDS,
                ]
            return []

        if player.playing_state == PlayingState.SIT_IN_AT_BLINDS_PENDING:
            return [
                Action.SIT_IN_AT_BLINDS,
                Action.SIT_IN,
            ]

        if player.playing_state == PlayingState.SIT_IN_PENDING:
            # SIT_OUT will cancel the pending SIT_IN event
            return [
                Action.SIT_IN_AT_BLINDS,
                Action.SIT_OUT,
            ]

        if not self.enough_players_to_play():
            return [Action.SIT_OUT]

        if player.playing_state == PlayingState.SIT_OUT_PENDING:
            # SIT_IN will cancel the pending SIT_OUT event
            # SIT_OUT_AT_BLINDS also cancels
            #   note: if set_to is False, it'll still cancel
            return [
                Action.SIT_IN,
                Action.SIT_OUT_AT_BLINDS,
            ]

        if player.playing_state == PlayingState.SITTING_IN:
            return [
                Action.SIT_OUT_AT_BLINDS,
                Action.SIT_OUT,
            ]

        # note: there is no PlayingState.SIT_OUT_AT_BLINDS; it's
        #   its own field on the Player model. Sorry future dev.
        msg = f'Sanity fail: PlayingState {player.playing_state.value}'\
               " shouldn't be possible."
        raise Exception(msg)

    def _sitting_in_actions(self, player):
        sitting_in_actions = []

        if not self.next_to_act() == player:
            if self.will_act_this_round(player):
                sitting_in_actions.append(Action.SET_PRESET_CHECKFOLD)

                if self.call_amt(player, diff=True) > 0:
                    sitting_in_actions.append(Action.SET_PRESET_CALL)
                else:
                    sitting_in_actions.append(Action.SET_PRESET_CHECK)

            return sitting_in_actions

        sitting_in_actions.append(Action.FOLD)
        raise_size = self.last_raise_size()

        if raise_size > player.uncollected_bets:
            sitting_in_actions.append(Action.CALL)
        else:
            sitting_in_actions.append(Action.CHECK)

        if (player.stack + player.uncollected_bets > raise_size
                and not self.everyone_is_all_in(exclude=player)):
            if raise_size == 0:
                sitting_in_actions.append(Action.BET)
            else:
                sitting_in_actions.append(Action.RAISE_TO)

        return sitting_in_actions

    def everyone_is_all_in(self, exclude=None):
        if not exclude:
            exclude = []
        if isinstance(exclude, Player):
            exclude = [exclude]
        for player in self.showdown_players():
            if player not in exclude and not self.is_all_in(player):
                return False

        return True

    def will_act_this_round(self, player):
        not_folding = player.last_action not in FOLD_OR_TOGGLE_PENDING
        return (len(player.cards)
                and not_folding
                and not self.is_all_in(player)
                and (self.call_amt(player, diff=True) > 0
                        or player.last_action == Event.POST))

    def is_all_in(self, player):
        return player.stack == 0 and len(player.cards)

    def btn_player(self):
        return self.players_at_position(self.table.btn_idx, active_only=True)

    def sb_player(self):
        return self.players_at_position(self.table.sb_idx, active_only=True)

    def bb_player(self):
        return self.players_at_position(self.table.bb_idx, active_only=True)

    def current_pot(self):
        return sum(player.total_contributed()
                    for player in self._filter_active_players())

    def current_uncollected(self):
        return sum(player.uncollected_bets
                    for player in self._filter_active_players())

    def is_new_round(self):
        return self.is_first_hand() or self.btn_is_locked()

    def is_first_hand(self):
        return self.table.btn_idx is None

    def btn_is_locked(self):
        return self.table.bb_idx is None and self.table.btn_idx is not None

    def first_to_act_pos(self):
        # note that this can return a seat position that has no player
        #   in those cases, the first_to_act will be the next active
        #   player to the left of that position.

        actives = self._filter_active_players()
        if not actives or not self.enough_players_to_play():
            return None
        if self.is_predeal():
            # this is for dealing order
            if len(actives) > 2:
                return self.table.sb_idx
            else:
                return self.table.bb_idx
        elif self.is_preflop():
            return (self.table.bb_idx + 1) % self.table.num_seats
        elif len(actives) > 2:
            return self.table.sb_idx
        else:
            return self.table.bb_idx

    def user_has_active_sidebets(self, user_id, table_id):
        qs = Sidebet.objects.filter(user_id=user_id,
                                    table_id=table_id,
                                    status='active')
        return qs.count() > 0

    def user_sidebets_for_player(self, user, player):
        return Sidebet.objects.filter(user=user, player=player)

    def players_in_acting_order(self):
        first = self.first_to_act_pos()
        return filter_nonactors(self.active_players(first))

    def first_to_act(self):
        return self.players_in_acting_order()[0]

    def user_by_id(self, user_id):
        for player in self.players:
            if player.user and player.user.id == user_id:
                return player.user

        return get_user_model().objects.get(id=user_id)

    def player_by_user_id(self, user_id):
        players = [
            p for p in self.players
            if (p.user and str(p.user.id) == str(user_id))
        ]
        if not players:
            try:
                return Player.objects.get(user__id=user_id,
                                          table__id=self.table.id)
            except Player.DoesNotExist:
                return None

        assert len(players) == 1, (
            "Sanity check fail: multiple players returned"
        )
        return players[0]

    def player_by_player_id(self, player_id):
        players = [
            p for p in self.players
            if p.id == player_id or str(p.id) == str(player_id)
        ]
        if not players:
            return None
        assert len(players) == 1, (
            "Sanity check fail: multiple players returned"
        )
        return players[0]

    def player_by_username(self, username):
        players = [p for p in self.players if p.username == username]
        if not players:
            return None
        assert len(players) == 1, (
            "Sanity check fail: multiple players returned"
        )
        return players[0]

    def is_out_of_time(self, player):
        autofold_delay = self.seconds_to_act() + player.timebank_remaining
        should_have_acted_by = (self.table.last_action_timestamp
                                 + timedelta(seconds=autofold_delay))
        return timezone.now() > should_have_acted_by

    def is_legal_betsize(self, player, amt):
        if amt == player.stack:
            return True
        elif amt > player.stack:
            return False

        if amt - self.last_raise_size() >= self.last_raise_diff():
            return True

        return False

    def is_legal_buyin(self, player, amt, include_pending_rebuy=True):
        if player is None:
            amt_adjusted = amt
        else:
            pending_rebuy = player.pending_rebuy if include_pending_rebuy \
                            else 0
            amt_adjusted = amt + player.stack + pending_rebuy
        return (
            self.table.min_buyin <= amt_adjusted <= self.table.max_buyin
            and amt > 0
        )

    def legal_min_buyin(self, player):
        current_amt = player.stack + player.pending_rebuy

        if current_amt >= self.table.min_buyin:
            return 1
        else:
            return self.table.min_buyin - current_amt

    def legal_max_buyin(self, player):
        current_amt = player.stack + player.pending_rebuy

        if current_amt >= self.table.max_buyin:
            return 0
        else:
            return self.table.max_buyin - current_amt

    def last_raise_diff(self):
        raises = {p.uncollected_bets for p in self._filter_active_players()}
        if raises:
            raise_size = max(raises)
            raises.remove(raise_size)
            if raises:
                before_that = max(raises)
                return raise_size - before_that
            else:
                return raise_size

        return 0

    def last_raise_size(self):
        return max(p.uncollected_bets for p in self._filter_active_players())

    def next_to_act(self):
        players = self.players_in_acting_order()

        # takes 2 to tango
        if len(players) < 2:
            return None

        players_with_chips = [p for p in players if p.stack > 0]
        # make sure that there is at least one non-allin player
        if len(players_with_chips) == 0 or self.is_predeal():
            return None
        # if just one, check to see if there has been action this round
        #   (i.e. not dealing out all-in)
        if len(players_with_chips) == 1 and self.last_raise_size() == 0:
            return None

        # if anyone with chips left has not yet acted,
        #   then return the first one
        last_raiser = None
        for player in players:
            if player.stack > 0 and self.has_not_acted(player):
                return player
            elif player.last_action in (Event.BET, Event.RAISE_TO):
                if (last_raiser is None
                    or player.uncollected_bets > last_raiser.uncollected_bets):
                    last_raiser = player

        # otherwise, we need to find the largest raise at the table
        #   of those players, return the first with chips left
        #   whose amt wagered < raiser
        if last_raiser:
            for player in rotated(players, players.index(last_raiser)):
                bet_lss = player.uncollected_bets < last_raiser.uncollected_bets
                if player.stack > 0 and bet_lss:
                    return player

        return None

    def has_not_acted(self, player):
        return player.last_action in (None, Event.POST)

    def robot_is_next(self):
        next_player = self.next_to_act()
        if next_player:
            return next_player.is_robot
        return False

    def hu_blinds_wait_edgecase_players(self, bb_idx):
        # there is an edge case that looks like this:
        #   0: BB
        #   1: BTN/SB
        #   2... any number of players who just sat in
        # when this happens, one more hand needs to be played head-up so that
        #   the bb can rotate onto a new player
        already_in = self.active_players(include_pending_at_idx=bb_idx)

        if len(already_in) != 2:
            return []

        return [
            plyr for plyr in self.seated_players()
            if plyr.playing_state == PlayingState.SIT_IN_PENDING
        ]

    def btn_sb_locations(self, next_sb, next_bb, curr_bb_idx):
        if (len(self.active_players(include_pending_at_idx=next_bb)) == 2
                    or self.hu_blinds_wait_edgecase_players(next_bb)):
            already_in = self.active_players()
            assert len(already_in) == 2, \
                'sanity check fail: hu_blinds_edgecase when not hu'
            sb_player = [
                plyr for plyr in already_in
                if plyr.position != next_bb
            ].pop()
            return sb_player.position, sb_player.position
        else:
            next_btn = (next_sb - 1) % self.table.num_seats
            # active_only; cannot sit in at btn
            plyr = self.players_at_position(next_btn, active_only=True)
            while not plyr:
                next_btn = (next_btn - 1) % self.table.num_seats
                assert next_btn != next_bb, \
                    'Sanity check fail: btn rotated back onto bb'
                plyr = self.players_at_position(next_btn, active_only=True)

            return next_btn, next_sb

    def must_wait_to_sit_in_players(self, next_btn_idx, next_bb_idx):
        if self.is_new_round():
            return []

        already_in = self.active_players(include_pending_at_idx=next_bb_idx)
        if len(already_in) == 2:
            return self.hu_blinds_wait_edgecase_players(next_bb_idx)
        else:
            players = []
            pos = next_btn_idx
            while pos != next_bb_idx:
                plyr = self.players_at_position(pos)
                if plyr and plyr.playing_state == PlayingState.SIT_IN_PENDING:
                    players.append(plyr)

                pos = (pos + 1) % self.table.num_seats

        return players

    def player_is_active_or_pending(self, player):
        if player is None:
            return False

        return (player.is_active()
                or player.playing_state == PlayingState.SIT_IN_PENDING)

    def next_bb_location_info(self, curr_bb_idx):
        skipped_positions = []
        next_bb = (curr_bb_idx + 1) % self.table.num_seats
        next_player = self.players_at_position(next_bb)

        # move the bb to the first player who can post it.
        while not self.player_is_active_or_pending(next_player):
            skipped_positions.append(next_bb)
            next_bb = (next_bb + 1) % self.table.num_seats
            assert next_bb != curr_bb_idx, \
                "Sanity check fail: bb rotated back onto itself"
            next_player = self.players_at_position(next_bb)

        return (next_bb, skipped_positions)

    def next_sb_location_info(self, curr_sb_idx, next_bb_idx):
        next_sb = (curr_sb_idx + 1) % self.table.num_seats
        skipped_positions = []
        while True:
            # active_only; player can't sit in at sb
            player = self.players_at_position(next_sb, active_only=True)
            bb_is_next = (next_sb + 1) % self.table.num_seats == next_bb_idx

            if not (player or bb_is_next):
                skipped_positions.append(next_sb)
                next_sb = (next_sb + 1) % self.table.num_seats
            else:
                break

        return next_sb, skipped_positions

    def is_effectively_new_game_edgecase(self):
        ready = self.players_who_can_play()
        already_in = self.active_players()
        return len(already_in) <= 1 < len(ready)

    def btn_idx_for_new_hand(self):
        plyrs = self.players_who_can_play()
        already_in = self.active_players()
        n_already_in = len(already_in)
        # n_already_in == 0 is an edgecase where everyone from the previous
        #   hand sat out simultaneously, and more than one player queued
        #   a sit in
        if (n_already_in == len(plyrs)
                or self.is_first_hand()
                or n_already_in == 0):
            random_next_player_idx = secure_random_number(max_num=len(plyrs))
            btn_idx = plyrs[random_next_player_idx].position
        else:
            assert n_already_in == 1, \
                    "This should only happen when btn is locked "\
                    "or in the effectively_new_game_edgecase"
            btn_idx = already_in[0].position

        return btn_idx

    def player_hand(self, player: Player):
        return best_hand_from_cards(player.cards + self.table.board)

    def has_gte_hand(self, player1, player2):
        winners = self.winners([player1, player2])
        return player1 in winners

    def sidepot_members(self, rotate=0, exclude_uncollected_bets=False):
        actives = self.active_players(rotate)
        if not actives:
            return []

        def get_wagers(p):
            if exclude_uncollected_bets:
                return p.wagers - p.uncollected_bets
            return p.wagers

        max_wager = max(get_wagers(p) for p in actives)
        return [
            p for p in actives
            if (
                get_wagers(p) > 0 and
                p.last_action not in FOLD_OR_TOGGLE_PENDING and
                not p.stack and
                get_wagers(p) < max_wager
            )
        ]

    def player_has_balance(self, player, amt):
        if self.table.is_tutorial:
            return True

        return player.user.userbalance().balance >= amt

    def sidepot_summary(self, exclude_uncollected_bets=False):
        '''
            returns a list of the sidepots in order of the
            [main pot, sidepot involving smallest...biggest stacks]
        '''
        def get_wagers(p):
            if exclude_uncollected_bets:
                return p.wagers - p.uncollected_bets
            return p.wagers

        sidepot_members = self.sidepot_members()
        sidepot_members.sort(key=lambda p: get_wagers(p))

        sidepots = []
        last_allin_amt = Decimal(0)
        actives = self.active_players()
        sidepot = sum(p.dead_money for p in actives)

        for p in sidepot_members:
            allin_amt = get_wagers(p)

            if allin_amt > last_allin_amt:
                contributors = set()

                for player in actives:
                    if last_allin_amt < get_wagers(player) < allin_amt:
                        sidepot += get_wagers(player) - last_allin_amt
                        contributors.add(player)
                    elif allin_amt <= get_wagers(player):
                        sidepot += allin_amt - last_allin_amt
                        contributors.add(player)

                sidepots.append((sidepot, contributors))
                last_allin_amt = allin_amt

                sidepot = 0

        # sidepot added here for edgecase where there is only dead
        #   money in the center
        last_pot = sidepot + sum(
            get_wagers(p) - last_allin_amt for p in actives
            if get_wagers(p) > last_allin_amt
        )
        last_contributors = {
            p for p in actives
            if get_wagers(p) > last_allin_amt
        }

        if last_pot:
            sidepots.append((last_pot, last_contributors))

        return sidepots

    def frontend_sidepot_summary(self, exclude_uncollected_bets=True):
        return idx_dict(
            {'amt': value}
            for value in self.player_contributions(exclude_uncollected_bets)
        )

    def min_bet_amt(self):
        players = self.active_players()
        order = [
            Event.RAISE_TO,
            Event.BET,
            Event.POST,
        ]
        players.sort(key=lambda p: p.wagers, reverse=True)
        players.sort(key=lambda p: order.index(p.last_action)
                                    if p.last_action in order
                                    else 999)

        if players and players[0].last_action in (Event.BET, Event.POST):
            return 2 * players[0].uncollected_bets
        elif players and players[0].last_action == Event.RAISE_TO:
            return (  players[0].uncollected_bets
                    + players[0].uncollected_bets
                    - players[1].uncollected_bets)

        assert self.table.bb, 'Table has no big blind set.'
        return self.table.bb

    def call_amt(self, player=None, diff=False):
        '''
        diff:
            False: total size of uncollected bets after calling
            True: amt more to put into the pot, given uncollected_bets
        '''
        showdown_players = self.showdown_players(0)
        assert showdown_players, \
            "call_amt() called when there are no players left in the hand"
        amt = max(plyr.uncollected_bets for plyr in showdown_players)
        if player is not None:
            if diff:
                return min(amt - player.uncollected_bets,
                        player.stack_available - player.uncollected_bets)
            return min(amt, player.stack_available)
        return amt

    def is_predeal(self):
        if sum(len(player.cards) for player in self.players) == 0:
            return True

        # if anyone hasn't been dealt their cards yet, return True
        n_cards = NUM_HOLECARDS[self.table.table_type]
        for plyr in self.predeal_active_players():
            if (len(plyr.cards) < n_cards
                    and plyr.last_action not in (Event.FOLD, Event.SIT_OUT)):
                return True
        return False

    def is_preflop(self):
        return len(self.table.board) == 0

    def is_flop(self):
        return len(self.table.board) == 3

    def is_turn(self):
        return len(self.table.board) == 4

    def is_river(self):
        return len(self.table.board) == 5

    def is_river_or_end(self):
        return self.is_river() or len(self.showdown_players()) == 1

    def hand_is_over(self):
        return self.next_to_act() is None and self.is_river_or_end()

    def seconds_since_last_action(self):
        if self.table.last_action_timestamp is None:
            return None
        timestamp_diff = (timezone.now() - self.table.last_action_timestamp)
        return timestamp_diff.total_seconds()

    def seconds_to_act(self):
        next_plyr = self.next_to_act()
        if next_plyr is None:
            return 0

        basetime = self.table.seconds_per_action_base \
                 + self.newbie_time_bonus(next_plyr)

        num_blinds_in_pot = self.current_pot() / self.table.bb
        if num_blinds_in_pot < 10:
            return basetime
        elif num_blinds_in_pot < 20:
            increment = self.table.seconds_per_action_increment
            return basetime + increment
        elif num_blinds_in_pot < 40:
            increment = self.table.seconds_per_action_increment * 2
            return basetime + increment
        elif num_blinds_in_pot < 80:
            increment = self.table.seconds_per_action_increment * 3
            return basetime + increment
        elif num_blinds_in_pot < 160:
            increment = self.table.seconds_per_action_increment * 4
            return basetime + increment
        elif num_blinds_in_pot < 320:
            increment = self.table.seconds_per_action_increment * 5
            return basetime + increment
        else:
            increment = self.table.seconds_per_action_increment * 6
            return basetime + increment

    def newbie_time_bonus(self, player):
        if player.n_hands_played < 100:
            return 15

        if player.n_hands_played < 200:
            return 14

        if player.n_hands_played < 300:
            return 13

        if player.n_hands_played < 400:
            return 12

        if player.n_hands_played < 500:
            return 11

        # 10s at 600-1000, 9s at 1-2k, 8s at 2-3k, ... 0 at 10000
        return max((10999 - player.n_hands_played) // 1000, 0)

    def pot_raise_size(self):
        player = self.next_to_act()

        pot_amt = self.current_pot()

        if not player:
            return pot_amt

        call_amt = self.call_amt()
        call_diff = call_amt - player.uncollected_bets

        total_pot = pot_amt + call_diff

        # if total_pot == 6:
        #     import ipdb; ipdb.set_trace()

        return call_amt + total_pot

    def players_who_showed_down(self):
        return [
            plyr for plyr in self.active_players()
            if plyr.last_action != Event.FOLD
        ]

    def bots_who_should_sit_in(self):
        return [
            plyr for plyr in self.seated_players()
            if (
                plyr.is_robot
                and not plyr.playing_state == PlayingState.SIT_IN_PENDING
                and plyr.is_sitting_out()
                and Action.SIT_IN in self.available_actions(plyr)
            )
        ]

    def pos_str(self, player):
        tbl = self.table
        if player.position == tbl.btn_idx and player.position == tbl.sb_idx:
            return 'btn/sb'
        elif player.position == tbl.btn_idx:
            return 'btn'
        elif player.position == tbl.sb_idx:
            return 'sb'
        elif player.position == tbl.bb_idx:
            return 'bb'

        return ''

    # use this when debugging
    def describe(self, print_me=True):
        tbl = self.table

        desc = [
            f'{tbl.name}\t{tbl.sb}/{tbl.bb} {tbl.table_type}\t'
            f'hand {tbl.hand_number}'
        ]
        desc.append(f'board: {str(tbl.board)}')

        # try:
        #     rotate_to = self.first_to_act_pos()
        # except:
        #     rotate_to = 0

        def cards_or_state(player):
            state = player.playing_state
            if state == PlayingState.SITTING_IN:
                cards_str = ','.join(str(card) for card in player.cards)
                cards_str = cards_str or 'in'
            elif state == PlayingState.SITTING_OUT:
                cards_str = 'out'
            elif state == PlayingState.SIT_IN_PENDING:
                cards_str = 'pend:in'
            elif state == PlayingState.SIT_OUT_PENDING:
                cards_str = 'pend:out'
            elif state == PlayingState.SIT_IN_AT_BLINDS_PENDING:
                cards_str = 'pend:blinds'
            elif state == PlayingState.LEAVE_SEAT_PENDING:
                cards_str = 'pend:leave'
            elif state == PlayingState.DISCONNECTED:
                cards_str = 'disc'
            elif state == PlayingState.TOURNEY_SITTING_OUT:
                cards_str = 'afk(tourn)'
            else:
                print('unknown playing_state!!!!')
                import ipdb; ipdb.set_trace()

            return f'[{cards_str:^11}]'

        fmt_str = '{:>6} {}: {:^10}\t{:^13}\t{:^7} - {:^7} - {:^12}({})'
        desc.append(
            fmt_str.format('pos', '#', 'name', 'cards/state', 'stack',
                           'wagers', 'last_action', 'uncollected')
        )
        desc += [
            fmt_str.format(self.pos_str(plyr),
                            plyr.position,
                            plyr.username[:10],
                            cards_or_state(plyr),
                            plyr.stack,
                            plyr.wagers,
                            plyr.last_action or 'none',
                            plyr.uncollected_bets)
            for plyr in rotated(self.seated_players(), 0)
        ]

        output = '\n'.join(desc)
        if print_me:
            print(output)
        else:
            return output

    def detailed_state(self, print_me=True):
        acc = self
        desc = []
        desc.append("==PLAYER STATE==")
        desc.append('pos\tname\tstack\twagers\tuncollected\tlast_action')
        for plyr in acc.active_players():
            pos_str = self.pos_str(plyr)
            desc.append('{}\t{:<5}\t{}\t{}\t{}\t{}'.format(pos_str,
                                                        plyr.username[:5],
                                                        plyr.stack,
                                                        plyr.wagers,
                                                        plyr.uncollected_bets,
                                                        plyr.last_action))

        desc.append('--------------------')
        uncollected = sum(p.uncollected_bets for p in acc.players)
        wagers = sum(p.wagers for p in acc.players)
        stacks = sum(p.stack for p in acc.players)
        desc.append(f'total\t{stacks}\t{wagers}\t{uncollected}\n')
        desc.append('==SIDEPOT SUMMARY==')
        desc.append('pot_amt\tplayers')
        for pot, ppl in acc.sidepot_summary(exclude_uncollected_bets=True):
            desc.append(f'{pot:<7}\t{ppl}')

        output = '\n'.join(desc)
        if print_me:
            print(output)
        else:
            return output


class HoldemAccessor(PokerAccessor):
    """Default poker is hold'em, so no need to override anything"""
    pass


class OmahaAccessor(PokerAccessor):
    def player_hand(self, player: Player):
        return best_hand_using_holecards(player.cards, self.table.board)


class BountyAccessor(PokerAccessor):
    def bounty_call_amt(self, player, winner):
        return min(player.stack, winner.stack)

    def there_is_bounty_win(self):
        if not self.is_river_or_end() or self.next_to_act():
            return False

        showdown_players = self.showdown_players()
        if not showdown_players or not showdown_players[0].cards:
            return False

        bounty_hand = hand_to_description(showdown_players[0].cards)
        bounty = bounty_hand in BOUNTY_HANDS
        return len(showdown_players) == 1 and bounty

    def next_to_act(self):
        if self.table.bounty_flag:
            if not self.is_predeal() and self.is_preflop():
                bounty_winner = [
                    p for p in self.active_players()
                    if p.last_action is None
                ]
                # this means should only ever happen between
                #   the bounty_sequence and call_sequence in forced_flip
                if len(bounty_winner) > 1:
                    return None
                return bounty_winner[0] if len(bounty_winner) == 1 else None
            return None

        return super().next_to_act()


class IrishAccessor(PokerAccessor):
    """Accessor methods that need to change for irish poker"""

    def __init__(self):
        raise NotImplementedError('Irish is not yet implemented.')


class FreezeoutAccessor:
    def _unseated_actions(self):
        return []

    def _always_available_actions(self, player):
        return []

    def _buy_actions(self, player):
        return []

    def _sitting_toggle_actions(self, player):
        if player.playing_state == PlayingState.TOURNEY_SITTING_OUT:
            return [Action.SIT_IN]

        if player.playing_state == PlayingState.SITTING_IN:
            return [Action.SIT_OUT]

        # note: there is no PlayingState.SIT_OUT_AT_BLINDS; it's
        #   its own field on the Player model. Sorry future dev.
        msg = f'Sanity fail: PlayingState {player.playing_state.value}'\
               " shouldn't be possible in a tournament."
        raise Exception(msg)

    def tourney_first_to_act_grace_period(self, player):
        last_action = self.table.last_action_timestamp
        autofold_delay = timedelta(seconds=TOURNEY_AUTOFOLD_DELAY)
        return (
            self.is_acting_first(player)
            and timezone.now() < (last_action + autofold_delay)
        )

    def is_acting_first(self, player):
        necessary_conditions = (self.is_preflop()
                                and player.id == self.first_to_act().id)
        if self.heads_up():
            return necessary_conditions and player.last_action == Event.POST

        return necessary_conditions and player.last_action is None

    def has_not_acted(self, player):
        return (
            player.last_action in (None, Event.POST)
            or (player.last_action == Event.SIT_OUT
                and player.playing_state == PlayingState.TOURNEY_SITTING_OUT)
        )

    def tournament_is_over(self):
        return len(self.seated_players()) < 2

    def is_out_of_time(self, player):
        if player.playing_state == PlayingState.TOURNEY_SITTING_OUT:
            return not self.tourney_first_to_act_grace_period(player)
        return super().is_out_of_time(player)

    def heads_up(self):
        return len(self.seated_players()) == 2


class HoldemFreezeoutAccessor(FreezeoutAccessor, HoldemAccessor):
    pass


class OmahaFreezeoutAccessor(FreezeoutAccessor, OmahaAccessor):
    pass


class BountyFreezeoutAccessor(FreezeoutAccessor, BountyAccessor):
    def bounty_call_amt(self, player, _):
        bb = self.table.bb
        return min(player.stack, bb * BOUNTY_TOURNEY_BBS_TO_CALL)


def accessor_type_for_table(table):
    if table.table_type == NL_HOLDEM:
        if table.tournament:
            return HoldemFreezeoutAccessor
        return HoldemAccessor

    if table.table_type == NL_BOUNTY:
        if table.tournament:
            return BountyFreezeoutAccessor
        return BountyAccessor

    if table.table_type == PL_OMAHA:
        if table.tournament:
            return OmahaFreezeoutAccessor
        return OmahaAccessor

