import os, json
# from poker.replayer import ActionReplayer

HH_TEST_PATH = 'poker/tests/data'
data_fns = [
    os.path.join(HH_TEST_PATH, f)
    for f in os.listdir(HH_TEST_PATH)
    if os.path.isfile(os.path.join(HH_TEST_PATH, f)) and '.json' in f
]


for fn in data_fns:
    with open(fn, 'r') as f:
        data = json.load(f)

    for hand in data['hands']:
        # update playing_state
        for player in hand['players']:
            playing_state = 'SITTING_IN'

            try:
                if player.pop('sitting_out'):
                    playing_state = 'SITTING_OUT'
            except KeyError:
                pass

            try:
                if player.pop('sit_in_at_blinds'):
                    playing_state = 'SIT_IN_AT_BLINDS_PENDING'
            except KeyError:
                pass

            player['playing_state'] = playing_state

        # reorder deck
        if 'actions' in hand.keys():
            card_deals = [
                event['args']['card']
                for event in hand['events']
                if event['event'] == 'DEAL'
            ]
            deals_str = ','.join(card_deals)

            plyr_set = {
                plyr['username']
                for plyr in hand['players']
            }
            plyrs = []

            # get players in deal-order
            for event in hand['events']:
                if event['event'] == 'DEAL':
                    subj = event['subj']
                    if subj not in plyrs and subj in plyr_set:
                        plyrs.append(subj)

            plyr_cards = {
                plyr: [
                    event['args']['card']
                    for event in hand['events']
                    if event['event'] == 'DEAL' and event['subj'] == plyr
                ]
                for plyr in plyrs
            }

            n_cards = 4 if hand['table']['table_type'] == 'PLO' else 2
            deck_should_be = []

            for i in range(n_cards):
                for plyr in plyrs:
                    deck_should_be.append(plyr_cards[plyr][i])

            new_deck = ','.join(deck_should_be)
            new_deck = new_deck + hand['table']['deck_str'][len(new_deck):]

            if not len(new_deck) == 52 * 2 + 51:
                import ipdb; ipdb.set_trace()

            hand['table']['deck_str'] = new_deck

        # update TAKE_SEAT actions
        for action in hand.get('actions', []):
            if action['action'] == 'TAKE_SEAT':
                sit_in_at_blinds = action['args'].pop('sit_in_at_blinds')
                if sit_in_at_blinds:
                    action['args']['playing_state'] = 'SIT_IN_AT_BLINDS_PENDING'
                else:
                    action['args']['playing_state'] = 'SITTING_OUT'



    with open(fn, 'w') as f:
        json.dump(data, f, indent=2)
        print(f'updated {fn}')


    # replayer = ActionReplayer(json_log=data,
    #                           hand_idx=0,
    #                           logging=True)

    # while True:
    #     try:
    #         replayer.step_forward(multi_hand=True)
    #     except StopIteration:
    #         break

    # replayer.controller.log.save_to_file('poker/tests/data/a_few_hands.json',
    #                                      player='all',
    #                                      indent=True,
    #                                      notes=replayer.__notes__,)
