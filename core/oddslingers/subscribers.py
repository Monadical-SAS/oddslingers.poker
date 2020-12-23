from poker.subscribers import MutationSubscriber
from poker.constants import Event
from poker.models import PokerTable

from oddslingers.mutations import increase_hands_played


class UserStatsSubscriber(MutationSubscriber):

    @property
    def players(self):
        return self.accessor.active_players()

    def dispatch(self, subj, event, changes=None, **kwargs):
        if isinstance(subj, PokerTable) and event == Event.END_HAND:
            for player in self.players:
                self.mutations += increase_hands_played(player)
