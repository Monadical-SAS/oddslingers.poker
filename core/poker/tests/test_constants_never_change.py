from django.test import TestCase

from poker.constants import Action, Event, AnimationEvent

class ConstantsTest(TestCase):
    def enforce_consistency(self, enum_type, expected_values):
        for enum in enum_type:
            assert enum in expected_values
            assert expected_values[enum] == enum.value

    def test_constants(self):
        ''' This test is here to make sure the enums defined in poker.constants
        NEVER CHANGE. This is crucial because they are stored in the database
        according to their integer values, so if any change the database will be
        incorrect. '''
        action = {
            Action.BET: 1,
            Action.RAISE_TO: 2,
            Action.CALL: 3,
            Action.CHECK: 4,
            Action.FOLD: 5,
            Action.TIMEOUT_FOLD: 6,
            Action.BUY: 7,
            Action.TAKE_SEAT: 8,
            Action.LEAVE_SEAT: 9,
            Action.SIT_IN: 10,
            Action.SIT_OUT: 11,
            Action.SIT_OUT_AT_BLINDS: 12,
            Action.SET_AUTO_REBUY: 13,
            Action.SIT_IN_AT_BLINDS: 16,
            Action.SET_PRESET_CHECKFOLD: 17,
            Action.SET_PRESET_CHECK: 18,
            Action.SET_PRESET_CALL: 19,
            Action.CREATE_SIDEBET: 20,
            Action.CLOSE_SIDEBET: 21,
        }
        self.enforce_consistency(Action, action)

        event = {
            Event.DEAL: 1,
            Event.POST: 2,
            Event.POST_DEAD: 3,
            Event.ANTE: 4,
            Event.BET: 5,
            Event.RAISE_TO: 6,
            Event.CALL: 7,
            Event.CHECK: 8,
            Event.FOLD: 9,
            Event.BUY: 10,
            Event.TAKE_SEAT: 11,
            Event.LEAVE_SEAT: 12,
            Event.SIT_IN: 13,
            Event.SIT_OUT: 14,
            Event.WIN: 15,
            Event.RETURN_CHIPS: 16,
            Event.OWE_SB: 18,
            Event.OWE_BB: 19,
            Event.SET_BLIND_POS: 20,
            Event.NEW_HAND: 21,
            Event.NEW_STREET: 22,
            Event.POP_CARDS: 24,
            Event.UPDATE_STACK: 26,
            Event.SIT_IN_AT_BLINDS: 28,
            Event.SIT_OUT_AT_BLINDS: 29,
            Event.SET_AUTO_REBUY: 30,
            Event.CREATE_TRANSFER: 31,
            Event.ADD_ORBIT_SITTING_OUT: 33,
            Event.END_HAND: 34,
            Event.SET_TIMEBANK: 36,
            Event.RECORD_ACTION: 37,
            Event.CHAT: 38,
            Event.NOTIFICATION: 39,
            Event.SET_BOUNTY_FLAG: 40,
            Event.REVEAL_HAND: 41,
            Event.DELAY_COUNTDOWN: 42,
            Event.RESET: 43,
            Event.SET_PRESET_CHECKFOLD: 44,
            Event.SET_PRESET_CHECK: 45,
            Event.SET_PRESET_CALL: 46,
            Event.MUCK: 47,
            Event.WAIT_TO_SIT_IN: 48,
            Event.SHOWDOWN_COMPLETE: 49,
            Event.BOUNTY_WIN: 50,
            Event.SET_BLINDS: 51,
            Event.FINISH_TOURNAMENT: 52,
            Event.CREATE_SIDEBET: 53,
            Event.CLOSE_SIDEBET: 54,
            Event.SHUFFLE: 55,
        }
        self.enforce_consistency(Event, event)

        animation_event = {
            AnimationEvent.DEAL: 1,
            AnimationEvent.POST: 2,
            AnimationEvent.POST_DEAD: 3,
            AnimationEvent.ANTE: 4,
            AnimationEvent.BET: 5,
            AnimationEvent.RAISE_TO: 6,
            AnimationEvent.CALL: 7,
            AnimationEvent.CHECK: 8,
            AnimationEvent.FOLD: 9,
            AnimationEvent.TAKE_SEAT: 10,
            AnimationEvent.LEAVE_SEAT: 11,
            AnimationEvent.SIT_IN: 12,
            AnimationEvent.SIT_OUT: 13,
            AnimationEvent.WIN: 14,
            AnimationEvent.SET_BLIND_POS: 15,
            AnimationEvent.NEW_HAND: 16,
            AnimationEvent.NEW_STREET: 17,
            AnimationEvent.UPDATE_STACK: 18,
            AnimationEvent.RESET: 19,
            AnimationEvent.REVEAL_HAND: 20,
            AnimationEvent.RETURN_CHIPS: 21,
            AnimationEvent.MUCK: 22,
            AnimationEvent.BOUNTY_WIN: 23,
        }
        self.enforce_consistency(AnimationEvent, animation_event)
