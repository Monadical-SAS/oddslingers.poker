from datetime import timedelta

from django.utils import timezone

from banker.deprecated import create_transfer

from sidebets.models import Sidebet


def make_sidebet(user, player, amt=None, sidebet_parent=None, rebuy=False,
                 status='active', mins_delay=None, end_time=None, **kwargs):

    odds = get_odds(player)
    start_time = timezone.now()
    if mins_delay:
        start_time += timedelta(minutes=mins_delay)

    bet = Sidebet(
        user=user,
        player=player,
        table=player.table,
        odds=odds,
        amt=amt,
        start_time=start_time,
        end_time=end_time,
        from_rebuy=rebuy,
        status=status,
        sidebet_parent=sidebet_parent
    )
    notes = f'{user.username} sidebet on {player.username} amt {amt}'
    transfer = create_transfer(user, bet, amt, notes)

    user_balance = user.userbalance().balance
    if not user_balance >= amt:
        msg = f'{user} cannot sidebet with {amt} when balance={user_balance}'
        raise ValueError(msg)

    return (bet, transfer)


def get_sidebets(user, table=None, order_by=('status', '-created')):
    if not user or not user.is_authenticated:
        return Sidebet.objects.none()
    
    sidebets = Sidebet.objects.filter(user_id=user.id)
    if table is not None:
        sidebets = sidebets.filter(table=table)
    
    if order_by:
        return sidebets.order_by(*order_by)
    return sidebets


def get_odds(player):
    # TODO: bookmaking math
    return 1
