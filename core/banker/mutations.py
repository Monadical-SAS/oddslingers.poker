from typing import Union
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import F

from oddslingers.models import UserBalance
from oddslingers.mutations import Mutation, MutationList

from banker.models import BalanceTransfer, Cashier

from poker.models import PokerTable


User = get_user_model()


BalanceHolder = Union[User, PokerTable, Cashier]

def create_transfer(src: BalanceHolder, dst: BalanceHolder, amt: Decimal,
                    notes: str=None) -> MutationList:
    mutations = []
    src_is_user = isinstance(src, User)
    dst_is_user = isinstance(dst, User)

    if src_is_user:
        mutations += [
            # Throws if player doesn't have enough balance
            Mutation(
                qs=UserBalance.objects.current_season().select_for_update(),
                method_name='get',
                kwargs={'user': src, 'balance__gte': amt},
                error_msg=f"User {src.username} does not have the required balance"
            ),
            Mutation(
                qs=UserBalance.objects.current_season().filter(user=src),
                method_name='update',
                kwargs={'balance': F('balance') - amt}
            )
        ]
    if dst_is_user:
        mutations.append(Mutation(
            qs=UserBalance.objects.current_season()
                                  .filter(user=dst)
                                  .select_for_update(),
            method_name='update',
            kwargs={'balance': F('balance') + amt}
        ))
    mutations.append(Mutation(
        qs=BalanceTransfer.objects,
        method_name='create',
        kwargs={'source': src, 'dest': dst, 'amt': amt, 'notes': notes}
    ))
    return mutations


def buy_chips(user: User, amt: Decimal, notes: str='buy-in') -> MutationList:
    cashier = Cashier.load()
    return create_transfer(cashier, user, amt, notes)


def transfer_chips(from_user: User, to_user: User, amt: Decimal) -> MutationList:
    return create_transfer(from_user, to_user, amt, 'chip-transfer')
