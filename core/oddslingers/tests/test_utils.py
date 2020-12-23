from datetime import timedelta
from django.test import TestCase

from oddslingers.utils import deep_diff
from django.utils import timezone


class DeepDiffTest(TestCase):
    def test_deep_diff(self):
        dict1 = {
            'diff_dict': {
                'list_to_num': [1, 2, 3],
                'change_and_remove': {
                    'changed_list': ['the', 'witch', 'is', 'dead'],
                    'removed': 'derp'
                },
                'dict_no_diff': {
                    'chimi': 1,
                    'churri': 2
                }
            },
            'same_val': 8,
            'same_val2': 'pop'
        }

        dict2 = {
            'diff_dict': {
                'list_to_num': 1.5,
                'change_and_remove': {
                    'changed_list': ['the', 'witch', 'is', 'funky']
                },
                'dict_no_diff': {
                    'chimi': 1,
                    'churri': 2
                },
                'added_sub': 1234
            },
            'same_val': 8,
            'same_val2': 'pop',
            'added_top': 'goober'
        }

        expected_diff = {
            'diff_dict': {
                'list_to_num': 1.5,
                'change_and_remove': {
                    'changed_list': ['the', 'witch', 'is', 'funky'],
                    'removed': None
                },
                'added_sub': 1234
            },
            'added_top': 'goober'
        }
        # import ipdb; ipdb.set_trace()
        actual_diff = deep_diff(dict1, dict2)

        self.assert_deep_equal(actual_diff, expected_diff)

    def assert_deep_equal(self, obj1, obj2):
        for key, val1 in obj1.items():
            assert key in obj2
            val2 = obj2[key]
            assert val1 == val2
            if isinstance(key, dict):
                self.assert_deep_equal(val1, val2)

        for key, val2 in obj2.items():
            assert key in obj1
            val1 = obj1[key]
            assert val1 == val2
            if isinstance(key, dict):
                self.assert_deep_equal(val1, val2)


class TimezoneMocker:
    """
    monkey-patch timezone.now to mock_time for testing

    IMPORTANT: python debuggers (ipdb/pdb) break this;
        somehow the `with` context is lost and timezone.now()
        returns to its original behaviour after entering debug
        mode
    """
    def __init__(self, mock_time):
        self.mock_time = mock_time
        self.prev_tz = timezone.now

    def __enter__(self):
        timezone.now = lambda: self.mock_time
        return self

    def __exit__(self, *args):
        timezone.now = self.prev_tz

    def bump_time(self, seconds=0.001):
        self.mock_time = self.mock_time + timezone.timedelta(seconds=seconds)


class TimezoneMockerTest(TestCase):
    def test_timezone_mocker(self):
        now = timezone.now()
        soon = now + timedelta(minutes=5)
        in_a_bit = now + timedelta(hours=1)
        in_a_bit_plus_1 = in_a_bit + timedelta(seconds=1)

        with TimezoneMocker(soon) as time:
            assert timezone.now() == soon
            time.bump_time()
            assert timezone.now() > soon

        with TimezoneMocker(in_a_bit) as time:
            assert timezone.now() > soon
            assert timezone.now() == in_a_bit
            time.bump_time()
            assert in_a_bit < timezone.now() < in_a_bit_plus_1


class MonkeyPatch:
    """monkey-patch a method with a mock method"""
    def __init__(self, klass, method_name, mock_method):
        self.klass = klass
        self.mock_method = mock_method
        self.original_method = getattr(klass, method_name)
        self.method_name = method_name

    def __enter__(self):
        setattr(self.klass, self.method_name, self.mock_method)

    def __exit__(self, *args):
        setattr(self.klass, self.method_name, self.original_method)
