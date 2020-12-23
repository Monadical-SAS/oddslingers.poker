import json
import os

from fnmatch import fnmatch

from poker.replayer import EventReplayer
from poker.constants import HH_TEST_PATH
# from poker.accessors import HoldemAccessor
# from poker.handhistory import DBLog
# from poker.models import PokerTable

def examine_pot_changes(log):
	rep = EventReplayer(log, hand_number=-1)
	# while rep.controller.table.hand_number < 1556:
	# 	rep.next_hand()

	acc = rep.controller.accessor

	# while True:
	for i in range(70):
		if i == 32:
			import ipdb; ipdb.set_trace()
		try:
			print(i)
			print('name\tstack\twagers\tuncollected')
			for p in acc.active_players():
				print('{}\t{:<5}\t{}\t{}'.format(p.username[:5], p.stack, p.wagers, p.uncollected_bets))

			print('--------------------')
			uncollected = sum(p.uncollected_bets for p in acc.players)
			wagers = sum(p.wagers for p in acc.players)
			stacks = sum(p.stack for p in acc.players)
			print('total\t{}\t{}\t{}\n'.format(stacks, wagers, uncollected))

			curr_pot = acc.current_pot()
			print('curr_pot', curr_pot, '\n')

			print('pot_amt\tplayers')
			for pot, ppl in acc.sidepot_summary(exclude_uncollected_bets=True):
				print('{:<7}\t{}'.format(pot, ppl))

			print('\n', 'dead_money: {}'.format(sum(p.dead_money for p in acc.players)), '\n')

			sidepot_total = sum(pot for pot, _ in acc.sidepot_summary(exclude_uncollected_bets=True))
			print('sidepot_summary total:', sidepot_total)

			print('\nsidepots + uncollected_bets == curr_pot')
			print('{} + {} == {}'.format(sidepot_total, uncollected, curr_pot))
			assertion = curr_pot == sidepot_total + uncollected
			print(assertion)
			assert assertion

			print('\n\t***\n')
			print('event #', rep.event_idx)
			print(rep.current_hand()['events'][rep.event_idx])

			rep.step_forward()

		except (IndexError, StopIteration):
			break

		# except Exception as e:
		# 	print(e)
		# 	import ipdb; ipdb.set_trace()
		# 	pass

# table_id = '51beb1d4-49b4-410f-b306-c1e62c1e8184'
# hand_number = 109

# table = PokerTable.objects.get(id=table_id)
# log = DBLog(HoldemAccessor(table)).get_log(player='all', hand_gte=hand_number, hand_lt=hand_number+1)
# log = json.load(open('poker/tests/data/missing_chip.json'))

log_fns = [
	os.path.join(HH_TEST_PATH, f) for f in os.listdir(HH_TEST_PATH)
	if os.path.isfile(os.path.join(HH_TEST_PATH, f)) \
		and fnmatch(f, '*simfail_???.json')
]

log_fn = os.path.join(HH_TEST_PATH, 'simulation_pots_not_adding_up.json')
log = json.load(open(log_fn))

examine_pot_changes(log)
