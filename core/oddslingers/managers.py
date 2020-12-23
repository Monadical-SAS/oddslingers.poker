from typing import Tuple

from django.db import models
from django.conf import settings

from poker.constants import SEASONS


class SeasonLogLikeManager(models.Manager):
    def __init__(self, creation_date_field=None, *args, **kwargs):
        super().__init__()
        self.creation_date_field = creation_date_field or 'created_at'

    def season(self, season_number: int):
        season_range = SEASONS[season_number]
        season_start, season_end = season_range
        return self.filter(**{
            f'{self.creation_date_field}__gte': season_start,
            f'{self.creation_date_field}__lt': season_end
        })

    def current_season(self):
        return self.season(settings.CURRENT_SEASON)


class SeasonRegularManager(models.Manager):
    def create_for_season(self, season_number: int, user, **kwargs) -> Tuple:
        try:
            self.get_or_create(season=season_number, user=user, **kwargs)
        except self.model.MultipleObjectsReturned:
            self.create(season=season_number, user=user, **kwargs)

    def create_for_current_season(self, user, **kwargs) -> Tuple:
        return self.create_for_season(settings.CURRENT_SEASON, user, **kwargs)

    def season(self, season_number: int) -> models.QuerySet:
        return self.filter(season=season_number)

    def current_season(self) -> models.QuerySet:
        return self.season(settings.CURRENT_SEASON)
