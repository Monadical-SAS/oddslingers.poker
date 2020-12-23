from unittest.mock import Mock

from poker.animations import (frontend_transform, get_change_for_key,
                              patch_path, player_card_patch, process_event,
                              process_eventstream, subj_repr)
from poker.cards import Card
from poker.constants import (AnimationEvent, Event,
                             SIDE_EFFECT_SUBJ, PlayingState)
from poker.tests.test_controller import GenericTableTest
from poker.subscribers import AnimationSubscriber


class SubjReprTests(GenericTableTest):
    def test_player(self):
        assert (subj_repr(self.pirate_player)
                == {'class': 'Player',
                    'id': self.pirate_player.id,
                    'short_id': self.pirate_player.short_id,
                    'username': self.pirate_player.username})

    def test_table(self):
        assert (subj_repr(self.table)
                == {'class': 'PokerTable',
                    'id': self.table.id,
                    'short_id': self.table.short_id,
                    'name': self.table.name})

    def test_other(self):
        assert (subj_repr(Mock(__str__=Mock(return_value='test')))
                == {'class': 'Mock',
                    'name': 'test'})


class GetChangeForKeyTests(GenericTableTest):
    def build_changes(self, key, obj):
        return {patch_path(self.pirate_player, key): obj}

    def test_last_action_none(self):
        key = 'last_action'
        assert None == get_change_for_key(self.pirate_player,
                                          key,
                                          self.build_changes(key, None))

    def test_last_action_stringified(self):
        key = 'last_action'
        obj = Mock(__str__=Mock(return_value='str_version'))
        assert 'str_version' == get_change_for_key(self.pirate_player, key,
                                                self.build_changes(key, obj)
                                                    )

    def test_non_last_action(self):
        key = 'random_key'
        obj = Mock()
        assert obj == get_change_for_key(self.pirate_player, key,
                                            self.build_changes(key, obj)
                                            )

    def test_missing_key_raises(self):
        self.assertRaises(
            KeyError,
            get_change_for_key,
            self.pirate_player,
            'k',
            {}
        )


class AnimationsTestBase(GenericTableTest):
    def setUp(self):
        super().setUp()
        self.accessor = Mock(table=self.table)

    def build_player_event(self, player, event, anim_event):
        return process_event(self.accessor, player, anim_event,
                player.dispatch(event))

    def player_patch_path(self, player, key):
        return frontend_transform(patch_path(player, key))

    def uncollected_patch(self, player):
        return {
            'path': self.player_patch_path(player, 'uncollected_bets'),
            'value': 0
        }

    def last_action_none_patch(self, player):
        return {
            'path': self.player_patch_path(player, 'last_action'),
            'value': None
        }


class TestNewStreetEvent(AnimationsTestBase):
    def setUp(self):
        GenericTableTest.setUp(self)

    def build_player_event(self, player):
        return super().build_player_event(player, Event.NEW_STREET,
                AnimationEvent.NEW_STREET)

    def exp_processed_value(self, player):
        return (f'/players/{player.id}/uncollected_bets',)

    def test_player_new_street_is_ignored(self):
        stream = [
            self.build_player_event(self.pirate_player),
            self.build_player_event(self.ajfenix_player),
        ]
        output = process_eventstream(self.accessor, stream)
        expected = []
        assert output == expected

    def test_processed_event(self):
        self.pirate_player.uncollected_bets = 10
        self.ajfenix_player.uncollected_bets = 10
        event = (SIDE_EFFECT_SUBJ, AnimationEvent.NEW_STREET, [])
        processed_event = process_event(self.accessor, *event)

        patches = processed_event['event_args']['patches']
        value = processed_event['event_args']['value']

        assert len(value) == 2
        fenix_key = frontend_transform(patch_path(self.ajfenix_player,
                                                  'uncollected_bets'))
        fenix_patch = [
            patch for patch in patches
            if patch['path'] == fenix_key
        ].pop()
        assert fenix_patch
        assert fenix_patch['value'] == 0


class TestResetEvent(AnimationsTestBase):
    def build_player_event(self, player):
        return super().build_player_event(player, Event.RESET,
                AnimationEvent.RESET)

    def empty_cards_patch(self, player):
        return {'path': self.player_patch_path(player, 'cards'), 'value': []}

    def test_combines_successive_reset_events(self):
        stream = [
            self.build_player_event(self.pirate_player),
            self.build_player_event(self.ajfenix_player),
        ]
        output = process_eventstream(self.accessor, stream)
        expected = [{
            'type': 'RESET',
            'subj': subj_repr(self.table),
            'value': (),
            'patches': (
                self.uncollected_patch(self.pirate_player),
                self.empty_cards_patch(self.pirate_player),
                self.last_action_none_patch(self.pirate_player),
                self.uncollected_patch(self.ajfenix_player),
                self.empty_cards_patch(self.ajfenix_player),
                self.last_action_none_patch(self.ajfenix_player),
            )
        }]
        assert output == expected

    def test_without_last_action(self):
        self.pirate_player.dispatch(Event.SIT_OUT)

        stream = [self.build_player_event(self.pirate_player)]
        output = process_eventstream(self.accessor, stream)
        expected = [{
            'type': 'RESET',
            'subj': subj_repr(self.table),
            'value': (),
            'patches': (
                self.uncollected_patch(self.pirate_player),
                self.empty_cards_patch(self.pirate_player),
                self.last_action_none_patch(self.pirate_player),
            )
        }]
        assert output == expected

    def test_board(self):
        stream = [{
            'type': AnimationEvent.RESET,
            'subj': self.table,
            'event_args': {},
            'changes': {'/table/board': ()}
        }]

        output = process_eventstream(self.accessor, stream)
        expected = [{
            'type': 'RESET',
            'subj': subj_repr(self.table),
            'value': (),
            'patches': ({'path': '/table/board', 'value': ()},)
        }]

        assert output == expected


class TestPlayerDealEvent(AnimationsTestBase):
    def setUp(self):
        super().setUp()
        self.card = Card('Ts')
        self.card_idx = 0

    def build_player_event(self, player):
        event_kwargs = {'card': self.card}
        return process_event(
            self.accessor,
            player,
            AnimationEvent.DEAL,
            player.dispatch(Event.DEAL, **event_kwargs),
            **event_kwargs
       )

    def test_player_deal_type(self):
        stream = [self.build_player_event(self.pirate_player)]
        output = process_eventstream(self.accessor, stream)
        expected = [{
            'type': 'DEAL_PLAYER',
            'subj': subj_repr(self.pirate_player),
            'value': {'card': '?', 'idx': self.card_idx},
            'patches': (
                player_card_patch(self.pirate_player.id,
                                  self.card_idx, '?'),
            ),
            '_PRIVATE_': {
                self.pirate_player.id: {
                    'type': 'DEAL_PLAYER',
                    'subj': subj_repr(self.pirate_player),
                    'value': {'card': self.card, 'idx': self.card_idx},
                    'patches': (player_card_patch(
                                self.pirate_player.id,
                                self.card_idx,
                                self.card),)
                }
            }
        }]
        assert output == expected


class TestPassiveActionSnapTo(GenericTableTest):
    def test_passive_action_snapto(self):
        self.cowpig_player.playing_state = PlayingState.SITTING_OUT
        anim_sub = AnimationSubscriber(self.controller.accessor)
        self.controller.subscribers.append(anim_sub)
        self.controller.step()
        self.controller.commit()

        self.controller.dispatch('SIT_IN',
                                 player_id=self.cowpig_player.id)

        anims = anim_sub.updates_for_broadcast(player=self.cowpig_player)
        anims = anims['animations']

        assert len(anims) == 1
        tbl_json = anims[0]['value']['table']
        assert tbl_json == self.controller.accessor.table_json()

        cowpig_json = anims[0]['value']['players'][self.cowpig_player.id]
        self.assertEqual(
            cowpig_json,
            self.controller.accessor.player_json(
                self.cowpig_player,
                private=True
            )
        )
