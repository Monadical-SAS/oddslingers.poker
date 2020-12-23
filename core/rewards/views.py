import logging

from typing import List, Tuple

from django.conf import settings

from oddslingers.tasks import track_analytics_event
from oddslingers.model_utils import BaseModel
from oddslingers.models import User

from banker.views import buy_chips

from .models import Badge
from .constants import (
    BADGE_DESCRIPTIONS, NEWCOMER_BADGES, NEWCOMER_REWARD,
    EXCEPTIONAL_BADGES, EXCEPTIONAL_UNUSUAL_REWARD, REGULAR_BADGE_REWARD,
    COMPLETED_NEWCOMER_REWARD, NO_REWARD_BADGES, XSS_STRINGS, SWEAR_WORDS
)

logger = logging.getLogger('oddslingers')


def earn_first_time_chips(badge: Badge) -> List[BaseModel]:
    if badge.name in NEWCOMER_BADGES.keys():
        reward_amt = NEWCOMER_REWARD
    elif badge.name in EXCEPTIONAL_BADGES.keys():
        reward_amt = EXCEPTIONAL_UNUSUAL_REWARD
    else:
        reward_amt = REGULAR_BADGE_REWARD
    return buy_chips(
        badge.user,
        reward_amt,
        notes=f"Badge: {badge.description}"
    )


def reward_completed_badge(user: User, currently_earned=None) -> List[BaseModel]:
    for badge in NEWCOMER_BADGES.keys():
        badge_doesnt_exist = not Badge.objects.filter(
            user=user,
            name=badge
        ).exists()
        if badge_doesnt_exist or badge != currently_earned:
            return []

    return [
        *award_badge(user=user, name='completed', max_times=1),
        *buy_chips(
            user,
            COMPLETED_NEWCOMER_REWARD,
            notes="Completed easily obtained badges"
        )
    ]


def award_badge(user: User, name: str, max_times: int=None) -> List[BaseModel]:
    objects_to_save: List[BaseModel] = []
    if name not in BADGE_DESCRIPTIONS.keys():
        raise ValueError(
            f"Trying to reward a badge that doesn't exist: {name}"
        )

    if name in NEWCOMER_BADGES.keys():
        max_times = 1

    if max_times:
        if Badge.objects\
                .current_season()\
                .filter(user=user, name=name)\
                .count() >= max_times:
            return []

    first_time_earned = not Badge.objects\
                                 .current_season()\
                                 .filter(user=user, name=name)\
                                 .exists()
    badge = Badge(user=user, name=name, season=settings.CURRENT_SEASON)
    objects_to_save.append(badge)

    if first_time_earned and name not in NO_REWARD_BADGES.keys():
        objects_to_save += earn_first_time_chips(badge)
        objects_to_save += reward_completed_badge(user, name)

    conditions_to_notify = [
        name not in ('genesis', 'fearless_leader', 'hello_world', 'shove'),
        not user.is_robot
    ]
    if all(conditions_to_notify):
        track_analytics_event.send(
            user.username,
            f'got badge: {name}',
            topic='Badges'
        )

    return objects_to_save


def reward_attempted_xss(user: User, input_val: dict) -> List[BaseModel]:
    string = str(input_val).lower()

    if any(attack in string for attack in XSS_STRINGS):
        logger.warning('User attempted an exploit', extra={
            'user': user,
            'val': string,
        })
        return award_badge(user=user, name='black_hat', max_times=10)
    return []


def reward_swearing(user: User, input_val: dict) -> List[BaseModel]:
    string = str(input_val).lower()

    if any(word in string for word in SWEAR_WORDS):
        return award_badge(user=user, name='potty_mouth', max_times=10)
    return []

def check_xss_swearing(user: User, input_val: dict) -> Tuple[List[BaseModel], bool]:
    badge_objs = reward_attempted_xss(user, input_val)
    badge_objs += reward_swearing(user, input_val)
    return badge_objs
