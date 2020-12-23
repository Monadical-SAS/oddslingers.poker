from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from banker.models import BalanceTransfer
from banker.mutations import create_transfer, buy_chips

from oddslingers.mutations import execute_mutations, MutationError


class CashierTest(TestCase):
    def setUp(self):
        self.pirate = get_user_model().objects.create_user(
            username='pirate',
            email='nick@hello.com',
            password='banana'
        )
        self.cuttlefish = get_user_model().objects.create_user(
            username='cuttlefish',
            email='sam@hello.com',
            password='banana'
        )
        self.cowpig = get_user_model().objects.create_user(
            username='cowpig',
            email='maxy@hello.com',
            password='banana'
        )
        self.ajfenix = get_user_model().objects.create_user(
            username='ajfenix',
            email='aj@hello.com',
            password='banana'
        )

        self.users = [self.pirate, self.cuttlefish, self.cowpig, self.ajfenix]

    def tearDown(self):
        BalanceTransfer.objects.all().delete()
        get_user_model().objects.all().delete()


class TransfersTest(CashierTest):
    def test_user_to_user(self):
        execute_mutations(
            buy_chips(self.pirate, Decimal(1337) * 2)
        )
        execute_mutations(
            create_transfer(self.pirate, self.cowpig, Decimal(1337))
        )
        # import ipdb; ipdb.set_trace()
        self.assertEqual(
            self.pirate.userbalance().balance,
            self.cowpig.userbalance().balance
        )

    def test_user_to_user_not_enough_balance(self):
        with self.assertRaisesMessage(
                MutationError,
                f'User {self.pirate.username} does not have the required balance'
            ):
            execute_mutations(
                create_transfer(self.pirate, self.cowpig, Decimal(1337))
            )
