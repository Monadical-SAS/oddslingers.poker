import logging
from typing import List, NamedTuple, Union, Dict, Tuple, Any

from django.db.models.query import QuerySet
from django.db.models.manager import Manager
from django.db.models import Model
from django.db import transaction
from django.db.models import F

from poker.models import Player

from oddslingers.models import UserStats, User


logger = logging.getLogger('oddslingers')


QS_ERROR_MSG = 'QuerySets should not be evaluated before they are executed to '\
               'maintain concurrency safety'

SUPPORTED_METHODS = [
    'get', 'get_or_create', 'create', 'update', 'update_or_create', 'delete',
    'create_for_current_season', 'create_for_season'
]
METHOD_ERROR_MSG = "Method '{1}' currently not supported in Mutations"


MutationResult = Union[int, None, Tuple[Model, bool], Model]


class Mutation(NamedTuple):
    qs: Union[QuerySet, Manager]
    method_name: str
    kwargs: Dict[str, Any]
    error_msg: str = None


MutationList = List[Mutation]


class MutationError(Exception):
    pass


def execute_mutations(mutations: MutationList):
    with transaction.atomic():
        for qs, method_name, kwargs, error_msg in mutations:
            assert isinstance(qs, QuerySet)\
                   or isinstance(qs, Manager), QS_ERROR_MSG
            assert method_name in SUPPORTED_METHODS,\
                   METHOD_ERROR_MSG.format(method_name)

            method = getattr(qs, method_name)
            try:
                method(**kwargs)
            except Exception as e:
                logger.exception(error_msg or str(e), extra={
                    'exception': f'{e.__class__.__name__}: {e}',
                    'error_msg': error_msg,
                    'mutation': {
                        'qs': qs,
                        'method_name': method_name,
                        'kwargs': kwargs
                    }
                })
                raise MutationError(error_msg or str(e)) from e


def increase_hands_played(player: Player) -> MutationList:
    return [Mutation(
        qs=UserStats.objects.current_season()
                            .filter(user=player.user)
                            .select_for_update(),
        method_name='update',
        kwargs={'hands_played': F('hands_played') + 1},
    )]


def increase_games_level(user: User, chips: float) -> MutationList:
    return [Mutation(
        qs=UserStats.objects.current_season()
                            .filter(user=user)
                            .select_for_update(),
        method_name='update',
        kwargs={'games_level': chips}
    )]
