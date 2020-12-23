from django.db import models
from django.conf import settings

from banker.deprecated import create_transfer

from oddslingers.model_utils import BaseModel

from poker.constants import SIDEBET_STATUS
from poker.models import Player, PokerTable


class Sidebet(BaseModel):
    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                             on_delete=models.CASCADE,
                             null=False)

    player = models.ForeignKey(Player,
                               on_delete=models.CASCADE,
                               null=False)

    table = models.ForeignKey(PokerTable,
                              on_delete=models.CASCADE,
                              null=False)

    sidebet_parent = models.ForeignKey("Sidebet",
                                        on_delete=models.SET_NULL,
                                        null=True)

    odds = models.DecimalField(max_digits=15, decimal_places=10)
    amt = models.DecimalField(max_digits=20, decimal_places=2)

    created = models.DateTimeField(auto_now_add=True)
    start_time = models.DateTimeField(null=True)
    end_time = models.DateTimeField(null=True)

    status = models.CharField(max_length=25, choices=SIDEBET_STATUS,
                              default='active')

    starting_stack = models.DecimalField(max_digits=20, decimal_places=2,
                                         default=0)
    ending_stack = models.DecimalField(max_digits=20, decimal_places=2,
                                       default=0)
    from_rebuy = models.BooleanField(default=False)

    class Meta:
        index_together = (('table', 'status'),)

    @property
    def player_stack(self):
        if self.is_closed():
            return self.ending_stack
        return self.player.stack

    @property
    def sidebets_children(self):
        return self.sidebet_set.all()

    def is_opening(self):
        return self.status == 'opening'

    def is_active(self):
        return self.status == 'active'

    def is_closing(self):
        return self.status == 'closing'

    def is_closed(self):
        return self.status == 'closed'

    def open(self):
        self.status = 'active'
        self.starting_stack = self.player_stack

    def close(self, use_current_stack=False):
        self._close(use_current_stack)

        amt = self.current_value()
        notes = f'{self.user.username} gets paid {amt} for {self.player.username} sidebet'
        return create_transfer(self, self.user, amt, notes)

    def _close(self, use_current_stack=False):
        if use_current_stack:
            self.ending_stack = self.player_stack
        self.status = 'closed'

    def prepare_to_close(self):
        self.status = 'closing'

    def current_value(self):
        if self.starting_stack == 0:
            return self.amt

        ratio = self.amt / self.starting_stack
        diff = self.player_stack - self.starting_stack

        if diff > 0:
            diff *= self.odds

        normalized_stack = self.starting_stack + diff

        return ratio * normalized_stack

    def __json__(self, *attrs):
        value = self.current_value()
        created = f'{self.created:%Y-%m-%d %H:%M}' if self.created else '---'
        parent_id = self.sidebet_parent.id if self.sidebet_parent else None

        value_class = ''
        if self.amt < value:
            value_class = 'green'
        elif self.amt != value:
            value_class = 'red'
        return {
            'id': self.id,
            'table': {
                'id': self.table.id,
                'path': self.table.path,
                'name': self.table.name
            },
            'player': {
                'username': self.player.username,
                'id': self.player.id
            },
            'sidebet_parent_id': parent_id,
            'amt': f'{self.amt:.2f}',
            'starting_stack': self.starting_stack or 'First hand',
            'current_stack': self.player_stack,
            'odds': f'{self.odds:.2f}',
            'current_value': f'{value:.3f}',
            'value_class': value_class,
            'status': self.get_status_display(),
            'created': created,
            'from_rebuy': self.from_rebuy
        }
