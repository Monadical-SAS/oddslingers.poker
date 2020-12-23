from datetime import datetime
from decimal import Decimal
from typing import List, Dict

from django.db.models import Sum, Q, QuerySet, F
from django.core.cache import cache
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType

from oddslingers.models import User, UserBalance
from oddslingers.model_utils import BaseModel
from oddslingers.settings import CURRENT_SEASON
from banker.models import BalanceTransfer, Cashier
from poker.models import PokerTable, Freezeout


def get_timing_kwargs(start_date: datetime=None,
                      end_date: datetime=None) -> Dict:
    timing_kwargs = {}
    if start_date is not None:
        timing_kwargs['timestamp__gte'] = start_date
    if end_date is not None:
        timing_kwargs['timestamp__lt'] = end_date
    return timing_kwargs


def deposits(user: User, start_date: datetime=None,
             end_date: datetime=None, season: int=CURRENT_SEASON) -> QuerySet:
    timing_kwargs = get_timing_kwargs(start_date, end_date)

    cashier = Cashier.load()
    return BalanceTransfer.objects.season(season).filter(
        source_id=cashier.id,
        dest_id=user.id,
        **timing_kwargs
    ).order_by('timestamp')

def winnings(user: User, start_date: datetime=None,
             end_date: datetime=None,
             season: int=CURRENT_SEASON) -> QuerySet:
    timing_kwargs = get_timing_kwargs(start_date, end_date)

    tabletype = ContentType.objects.get_for_model(PokerTable)

    credits = BalanceTransfer.objects.season(season).filter(
        source_type=tabletype,
        dest_id=user.id,
        **timing_kwargs
    ).aggregate(Sum('amt'))['amt__sum'] or 0

    debits = BalanceTransfer.objects.season(season).filter(
        dest_type=tabletype,
        source_id=user.id,
        **timing_kwargs
    ).aggregate(Sum('amt'))['amt__sum'] or 0

    return credits - debits


def buyins_for_table(user: User, table: PokerTable,
                     season: int=CURRENT_SEASON) -> QuerySet:
    return BalanceTransfer.objects.season(season).filter(
        source_id=user.id,
        dest_id=table.id
    ).aggregate(Sum('amt'))['amt__sum'] or 0

def transfer_history(user: User,
                     start_date: datetime=None,
                     end_date: datetime=None,
                     season: int=CURRENT_SEASON) -> QuerySet:
    timing_kwargs = get_timing_kwargs(start_date, end_date)

    return BalanceTransfer.objects.season(season).filter(
        Q(source_id=user.id) | Q(dest_id=user.id),
        **timing_kwargs
    ).order_by('-timestamp')

def table_transfer_history(user: User,
                           start_date: datetime=None,
                           end_date: datetime=None,
                           season: int=CURRENT_SEASON) -> QuerySet:
    timing_kwargs = get_timing_kwargs(start_date, end_date)

    tabletype = ContentType.objects.get_for_model(PokerTable)

    return BalanceTransfer.objects.season(season).filter(
          (Q(source_type=tabletype) & Q(dest_id=user.id))
        | (Q(source_id=user.id) & Q(dest_type=tabletype)),
        **timing_kwargs
    ).order_by('-timestamp')

def freezeout_transfer_history(user: User,
                               start_date: datetime=None,
                               end_date: datetime=None,
                               season: int=CURRENT_SEASON) -> QuerySet:
    timing_kwargs = get_timing_kwargs(start_date, end_date)

    freezeouttype = ContentType.objects.get_for_model(Freezeout)

    return BalanceTransfer.objects.season(season).filter(
          (Q(source_type=freezeouttype) & Q(dest_id=user.id))
        | (Q(source_id=user.id) & Q(dest_type=freezeouttype)),
        **timing_kwargs
    ).order_by('-timestamp')

def balance(obj: BaseModel, other_obj: BaseModel=None,
            season: int=CURRENT_SEASON) -> Decimal:
    assert obj is not None, 'Tried to check the balance of a None object'

    if other_obj is None:
        credits = BalanceTransfer.objects.season(season).filter(
            dest_id=obj.id
        ).aggregate(Sum('amt'))['amt__sum'] or Decimal(0)
        debits = BalanceTransfer.objects.season(season).filter(
            source_id=obj.id
        ).aggregate(Sum('amt'))['amt__sum'] or Decimal(0)
    else:
        credits = BalanceTransfer.objects.season(season).filter(
            dest_id=obj.id,
            source_id=other_obj.id
        ).aggregate(Sum('amt'))['amt__sum'] or Decimal(0)
        debits = BalanceTransfer.objects.season(season).filter(
            source_id=obj.id,
            dest_id=other_obj.id
        ).aggregate(Sum('amt'))['amt__sum'] or Decimal(0)
    return credits - debits


def create_transfer(src: BaseModel, dst: BaseModel,
                    amt: int, notes=None) -> List[BaseModel]:
    objs_to_save = []
    src_is_user = isinstance(src, get_user_model())
    dst_is_user = isinstance(dst, get_user_model())
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


def update_user_balance(user: User, amt: int, is_dst=False) -> UserBalance:
    user_balance = user.userbalance()
    if not is_dst and user_balance.balance < amt:
        raise ValueError('User does not have enough balance for the transfer')
    amount = amt if is_dst else -amt
    user_balance.balance = F('balance') + amount
    return user_balance


def buy_chips(user: User, amt: int, notes='buy-in') -> List[BaseModel]:
    cashier = Cashier.load()
    return create_transfer(cashier, user, amt, notes)

def sell_chips(user, amt, notes='sell-out'):
    cashier = Cashier.load()
    return create_transfer(user, cashier, amt, notes)

def transfer_chips(from_user: User,
                   to_user: User, amt: int) -> List[BaseModel]:
    return create_transfer(from_user, to_user, amt, 'chip-transfer')

def cashier_balance(cached=False):
    if cached:
        return cache.get_or_set('cashier_balance', cashier_balance)

    cashier = Cashier.load()
    return balance(cashier)

def chips_received(user: User, season: int=CURRENT_SEASON) -> Decimal:
    user_type = ContentType.objects.get_for_model(User)
    user_filter = Q(dest_id=user.id) & Q(source_type=user_type)
    return BalanceTransfer.objects\
                          .season(season)\
                          .filter(user_filter)\
                          .aggregate(Sum('amt'))['amt__sum'] or Decimal(0)

def chips_sent(user: User, season: int=CURRENT_SEASON) -> Decimal:
    user_type = ContentType.objects.get_for_model(User)
    user_filter = Q(source_id=user.id) & Q(dest_type=user_type)
    return BalanceTransfer.objects\
                          .season(season)\
                          .filter(user_filter)\
                          .aggregate(Sum('amt'))['amt__sum'] or Decimal(0)
