import subprocess
import json
import locale

from timeit import default_timer as timer

from oddslingers.utils import ExtendedEncoder

from poker.hand_ranges import (
    Hand, HandRange, FULL_RANGE, with_hand_values, pruned
)

def monte_carlo(handranges, board='', dead='', hand_values=True):
    '''
    Takes a game situation and returns a bunch of useful info based
    on monte carlo rollout of the board.

    For example, I raise preflop heads-up, you call, flop comes AcTdKh
    `montecarlo([preflop_raise_range, preflop_call_range], board='AcTdKh')`
    Tells me the relative values of each hand in those ranges,
    plus each players' probability of winning (assuming they go
    all-in right now).

    Calls out to highly-optimized C++ process found in 'bin/monte_carlo'
    If the binary doesn't work on your architecture, you can clone
    https://github.com/cowpig/monte-carlo
    and compile it locally

    for now this can only evaluate NLHE.

    inputs -
    handranges: a list of HandRange objects, or handranges described
        by strings, e.g. "AcAh,AsAd..."
    board: a Hand objct or string describing the board e.g. "Ac3d4c"
    dead: a Hand object or string describing cards to be excluded from
        the montecarlo evals
    hand_values: bool. if True, record the winrates on a hand-by-hand
        basis. Note that this calculation is biased if the input ranges
        are not identical. e.g. the second-worst-possible hand on the
        river will have a 100% winrate if the range it is up against
        consists solely of the worst-possible hand.

    output - a dict that looks like this:
    {
        'input': {
            'ranges': <list of str>,
            'board': <str>,
            'dead': <str>,
            'recordHandWins': <bool; equal to hand_values>
        },
        'results': {
            'equity': <list of floats; equal to equity of each input range>,
            'hand_values': <dict of Hand: float; null if hand_values is False>,
            'time': <float; processing time in seconds excluding parsing>,
            'total_proc_time': <float; total processing time in seconds>
            'stdev': <float; represents the error bounds of 'equity',

            # these can probably be ignored unless you're debugging
            'hands': <int; # of evals including table lookups>,
            'evaluations': <int; # of monte carlo simulations>,
            'players': <int; should be equal to len(ranges)>,
            'recordHandWins': <bool; should be equal to hand_values>,
            'board': <int; this is a cardmask and should be ignored>,
            'dead': <int; this is a cardmask and should be ignored>,
            'ties': <list of floats; number of ties for each range>,
            'wins': <list of floats; number of wins for each range>,
            'finished': <bool; should always be True>,
        }
    }
    '''

    # type checking is important because monte_carlo subprocess
    #   will fail silently with invalid input
    if not all(isinstance(hr, HandRange) for hr in handranges):
        handranges = [HandRange(hr) for hr in handranges]
    assert all(isinstance(hr, HandRange) for hr in handranges)

    if isinstance(board, str):
        board = Hand(board)
    assert isinstance(board, Hand)

    if isinstance(dead, str):
        dead = Hand(board)
    assert isinstance(dead, Hand)

    carlo_input = {
        'ranges': [str(hr) for hr in handranges],
        'board': board, #str(board),
        'dead': dead, #str(dead),
        'recordHandWins': hand_values,
    }
    start_time = timer()
    completed_process = subprocess.run(
        'bin/monte_carlo',
        input=json.dumps(carlo_input, cls=ExtendedEncoder),
        stdout=subprocess.PIPE,  # this changes in 3.7
        encoding=locale.getpreferredencoding(),
    )
    end_time = timer()
    output = json.loads(completed_process.stdout)
    output['results']['equity'] = [
        round(equity, 4)
        for equity in output['results']['equity']
    ]
    output['results']['total_proc_time'] = end_time - start_time
    if hand_values:
        output['results']['hand_values'] = {
            Hand(hand): round(value, 4)
            for hand, value in output['results']['hand_values'].items()
        }

    return output


def overall_hand_percentile(hand, board=''):
    '''
    determines the "percentile" of the hand, equal to:
    all_hands.index(hand) / len(all_hands)
    assuming hands are ordered best-to-worst
    '''

    if board == '':
        return FULL_RANGE.percentile(hand)

    all_possible = pruned(FULL_RANGE, known_cards=board)
    carlo_input = [all_possible, all_possible]
    carlo_results = monte_carlo(carlo_input, board)['results']
    handrange = with_hand_values(all_possible, carlo_results['hand_values'])
    return handrange.percentile(hand)
