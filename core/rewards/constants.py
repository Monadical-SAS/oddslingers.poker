from collections import defaultdict

from poker.constants import StrBasedEnum


class StrBasedEnumWithDescription(StrBasedEnum):
    @classmethod
    def from_str(cls, string: str):
        return cls._member_map_[string.upper()]

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

XSS_STRINGS = ('<script', 'alert(', 'drop table', 'or 1=1')
SWEAR_WORDS = ('fuck', 'shit')  # TODO: make this more... comprehensive...

BIG_WIN_BBS = 500
THE_DUCK_BBS = 400
# Badges for amount of hands
DEDICATED_HANDS = 5000
ADEPT_HANDS = 10000


NEWCOMER_BADGES = {
    # @showdown
    'shove': 'Bet or raise all-in',
    'big_bluff': 'Win a 200bb+ pot without showdown with a bottom 20%% '\
                 'hand',  # NOT IMPLEMENTED
    'big_call': 'Call a 50bb+ bet on the river with a bottom 20%% hand, '\
                'and win',  # NOT IMPLEMENTED
    'big_win': f'Win a {BIG_WIN_BBS}bb+ pot',
    'run_bad': 'Lose 800bbs or more in a continuous session',  # NOT IMPLEMENTED
    'marathon': 'Play 500 hands in a continuous session',  # NOT IMPLEMENTED
    'hello_world': 'Filled out profile information',
    'nice_session': 'Win 800bbs or more in a continuous session',  # NOT IMPLEMENTED
    'dedicated': f'Play at least {DEDICATED_HANDS} total hands',
    'adept': f'Play at least {ADEPT_HANDS} total hands',
}

EXCEPTIONAL_BADGES = {
    'the_teddy': 'Win with pocket aces against an Ax full house',
    'mike_mcd': 'Lose with an Ax full house against pocket aces ',
    'its_a_trap': 'Check-raise all-in on the river, get called, and win',  # NOT IMPLEMENTED
    'cool_hand_luke': 'Win a 500bb+ pot with a bottom 5%% hand',  # NOT IMPLEMENTED
    'bombs_away': 'Win a 300bb+ pot without ever facing a bet or raise',  # NOT IMPLEMENTED
    'true_grit': 'Win a 500bb+ pot without ever betting or raising',
    # NOT IMPLEMENTED
    'double_check_raise': 'Check-raise twice in the same hand and win the pot',
    'trifecta': 'Check-raise, check-raise, check-raise all-in and win',  # NOT IMPLEMENTED
    'quadfecta': 'Limp- or call-reraise, plus a trifecta',  # NOT IMPLEMENTED
    'soul_reader': 'Call on the river and win a pot with Jx or worse '\
                   'and no pair',  # NOT IMPLEMENTED
}


LEADERBOARD_WEEKLY_BADGES = {
    'golden_week': 'Finish week {} in 1st place Season {}',
    'silver_week': 'Finish week {} in 2nd place Season {}',
    'bronze_week': 'Finish week {} in 3rd place Season {}',
}


LEADERBOARD_YEARLY_BADGES = {
    'golden_season': 'Finish Season {} in 1st place',
    'silver_season': 'Finish Season {} in 2nd place',
    'bronze_season': 'Finish Season {} in 3rd place',
    'season_top_5': 'Finish Season {} in top 5',
    'season_top_10': 'Finish Season {} in top 10',
    'season_one_percent': 'Finish Season {} in top 1%',
    'season_five_percent': 'Finish Season {} in top 5%',
    'badgelord': 'Finish Season in top 1% with most unique badges',
}


NO_REWARD_BADGES = {
    # This have its own reward amount
    'completed': 'Earn all the easily obtained badges',
    # === bad behavior shame badges ===
    'black_hat': 'Attempt a technical exploit against Oddslingers',
    'potty_mouth': 'Attempted to use swear words on the site',

    # === Tournament badges ===
    'tourney_winner': 'Win a tournament',
}


BADGE_DESCRIPTIONS = {
    #  === EASILY-OBTAINED BADGES ===
    **NEWCOMER_BADGES,

    # === exceptional play or unusual hand badges ===
    # @showdown
    **EXCEPTIONAL_BADGES,

    # === win at the end of season/week ===
    **LEADERBOARD_WEEKLY_BADGES,
    **LEADERBOARD_YEARLY_BADGES,

    **NO_REWARD_BADGES,

    # === win with specific hands at showdown ===
    # @showdown
    'the_duck': f'Win a {THE_DUCK_BBS}bb+ pot with 72o at showdown',
    'quads': 'Win with four-of-a-kind',
    'straight_flush': 'Win with a straight flush at showdown',
    'steel_wheel': 'Win with an ace-to-5 straight flush at showdown',
    'royalty': 'Win with a royal flush at showdown',


    # === luck or wins/losses badges ===
    'champion': 'Win a tournament with at least 500 entrants',  # NOT IMPLEMENTED
    'because_it_is_there': 'Be the king-of-the-hill at the end of a week',  # NOT IMPLEMENTED
    # @showdown
    'so_many_chips': 'Obtain a play-chip balance of 1,000,000 chips or more',  # NOT IMPLEMENTED
    'play_chip_diety': 'Obtain a play-chip balance of 9,999,999 chips or '\
                       'more',  # NOT IMPLEMENTED
    'heater': 'Win at least 1000 bbs in one session',  # NOT IMPLEMENTED
    'sizzler': 'Win 1500 bbs in a 24-hour period',  # NOT IMPLEMENTED
    'god_mode': 'Win at least 2000 bbs in one session',  # NOT IMPLEMENTED
    'bad_beat': 'Lose with aces-full (using both holecards) or better',  # NOT IMPLEMENTED
    'cooler': 'Lose 300bbs or more with top 0.1%% hand',  # NOT IMPLEMENTED
    'suckout': 'Win an all-in with 1%% equity',  # NOT IMPLEMENTED
    'hes_on_fire': 'Get all-in and win three times in a row',  # NOT IMPLEMENTED
    'this_is_rigged': 'Lose 1000bbs or more in a continuous session',  # NOT IMPLEMENTED
    'bountytown': 'Achieve a 27 bounty',

    # === grinder badges ===
    # @showdown
    'just_one_more_hand': 'Play 5,000 hands in a continuous session',  # NOT IMPLEMENTED
    'cant_stop_wont_stop': 'Play 10,000 hands in a continuous session and '\
                           'in at least 500bbs',  # NOT IMPLEMENTED
    'grinder': 'Play 50,000 hands in a month',  # NOT IMPLEMENTED
    'true_grinder': 'Play 100,000 hands in a month',  # NOT IMPLEMENTED
    'capital_g_grinder': 'Play the more hands than any other player in a '\
                         'month',  # NOT IMPLEMENTED
    'fiend': 'Play 500,000 hands in a 1-year period',  # NOT IMPLEMENTED
    'veteran': 'Play at least 100,000 total hands',  # NOT IMPLEMENTED
    'pro': 'Play at least 500,000 total hands',  # NOT IMPLEMENTED
    'seen_it_all': 'Play a total of 1,000,000 hands',  # NOT IMPLEMENTED

    # === special alpha-release badges ===
    'bug_hunter': 'Report a bug that gets fixed',  # NOT IMPLEMENTED
    'genesis': 'One of the first 1000 accounts',
    'fearless_leader': 'Open an account before 2019',

    # === unique badges (only one person can hold at a time)
    'badgiest_badger': 'The player with the most badges',  # NOT IMPLEMENTED
    # @showdown, but global
    'king_of_the_hill': 'The biggest winner this week so far in KOTH points',  # NOT IMPLEMENTED

    # === incentivized behaviour badges ===
    'security_minded': 'Reviewed login history for suspicious activity',
    'good_samaritan': 'Manually awarded for recognized good behaviour',  # NOT IMPLEMENTED
    'streamer': 'Stream a session',  # NOT IMPLEMENTED
    'popular_streamer': 'Streamed play and got 100+ simultaneous viewers',  # NOT IMPLEMENTED
    'do_unto_others': 'Positive "handshake" balance',  # NOT IMPLEMENTED
}


BADGE_ICONS = defaultdict(lambda: 'reward.svg')
BADGE_ICONS.update({
    'black_hat': 'black_hat.png',
})


def get_badge_icon(badge_name):
    return f'/static/images/reward_icons/{BADGE_ICONS[badge_name]}'


BADGES_FOR_HANDS = {
    DEDICATED_HANDS: 'dedicated',
    ADEPT_HANDS: 'adept'
}

NEWCOMER_REWARD = 400
COMPLETED_NEWCOMER_REWARD = 2000
REGULAR_BADGE_REWARD = 2000
EXCEPTIONAL_UNUSUAL_REWARD = 10000
