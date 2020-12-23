import uuid

from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from oddslingers.model_utils import BaseModel
from oddslingers.managers import SeasonLogLikeManager


class Cashier(BaseModel):
    ID = '10' * 16
    id = models.UUIDField(primary_key=True, default=ID, editable=False)

    def save(self, *args, **kwargs):
        # make sure the ID they are trying to save matches the singleton's 
        #   only allowed ID
        if str(self.id) != str(self.ID):
            raise ValueError('This is intended to be a singleton.')

        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        try:
            return cls.objects.get()
        except cls.DoesNotExist:
            obj, _ = cls.objects.get_or_create()
            return obj


class BalanceTransfer(BaseModel):
    objects = SeasonLogLikeManager(creation_date_field='timestamp')

    balance_models = (models.Q(app_label='oddslingers', model='User') | 
                      models.Q(app_label='poker', model='PokerTable') | 
                      models.Q(app_label='banker', model='Cashier'))

    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    timestamp = models.DateTimeField(auto_now=True, db_index=True)

    source_type = models.ForeignKey(ContentType, 
                                    on_delete=models.DO_NOTHING, 
                                    limit_choices_to=balance_models, 
                                    related_name='sent_transfers')
    
    source_id = models.UUIDField(null=False, db_index=True)
    source = GenericForeignKey('source_type', 'source_id')

    dest_type = models.ForeignKey(ContentType, 
                                  on_delete=models.DO_NOTHING, 
                                  limit_choices_to=balance_models, 
                                  related_name='recv_transfers')
    
    dest_id = models.UUIDField(null=False, db_index=True)
    dest = GenericForeignKey('dest_type', 'dest_id')

    amt = models.DecimalField(max_digits=20, decimal_places=2, null=False)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        index_together = (('source_type', 'dest_type', 'timestamp'))

    def __str__(self):
        return f'{self.source} -> {self.dest} {self.amt} ({self.notes})'

    def __repr__(self):
        source, dest = (self.source_type, self.dest_type)
        return f'<Transfer {self.amt} from {source} to {dest}>'
