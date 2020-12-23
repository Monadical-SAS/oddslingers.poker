import logging

from django.utils import timezone

from oddslingers.utils import secure_random_number
from poker.constants import Action, ACTIVE_ACTIONS, NL_HOLDEM, NL_BOUNTY
from poker.new_ai import (
    ai_betsize, ai_raisesize, get_smart_move, situation_is_preflop_open
)

logger = logging.getLogger('robots')


def get_robot_move(accessor, log, delay=False, stupid=True,
                warnings=True, suggested=None):
    logger.debug(f'>get_robot_move, stupid={stupid}, delay={delay}')
    robot = accessor.next_to_act()

    if not robot.user.is_robot and warnings:
        logger.warning("get_robot_move() was called for a non-robot player.")

    if stupid or accessor.table.table_type not in (NL_HOLDEM, NL_BOUNTY):
        logger.debug('getting a stupid move because')
        if stupid:
            logger.debug('stupid')
        else:
            logger.debug('gametype is ', accessor.table.table_type)

        if delay and get_delay(robot, accessor):
            # dont act yet, wait until next heartbeat tick
            # logger.debug('return None')
            return None

        actions = accessor.available_actions(robot.id)
        filtered_actions = set(actions).intersection(ACTIVE_ACTIONS)

        if suggested:
            suggested = Action.from_str(suggested)
            if suggested in filtered_actions:
                filtered_actions = {suggested}
        move = random_bot_move(robot, accessor, filtered_actions)
    else:
        logger.debug('getting a smart move')
        move = get_smart_move(accessor, log, delay=delay)

    # logger.debug(f'return {move}')
    return move


def get_delay(robot, accessor):
    last_timestamp = accessor.table.last_action_timestamp
    time_passed = (timezone.now() - last_timestamp).total_seconds()

    # for preflop opens, don't think too hard [0, 1]
    if situation_is_preflop_open(robot, accessor):
        random_delay = last_timestamp.microsecond % 2
    else:
        # effectively random number [2, 5] that won't change on next tick
        random_delay = last_timestamp.microsecond % 4 + 2

    return time_passed < random_delay


def random_bot_move(robot, accessor, available_actions):
    random_action_idx = secure_random_number(max_num=len(available_actions))
    action = list(available_actions)[random_action_idx]

    if action == Action.FOLD and Action.CHECK in available_actions:
        action = Action.CHECK

    args = {'player_id': robot.id}

    if action == Action.RAISE_TO:
        args['amt'] = ai_raisesize(accessor, robot)

    elif action == Action.BET:
        args['amt'] = ai_betsize(accessor, robot)

    elif action in (Action.FOLD, Action.CHECK, Action.CALL):
        pass

    else:
        raise Exception(f"Robot decided to {action} but doesn't know how")

    return str(action), args
