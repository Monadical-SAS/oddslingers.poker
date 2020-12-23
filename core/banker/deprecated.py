from django.contrib.auth import get_user_model

from banker.models import BalanceTransfer, Cashier


User = get_user_model()

# NOTE: This file is a legacy version of banker methods using the old logic
# This exists only to support Sidebets with the previous style
# For a more recent version of these methods please check `banker/mutations.py`
# Be mindful that these methods will disappear in the near future when Sidebets
# get refactored.

def create_transfer(src, dst, amt, notes=None):
    objs_to_save = []
    src_is_user = isinstance(src, User)
    dst_is_user = isinstance(dst, User)
    if src_is_user:
        objs_to_save.append(update_user_balance(src, amt))
    if dst_is_user:
        objs_to_save.append(update_user_balance(dst, amt, is_dst=True))
    transfer = BalanceTransfer(
        source=src,
        dest=dst,
        amt=amt,
        notes=notes
    )
    objs_to_save.append(transfer)
    return objs_to_save


def update_user_balance(user, amt, is_dst=False):
    user_balance = user.userbalance()
    if not is_dst and user_balance.balance < amt:
        raise ValueError('User does not have enough balance for the transfer')
    amount = amt if is_dst else -amt
    user_balance.balance += amount
    return user_balance


def buy_chips(user, amt, notes='buy-in'):
    cashier = Cashier.load()
    return create_transfer(cashier, user, amt, notes)


def sell_chips(user, amt, notes='sell-out'):
    cashier = Cashier.load()
    return create_transfer(user, cashier, amt, notes)
