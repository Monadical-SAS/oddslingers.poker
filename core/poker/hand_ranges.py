from itertools import combinations
from re import findall

from poker.cards import Card, SUITS, RANKS

class Hand:
    '''
    Iterable and indexable collection of card combinations.

    Can be build with Card objects or a string like "AhTc"
    '''
    def __init__(self, cards):
        if isinstance(cards, str):
            # e.g. 'Ac,3d9h' will become [Card(Ac), Card(3d), Card(9h)]
            cards = [
                Card(card_str)
                # findall('..') splits strings into groups of two chars
                # comma removal because of the way cards are stored on models
                for card_str in findall('..', cards.replace(',', ''))
            ]
        # copy constructor
        elif isinstance(cards, self.__class__):
            cards = [Card(card) for card in cards.cards]
        elif cards and isinstance(cards[0], str):
            cards = [Card(card_str) for card_str in cards]

        self.cards = sorted(cards)

    def __str__(self):
        return ''.join(str(card) for card in self)

    def __json__(self):
        return str(self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.cards == other.cards
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return self.__str__().__hash__()

    def __getitem__(self, i):
        return self.cards[i]

    def __len__(self):
        return len(self.cards)

    def __iter__(self):
        for card in self.cards:
            yield card

    def __repr__(self):
        return f"<Hand({self}) at {hex(id(self))}>"


class HandRange:
    '''
    Iterable and indexable collection of hands, plus a { hand: value }
    mapping. The mapping determines the order, so before the flop,
    aces will be first and 32o will be last.

    Can be build with Hand objects or string like "AhTc,KcKd".

    The default mapping is pre-calculated preflop hand equities at
    a 4-player table. For example, two aces win a 4-way all-in 63.9%
    of the time, and 32o wins 13.7% of the time. See PREFLOP_HANDS
    for the actual numbers
    '''
    @classmethod
    def from_descriptions(cls, hand_descriptions):
        return cls([
            hand
            for hand_desc in hand_descriptions.split(',')
                for hand in hands_from_description(hand_desc)
        ])

    def __init__(self, hands, hand_values=None, **prune_kwargs):
        if hand_values is None:
            hand_values = PREFLOP_HAND_VALUES

        if isinstance(hands, str):
            self.hands = list({Hand(hand) for hand in hands.split(',')})
        # copy constructor
        elif isinstance(hands, self.__class__):
            self.hands = [Hand(hand) for hand in hands.hands]
            self.hand_values = hands.hand_values
        else:
            self.hands = list(set(Hand(hand) for hand in hands))

        self.hand_values = hand_values

        if prune_kwargs:
            self.hands = pruned(self, **prune_kwargs).hands

        self.sort_hands()

    def __str__(self):
        return ','.join(str(hand) for hand in self)

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.hands == other.hands
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __json__(self):
        return str(self)

    def __getitem__(self, i):
        return self.hands[i]

    def __len__(self):
        return len(self.hands)

    def __iter__(self):
        for hand in self.hands:
            yield hand

    def __repr__(self):
        return f'<HandRange {self[0]}:{self[-1]} -- '\
               f'{len(self)} combos ({len(self)/13.26:.1f}%)>'

    def index(self, hand):
        if not isinstance(hand, Hand):
            hand = Hand(hand)
        return self.hands.index(hand)

    def percentile(self, hand):
        if not isinstance(hand, Hand):
            hand = Hand(hand)
        return self.index(hand) / float(len(self))

    def describe(self, print_me=True):
        hands_with_values = [
            (hand, self.hand_values[hand])
            for hand in self
        ]
        output = '\n'.join(f'{hand}: {val}' for hand, val in hands_with_values)
        if print_me:
            print(output)
        else:
            return output

    def sort_hands(self):
        try:
            self.hands.sort(key=self.hand_values.__getitem__, reverse=True)
        except KeyError as err:
            msg = f'HandRange missing value for Hand: {err}'
            raise KeyError(msg).with_traceback(err.__traceback__)


def with_hand_values(handrange, hand_values):
    return HandRange(handrange.hands, hand_values)


def pruned(handrange, keep_ratio=1, known_cards=None, min_value=0):
    '''
    Returns a transformed handrange, according to parameters.

    For example, a player starts with all possible hands. Then they
    raise from the button, so you assume they are only doing that with
    the top 30% of hands. You call `pruned(FULL_RANGE, keep_ratio=0.3)`
    and get their new HandRange.

    If both ratio and known_cards/min_value are provided, then
    the ratio of the resulting range (after first pruning) is returned
    '''
    if known_cards is not None:
        if isinstance(known_cards, str):
            known_cards = Hand(known_cards)
        remove = set(card for card in known_cards)
        assert set(isinstance(card, Card) for card in remove) == {True}
        handrange = HandRange(
            [
                hand for hand in handrange
                if len({*hand} - remove) == len(hand)
            ],
            handrange.hand_values
        )

    if min_value > 0:
        handrange = HandRange(
            [
                hand for hand in handrange
                if handrange.hand_values[hand] > min_value
            ],
            handrange.hand_values
        )

    # min "keep_ratio" equal to only AA preflop
    keep_ratio = max(6 / 1326, keep_ratio)
    # always keep at least one hand
    n_cards_to_keep = max(1, int(len(handrange) * keep_ratio))

    return HandRange(
        handrange[:n_cards_to_keep],
        handrange.hand_values
    )


def preflop_range(ratio):
    return pruned(FULL_RANGE, keep_ratio=ratio)


def hands_from_description(hand):
    # e.g. 'AA' -> [('Ac', 'As'), ('Ac', 'Ah'), ...]

    cards_of_suit = lambda rank: [f'{rank}{suit}' for suit in SUITS]
    possible_cards = {*cards_of_suit(hand[0]), *cards_of_suit(hand[1])}

    if len(hand) == 3 and hand[2] == 's':
            return [
                Hand((h1, h2))
                for h1, h2 in combinations(possible_cards, 2)
                if h1[1] == h2[1]  # suited
            ]
    elif len(hand) == 3:
        return [
            Hand((h1, h2))
            for h1, h2 in combinations(possible_cards, 2)
            if h1[0] != h2[0] and h1[1] != h2[1]  # unsuited
        ]
    elif len(hand) == 4:  #specific hand described
        return [Hand(hand)]
    elif len(hand) == 2:  # pairs
        return [
            Hand((h1, h2))
            for h1, h2 in combinations(possible_cards, 2)
        ]
    raise ValueError(f"Failed to parse hand description '{hand}'")


def hand_to_description(hand):
    if not isinstance(hand, Hand):
        hand = Hand(hand)

    assert len(hand.cards) == 2, "TODO: implement for PLO"

    r1, s1 = hand.cards[0]
    r2, s2 = hand.cards[1]
    suited = 's' if s1 == s2 else 'o'
    # pairs don't get marked as offsuit
    suited = '' if r1 == r2 else suited
    rank = ''.join(sorted([r1, r2], key=RANKS.index, reverse=True))
    return f'{rank}{suited}'


# (hand_descrption, equity vs PREFLOP_BASE_CALC_RANGES defined below)
#   see starting_hand_values_calc.py in scripts folder for details
# NOTE: AKs, AKo, AQs, and AQo have been manually adjusted
#   because pocket pairs are much stronger vs wide ranges
# TODO: recalc top-end equities against other top-end cards only
PREFLOP_HANDS = [
    ('AA', 0.6099),
    ('KK', 0.5277),
    ('QQ', 0.464),
    ('AKs', 0.4548),
    ('JJ', 0.4104),
    ('AKo', 0.3722),
    ('AQs', 0.3705),
    ('TT', 0.3678),
    ('AQo', 0.3364),
    ('99', 0.3329),
    ('AJs', 0.3201),
    ('KQs', 0.3094),
    ('88', 0.3026),
    ('ATs', 0.3011),
    ('KJs', 0.2921),
    ('AJo', 0.2835),
    ('77', 0.2805),
    ('QJs', 0.2802),
    ('KTs', 0.2799),
    ('KQo', 0.2767),
    ('A9s', 0.2737),
    ('QTs', 0.2698),
    ('JTs', 0.2663),
    ('ATo', 0.2634),
    ('66', 0.2623),
    ('A8s', 0.262),
    ('KJo', 0.2581),
    ('K9s', 0.2577),
    ('A7s', 0.2533),
    ('A5s', 0.252),
    ('Q9s', 0.2495),
    ('T9s', 0.2471),
    ('QJo', 0.2457),
    ('55', 0.2455),
    ('A4s', 0.2454),
    ('A6s', 0.244),
    ('J9s', 0.2389),
    ('A3s', 0.237),
    ('98s', 0.2358),
    ('K8s', 0.2311),
    ('T8s', 0.23),
    ('87s', 0.2292),
    ('KTo', 0.2282),
    ('K7s', 0.2277),
    ('44', 0.2255),
    ('76s', 0.2254),
    ('A2s', 0.2244),
    ('J8s', 0.2238),
    ('97s', 0.2237),
    ('Q8s', 0.2229),
    ('65s', 0.2222),
    ('QTo', 0.222),
    ('K6s', 0.2216),
    ('JTo', 0.221),
    ('A9o', 0.2195),
    ('86s', 0.2191),
    ('K5s', 0.2176),
    ('54s', 0.2171),
    ('33', 0.2143),
    ('K4s', 0.2138),
    ('75s', 0.2128),
    ('T7s', 0.2121),
    ('96s', 0.2108),
    ('64s', 0.2096),
    ('A8o', 0.2092),
    ('Q6s', 0.2076),
    ('22', 0.2056),
    ('Q7s', 0.2053),
    ('85s', 0.2052),
    ('J7s', 0.2051),
    ('K3s', 0.2032),
    ('53s', 0.2031),
    ('T9o', 0.2025),
    ('T6s', 0.2017),
    ('K2s', 0.2),
    ('74s', 0.1993),
    ('Q5s', 0.1992),
    ('K9o', 0.198),
    ('43s', 0.1977),
    ('63s', 0.1957),
    ('98o', 0.1955),
    ('95s', 0.1946),
    ('J9o', 0.1939),
    ('Q9o', 0.1936),
    ('87o', 0.1932),
    ('A5o', 0.1918),
    ('A7o', 0.1906),
    ('Q3s', 0.1905),
    ('76o', 0.1904),
    ('J6s', 0.1894),
    ('T8o', 0.1889),
    ('52s', 0.1886),
    ('65o', 0.1884),
    ('97o', 0.1879),
    ('Q4s', 0.1868),
    ('84s', 0.1866),
    ('J5s', 0.1865),
    ('J4s', 0.1859),
    ('T5s', 0.1859),
    ('A4o', 0.1857),
    ('42s', 0.1849),
    ('Q2s', 0.1847),
    ('A6o', 0.1831),
    ('54o', 0.1827),
    ('73s', 0.1826),
    ('T4s', 0.1823),
    ('86o', 0.1823),
    ('K8o', 0.1817),
    ('62s', 0.1817),
    ('T3s', 0.1804),
    ('J3s', 0.1798),
    ('A3o', 0.1798),
    ('94s', 0.1797),
    ('K7o', 0.1797),
    ('32s', 0.1797),
    ('75o', 0.1792),
    ('J8o', 0.1791),
    ('Q8o', 0.1782),
    ('93s', 0.1781),
    ('92s', 0.1765),
    ('T2s', 0.1756),
    ('J2s', 0.1748),
    ('A2o', 0.1744),
    ('64o', 0.1736),
    ('82s', 0.1733),
    ('83s', 0.1726),
    ('K6o', 0.1715),
    ('T7o', 0.1711),
    ('53o', 0.1701),
    ('72s', 0.1692),
    ('96o', 0.1683),
    ('K5o', 0.1682),
    ('85o', 0.1663),
    ('43o', 0.164),
    ('74o', 0.1636),
    ('K4o', 0.1624),
    ('J7o', 0.1618),
    ('Q7o', 0.1607),
    ('63o', 0.1594),
    ('Q6o', 0.1586),
    ('T6o', 0.1578),
    ('K3o', 0.1578),
    ('52o', 0.1567),
    ('95o', 0.1561),
    ('K2o', 0.1553),
    ('Q5o', 0.155),
    ('42o', 0.1527),
    ('Q4o', 0.1515),
    ('J6o', 0.1504),
    ('84o', 0.15),
    ('73o', 0.1486),
    ('J5o', 0.1476),
    ('Q3o', 0.1473),
    ('32o', 0.1461),
    ('Q2o', 0.1456),
    ('J4o', 0.1452),
    ('T5o', 0.1448),
    ('62o', 0.1445),
    ('T4o', 0.1428),
    ('94o', 0.142),
    ('93o', 0.1415),
    ('J3o', 0.1405),
    ('T3o', 0.1397),
    ('T2o', 0.1383),
    ('92o', 0.138),
    ('J2o', 0.1374),
    ('82o', 0.1369),
    ('83o', 0.1351),
    ('72o', 0.1351),
]


PREFLOP_HAND_VALUES = {
    Hand(hand): value
    for desc, value in PREFLOP_HANDS
        for hand in hands_from_description(desc)
}


FULL_RANGE = HandRange(list(PREFLOP_HAND_VALUES.keys()))


LOOSE_RANGE = HandRange.from_descriptions('''
AA,KK,QQ,JJ,TT,99,88,77,66,55,44,33,22,
AKs,AQs,AJs,ATs,A9s,A8s,A7s,A6s,A5s,A4s,A3s,A2s,
AKo,AQo,AJo,ATo,A9o,A8o,A7o,A6o,A5o,A4o,A3o,A2o,
KQs,KJs,KTs,K9s,K8s,K7s,K6s,K5s,K4s,K3s,K2s,
KQo,KJo,KTo,K9o,K8o,K7o,
QJs,QTs,Q9s,Q8s,Q7s,Q6s,Q5s,
QJo,QTo,Q9o,Q8o,
JTs,J9s,J8s,J7s,
JTo,J9o,J8o,
T9s,T8s,T7s,T6s,
T9o,T8o,
98s,97s,96s,
98o,97o,
87s,86s,85s,
87o,86o,
76s,75s,74s,
76o,75o,
65s,64s,63s,
65o,64o,
54s,53s,
54o,
43s, 42s,
32s
'''.replace(' ', '').replace('\n', ''))


PREFLOP_BASE_CALC_RANGES = [
    LOOSE_RANGE,
    pruned(LOOSE_RANGE, 0.5),
    pruned(LOOSE_RANGE, 0.3),
]
