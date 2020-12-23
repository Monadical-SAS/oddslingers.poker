from django.db import models
from django.conf import settings

from oddslingers.settings import DEFAULT_HOST, DEFAULT_HTTP_PROTOCOL
from oddslingers.model_utils import BaseModel

class TrackedLink(BaseModel):
    key = models.CharField(max_length=16, null=False, db_index=True)
    campaign = models.CharField(max_length=64, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL,
                                   on_delete=models.SET_NULL,
                                   null=True)
    target_url = models.URLField(max_length=128, null=False)

    created = models.DateTimeField(auto_now_add=True)
    clicks = models.IntegerField(default=0)

    def short_url(self):
        return f'{DEFAULT_HTTP_PROTOCOL}://{DEFAULT_HOST}/s/{self.key}/'
