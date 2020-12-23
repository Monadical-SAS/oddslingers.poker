import logging

from oddslingers.tasks import track_analytics_event
from oddslingers.models import User

from banker.mutations import create_transfer
from banker.models import Cashier

from oddslingers.mutations import Mutation, MutationList

from .models import Badge
from .constants import (
    BADGE_DESCRIPTIONS, NEWCOMER_BADGES, NEWCOMER_REWARD,
    EXCEPTIONAL_BADGES, EXCEPTIONAL_UNUSUAL_REWARD, REGULAR_BADGE_REWARD,
    COMPLETED_NEWCOMER_REWARD, NO_REWARD_BADGES, XSS_STRINGS, SWEAR_WORDS
)

logger = logging.getLogger('oddslingers')


def earn_first_time_chips(user: User, name: str):
    cashier = Cashier.load()
    notes = f'Badge {name} chips reward'
    if name in NEWCOMER_BADGES.keys():
        reward_amt = NEWCOMER_REWARD
    elif name in EXCEPTIONAL_BADGES.keys():
        reward_amt = EXCEPTIONAL_UNUSUAL_REWARD
    else:
        reward_amt = REGULAR_BADGE_REWARD
    return create_transfer(
        cashier,
        user,
        reward_amt,
        notes=notes
    )


def reward_completed_badge(user: User, currently_earned=None) -> MutationList:
    for badge in NEWCOMER_BADGES.keys():
        badge_doesnt_exist = not Badge.objects.current_season().filter(
            user=user,
            name=badge
        ).exists()
        if badge_doesnt_exist or badge != currently_earned:
            return []

    return [
        Mutation(
            qs=Badge.objects,
            method_name='create_for_current_season',
            kwargs={'user': user, 'name': 'completed'}
        ),
        *create_transfer(
            Cashier.load(),
            user,
            COMPLETED_NEWCOMER_REWARD,
            notes="Completed easily obtained badges"
        )
    ]


def award_badge(user: User, name: str, max_times: int=None) -> MutationList:
    mutations = []
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
    mutations.append(Mutation(
        qs=Badge.objects,
        method_name='create_for_current_season',
        kwargs={'user': user, 'name': name}
    ))

    if first_time_earned and name not in NO_REWARD_BADGES.keys():
        mutations += earn_first_time_chips(user, name)
        mutations += reward_completed_badge(user, name)

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

    return mutations


def reward_attempted_xss(user: User, input_val: dict) -> MutationList:
    string = str(input_val).lower()

    if any(attack in string for attack in XSS_STRINGS):
        logger.warning('User attempted an exploit', extra={
            'user': user,
            'val': string,
        })
        return award_badge(user=user, name='black_hat', max_times=10)
    return []


def reward_swearing(user: User, input_val: dict) -> MutationList:
    string = str(input_val).lower()

    if any(word in string for word in SWEAR_WORDS):
        return award_badge(user=user, name='potty_mouth', max_times=10)
    return []


def check_xss_swearing(user: User, input_val: dict) -> MutationList:
    return [
        *reward_attempted_xss(user, input_val),
        *reward_swearing(user, input_val)
    ]


def reward_signup_badges(user, post_data) -> MutationList:
    mutations = []
    if User.objects.count() <= 1000:
        mutations += award_badge(user, 'genesis')

    if user.created.year < 2019:
        mutations += award_badge(user, 'fearless_leader')

    mutations += reward_attempted_xss(user, post_data)
    mutations += reward_swearing(user, post_data)
    return mutations
