from django.test import TestCase

from poker import rankings

from poker.cards import Card

def assert_even_descending_hand_strength(list1, list2):
    for i, hand1 in enumerate(list1):
        for j, hand2 in enumerate(list2):
            # print(hand1, ": ", rankings.hand_sortkey(hand1), "\t", hand2, ": ", rankings.hand_sortkey(hand2))
            if (i == j):
                assert(rankings.hand_sortkey(hand1) == rankings.hand_sortkey(hand2))
            elif (i > j):
                assert(rankings.hand_sortkey(hand1) < rankings.hand_sortkey(hand2))
            else:
                assert(rankings.hand_sortkey(hand1) > rankings.hand_sortkey(hand2))


class RankingTest(TestCase):
    def setUp(self):
        self.examples1 = [
            ("Th Kh Qh Ah Jh", "Royal Flush"),
            ("Ts 9s 7s 8s 6s", "Straight Flush, six to ten"),
            ("4c 3c 2c Ac 5c", "Straight Flush, ace to five"),
            ("Ah Ac Ad As 9d", "Four of a Kind, aces"),
            ("Ah Ac Ad As 3d", "Four of a Kind, aces"),
            ("3h 3c 3s As 3d", "Four of a Kind, threes"),
            ("7h 7c 3d 3s 7d", "Full House, sevens full of threes"),
            ("7h 7c 2d 2s 7d", "Full House, sevens full of twos"),
            ("Ts 9s 3s 8s 6s", "Flush, ten high"),
            ("Ts 9s 2s 8s 6s", "Flush, ten high"),
            ("5s 6s 7s 8s 4c", "Straight, four to eight"),
            ("5s 3s 2s As 4c", "Straight, ace to five"),
            ("9h 8c 8d Ks Kd", "Two Pair, kings and eights"),
            ("3h 8c 8d Ks Kd", "Two Pair, kings and eights"),
            ("3h 6c 6d Ks Kd", "Two Pair, kings and sixes"),
            ("6h 6c 2s Ks 2d", "Two Pair, sixes and twos"),
            ("Jh Ac 3d 2s Jd", "Pair of jacks, ace kicker"),
            ("Jh Kc 3d 2s Jd", "Pair of jacks, king kicker"),
            ("9h Kc 3d 2s 9d", "Pair of nines, king kicker"),
            ("6h 5c 7d Ks Ad", "High Card ace, king kicker"),
            ("6h 2c 7d Ks Ad", "High Card ace, king kicker"),
            ("4h 2c 7d Ks Ad", "High Card ace, king kicker"),
            ("6h 2c 3d Ks Ad", "High Card ace, king kicker"),
            ("5h 2c 3d 4s 7d", "High Card seven, five kicker"),
        ]

        self.examples2 = [
            ("Td Kd Qd Ad Jd", "Royal Flush"),
            ("Td 9d 7d 8d 6d", "Straight Flush, six to ten"),
            ("4d 3d 2d Ad 5d", "Straight Flush, ace to five"),
            ("Ah Ac Ad As 9c", "Four of a Kind, aces"),
            ("Ah Ac Ad As 3c", "Four of a Kind, aces"),
            ("3h 3c 3s Ac 3d", "Four of a Kind, threes"),
            ("7h 7c 3d 3s 7s", "Full House, sevens full of threes"),
            ("7h 7c 2h 2c 7d", "Full House, sevens full of twos"),
            ("Th 9h 3h 8h 6h", "Flush, ten high"),
            ("Th 9h 2h 8h 6h", "Flush, ten high"),
            ("5c 6s 7s 8s 4c", "Straight, four to eight"),
            ("5c 3s 2s As 4c", "Straight, ace to five"),
            ("9c 8c 8d Ks Kd", "Two Pair, kings and eights"),
            ("3c 8c 8d Ks Kd", "Two Pair, kings and eights"),
            ("3c 6c 6d Ks Kd", "Two Pair, kings and sixes"),
            ("6c 6c 2s Ks 2d", "Two Pair, sixes and twos"),
            ("Jc Ac 3d 2s Jd", "Pair of jacks, ace kicker"),
            ("Jc Kc 3d 2s Jd", "Pair of jacks, king kicker"),
            ("9c Kc 3d 2s 9d", "Pair of nines, king kicker"),
            ("6c 5c 7d Ks Ad", "High Card ace, king kicker"),
            ("6c 2c 7d Ks Ad", "High Card ace, king kicker"),
            ("4c 2c 7d Ks Ad", "High Card ace, king kicker"),
            ("6c 2c 3d Ks Ad", "High Card ace, king kicker"),
            ("5c 2c 3d 4s 7d", "High Card seven, five kicker"),
        ]

        self.examples3 = ["4s As 8s 9s Ks", "3s As 8s 9s Ks", "2s As 8s 9s Ks", "4c 4d As 9s Ks"]

    def test_relative_rankings(self):
        list1 = [hand for hand, _ in self.examples1]
        list2 = [hand for hand, _ in self.examples2]
        assert_even_descending_hand_strength(list1, list2)

    def test_example3(self):
        assert_even_descending_hand_strength(self.examples3, self.examples3)

    def test_hand_names(self):
        for hand, name in self.examples1:
            # print(hand, " -> ", rankings.hand_to_name(hand))
            assert(name == rankings.hand_to_name(hand))
        for hand, name in self.examples2:
            # print(hand, " -> ", rankings.hand_to_name(hand))
            assert(name == rankings.hand_to_name(hand))


class BestHandTest(TestCase):
    def setUp(self):
        self.board1 = [Card(c) for c in "Ac 2s 3c 4h 5s".split()]
        self.board2 = [Card(c) for c in "Ks Qh 9s 8c 7s".split()]
        self.board3 = [Card(c) for c in "2c 5c 8c 9s Jc".split()]
        self.board4 = [Card(c) for c in "2c 5h 8c 9s 2s".split()]
        self.board5 = [Card(c) for c in "2c 5c 7h 9s 2s".split()]

    def test_best_hand_from_cards(self):
        hand1 = [Card(c) for c in "As Ac".split()]
        hand2 = [Card(c) for c in "6s 7h".split()]
        hand3 = [Card(c) for c in "Jc Th".split()]
        hand4 = [Card(c) for c in "7s 2c".split()]
        hands = [hand1, hand2, hand3, hand4]

        def best_hand(board, hand=None):
            if hand is None:
                return sorted([best_hand(board, h) for h in hands], key=rankings.hand_sortkey)[-1]

            return rankings.best_hand_from_cards(hand + board)

        self.assert_same(best_hand(hand1, self.board1), best_hand([], self.board1))
        
        self.assert_same(best_hand(self.board1), best_hand(self.board1, hand2))
        self.assert_same(best_hand(self.board2), best_hand(self.board2, hand3))
        self.assert_same(best_hand(self.board3), best_hand(self.board3, hand1))
        self.assert_same(best_hand(self.board4), best_hand(self.board4, hand2))
        self.assert_same(best_hand(self.board5), best_hand(self.board5, hand4))

    def test_best_hand_using_holecards(self):
        hand1 = [Card(c) for c in "As Ac 3d 4d".split()]
        hand2 = [Card(c) for c in "6s 7h 6c 7c".split()]
        hand3 = [Card(c) for c in "Jc Th Qs Kd".split()]
        hand4 = [Card(c) for c in "7s 2c 8d Jh".split()]
        hands = [hand1, hand2, hand3, hand4]

        def best_hand(board, hand=None):
            if hand is None:
                return sorted([best_hand(board, h) for h in hands], key=rankings.hand_sortkey)[-1]

            return rankings.best_hand_using_holecards(hand, board, 2)

        self.assert_same(best_hand(self.board1), best_hand(self.board1, hand2))
        self.assert_same(best_hand(self.board2), best_hand(self.board2, hand3))
        self.assert_same(best_hand(self.board3), best_hand(self.board3, hand2))
        self.assert_same(best_hand(self.board4), best_hand(self.board4, hand4))
        self.assert_same(best_hand(self.board5), best_hand(self.board5, hand2))

    def assert_same(self, hand1, hand2):
        assert rankings.hand_sortkey(hand1) == rankings.hand_sortkey(hand2)
        