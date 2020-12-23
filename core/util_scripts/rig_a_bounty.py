from poker.models import PokerTable, Player
from poker.controllers import BountyController


tbl = PokerTable.objects.get(id='d194d058-c069-47bd-911f-ca6461712c04')
cont = HoldemController(tbl)
acc = cont.accessor

player = acc.player_by_username('derp')

player.cards = ['2s', '7h']
player.save()
