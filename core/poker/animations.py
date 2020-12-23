# To whomever next deals with this code: I'm sorry.
#   it might help to flatten the functions a little bit
#   note that NEW_STREET is ignored in all cases except for the
#   SIDE_EFFECT_SUBJ call which should happen *before* it's called
#   for the Players on the controller.

from poker.constants import AnimationEvent, SIDE_EFFECT_SUBJ
from poker.models import Player, PokerTable, PokerTournament


def event_for_player(event, player):
    if '_PRIVATE_' in event:
        if player and player.id in event['_PRIVATE_']:
            return event['_PRIVATE_'][player.id]
        return {k: v for k, v in event.items() if k != '_PRIVATE_'}
    return event


def snapto_for_accessor_state(accessor):
    return {
        'type': 'SNAPTO',
        'subj': None,
        'event_args': {
            'public': {
                'players': accessor.players_json(None),
                'table': accessor.table_json(),
            },
            '_PRIVATE_': {
                player.id: {
                    'players': accessor.players_json(player),
                    'table': accessor.table_json(),
                } for player in accessor.seated_players()
            }
        },
        'changes': {},
    }


def process_event(accessor, subj, event, changes, **kwargs):
    '''
    Model dispatch returns a list of changes, in the form
    [(<attr: str>, <val: T>)]
    here, the changes are here transformed into
    {"#{model_repr}/{attr}": <val: T>}
    The returned dict is an intermediary version of the animation
    event, which is later transformed by process_eventstream
    '''

    # In several cases, the backend model changes don't map 1-to-1 with
    #   frontend state changes. This if-clause mess handles those cases
    if event == AnimationEvent.NEW_STREET:
        if subj == SIDE_EFFECT_SUBJ:
            plyrs_uncollected = sum(
                plyr.uncollected_bets
                for plyr in accessor.active_players()
            )
            if plyrs_uncollected != 0:
                subj = accessor.table
                kwargs = {
                    **kwargs,
                    'patches': [
                        {
                            'path': frontend_transform(
                                patch_path(player, 'uncollected_bets')
                            ),
                            'value': 0,
                        }
                        for player in accessor.active_players()
                        if player.uncollected_bets
                    ],
                    'value': [
                        patch_path(player, 'uncollected_bets')
                        for player in accessor.active_players()
                        if player.uncollected_bets
                    ],
                }
                kwargs['patches'].append({
                    'path': '/table/sidepot_summary',
                    'value': accessor.frontend_sidepot_summary(False)
                })
            else:
                kwargs = {'ignore': True}
        else:
            kwargs = {'ignore': True}

    elif event == AnimationEvent.SET_BLIND_POS:
        changes = tuple(c for c in changes if c[0] == 'btn_idx')

    elif event == AnimationEvent.WIN:
        winning_hand = kwargs.get('winning_hand', None)
        if winning_hand:
            table = accessor.table
            kwargs = {
                **kwargs,
                'winning_hand': [
                    {'path': get_cardpath(card, subj, table)}
                    for card in list(winning_hand)
                ]
            }

    elif event in [AnimationEvent.BET,
                   AnimationEvent.RAISE_TO,
                   AnimationEvent.CALL,
                   AnimationEvent.POST,
                   AnimationEvent.ANTE]:
        kwargs = {
            **kwargs,
            'patches': [{
                'path': '/table/total_pot',
                'value': accessor.current_pot()
            }]
        }

    return {
        'type': event,
        'subj': subj,
        'event_args': kwargs,
        'changes': {patch_path(subj, k): v for k, v in changes},
    }


def get_cardpath(card, player, table):
    try:
        card_idx = table.board.index(card)
        path = patch_path(table, f'board/{card_idx}')
    except ValueError:
        card_idx = player.cards.index(card)
        path = patch_path(player, f'cards/{card_idx}')
    return path


def subj_repr(subj):
    if isinstance(subj, Player):
        subj_repr = subj.attrs('id', 'short_id', 'username')
        subj_repr['class'] = 'Player'
    elif isinstance(subj, PokerTable):
        subj_repr = subj.attrs('id', 'short_id', 'name')
        subj_repr['class'] = 'PokerTable'
    elif subj is None:
        return None
    else:
        return {
            'class': subj.__class__.__name__,
            'name': str(subj),
        }

    return subj_repr


def patch_path(subj, key=None):
    if isinstance(subj, Player):
        path = f'/players/{subj.id}'
    elif isinstance(subj, PokerTable) or isinstance(subj, PokerTournament):
        path = '/table'
    else:
        raise ValueError(f'Unknown subject type {type(subj)}')

    if key:
        return f"{path}/{key}"

    return path


def get_change_for_key(subj, key, changes):
    change = changes[patch_path(subj, key)]
    if key == 'last_action' and change is not None:
        change = str(change)
    return change


def frontend_transform(path):
    if path.endswith('/stack') or path.endswith('/uncollected_bets'):
        return path + '/amt'

    return path


def build_patches(subj, changes, keys):
    return tuple({
        'path': frontend_transform(patch_path(subj, key)),
        'value': get_change_for_key(subj, key, changes),
    } for key in keys)


def player_card_patch(player_id, card_idx, card):
    return {
        'path': f'/players/{player_id}/cards/{card_idx}/card',
        'value': card,
    }


def remove_cards_patch(player_id):
    return {'path': f'/players/{player_id}/cards', 'value': {}}


def build_animation(anim_type, subj, value, patches, private=None):
    private_dict = {'_PRIVATE_': private} if private is not None else {}
    return {
        'type': anim_type,
        'subj': subj_repr(subj),
        'value': value,
        'patches': patches,
        **private_dict
    }


def anim_with_patchkeys(event, value, patch_keys):
    return build_animation(
        str(event['type']),
        event['subj'],
        value,
        build_patches(event['subj'], event['changes'], patch_keys)
    )


def chip_change_event(event):
    anims = anim_with_patchkeys(
        event,
        {
            'amt': event['event_args']['amt'],
            'all_in': event['event_args'].get('all_in')
        },
        ('stack', 'uncollected_bets', 'last_action',)
    )
    anims['patches'] += tuple(event['event_args']['patches'])
    return anims


def post_dead_event(event):
    # note: I'm assuming post_dead only ever happens at
    #   the beginning of the hand, hence the hardcoded
    #   sidepot_summary value
    dead_amt = event['event_args']['amt']
    return build_animation(
        'POST_DEAD',
        event['subj'],
        {'amt': dead_amt},
        (
            *build_patches(event['subj'], event['changes'], ('stack',)),
            {'path': '/table/sidepot_summary/0/amt', 'value': dead_amt},
        )
    )


def fold_event(event):
    subj = event['subj']
    cards = []
    if event['event_args'].get('show_cards'):
        cards = event['event_args']['cards']
    return build_animation('FOLD', subj, cards, (
        remove_cards_patch(subj.id),
        *build_patches(subj, event['changes'], ('last_action',)),
    ))


def muck_event(event):
    subj = event['subj']
    return build_animation('MUCK', subj, [], (
        remove_cards_patch(subj.id),
    ))


def table_seat_event(event):
    subj = event['subj']
    return build_animation(str(event['type']), subj, None, (
        {'path': f'/players/{subj.id}','value': subj_repr(subj)},
    ))


def player_deal_event(event):
    subj = event['subj']
    event_args = event['event_args']
    changes = event['changes']
    cards = changes[patch_path(subj, 'cards')]
    idx = cards.index(event_args['card'])

    private = {
        subj.id: build_animation(
            'DEAL_PLAYER',
            subj,
            {'card': event_args['card'], 'idx': idx},
            (player_card_patch(subj.id, idx, event_args['card']),)
        )
    }

    return build_animation(
        'DEAL_PLAYER',
        subj,
        {'card': '?', 'idx': idx},
        (player_card_patch(subj.id, idx, '?'),),
        private
    )


def board_deal_event(event):
    subj = event['subj']
    event_args = event['event_args']
    changes = event['changes']
    board = changes[patch_path(subj, 'board')]
    idx = board.index(event_args['card'])

    return build_animation(
        'DEAL_BOARD',
        event['subj'],
        {'card': event_args['card'], 'idx': idx},
        ({
            'path': f'/table/board/{idx}/card',
            'value': event_args['card'],
        },)
    )


def snapto_event(event):
    event_args = event['event_args']
    private = {
        pid: build_animation('SNAPTO', None, event_args['_PRIVATE_'][pid], [])
        for pid in event_args['_PRIVATE_'] if pid != 'all'
    }

    return build_animation('SNAPTO', None, event_args['public'], [], private)


def new_street_event(event):
    subj = event['subj']

    return build_animation(
        'NEW_STREET',
        subj,
        event['event_args']['value'],
        event['event_args']['patches'],
    )


def reset_event(event):
    subj = event['subj']
    changes = event['changes']
    if isinstance(subj, PokerTable):
        patch_keys = ('board',)

    else:
        patch_keys = ('uncollected_bets', 'cards')
        if patch_path(subj, 'last_action') in changes:
            patch_keys += ('last_action',)

    return (build_patches(subj, changes, patch_keys), ())


def append_or_add_to_prev_if_eq_type(event, accessor, func, output):
    patches, value = func(event)

    type_str = str(event['type'])
    if output and output[-1]['type'] == type_str:
        output[-1]['patches'] += patches
        output[-1]['value'] += value
    else:
        output.append(build_animation(
            type_str,
            accessor.table,
            value,
            patches,
        ))


def sit_in_out_event(event):
    # TODO: probably need to add something in the subscriber to figure out
    #   the public gamestate changes (sitting_out instead of playing_state)
    if patch_path(event['subj'], 'last_action') in event['changes']:
        change = 'last_action'
    elif event['type'] == AnimationEvent.SIT_OUT:
        change = 'sitting_out'
    else:
        change = 'sitting_in'
    return anim_with_patchkeys(event, [], (change,))


def win_event(event):
    event_args = event['event_args']
    anim = anim_with_patchkeys(
        event,
        {
            'amt': event_args['amt'],
            'pot_id': event_args['pot_id'],
            'winning_hand': event_args.get('winning_hand', None),
        },
        ('stack',)
    )
    anim['patches'] += ({
        'path': f'/table/sidepot_summary/{event_args["pot_id"]}',
        'value': None,
    },)
    return anim


def process_eventstream(accessor, eventstream):
    # When it's time to broadcast, the eventstream log is processed, filtering
    #   any changes that don't need to be shown at animation-time
    output = []

    for event in eventstream:
        event_type = event['type']
        if event_type == 'SNAPTO':
            output.append(snapto_event(event))

        elif event_type == AnimationEvent.DEAL:
            if isinstance(event['subj'], Player):
                output.append(player_deal_event(event))
            else:
                output.append(board_deal_event(event))

        elif event_type in (
                AnimationEvent.POST,
                AnimationEvent.ANTE,
                AnimationEvent.BET,
                AnimationEvent.RAISE_TO,
                AnimationEvent.CALL
            ):
            output.append(chip_change_event(event))

        elif event_type == AnimationEvent.POST_DEAD:
            output.append(post_dead_event(event))

        elif event_type == AnimationEvent.CHECK:
            output.append(anim_with_patchkeys(event, None, ('last_action',)))

        elif event_type == AnimationEvent.FOLD:
            output.append(fold_event(event))

        elif event_type in (AnimationEvent.TAKE_SEAT,
                            AnimationEvent.LEAVE_SEAT):
            output.append(table_seat_event(event))

        elif event_type in (AnimationEvent.SIT_IN, AnimationEvent.SIT_OUT):
            continue
            # TODO
            # output.append(sit_in_out_event(event))

        elif event_type == AnimationEvent.WIN:
            # these might have to be grouped by pot_id for the
            #   animation to work
            output.append(win_event(event))

        elif event_type == AnimationEvent.SET_BLIND_POS:
            output.append(anim_with_patchkeys(
                event,
                {**event['event_args']},
                ('btn_idx',)
            ))

        elif event_type == AnimationEvent.NEW_HAND:
            # TODO: decide whether we care about this
            pass

        elif event_type == AnimationEvent.RESET:
            append_or_add_to_prev_if_eq_type(event,
                                             accessor,
                                             reset_event,
                                             output)

        elif event_type == AnimationEvent.NEW_STREET:
            if event['event_args'].get('ignore'):
                continue
            else:
                output.append(new_street_event(event))

        elif event_type == AnimationEvent.UPDATE_STACK:
            output.append(anim_with_patchkeys(event, None, ('stack',)))

        elif event_type == AnimationEvent.REVEAL_HAND:
            subj = event['subj']
            event_args = event['event_args']
            cards = event_args['cards']

            output.append(build_animation(
                'REVEAL_HAND',
                subj,
                cards,
                [
                    player_card_patch(subj.id, idx, card)
                    for idx, card in enumerate(cards)
                ]
            ))

        elif event_type == AnimationEvent.RETURN_CHIPS:
            output.append(anim_with_patchkeys(
                event,
                {'amt': event['event_args']['amt']},
                (
                    'stack',
                    'uncollected_bets',
                )
            ))

        elif event_type == AnimationEvent.MUCK:
            output.append(muck_event(event))

        elif event_type == AnimationEvent.BOUNTY_WIN:
            subj = event['subj']
            event_args = event['event_args']
            cards = event_args['cards']

            output.append(
                build_animation('BOUNTY_WIN', subj, cards, None)
            )

    return output
