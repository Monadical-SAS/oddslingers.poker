import math
import logging

from decimal import Decimal

from oddslingers.utils import (
    round_to_multiple, secure_random_number  # noqa
)

from poker.hand_ranges import (
    Hand, HandRange, FULL_RANGE, preflop_range, pruned
)

from poker.monte_carlo import monte_carlo

from poker.bot_personalities import bot_personality, DEFAULT_BOT

from poker.constants import (
    NL_HOLDEM, PL_OMAHA, NL_BOUNTY, Action, Event
)
from poker.replayer import ActionReplayer

CACHE = {}
PREFLOP_BASE_RANGES = DEFAULT_BOT['preflop']

logger = logging.getLogger('robots')


def secure_random_float() -> float:
    """get a secure random float between 0.00000000 and 0.99999999"""
    return secure_random_number(100000000) / 100000000


def get_smart_move(accessor, log, delay=False, personality=None):
    '''
    Takes a player, accessor, assumed ranges, and the log, and spits
    out the move for the player. If the player doesn't have a known
    personality, it defaults to a basic one.

    You can find details now how the heuristics are done in
    `level_zero`, which is the only one that's currently finished.
    The basic idea is:
        * Calculate my hand's value. If it's high, value bet.
        * If it's not, decide whether to bluff.
        * If we're not bluffing or vbetting, but facing a wager,
            decide whether we have enough equity to call

    Each of these steps has a lot more detail and is governed by the
    personality of the player that's passed in.
    '''
    if accessor.table.table_type not in (NL_HOLDEM, NL_BOUNTY):
        raise NotImplementedError(f'No monte carlo for gametype: '\
                                  f'{accessor.table.table_type}')

    me = accessor.next_to_act()
    if not personality:
        personality = bot_personality(me)
    json_log = log.get_log(player='all', current_hand_only=True)

    logger.debug(f'\t>get_smart_move, player={me}')

    if situation_is_preflop_open(me, accessor):
        return preflop_open(me, accessor, personality)

    player_ranges = get_player_ranges(accessor, json_log)

    return ai_move(me, accessor, player_ranges, json_log, personality)


def ai_move(me, accessor, player_ranges, json_log, personality=None):
    if not personality:
        personality = bot_personality(me)

    level = bot_personality(me)['tactical']
    if level == 0:
        # look at hand value vs opp ranges
        # look at number of checks
        # high value: bet, low value: don't. If
        return level_zero(me, accessor, player_ranges, json_log, personality)

    return NotImplementedError('TODO: levels 1 and 2')
    # (TODO) LVL 1
    # calculate call ranges
    # get hand value vs those ranges
    # get fold equity
    # bet/raise equity == fold_equity + value
    # check/call equity == hand value * pot - amt
    # fold equity == 0
    # pick maximum equity play & bluff sometimes

    # (TODO) LVL 2
    # same as LVL 1 plus:
    # get implied odds (equity vs top-of-range)
    # find equity range "shape": flat vs top-of-range == semibluff
    return 'FOLD', {'player_id': me.id}


# LEVEL ZERO
def level_zero(me, accessor, player_ranges, json_log, personality=None):
    if not personality:
        personality = bot_personality(me)

    logger.debug(f'\t>level zero, personality={personality}')

    _chaotic = personality['chaotic']
    _belligerent = chaos_adjusted(personality['belligerent'], _chaotic)
    _tricky = chaos_adjusted(personality['tricky'], _chaotic)
    _opportunistic = chaos_adjusted(personality['opportunistic'], _chaotic)
    _storyteller = chaos_adjusted(personality['storyteller'], _chaotic)
    _curious = chaos_adjusted(personality['curious'], _chaotic, upper_bound=3)
    _optimist = chaos_adjusted(
        personality['optimist'],
        _chaotic,
        upper_bound=3
    )

    logger.debug('==>level_zero AI')
    logger.debug(f'personality:\n{personality}')
    logger.debug(accessor.describe(print_me=False))

    myhand = Hand(me.cards)
    ranges_with_my_hand = [
        hr if username != me.username else [myhand, *hr]
        for username, hr in player_ranges.items()
    ]

    global_handrange = global_range_from_ranges(
        ranges_with_my_hand,
        accessor.table.board_str
    )

    # decide whether to vbet
    myrank = global_handrange.percentile(myhand)
    logger.debug(f'\t myrank: {myrank}')

    slowplay = secure_random_float() < _tricky
    logger.debug(f'\t slowplay: {slowplay}')

    if not slowplay and myrank < _belligerent:
        return bet_or_raise(me, accessor)

    if not accessor.is_preflop():
        # decide whether to bluff
        check_rounds = n_checks(json_log) / len(accessor.showdown_players())
        weakness = check_rounds * _opportunistic
        fe_scalar = stackpot_fold_equity_scalar(accessor)
        logger.debug(f'\t check_rounds: {check_rounds}')
        logger.debug(f'\t fe_scalar: {fe_scalar}')

        bluff = secure_random_float() < fe_scalar * (_storyteller + weakness)
        logger.debug(f'\t bluff: {bluff}')

        if bluff:
            return bet_or_raise(me, accessor)

    # decide whether to call
    my_equity = global_handrange.hand_values[myhand]
    call_amt = accessor.call_amt(me, diff=True)
    logger.debug(f'\t call_amt: {call_amt}')

    n_streets_left = 0
    if accessor.is_preflop():
        n_streets_left = 3
    elif accessor.is_flop():
        n_streets_left = 2
    elif accessor.is_turn():
        n_streets_left = 1

    call_ev = ratio_adjusted(
        float(accessor.current_pot() + call_amt) * my_equity,
        float(_optimist) ** n_streets_left * float(_curious),
        upper_bound=math.inf
    )

    logger.debug(f'\t my_equity: {my_equity}')
    logger.debug(f'\t pot: {float(accessor.current_pot() + call_amt)}')
    logger.debug(f'\t call_ev: {call_ev}')
    call = call_ev > call_amt
    if call:
        return check_or_call(me, accessor)

    return check_or_fold(me, accessor)


def global_range_from_ranges(handranges, board_str):
    value_calc = monte_carlo(
        handranges,
        board_str
    )
    values = value_calc['results']['hand_values']

    # logger.debug('\t>global_range_from_ranges')
    # logger.debug('monte_carlo:')
    # logger.debug(ExtendedEncoder.convert_for_json(value_calc))

    return HandRange([
            hand
            for handrange in handranges
                for hand in handrange
        ], values)


def get_player_ranges(accessor, json_log):
    curr_action_idx = len(json_log['hands'][0]['actions'])

    logger.debug(f'\t>get_player_ranges @ action {curr_action_idx}')

    if accessor.table.bounty_flag:
        logger.debug(f'\t\tbounty_flag is set--all players have FULL_RANGE')
        return {
            plyr.username: FULL_RANGE
            for plyr in accessor.active_players()
        }

    # if nothing has been calculated yet, read_cache returns the default
    #   range for each player at the table (depends on position)
    _, action_idx, hand_ranges = read_cache(accessor)

    rep = ActionReplayer(json_log, action_idx=action_idx)
    # import ipdb; ipdb.set_trace()

    # each action then narrows down the range according to action taken

    # logger.debug(f'\t\twith log:{json_log}')
    while rep.action_idx != curr_action_idx:
        last_board = rep.table.board[:]
        plyr = rep.accessor.next_to_act()
        last_wagers = float(plyr.wagers)

        rep.step_forward()
        hand_ranges = update_ranges(
            plyr,
            hand_ranges,
            rep.accessor,
            last_wagers,
            last_board,
        )

    rep.delete()

    # results are cached to avoid repeating the same calcs
    cache_ranges(
        accessor.table.id,
        accessor.table.hand_number,
        rep.action_idx,
        hand_ranges,
    )
    return hand_ranges


def read_cache(accessor, at_idx=0):
    hand_number, action_idx, ranges = CACHE.get(
        accessor.table.id,
        (accessor.table.hand_number, at_idx, get_default_ranges(accessor))
    )
    # when it's a new hand, return
    if hand_number != accessor.table.hand_number:
        return (
            accessor.table.hand_number,
            0,
            get_default_ranges(accessor)
        )

    return hand_number, action_idx, ranges


def cache_ranges(table_id, hand_number, action_idx, hand_ranges):
    CACHE[table_id] = (hand_number, action_idx, hand_ranges)


def should_valuebet(me, accessor, player_ranges):
    # TODO: find hand value vs top hands in opponents' ranges
    return False


def calc_fold_equity(me, accessor, player_ranges, min_value):
    fold_equity = accessor.current_pot()

    for player in accessor.active_players():
        if player.id == me.id:
            continue

        plyr_range = player_ranges[player.username]
        call_combos = len(pruned(plyr_range, min_value=min_value))
        fold_likelihood = 1 - call_combos / len(plyr_range)

        fold_equity *= fold_likelihood

    return fold_equity


def semibluff_range(plyr, hand_ranges, top_ranges):
    # TODO: calculate semibluff range
    return hand_ranges[plyr]


def get_default_ranges(accessor):
    return {
        player.username: player_range_preflop(player, accessor)
        for player in accessor.active_players()
    }


def update_ranges(plyr, hand_ranges, accessor, last_wagers,
                  last_board):
    # TODO: refactor this so that it's organized by action
    #   if (CALL) remove stuff from range
    #   if (RAISE) remove stuff from range

    # wagers unchanged means no bet or call was made
    if last_wagers == plyr.wagers:
        if plyr.last_action == Event.FOLD:
            hand_ranges = {
                name: hr
                for name, hr in hand_ranges.items()
                if name != plyr.username
            }

        if len(last_board) == len(accessor.table.board):
            return {**hand_ranges}
        else:
            return prune_and_revalue_for_board(
                hand_ranges,
                accessor.table.board_str,
            )

    nth_raise = sum(
        plyr.last_action in (Event.RAISE_TO, Event.BET)
        for plyr in accessor.active_players()
    )

    if accessor.is_preflop():
        new_range = player_range_preflop(plyr, accessor)

    else:
        if len(last_board) != len(accessor.table.board):
            hand_ranges = prune_and_revalue_for_board(
                hand_ranges,
                accessor.table.board_str,
            )

        # TODO: rewrite & test this

        curr_pot = accessor.current_pot()
        wager_diff = float(plyr.uncollected_bets) - float(last_wagers)
        wager_ratio = wager_diff / float(curr_pot)
        base_reduction = (
            0.1 * (plyr.uncollected_bets > 0)
        )
        if plyr.last_action == Event.RAISE_TO:
            base_reduction *= 2

        raise_coeff = 1 / max(1, nth_raise - 0.5)
        prune_ratio = (
            (1 - wager_ratio)
          * raise_coeff
          * (1 - base_reduction)
        )
        logger.debug(
            f'wager ratio: {wager_ratio}, '
            f'raise_coeff: {raise_coeff}, '
            f'base_reduction: {base_reduction}'
        )
        logger.debug(f'postflop: ranges pruned to {prune_ratio}')

        new_range = pruned(
            hand_ranges[plyr.username],
            keep_ratio=prune_ratio
        )

    hand_ranges[plyr.username] = new_range
    return hand_ranges


def prune_and_revalue_for_board(ranges, board_str):
    curr_board = Hand(board_str)
    carlo = monte_carlo(
        ranges.values(),
        board_str
    )
    hand_values = carlo['results']['hand_values']
    return {
        plyr: HandRange(
            ranges[plyr],
            known_cards=curr_board,
            hand_values=hand_values)
        for plyr in ranges.keys()
    }


def player_hand_ratio_preflop(position, n_players, bbs):
    '''
    hand-tuned equations.
    use util_scripts/preflop_handrange_tweaker.py

     ratio:  limp  mini   3x    9x   27x   99x   333x  999x 9999x
      0.12
     r_adj: 0.201 0.154 0.132 0.091 0.065 0.045 0.031  0.02 0.008
     worst:   44   QJo   K9s   KQo   ATs   AQo   AKo    JJ    KK
       0.2
     r_adj:  0.33  0.25 0.213 0.137 0.088 0.053 0.032 0.021 0.008
     worst:  Q5s   86s   97s   A7s   KQo   AJs   AQs    JJ    KK
      0.36
     r_adj: 0.589 0.443 0.373  0.23 0.134 0.067 0.036 0.022 0.008
     worst:  T2s   97o   Q9o   K6s   K9s   KJs    TT    JJ    KK
      0.55
     r_adj: 0.896 0.671 0.564  0.34 0.189 0.083  0.04 0.023 0.008
     worst:  62o   85o   J8o   43s   KTo   QJs   AQo   AKo    KK
      0.85
     r_adj: 1.382 1.032 0.865 0.515 0.275  0.11 0.046 0.024 0.008
     worst:  83o   83o   32o   K8o   96s   ATo   AQo   AKo    KK
         1
     r_adj: 1.625 1.212 1.015 0.602 0.318 0.123 0.049 0.025 0.008
     worst:  83o   83o   83o   A2o   T9o   KJo    99   AKo    KK
    '''
    if position == 'bb' and bbs == 1:
        # bb can check anything
        return 1

    if n_players == 2:
        base_ratio = PREFLOP_BASE_RANGES['heads_up'][position]
    else:
        base_ratio = PREFLOP_BASE_RANGES['ring'][position]

    if bbs >= 1:
        # the higher the # of bbs, the more base_ratio should be pulled
        #   toward a baseline of GRAVITY_RNG, starting at GRAVITY_BBS
        GRAVITY_BBS = 50
        GRAVITY_RNG = 0.2
        ratio_gravity = (GRAVITY_BBS * base_ratio + bbs * GRAVITY_RNG)
        ratio_gravity /= (GRAVITY_BBS + bbs)
        # lower DIV means tighter hr weighted at lower bb numbers
        DIV = 3
        # lower ROOT means tighter hr weighted at higher bb numbers
        ROOT = 2
        divisor = (bbs / DIV) ** (1 / ROOT)
        ratio = ratio_gravity / divisor

    else:
        ratio = 1

    # cant play more than 100% of hands
    return min(1, ratio)


def player_range_preflop(plyr, accessor):
    # preflop, we're using a heuristic based on # of bbs added to the pot
    position = get_player_position(accessor, plyr)
    bbs_preflop = float(plyr.wagers / accessor.table.bb)
    pot_in_bbs = float(accessor.current_pot() / accessor.table.bb)
    n_players = len(accessor.active_players())

    ratio = player_hand_ratio_preflop(position, n_players, bbs_preflop)

    pot_odds = pot_in_bbs / (bbs_preflop or 1)

    # add to ratio based on pot odds
    if plyr.last_action == Event.CALL:
        if pot_odds > 4:
            ratio = min(1, ratio * 1.5)
        elif pot_odds > 3:
            ratio = min(1, ratio * 1.25)
        elif pot_odds > 2:
            ratio = min(1, ratio * 1.1)

    return preflop_range(ratio)


def situation_is_preflop_open(me, accessor):
    if not accessor.is_preflop():
        return False

    if me.position == accessor.table.sb_idx:
        return accessor.call_amt(me, diff=True) == 1

    if me.position == accessor.table.bb_idx:
        return accessor.call_amt(me, diff=True) == 0

    if me.wagers == 0:
        return accessor.call_amt(me, diff=True) == accessor.table.bb

    return False


def stackpot_fold_equity_scalar(accessor):
    # includes all players because if I have 0.3 spr I shouldn't bluff
    stackpot_ratios = {
        plyr: float(plyr.stack_available / accessor.current_pot())
        for plyr in accessor.showdown_players()
    }
    stackpot_ratio = min(stackpot_ratios.values())
    # 0 up to 0.3, 0.33 @ 0.5, 0.64 @ 1, 0.8 @ 2, slowly approaches 1
    return max(0, 1 - 0.4 / (stackpot_ratio + 0.1))


def has_72(plyr):
    ranks = [card.rank for card in plyr.cards]
    return '7' in ranks and '2' in ranks


def n_checks(hh):
    checks = 0
    for event in hh['hands'][0]['events'][::-1]:
        if event['event'].lower() == 'check':
            checks += 1
        if event['event'].lower() in ['bet', 'raise_to', 'call', 'post']:
            return checks

    msg = 'impossible state... should have at least hit a POST event'
    raise Exception(msg)


def chaos_adjusted(ratio, chaos=0, lower_bound=0, upper_bound=1):
    # wiggle the amt by chaos_ratio
    adjusted = (1 + (secure_random_float() - 0.5) * chaos) * ratio
    return max(min(adjusted, upper_bound), lower_bound)


def ratio_adjusted(x, ratio, lower_bound=0, upper_bound=1):
    adjusted = x * ratio
    return max(min(adjusted, upper_bound), lower_bound)


def preflop_open(me, accessor, personality=None):
    if personality is None:
        personality = bot_personality(me.username)
    logger.debug(f'\t>preflop_open, personality={personality}')
    _chaotic = personality['chaotic']
    _preflop = personality['preflop']
    _limper = chaos_adjusted(personality['limper'], _chaotic)
    _limp_balance = chaos_adjusted(personality['limp_balance'], _chaotic)

    mode = 'heads_up' if len(accessor.active_players()) == 2 else 'ring'
    preflop_ranges = _preflop[mode]

    position = get_player_position(accessor, me)
    percentile = FULL_RANGE.percentile(me.cards)

    ratio = chaos_adjusted(
        preflop_ranges[position],
        chaos=_chaotic
    )
    logging.debug(f'percentile={percentile}, ratio={ratio}')
    if accessor.table.table_type == NL_BOUNTY and has_72(me):
        logger.debug('72o in BNTY; percentile set to 0.01')
        percentile = 0.01

    if percentile < ratio:
        # because limpscale will divide the rate by two on avg
        base_limp = _limper * 2

        limpscale_intercept = _limp_balance / 2
        limpscale_slope = (1 - _limp_balance) / ratio

        limpscale = limpscale_slope * percentile + limpscale_intercept
        logging.debug(
            f'limp =  ({limpscale_slope} '
            f'* {percentile} + {limpscale_intercept} == {limpscale}) '
            f'* {base_limp}'
        )

        limp = limpscale * base_limp

        if secure_random_float() < limp:
            avail_acts = accessor.available_actions(me)
            action_str = 'CALL' if Action.CALL in avail_acts else 'CHECK'
            return (action_str, {'player_id': me.id})

        return ('RAISE_TO', {
            'player_id': me.id,
            'amt': ai_raisesize(accessor, me)
        })

    return ('FOLD', {'player_id': me.id})


def check_or_fold(me, accessor):
    avail_acts = accessor.available_actions(me)
    if Action.CHECK in avail_acts:
        return ('CHECK', {'player_id': me.id})

    return ('FOLD', {'player_id': me.id})


def check_or_call(me, accessor):
    avail_acts = accessor.available_actions(me)
    if Action.CHECK in avail_acts:
        return ('CHECK', {'player_id': me.id})

    return ('CALL', {'player_id': me.id})


def bet_or_raise(me, accessor):
    avail_acts = accessor.available_actions(me)
    if Action.BET in avail_acts:
        return ('BET', {'player_id': me.id, 'amt': ai_betsize(accessor, me)})

    elif Action.RAISE_TO in avail_acts:
        amt = ai_raisesize(accessor, me)
        return ('RAISE_TO', {'player_id': me.id, 'amt': amt})

    # for all-in situations
    return ('CALL', {'player_id': me.id})


def get_player_position(accessor, player):
    if player.position == accessor.table.btn_idx:
        return 'btn'
    elif player.position == accessor.table.sb_idx:
        return 'sb'
    elif player.position == accessor.table.bb_idx:
        return 'bb'

    players = accessor.active_players(rotate=accessor.table.btn_idx)
    n_players = len(players)
    player_idx = players.index(player)

    return n_players - player_idx


def rounded_capped_wager(wager, accessor, robot):
    rounded = round_to_multiple(wager, accessor.table.sb)
    capped = min(rounded, robot.stack_available)
    return Decimal(capped)


def ai_betsize(accessor, robot):
    potsize = accessor.current_pot()
    return rounded_capped_wager((7 * potsize) / 10, accessor, robot)


def ai_raisesize(accessor, robot):
    if accessor.table.table_type in (NL_HOLDEM, NL_BOUNTY):
        potsize = accessor.current_pot()
        minraise = accessor.min_bet_amt()
        if accessor.is_preflop():
            raisesize = minraise + potsize
        else:
            raisesize = minraise + (7 * potsize) / 10

    elif accessor.table.table_type == PL_OMAHA:
        raisesize = accessor.pot_raise_size()

    else:
        msg = 'No raisesize specified for gametype: '\
             f'{accessor.table.table_type}'
        raise NotImplementedError(msg)

    return rounded_capped_wager(raisesize, accessor, robot)


def total_combos(hand_list):
    return sum([line[2] for line in hand_list])

