from itertools import combinations

from poker.cards import Card, pluralize, to_cards, RANKS


CARD_ORDER = ['2', '3', '4', '5', '6', '7', '8', '9', 'T', 'J', 'Q', 'K', 'A']


def best_hand_using_holecards(holecards, board, n_holecards=2):
    if len(holecards) < n_holecards or len(board) + n_holecards < 5:
        err_msg = 'Impossible to make hands with the parameters provided'
        raise Exception(err_msg)

    holecard_combos = list(combinations(holecards, n_holecards))
    board_combos = list(combinations(board, 5 - n_holecards))

    possible_hands = [
        hcs + board
        for hcs in holecard_combos
            for board in board_combos
    ]

    return best_hand(possible_hands)


def best_hand_from_cards(cards):
    if len(cards) < 5:
        raise Exception('Need 5 cards to make a poker hand')
    return best_hand(combinations(cards, 5))


def best_hand(hands):
    return sorted(hands, key=hand_sortkey, reverse=True)[0]


def hand_sortkey(hand):
    return handrank_encoding_to_key(handrank_encoding(hand))


def handrank_encoding_to_key(handrank_encoding):
    n = 0
    m = 1
    for k in handrank_encoding[::-1]:
        if k:
            if isinstance(k, int):  # we're at the N part of the encoding
                n += k * m
            elif k:
                n += CARD_ORDER.index(k) * m

        m *= 100

    return n


def handrank_encoding(hand):
    ''' Encodes a 5-card hand as:
                N K K K K K
        where each K represents a kicker, (a flush has 5, a straight
        has one, full house has two) and N represents a numerical
        value (0 is High Card and 9 is Straight Flush). See def
        handrank_encoding_to_name for more.
    '''
    hand = to_cards(hand)
    if len(hand) != 5:
        raise Exception('Need 5 cards to encode')

    # first look for pairs
    rankset = set(card.rank for card in hand)
    buckets = [
        (rank, sum(card.rank == rank for card in hand))
        for rank in rankset
    ]

    buckets.sort(key=lambda k: (k[1], RANKS.index(k[0])), reverse=True)

    bucket_dist = [size for rank, size in buckets]

    # four of a kind
    if bucket_dist == [4, 1]:
        return [7, buckets[0][0], buckets[1][0], None, None, None]
    # full house
    elif bucket_dist == [3, 2]:
        return [6, buckets[0][0], buckets[1][0], None, None, None]
    # three of a kind
    elif bucket_dist == [3, 1, 1]:
        return [3, buckets[0][0], buckets[1][0], buckets[2][0], None, None]
    # two pair
    elif bucket_dist == [2, 2, 1]:
        return [2, buckets[0][0], buckets[1][0], buckets[2][0], None, None]
    # one pair
    elif bucket_dist == [2, 1, 1, 1]:
        return [
            1,
            buckets[0][0], buckets[1][0], buckets[2][0], buckets[3][0], None
        ]
    else:
        flush = all(hand[0].suit == card.suit for card in hand)
        nums = sorted([CARD_ORDER.index(card.rank) for card in hand])
        straight = max(nums) - min(nums) == 4
        wheel = nums == [0, 1, 2, 3, 12]

        if flush:
            # straight flush
            if straight:
                return [
                    8,
                    buckets[0][0], buckets[1][0], buckets[2][0],
                    buckets[3][0], buckets[4][0]
                ]
            if wheel:
                return [
                    8,
                    buckets[1][0], buckets[2][0], buckets[3][0],
                    buckets[4][0], buckets[0][0]
                ]

            # flush
            return [
                5,
                buckets[0][0], buckets[1][0], buckets[2][0],
                buckets[3][0], buckets[4][0]
            ]

        # straight
        if straight:
            return [
                4,
                buckets[0][0], buckets[1][0], buckets[2][0],
                buckets[3][0], buckets[4][0]
            ]
        if wheel:
            return [
                4,
                buckets[1][0], buckets[2][0], buckets[3][0],
                buckets[4][0], buckets[0][0]
            ]

        # high card
        return [
            0,
            buckets[0][0], buckets[1][0], buckets[2][0],
            buckets[3][0], buckets[4][0]
        ]


def handrank_encoding_to_name(handrank_encoding):
    N, K1, K2, K3, K4, K5 = handrank_encoding
    if N == 0:
        return f'High Card {Card.ranknames[K1]}, {Card.ranknames[K2]} kicker'
    elif N == 1:
        return f'Pair of {pluralize(Card.ranknames[K1])}, '\
               f'{Card.ranknames[K2]} kicker'
    elif N == 2:
        return f'Two Pair, {pluralize(Card.ranknames[K1])} '\
               f'and {pluralize(Card.ranknames[K2])}'
    elif N == 3:
        return f'Three of a Kind {Card.ranknames[K1]}'
    elif N == 4:
        return f'Straight, {Card.ranknames[K5]} to {Card.ranknames[K1]}'
    elif N == 5:
        return f'Flush, {Card.ranknames[K1]} high'
    elif N == 6:
        return f'Full House, {pluralize(Card.ranknames[K1])} '\
               f'full of {pluralize(Card.ranknames[K2])}'
    elif N == 7:
        return f'Four of a Kind, {pluralize(Card.ranknames[K1])}'
    elif N == 8:
        if K1 == 'A':
            return 'Royal Flush'
        return f'Straight Flush, {Card.ranknames[K5]} to {Card.ranknames[K1]}'


def hand_to_name(hand):
    return handrank_encoding_to_name(handrank_encoding(hand))
