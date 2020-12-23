from oddslingers.utils import secure_random_number

def to_cards(hand):
    if isinstance(hand, str):
        return [Card(s) for s in hand.split(' ')]
    elif isinstance(hand[0], str):
        return [Card(s) for s in hand]
    elif isinstance(hand[0], Card):
        return hand

    raise Exception(f"Don't how to convert {hand} to a list of cards")


def pluralize(card_or_rank):
    if type(card_or_rank) is str:
        rankname = card_or_rank
    else:
        rankname = card_or_rank.rank
    if rankname == 'six':
        return 'sixes'
    else:
        return rankname + 's'


RANKS = ('2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A')
SUITS = ('c', 'd', 'h', 's')
PRETTY_SUITS = {
    'c': '♣',
    'd': '♦',
    'h': '♥',
    's': '♠',
}
INDICES = [f'{r}{s}' for r in RANKS for s in SUITS]


class Card:
    suitnames = {
        'c': 'clubs',
        'd': 'diamonds',
        'h': 'hearts',
        's': 'spades',
    }

    ranknames = {
        '2': 'two',
        '3': 'three',
        '4': 'four',
        '5': 'five',
        '6': 'six',
        '7': 'seven',
        '8': 'eight',
        '9': 'nine',
        'T': 'ten',
        'J': 'jack',
        'Q': 'queen',
        'K': 'king',
        'A': 'ace'
    }

    def __init__(self, rank, suit=None):
        if isinstance(rank, int):
            rank, suit = INDICES[rank]

        # so that Card('Th') or Card(other_card) work
        elif suit is None:
            suit = rank[1]
            rank = rank[0]

        if rank not in RANKS or suit not in SUITS:
            raise ValueError(f'Bad rank or suit: "{rank}{suit}"')

        self.rank = rank
        self.suit = suit
        self.index = 4 * RANKS.index(self.rank) + SUITS.index(self.suit)

    def clone(self):
        return Card(self.__str__())

    def __json__(self):
        return self.__str__()

    def __str__(self):
        return f'{self.rank}{self.suit}'

    def __repr__(self):
        return self.__str__()

    def pretty(self):
        return f'{self.rank}{PRETTY_SUITS[self.suit]}'

    def __eq__(self, other):
        if isinstance(other, self.__class__):
            return self.index == other.index
        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __lt__(self, other):
        if isinstance(other, self.__class__):
            return self.index < other.index
        raise TypeError(f'Cannot compare Card to {other.__class__}')

    def __gt__(self, other):
        if isinstance(other, self.__class__):
            return self.index > other.index
        raise TypeError(f'Cannot compare Card to {other.__class__}')

    def __le__(self, other):
        if isinstance(other, self.__class__):
            return self.index <= other.index
        raise TypeError(f'Cannot compare Card to {other.__class__}')

    def __ge__(self, other):
        if isinstance(other, self.__class__):
            return self.index >= other.index
        raise TypeError(f'Cannot compare Card to {other.__class__}')

    def __hash__(self):
        return self.index

    def __getitem__(self, i):
        if i == 0:
            return self.rank
        elif i == 1:
            return self.suit
        raise IndexError('Card objects only have a rank and suit')


class Deck:
    def __init__(self, cards=None):
        if cards:
            if type(cards[0]) in (int, str):
                self.cards = [Card(card) for card in cards]
            elif isinstance(cards[0], Card):
                self.cards = cards
        else:
            self.cards = []

            for suit in SUITS:
                for rank in RANKS:
                    self.cards.append(Card(rank, suit))

            self.shuffle()

    def shuffle(self):
        new_cards = []

        while self.cards:
            rand_idx = secure_random_number(max_num=len(self.cards))
            new_cards.append(self.cards.pop(rand_idx))

        self.cards = new_cards

    def deal(self):
        return self.cards.pop(0)

    def to_num(self):
        return [INDICES.index(str(c)) for c in self.cards]

    def to_list(self):
        return [str(c) for c in self.cards]
