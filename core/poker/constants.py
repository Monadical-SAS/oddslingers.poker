import pytz
from os import path
from datetime import datetime

from oddslingers.settings import BASE_DIR
from oddslingers.utils import StrBasedEnum

# GAME TYPES
NL_HOLDEM = 'NLHE'
PL_OMAHA = 'PLO'
NL_BOUNTY = 'BNTY'

TABLE_TYPES = (
    (NL_HOLDEM, 'No Limit Hold \'em'),
    (PL_OMAHA, 'Pot Limit Omaha'),
    (NL_BOUNTY, 'No Limit Bounty'),
)

NUM_HOLECARDS = {
    NL_HOLDEM: 2,
    NL_BOUNTY: 2,
    PL_OMAHA: 4,
}

ANALYTIC_HAND_THRESHOLDS = (1000, 2000, 5000, 10000, 25000, 50000, 100000)

HIDE_TABLES_AFTER_N_HANDS = 500
TOURNAMENT_CANCEL_HOURS = 12

NEW_HAND_STR = "====NEW HAND===="
TABLE_SUBJECT_REPR = "DEALER"

SIDE_EFFECT_SUBJ = "side_effect"

HH_TEST_PATH = path.join(BASE_DIR, 'poker/tests/data')

MAX_ORBITS_SITTING_OUT = 3

BOUNTY_HANDS = ('72o', '72s')

SIDEBET_STATUS = (
    ('opening', 'Opening'),
    ('active', 'Active'),
    ('closing', 'Closing'),
    ('closed', 'Closed'),
)
# !!! DO NOT CHANGE ENUM NUMBERS !!!

# an Action is what comes into a controller from the event queue
#   this is effectively the player interface (with the exception of
#   timeout_fold)

class Action(StrBasedEnum):
    BET = 1
    RAISE_TO = 2
    CALL = 3
    CHECK = 4
    FOLD = 5
    TIMEOUT_FOLD = 6 # deprecated

    BUY = 7
    TAKE_SEAT = 8
    LEAVE_SEAT = 9
    SIT_IN = 10
    SIT_OUT = 11
    SIT_OUT_AT_BLINDS = 12
    SET_AUTO_REBUY = 13
    SIT_IN_AT_BLINDS = 16
    SET_PRESET_CHECKFOLD = 17
    SET_PRESET_CHECK = 18
    SET_PRESET_CALL = 19
    CREATE_SIDEBET = 20
    CLOSE_SIDEBET = 21

# Events are the controller's internal state change interface
class Event(StrBasedEnum):
    DEAL = 1
    POST = 2
    POST_DEAD = 3
    ANTE = 4
    BET = 5
    RAISE_TO = 6
    CALL = 7
    CHECK = 8
    FOLD = 9
    BUY = 10
    TAKE_SEAT = 11
    LEAVE_SEAT = 12
    SIT_IN = 13
    SIT_OUT = 14
    WIN = 15
    RETURN_CHIPS = 16
    OWE_SB = 18
    OWE_BB = 19
    SET_BLIND_POS = 20
    NEW_HAND = 21
    NEW_STREET = 22
    POP_CARDS = 24
    UPDATE_STACK = 26
    SIT_IN_AT_BLINDS = 28
    SIT_OUT_AT_BLINDS = 29
    SET_AUTO_REBUY = 30
    CREATE_TRANSFER = 31
    ADD_ORBIT_SITTING_OUT = 33
    END_HAND = 34
    SET_TIMEBANK = 36
    RECORD_ACTION = 37
    CHAT = 38
    NOTIFICATION = 39
    SET_BOUNTY_FLAG = 40
    REVEAL_HAND = 41
    DELAY_COUNTDOWN = 42
    RESET = 43
    SET_PRESET_CHECKFOLD = 44
    SET_PRESET_CHECK = 45
    SET_PRESET_CALL = 46
    MUCK = 47
    WAIT_TO_SIT_IN = 48
    SHOWDOWN_COMPLETE = 49
    BOUNTY_WIN = 50
    SET_BLINDS = 51
    FINISH_TOURNAMENT = 52
    CREATE_SIDEBET = 53
    CLOSE_SIDEBET = 54
    SHUFFLE = 55


# all chip movements will get to the front end with an 'amt' keyword
class AnimationEvent(StrBasedEnum):
    DEAL = 1 # self-explanatory
    POST = 2 # should be same as bet
    POST_DEAD = 3 # same as bet, except shown in the center
    ANTE = 4 # chips go directly to the center (combo of bet & new_street)
    BET = 5 # chips move to in front of player
    RAISE_TO = 6 # same as bet
    CALL = 7 # same as bet
    CHECK = 8 # player box 'blinks' or something
    FOLD = 9 # cards are discarded to center and disappear
    TAKE_SEAT = 10 # player box changes to inclu'de a new player
    LEAVE_SEAT = 11 # player box changes to become empty
    SIT_IN = 12 # same as check
    SIT_OUT = 13 # same as check
    WIN = 14 # chips move from the center pot to the player
    SET_BLIND_POS = 15 # move btn from the previous position to the new one
    NEW_HAND = 16 # some sort of deck shuffle animation
    NEW_STREET = 17 # chips go from in front of players to the table center
    UPDATE_STACK = 18 # something to show a player's stack changed
    RESET = 19 # clear board, player cards, uncollected bets from table
    REVEAL_HAND = 20 # player's hand is shown to the rest of the table
    RETURN_CHIPS = 21 # return uncalled chips
    MUCK = 22 # player's hand is discarded. visually similar to FOLD
    BOUNTY_WIN = 23 # Player wins bounty: 7 & 2 become bigger and gold

    @classmethod
    def from_event(cls, event: Event):
        try:
            return cls._member_map_[event.name]
        except KeyError:
            raise ValueError(f"No AnimationEvent for Event.{event.name}")


class PlayingState(StrBasedEnum):
    SITTING_IN = 1  # sitting into the game, ready to play
    SITTING_OUT = 2  # sitting out; inactive
    SIT_IN_PENDING = 3  # 'sit_in' during a hand; unprocessed
    SIT_OUT_PENDING = 4  # 'sit_out' during a hand; unprocessed
    SIT_IN_AT_BLINDS_PENDING = 5  # sitting out, but ready to play at blinds
    LEAVE_SEAT_PENDING = 6  # 'leave_seat' during a hand; unprocessed
    DISCONNECTED = 7  # this isn't used anywhere
    TOURNEY_SITTING_OUT = 8  # player is treated as in, but auto-folds

ACTIVE_PLAYSTATES = (
    PlayingState.SITTING_IN,
    PlayingState.SIT_OUT_PENDING,
    PlayingState.LEAVE_SEAT_PENDING,
    PlayingState.TOURNEY_SITTING_OUT,
)

BLINDS_SCHEDULE = [
    (25, 50),
    (40, 80),
    (50, 100),
    (75, 150),
    (100, 200),
    (150, 300),
    (250, 500),
    (300, 600),
    (400, 800),
    (500, 1000),
    (600, 1200),
    (750, 1500),
    (1000, 2000),
    (1200, 2400),
    (1500, 3000),
    (2000, 4000),
    (2500, 5000),
    (3000, 6000),
    (4000, 8000),
    (5000, 10000),
    (6000, 12000),
    (7500, 15000),
    (10000, 20000),
    (12000, 24000),
    (15000, 30000),
    (20000, 40000),
    (25000, 50000),
    (30000, 60000),
    (40000, 80000),
    (50000, 100000),
]

CASHTABLES_LEVELUP_BONUS = 200
N_BB_TO_NEXT_LEVEL = 2000
CASH_GAME_BBS = [
    2,
    4,
    6,
    10,
    20,
    50,
    100,
    200,
    400,
    1000,
    2000,
    4000,
    10000,
]

TOURNEY_BUYIN_TIMES = 20
TOURNEY_BUYIN_AMTS = [
    200,
    400,
    600,
    1000,
    2000,
    5000,
    10000,
    20000,
    40000,
    100000,
]

class TournamentStatus(StrBasedEnum):
    PENDING = 1
    STARTED = 2
    FINISHED = 3
    CANCELED = 4

TOURNEY_STARTING_CHIPS = '5000.00'
HANDS_TO_INCREASE_BLINDS = 10

ANIMATION_DELAYS = {
    Event.REVEAL_HAND: 2,
    Event.WIN: 2,
}

FOLD_OR_TOGGLE_PENDING = (Event.SIT_IN, Event.FOLD,
                          Event.SIT_OUT, Event.LEAVE_SEAT)

PLAYER_API = (
    Event.TAKE_SEAT, Event.LEAVE_SEAT, Event.SIT_IN, Event.SIT_OUT,
    Event.BET, Event.RAISE_TO, Event.CALL, Event.CHECK, Event.FOLD,
    Event.BUY, Event.SIT_IN_AT_BLINDS, Event.SIT_OUT_AT_BLINDS,
    Event.SET_AUTO_REBUY)

ACTIVE_ACTIONS = (Action.FOLD, Action.BET, Action.RAISE_TO, Action.CALL,
                  Action.CHECK)

VISIBLE_ACTIONS = (
    *ACTIVE_ACTIONS, Action.SIT_OUT, Action.SIT_IN, Action.LEAVE_SEAT
)

SIDEBET_ACTIONS = (Action.CREATE_SIDEBET, Action.CLOSE_SIDEBET)

PLAYER_ACTION_ANIMATION_EVENTS = (
    AnimationEvent.FOLD, AnimationEvent.BET, AnimationEvent.RAISE_TO,
    AnimationEvent.CALL, AnimationEvent.CHECK
)

ACTION_TYPES = [(a.value, a.name) for a in Action]

HAND_SAMPLING_CAP = 20

TAKE_SEAT_BEHAVIOURS = (
    PlayingState.SITTING_OUT,
    PlayingState.SIT_IN_AT_BLINDS_PENDING,
    PlayingState.SIT_IN_PENDING,
)
# This constant will be 15 for now but once the frontend time delay problem
# is solved, it should be moved back to 7 or less.
TOURNEY_AUTOFOLD_DELAY = 10
BOUNTY_TOURNEY_BBS_TO_CALL = 5

THRESHOLD_BB_FOR_BOTS = 100
THRESHOLD_BB_EMAIL_VERIFIED = 50

BUMP_AFTER_INACTIVE_MINS = 10

BETWEEN = datetime(2019, 1, 2, 21, 8, 17, tzinfo=pytz.utc)
SEASONS = {
    0: (
        datetime(year=2016, month=1, day=3, tzinfo=pytz.utc),  # 2016-1-3
        BETWEEN,
    ),
    1: (
        BETWEEN,
        datetime(year=2021, month=1, day=1, tzinfo=pytz.utc),  # 2020-1-1
    )
}


# Used in refresh_from_db calls in replayer for django >= 2.1
PLAYER_REFRESH_FIELDS = (
    'stack', 'wagers', 'uncollected_bets', 'dead_money', 'auto_rebuy',
    'pending_rebuy', 'preset_call'
)

TABLE_REFRESH_FIELDS = (
    'min_buyin', 'max_buyin', 'ante', 'sb', 'bb'
)
