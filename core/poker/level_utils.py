from typing import List, Tuple

from django.db.models import Q
from django.contrib.contenttypes.models import ContentType

from banker.mutations import buy_chips
from banker.models import BalanceTransfer

from poker.constants import (
    CASH_GAME_BBS, CASHTABLES_LEVELUP_BONUS, TOURNEY_BUYIN_AMTS,
    TOURNEY_BUYIN_TIMES, N_BB_TO_NEXT_LEVEL,
)

from oddslingers.model_utils import BaseModel
from oddslingers.models import User
from oddslingers.tasks import track_analytics_event
from oddslingers.mutations import MutationList, increase_games_level



def update_levels(user: User, earned_amt: int=None,
                  plus_amt: int=None) -> Tuple[MutationList, bool]:
    mutations = []
    leveledup = False

    current_earned_chips = (
        (earned_chips(user) if earned_amt is None else earned_amt)
      + (user.public_chips_in_play if plus_amt is None else plus_amt)
    )
    if current_earned_chips > user.games_level:
        mutations += increase_games_level(user, current_earned_chips)

        cash_lvl = max(
            user.cashtables_level,
            current_earned_chips / N_BB_TO_NEXT_LEVEL
        )
        tourney_lvl = max(
            user.tournaments_level,
            current_earned_chips / TOURNEY_BUYIN_TIMES
        )
        calculated_levels = {
            'cashtables_level': max(
                (lvl for lvl in CASH_GAME_BBS if lvl <= cash_lvl),
                default=CASH_GAME_BBS[0]
            ),
            'tournaments_level': max(
                (lvl for lvl in TOURNEY_BUYIN_AMTS if lvl <= tourney_lvl),
                default=TOURNEY_BUYIN_AMTS[0]
            ),
        }

        for lvl_type, new_lvl in calculated_levels.items():
            if new_lvl > getattr(user, lvl_type):
                leveledup = True
                if lvl_type == 'cashtables_level':
                    mutations += levelup_bonuses(
                        user,
                        getattr(user, lvl_type),
                        new_lvl
                    )
                track_analytics_event.send(
                    user.username,
                    f'reached {lvl_type} from {getattr(user, lvl_type)} to {new_lvl}'
                )

    return mutations, leveledup


def levelup_bonuses(user: User, old_lvl, new_lvl) -> List[BaseModel]:
    mutations = []
    for lvl in CASH_GAME_BBS[::-1]:
        if old_lvl < lvl <= new_lvl:
            bonus_amt = CASHTABLES_LEVELUP_BONUS * lvl
            mutations += buy_chips(
                user,
                bonus_amt,
                f"Levelup: ㆔{lvl} bb table unlock bonus"
            )

    return mutations


def earned_chips(user: User) -> int:
    """
        User winnings since the last time its balance fall below zero
        no taking into account the chips received nor sent with other users
    """
    user_type = ContentType.objects.get_for_model(User)
    user_transfers = Q(source_id=user.id) & Q(dest_type=user_type)\
                   | Q(source_type=user_type) & Q(dest_id=user.id)

    transfers = BalanceTransfer.objects.current_season().filter(
        Q(source_id=user.id) | Q(dest_id=user.id),
    ).exclude(
        user_transfers
    ).order_by('timestamp')

    total = 0
    target_ids = {}
    for transfer in transfers:
        is_credit = True if transfer.dest_id == user.id else False

        target_id = transfer.source_id if is_credit else transfer.dest_id
        if not target_id in target_ids:
            target_ids.update({
                target_id: transfer.source if is_credit else transfer.dest
            })

        target = target_ids[target_id]
        exclude = hasattr(target, 'is_private') and target.is_private

        if not exclude:
            total += transfer.amt if is_credit else -transfer.amt

        # This allow users to start again from zero
        # when they lose everything
        if total < 0:
            total = 0

    return total

