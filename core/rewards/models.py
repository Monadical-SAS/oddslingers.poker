from django.db import models
from django.conf import settings

from oddslingers.model_utils import BaseModel
from oddslingers.managers import SeasonRegularManager

from poker.constants import SEASONS

from .constants import BADGE_DESCRIPTIONS


class Badge(BaseModel):
    objects = SeasonRegularManager()

    user = models.ForeignKey(settings.AUTH_USER_MODEL,
                                on_delete=models.CASCADE,
                                null=False)

    created = models.DateTimeField(auto_now_add=True)
    season = models.IntegerField(db_index=True)
    name = models.CharField(
        choices=BADGE_DESCRIPTIONS.items(),
        max_length=32,
        null=False,
        db_index=True,
    )

    class Meta:
        index_together = (('user', 'season'),)

    @property
    def description(self):
        assert self.name in BADGE_DESCRIPTIONS.keys(),\
            "incorrect name choice in badge"

        season = self.season
        if 'week' in self.name:
            week = self.get_badge_week(season)
            return BADGE_DESCRIPTIONS[self.name].format(week, season)

        if 'season' in self.name:
            return BADGE_DESCRIPTIONS[self.name].format(season)

        return BADGE_DESCRIPTIONS[self.name]

    def get_badge_week(self, season):
        season_start = SEASONS[season][0]
        time_diff = self.created - season_start
        return int(time_diff.days / 7)


# class RewardsProfile(BaseModel):
#     user = models.OneToOneField(settings.AUTH_USER_MODEL,
#                                 on_delete=models.CASCADE,
#                                 null=False)

#     location = models.CharField(null=True, max_length=64)

#     hands_played_this_session = models.IntegerField(default=0)
#     total_hands_played = models.IntegerField(default=0)

#     winnings_this_session = models.IntegerField(default=0)

#     king_of_the_hill_points = models.IntegerField(default=0)

#     total_rewards_points = models.IntegerField(default=0)

