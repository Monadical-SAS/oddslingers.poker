from django.test import TestCase

from oddslingers.utils import autocast, rotated

from poker.cards import Card

class RotatedTest(TestCase):
    def setUp(self):
        pass

    def test_rotated(self):
        test_list = list(range(10))
        for i, j in zip(test_list, rotated(test_list, 3)):
            self.assertEqual((i + 3) % 10, j)

        for i, j in zip(test_list, rotated(test_list, 5)):
            self.assertEqual((i + 5) % 10, j)

        test_list = list(range(100))
        for i, j in zip(test_list, rotated(test_list, 30)):
            self.assertEqual((i + 30) % 100, j)

        rotated_list = list(rotated(test_list, 34))

        self.assertEqual(test_list[34], rotated_list[0])
        self.assertEqual(test_list[0], rotated_list[100-34])

    def tearDown(self):
        pass

def AutocastTest(TestCase):
    def setUp(self):
        @autocast
        def testfunc(a, b, c: int, d: str = 4, e: float = 5.1):
            return (a, b, c, d, e)

        self.testfunc = testfunc

    def test_autocast(self):
        expected = (1, 2, 3, '4', 5.1)

        output = self.testfunc(1, 2, '3', 4, '5.1')
        self.assertEqual(output, expected)

        output = self.testfunc(1, 2, '3')
        self.assertEqual(output, expected)

        bad_input = ('a', 'b', 'c')
        self.assertRaises(Exception, bad_input, self.testfunc)

    def tearDown(self):
        pass

def AutocastCardTest(TestCase):
    def setUp(self):
        @autocast
        def testfunc(c: Card):
            return c

        self.testfunc = testfunc

    def test_autocast(self):
        expected = Card('7h')

        output = self.testfunc(Card('7h'))
        self.assertEqual(output, expected)

    def tearDown(self):
        pass
