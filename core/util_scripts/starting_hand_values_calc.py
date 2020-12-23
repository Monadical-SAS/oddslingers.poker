from poker.monte_carlo import monte_carlo
from poker.hand_ranges import (
    hands_from_description, FULL_RANGE, HandRange, Hand, LOOSE_RANGE,
    pruned, PREFLOP_HANDS, PREFLOP_BASE_CALC_RANGES
)

starting_hand_values = monte_carlo(
    [FULL_RANGE, *PREFLOP_BASE_CALC_RANGES],
    hand_values=True
)['results']['hand_values']

for i in range(1, 25):
    updates = monte_carlo(
        [FULL_RANGE, *PREFLOP_BASE_CALC_RANGES],
        hand_values=True
    )['results']['hand_values']
    starting_hand_values = {
        hand: (starting_hand_values[hand] * i + updates[hand]) / (i + 1)
        for hand in starting_hand_values.keys()
    }

new_full_range = HandRange(FULL_RANGE, hand_values=starting_hand_values)

new_equities = {}
for hand_desc, _ in PREFLOP_HANDS:
    hands = hands_from_description(hand_desc)
    equity = sum(starting_hand_values[hand] for hand in hands) / len(hands)
    new_equities[hand_desc] = equity

new_preflop_hands = sorted(
    new_equities.items(),
    key=lambda item: -new_equities.get(item[0])
)
new_ranks = [hand for hand, _ in new_preflop_hands]
old_ranks = [hand for hand, _ in PREFLOP_HANDS]

for rank, hand in enumerate(new_ranks):
    print(f'{hand}: {rank}, {old_ranks.index(hand) - rank}')

for hand, eq in new_preflop_hands:
    print(f"('{hand}', {eq:.04}),")
