from decimal import Decimal
from datetime import timedelta
from collections import defaultdict

from django.utils import timezone
from django.contrib.auth import get_user_model

from poker.subscribers import Subscriber

from poker.constants import Event, ACTIVE_PLAYSTATES

from sidebets.views import make_sidebet


User = get_user_model()

class SidebetSubscriber(Subscriber):
    def __init__(self, accessor):
        self.accessor = accessor
        self.objects_to_save = []
        self.sidebets = self.get_sidebets()
        self.to_broadcast = defaultdict(list)
        for sidebet in self.sidebets:
            self.to_broadcast[sidebet.user].append(sidebet)

    def get_sidebets(self):
        try:
            sidebets_qs = self.accessor.table.sidebets
        except AttributeError:
            sidebets_qs = self.accessor.table.sidebet_set.exclude(status='closed')

        new_sidebets = set()
        for sidebet in sidebets_qs:
            sidebet.player = self.accessor.player_by_player_id(
                sidebet.player.id
            )
            new_sidebets.add(sidebet)

        return new_sidebets

    def dispatch(self, subj, event, **kwargs):
        if event == Event.NEW_HAND:
            self.to_broadcast = defaultdict(list)
            self.objects_to_save += list(self.sidebets)

            for sidebet in self.sidebets:
                if sidebet.is_active():
                    self.to_broadcast[sidebet.user].append(sidebet)

        elif event == Event.END_HAND:
            self.sidebets = self.get_sidebets()
            self.open_sidebets()
            self.set_closing_sidebets()
            self.close_sidebets()

        elif event in [Event.BET, Event.RAISE_TO, Event.CALL, Event.WIN]:
            self.to_broadcast = defaultdict(list)
            self.sidebets = self.get_sidebets()
            for sidebet in self.sidebets:
                if not sidebet.is_closed():
                    self.to_broadcast[sidebet.user].append(sidebet)

        elif event == Event.CREATE_SIDEBET:
            user = kwargs['user']
            plyr = kwargs['player']
            amt = Decimal(kwargs['amt'])
            try:
                sidebet, transfer = make_sidebet(
                    user, plyr, amt, delay=None, status='opening'
                )
                self.objects_to_save += [
                    sidebet,
                    *transfer
                ]
                self.to_broadcast[sidebet.user].append(sidebet)
            except ValueError:
                pass

        elif event == Event.CLOSE_SIDEBET:
            sidebets = kwargs['sidebets']
            for sidebet in sidebets:
                if sidebet.is_active():
                    sidebet.prepare_to_close()
                    self.objects_to_save.append(sidebet)

        elif event == Event.LEAVE_SEAT:
            self.close_sidebet_leaving_player(subj)

        elif event == Event.CREATE_TRANSFER:
            self.adjust_sidebets(**kwargs)

    def open_sidebets(self):
        for sidebet in self.sidebets:
            if sidebet.is_opening():
                sidebet.open()
                self.objects_to_save.append(sidebet)

    def close_sidebet_leaving_player(self, player):
        for sidebet in self.sidebets:
            if sidebet.player.id == player.id:
                transfer = sidebet.close(use_current_stack=True)
                self.objects_to_save += [
                    sidebet,
                    *transfer
                ]

    def set_closing_sidebets(self):
        for sidebet in self.sidebets:
            if sidebet.is_closing():
                transfer = sidebet.close(use_current_stack=True)
                self.objects_to_save += [
                    sidebet,
                    *transfer
                ]

    def close_sidebets(self):
        for sidebet in self.sidebets:
            if sidebet.player.stack == 0:
                sidebet.ending_stack = 0
                transfer = sidebet.close()
                self.objects_to_save += [
                    sidebet,
                    *transfer
                ]

    def initialize_stack(self, sidebet):
        now = timezone.now() + timedelta(seconds=1)
        if (now >= sidebet.start_time
                and not sidebet.starting_stack
                and sidebet.player.playing_state in ACTIVE_PLAYSTATES):
            sidebet.starting_stack = sidebet.player.stack

        return sidebet

    def adjust_sidebets(self, src=None, dst=None, amt=None, **kwargs):
        if isinstance(src, User):
            for sidebet in self.sidebets:
                if sidebet.player.user.id == src.id and sidebet.is_active():
                    sidebet.ending_stack = sidebet.player.stack - amt
                    transfer = sidebet.close()
                    self.objects_to_save += [
                        sidebet,
                        *transfer
                    ]

                    user = sidebet.user
                    plyr = sidebet.player
                    new_amt = sidebet.current_value()
                    parent = sidebet.sidebet_parent or sidebet
                    new_sidebet, new_transfer = make_sidebet(
                        user, plyr, new_amt, parent, delay=None, rebuy=True,
                    )
                    new_sidebet = self.initialize_stack(new_sidebet)
                    self.objects_to_save += [
                        new_sidebet,
                        *new_transfer
                    ]

    # def wins_and_losses(self):
    #     stack_record = PlayerStartingStackHistory.objects.get(
    #         table=self.accessor.table,
    #         hand_number=self.accesor.table.hand_number - 1,
    #     ).playerstacks

    #     diffs = {
    #         player.id: (
    #             stack_record[player]
    #           - self.accessor.player_by_player_id(plyr.id).stack
    #         )
    #         for player in stack_record.keys()
    #     }
    #     cashier = Cashier.load()

    #     updates = defaultdict(list)
    #     for active_sidebet in self.get_active_sidebets():
    #         amt = diffs.get(active_sidebet.player.id, 0)
    #         if amt:
    #             updates[user].append(
    #                 (player, amt * active_sidebet.odds)
    #             )

    #     return updates

    def updates_for_broadcast(self, player=None, spectator=None):
        updates = self.to_broadcast[spectator]
        return {'sidebets': updates or []}

    def commit(self):
        for obj in self.objects_to_save:
            obj.save()
