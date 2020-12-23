export const ODDSLINGERS_ROOT = __dirname + '/../..'  // oddslingers
export const GRATER_ROOT = 'core'
export const JS_ROOT = 'core/src'

export const DUMPS_FOLDER = `${ODDSLINGERS_ROOT}/${GRATER_ROOT}/dumps`

export const STATIC_URL = '/static'
export const IMAGES_URL = '/static/images'


export const URLS = {
    'Leaderboard': '/leaderboard',
}

export const ACTION_COLORS = {
    RAISE: 'yellowgreen',
    BET: 'green',
    READY: 'green',
    CALL: 'blue',
    CHECK: 'orange',
    FOLD: 'red',
    LEAVING: 'red',
    'ALL IN': 'lawngreen'
}

// In miliseconds
export const SOUNDS_DURATION = {
    deal_board: 160,
    win: 833,
    reveal_hand: 810,
    bet: 186,
    all_in: 417,
    raise: 444,
    your_turn: 130,
    deal_player: 417,
    return_chips: 833,
    check: 287,
    fold: 495,
    clap: 1123,
    out_of_time: 313,
    bounty: 600
}

export const LOGGED_USER_SPECIFIC_SOUNDS = {
    'win': 'clap'
}


// general chat cleanup, replace some substrings with tags
// tag format: |||{json props}|text content|||
export const CHAT_REPLACEMENTS = [
    ['from the main pot', ''],
    ['.00', ''],
    ['for SB', 'SB'],
    ['for BB', 'BB'],
    [/♥/g, '|||{"className": "light suit red"}|♥|||'],
    [/♦/g, '|||{"className": "light suit red"}|♦|||'],
    [/♠/g, '|||{"className": "light suit altblue"}|♠|||'],
    [/♣/g, '|||{"className": "light suit altblue"}|♣|||'],
    ['was dealt', '|||{"className": "light gray"}|was dealt|||'],
    ['posted', '|||{"className": "light gray"}|posted|||'],
    ['raised to', '|||{"className": "light lime"}|raised to|||'],
    ['bet', '|||{"className": "light green"}|bet|||'],
    ['called', '|||{"className": "light blue"}|called|||'],
    ['checked', '|||{"className": "light orange"}|checked|||'],
    ['folded', '|||{"className": "light red"}|folded|||'],
    ['has', '|||{"className": "light green"}|has|||'],
    ['won', '|||{"className": "light green"}|won|||'],
    ['with', '|||{"className": "light green"}|with|||'],
    ['[', '|||{"className": "light orange"}|[|||'],
    [']', '|||{"className": "light orange"}|]|||'],
    ['FLOP', '|||{"className": "light orange"}|FLOP|||'],
    ['TURN', '|||{"className": "light orange"}|TURN|||'],
    ['RIVER', '|||{"className": "light orange"}|RIVER|||'],
]

export const suit_icons = {
    'c': '♣︎',
    's': '♠︎',
    'd': '♦︎',
    'h': '♥︎',
}
export const suit_names = {
    'c': 'clubs',
    's': 'spades',
    'd': 'diamonds',
    'h': 'hearts',
}

/* All of the object's keys for the btn and chips
    represents the number of seats, and each position
    of the array match with the player's position */

// Position for the btn in the ellipse for desktop on landscape
export const btn_positions_desktop_landscape = {
    6: [63, 14, 20, 30, 46, 56],
    5: [53, 13, 24, 31, 42],
    4: [42, 13, 20, 31],
    3: [31, 10, 21],
    2: [21, 10],
}

// Position for the btn in the ellipse for desktop on portrait
export const btn_positions_desktop_portrait = {
    6: [63, 12, 22, 31, 44, 54],
    5: [53, 11, 23, 32, 44],
    4: [43, 12, 21, 32],
    3: [32, 12, 21],
    2: [21, 10],
}

/* This objects add an offset to the player's position
    i.e: {num_seats: [position offsets from player position for each seat]} */
export const btn_positions_mobile_landscape = {
    6: [
        {top: -20, left: 0},
        {top: 35, left: 90},
        {top: 50, left: 90},
        {top: 40, left: 90},
        {top: 50, left: -20},
        {top: 40, left: -20},
    ],
    5: [
        {top: -20, left: 0},
        {top: 40, left: 90},
        {top: 40, left: 90},
        {top: 40, left: -30},
        {top: 40, left: -30},
    ],
    4: [
        {top: -20, left: 0},
        {top: 10, left: 90},
        {top: 70, left: 0},
        {top: 10, left: -20},
    ],
    3: [
        {top: -20, left: 0},
        {top: 40, left: 90},
        {top: 40, left: -20},
    ],
    2: [
        {top: -20, left: 0},
        {top: 70, left: 0},
    ],
}

export const btn_positions_mobile_portrait = {
    6: [
        {top: -20, left: 0},
        {top: 10, left: 90},
        {top: 50, left: 90},
        {top: 70, left: 0},
        {top: 50, left: -20},
        {top: 10, left: -20},
    ],
    5: [
        {top: -20, left: 0},
        {top: 40, left: 90},
        {top: 70, left: 0},
        {top: 70, left: 0},
        {top: 40, left: -20},
    ],
    4: [
        {top: -20, left: 0},
        {top: 70, left: 60},
        {top: 60, left: 0},
        {top: 70, left: 0},
    ],
    3: [
        {top: -20, left: 0},
        {top: 40, left: 90},
        {top: 40, left: -20},
    ],
    2: [
        {top: -20, left: 0},
        {top: 70, left: 0},
    ],
}

export const chips_positions_mobile_landscape = {
    6: [
        {top: -30, left: 30},
        {top: 10, left: 90},
        {top: 20, left: 90},
        {top: 60, left: 25},
        {top: 20, left: -60},
        {top: 10, left: -60},
    ],
    5: [
        {top: -30, left: 30},
        {top: 10, left: 90},
        {top: 60, left: 30},
        {top: 60, left: 20},
        {top: 10, left: -50},
    ],
    4: [
        {top: -30, left: 30},
        {top: -30, left: 30},
        {top: 60, left: 30},
        {top: -30, left: 10},
    ],
    3: [
        {top: -30, left: 30},
        {top: 10, left: 90},
        {top: 10, left: -50},
    ],
    2: [
        {top: -30, left: 30},
        {top: 65, left: 30},
    ],
}

export const chips_positions_mobile_portrait = {
    6: [
        {top: -30, left: 20},
        {top: -30, left: 10},
        {top: 60, left: 10},
        {top: 60, left: 20},
        {top: 60, left: 10},
        {top: -30, left: 10},
    ],
    5: [
        {top: -30, left: 30},
        {top: -30, left: 20},
        {top: 60, left: 20},
        {top: 60, left: 20},
        {top: -30, left: 10},
    ],
    4: [
        {top: -30, left: 30},
        {top: -30, left: 40},
        {top: 60, left: 20},
        {top: -30, left: 10},
    ],
    3: [
        {top: -30, left: 30},
        {top: 60, left: 30},
        {top: 60, left: 20},
    ],
    2: [
        {top: -30, left: 30},
        {top: 60, left: 30},
    ],
}


//NOTE: Those values must match the ones in poker/constants.py
export const TAKE_SEAT_BEHAVIOURS = {
    SIT_IN_PENDING: "Sit in next hand",
    SIT_IN_AT_BLINDS_PENDING: "Sit in at bb",
    SITTING_OUT: "Sit in Without Playing",
}

export const MAX_CHAT_MSG_LINK_LENGTH = 30

export const LEFT_ARROW = 37
export const UP_ARROW = 38
export const RIGHT_ARROW = 39
export const DOWN_ARROW = 40

export const CHAT_BUBBLE_MAX_TIME = 3500
export const CHAT_BUBBLE_MAX_LENGTH = 60

export const CHAT_PRESETS = [
    "wow","🤠","🤑","💰💰💰","nh","lol","🤪","😤","🤯","⛔⛔⛔",
    "gg","💜💙💚💛","nice","oops","☕☕☕","🔥🔥🔥","💸💸💸",
    "👽","cool","🥺","🤔","🏳️‍🌈🏳️‍🌈🏳️‍🌈","awesome","🎊🎉"
]

export const MS_BETWEEN_MSGS = 700

export const THRESHOLD_BB_FOR_BOTS = 100

