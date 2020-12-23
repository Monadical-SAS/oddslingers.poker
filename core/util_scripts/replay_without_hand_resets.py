import json

from poker.replayer import ActionReplayer
log = json.load(open('poker/tests/data/simfail_001.json'))

rep = ActionReplayer(log, hand_number=1)
acc = rep.controller.accessor

def next_action(rep):
	try:
		import ipdb; ipdb.set_trace()
		hand_idx, action_idx, action = (rep.hand_idx, rep.action_idx, rep.current_action())
		rep.step_forward()
		return (hand_idx, action_idx, action)
	except IndexError:
		if rep.hand_idx + 1 >= len(rep.hands):
			raise StopIteration()
		else:
			rep.hand_idx += 1
			rep.action_idx = 0
			hand_idx, action_idx, action = (rep.hand_idx, rep.action_idx, rep.current_action())
			rep.step_forward()
			return (hand_idx, action_idx, action)

while True:
	print('-start-')
	try:
		hand_idx, action_idx, action = next_action(rep)
		print('* * *')
		print('hand #', hand_idx)
		print('action #', action_idx, ":", action)
		print('username\tstack  \twagers \tlast_action')
		for p in rep.controller.accessor.players:
			data = [
				str(p.username),
				str(p.stack),
				str(p.wagers),
				str(p.last_action),
			]
			print('{:<8}\t{:<7}\t{:<7}\t{:<7}'.format(*data))
	except StopIteration:
		print('-EOF-')
