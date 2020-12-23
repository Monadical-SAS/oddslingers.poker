from poker.hand_ranges import preflop_range, hand_to_description
# for tweaking new_ai/player_hand_ratio_preflop():

# the higher the # of bbs, the more base_ratio should be pulled
#   toward a baseline of GRAVITY_RNG, starting at GRAVITY_BBS
GRAVITY_BBS = 50
GRAVITY_RNG = 0.2
ratio_gravity = lambda base_ratio, bbs: (GRAVITY_BBS * base_ratio + bbs * GRAVITY_RNG) / (GRAVITY_BBS + bbs)
# lower DIV means tighter hr weighted at lower bb numbers
DIV = 3.5
# lower ROOT means tighter hr weighted at higher bb numbers
ROOT = 2.5
divisor = lambda bbs: (bbs / DIV) ** (1 / ROOT)
ratio = lambda base_ratio, bbs: ratio_gravity(base_ratio, bbs) / divisor(bbs)
worst_hand = lambda base_ratio, bbs: hand_to_description(preflop_range(ratio(base_ratio, bbs))[-1])

amts = (1, 2, 3, 9, 27, 99, 333, 999, 9999)
base_ratios = (0.12, 0.2, 0.36, 0.55, 0.85, 1)
fmt_str = '{:>6}: {:^6}{:^6}{:^6}{:^6}{:^6}{:^6}{:^6}{:^6}{:^6}'
key = ('ratio', 'limp', 'mini', '3x', '9x', '27x', '99x', '333x', '999x', '9999x')
print(fmt_str.format(*key))

for base_ratio in base_ratios:
    worst_hands = [worst_hand(base_ratio, amt) for amt in amts]
    ratios = [round(ratio(base_ratio, amt), 3) for amt in amts]
    divisors = [round(divisor(amt), 2) for amt in amts]
    gravity = [round(ratio_gravity(base_ratio, amt), 3) for amt in amts]
    print(f'{base_ratio:>6}')
    # print(fmt_str.format('grvty', *gravity))
    # print(fmt_str.format('divi', *divisors))
    print(fmt_str.format('r_adj', *ratios))
    print(fmt_str.format('worst', *worst_hands))
