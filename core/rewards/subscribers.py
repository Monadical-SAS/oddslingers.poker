import logging

from collections import defaultdict
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from oddslingers.utils import camelcase_to_capwords
from oddslingers.mutations import MutationList

from poker.subscribers import MutationSubscriber

from poker.constants import Event
from poker.cards import Card
from poker.rankings import handrank_encoding, best_hand_from_cards

from .constants import (
    BADGE_DESCRIPTIONS, get_badge_icon, BIG_WIN_BBS, THE_DUCK_BBS,
    BADGES_FOR_HANDS
)
from .mutations import award_badge


logger = logging.getLogger('root')


class BadgeSubscriber(MutationSubscriber):
    def __init__(self, accessor, log):
        self.accessor = accessor
        self.log = log
        self.to_broadcast = defaultdict(list)
        self.mutations: MutationList = []

    @property
    def table(self):
        return self.accessor.table

    def dispatch(self, subj, event, changes=None, **kwargs):
        try:
            new_badges = []
            if event == Event.SHOWDOWN_COMPLETE:
                new_badges = self.showdown_badges()
            elif event == Event.NEW_HAND:
                new_badges = self.new_hand_badges()
            elif event == Event.BET or event == Event.RAISE_TO:
                new_badges = self.aggressor_badges(subj, event, **kwargs)
            elif event == Event.FINISH_TOURNAMENT:
                new_badges = self.tournament_winner_badges(kwargs['winner'])
            elif event == Event.BOUNTY_WIN:
                new_badges = [(subj, 'bountytown')]

            for new_badge in new_badges:
                self.add_badge(*new_badge)

        except Exception:
            logger.exception('BadgeSubscriber Error', extra={
                'event': event,
                'subj': subj,
                **kwargs,
            })

    def add_badge(self, player, badge_name, max_times=None):
        self.mutations += award_badge(
            player.user,
            badge_name,
            max_times
        )
        self.to_broadcast[player].append(
            self._get_badge_to_broadcast(badge_name)
        )

    def tournament_winner_badges(self, winner):
        return [(winner, 'tourney_winner')]

    def showdown_badges(self):
        if self.accessor.table.bounty_flag:
            return []

        player_winnings = self.player_winnings_from_history()
        output = (
            *self.large_win_badges(player_winnings),
            *self.specific_hand_badges(player_winnings),
            *self.profile_updates(),
        )

        return output

    def new_hand_badges(self):
        badges = []
        for player in self.accessor.active_players():
            # TODO: determine how to keep this value up-to-date without
            # refresh_from_db on every subscriber dispatch
            # (refresh is currently located in PokerAccessor.commit)
            hands_played = player.user.userstats().hands_played
            if hands_played in BADGES_FOR_HANDS.keys():
                badges.append((player, BADGES_FOR_HANDS[hands_played],))

        return badges

    def aggressor_badges(self, subj, event, **kwargs):
        if (subj.stack_available - kwargs['amt'] == 0):
            return [(subj, 'shove')]

        return []

    def commit(self):
        super().commit()
        self.to_broadcast = defaultdict(list)

    def _get_badge_to_broadcast(self, badge_name):
        badge_title = camelcase_to_capwords(badge_name)
        return {
            'type': 'badge',
            'subtype': badge_name,
            'bsStyle': 'warning',
            'ts': timezone.now(),
            'title': f'{badge_title} achieved!',
            'description': BADGE_DESCRIPTIONS[badge_name],
            'url': reverse('UserProfile'),
            'icon': get_badge_icon(badge_name),
        }

    def updates_for_broadcast(self, player=None, spectator=None):
        return {'badge_notifications': self.to_broadcast[player]}

    def recent_hh(self):
        return self.log.current_hand_log(player='all')['hands'][0]

    def player_winnings_from_history(self):
        history = self.recent_hh()['events']
        wins = [rec for rec in history if rec['event'] == 'WIN']
        player_winnings = {
            self.accessor.player_by_username(player_name): [
                win['args'] for win in wins
                if win['subj'] == player_name
            ]
            for player_name in set(win['subj'] for win in wins)
        }
        return {
            player: {
                'total': sum([
                    Decimal(win['amt'])
                    for win in player_winnings[player]
                ]),
                'showdown': sum([
                    Decimal(win['amt'])
                    for win in player_winnings[player]
                    if win['showdown']
                ]),
                'non-showdown': sum([
                    Decimal(win['amt']) for win in player_winnings[player]
                    if not win['showdown']
                ]),
            }
            for player in player_winnings.keys()
        }

    def large_win_badges(self, player_winnings):
        badges = []
        for winner, winnings in player_winnings.items():
            if winnings['total'] > BIG_WIN_BBS * self.table.bb:
                if self.rivals_in_showdown(winner):
                    badges.append((winner, 'big_win'))

                if not self.did_raise_or_bet(winner):
                    # Third item in the tuple goes for 'max_times'
                    badges.append((winner, 'true_grit', 1))

            if (winnings['showdown'] > THE_DUCK_BBS * self.table.bb
                    and '2' in winner.cards_str
                    and '7' in winner.cards_str):
                badges.append((winner, 'the_duck'))

        return badges

    def rivals_in_showdown(self, winner):
        return [
            plyr for plyr in self.accessor.players_who_showed_down()
            if plyr != winner
        ]

    def specific_hand_badges(self, player_winnings):
        badges = []
        for player in player_winnings.keys():
            if player_winnings[player]['showdown'] == 0:
                continue

            handrank = handrank_encoding(self.accessor.player_hand(player))
            # handrank[0] is 8 (str8 flush) to 0 (high card)
            #   and handrank[1:] are kickers
            if handrank[0] == 8:  # str8 flush
                badges.append((player, 'straight_flush'))
                if handrank[1] == '5':
                    badges.append((player, 'steel_wheel'))
                elif handrank[1] == 'A':
                    badges.append((player, 'royalty'))
            elif handrank[0] == 7:  # quads
                badges.append((player, 'quads'))
            elif (handrank[0] == 6  # full house
                    and handrank[1] == 'A'  # aces full
                    and player.cards_str.count('A') == 2):
                for opp in self._players_who_showed_down():
                    opp_cards_str = self.recover_opponent_cards_str(opp)
                    if opp_cards_str.count('A') == 1:
                        opp_cards = [
                            Card(card)
                            for card in opp_cards_str.split(',')
                        ] + self.table.board
                        opp_hand = best_hand_from_cards(opp_cards)
                        hr = handrank_encoding(opp_hand)
                        if hr[0] == 6:
                            badges.append((player, 'the_teddy'))
                            badges.append((opp, 'mike_mcd'))

        return badges

    def _players_who_showed_down(self):
        return [
            plyr for plyr in self.accessor.active_players()
            if plyr.last_action != Event.FOLD
        ]

    def did_raise_or_bet(self, player):
        bets_and_raises = [
            rec for rec in self.recent_hh()['events']
            if (rec['event'] in ('RAISE_TO', 'BET')
                    and rec['subj'] == player.username)
        ]
        return len(bets_and_raises) != 0

    def profile_updates(self):
        # TODO
        return []

    def recover_opponent_cards_str(self, opponent):
        # import ipdb; ipdb.set_trace()
        if opponent.cards_str:
            return opponent.cards_str
        else:
            player_records = [
                rec for rec in self.recent_hh()['events']
                if rec['subj'] == opponent.username
            ]
            # make sure this isn't being used incorrectly.
            #   may have to remove this check later if it's used in
            #   contexts other than checking mucked hands
            assert 'MUCK' in [rec['event'] for rec in player_records]
            original_hand = ','.join([
                record['args']['card']
                for record in player_records
                if record['event'] == 'DEAL'
            ])
        return original_hand
