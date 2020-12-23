import os
import sys
import json
import bleach
import uuid
import signal
import shutil
import zulip
import random
import secrets

from typing import Tuple, Optional
from fnmatch import fnmatch
from functools import wraps
from decimal import Decimal
from datetime import datetime
from inspect import signature, _empty
from hashlib import md5
from string import capwords
from enum import Enum

from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.utils.http import urlencode
from django.shortcuts import redirect
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import (DecimalField, CharField, IntegerField,
                              AutoField, QuerySet)
from django.utils import timezone


# ANSI Terminal escape sequences for printing colored log messages to shell
ANSI = {
    'reset': '\033[00;00m',
    'lightblue': '\033[01;30m',
    'lightyellow': '\033[01;33m',
    'lightred': '\033[01;35m',
    'red': '\033[01;31m',
    'green': '\033[01;32m',
    'blue': '\033[01;34m',
    'white': '\033[01;37m',
    'black': '\033[01;30m',
}
if not settings.CLI_COLOR:
    ANSI = {k: '' for k in ANSI.keys()}  # dont show colors in log files


def DEBUG_ONLY(f):
    """decorator to make a function only available in the debug shell"""

    # To use debug functions in your shell, set an environment variable:
    #        set DJANGO_DEBUG_HELPERS=1 in secrets.env
    #    or:
    #        export DJANGO_DEBUG_HELPERS=1               (in bash/zsh)
    #    or:
    #        env DJANGO_DEBUG_HELPERS=1 ./manage.py [command]

    @wraps(f)
    def wrapped(*args, **kwargs):
        if 'DJANGO_DEBUG_HELPERS' in os.environ:
            return f(*args, **kwargs)
        else:
            raise Exception(
                'This function is not available unless you have '
                '"DJANGO_DEBUG_HELPERS" set in your ENV.  '
                'It is intended for debug shell use only.'
            )
    return wrapped


def sanitize_html(text, strip=False, allow_safe=True):
    """
    Strip/escape html tags, attributes, and styles using a whitelist.
    Set allow_safe=False to escape all html tags, by default it allows
    a limited subset of safe ones (e.g. <b>, <i>, <img>...).
    """
    attrs = {
        '*': [
            'style', 'href', 'alt', 'title', 'class',
            'border', 'padding', 'margin', 'line-height'
        ],
        'img': ['src'],
    }
    if not allow_safe:
        tags = []
        styles = []
    else:
        tags = [
            'p', 'b', 'br', 'em', 'blockquote', 'strong', 'i', 'u',
            'a', 'ul', 'li', 'ol', 'img', 'span', 'h1', 'h2', 'h3',
            'h4', 'h5', 'h6', 'h7', 'table', 'td', 'thead', 'tbody',
            'tr', 'div', 'sub', 'sup', 'small'
        ]
        styles = [
            'color', 'font-weight', 'font-size', 'font-family',
            'text-decoration', 'font-variant'
        ]

    cleaned_text = bleach.clean(text, tags, attrs, styles, strip=strip)

    return cleaned_text  # "free of XSS"


def sanitize_csv(text: str):
    """escape csv values that can contain executable excel formulas"""
    # see https://hackerone.com/reports/72785
    text = text or ''
    if text.startswith('=') or text.startswith('+') or text.startswith('-'):
        # prepend apostraphe to prevent excel operator hacks
        return f"'{text}"
    return text


def split_name(name: str):
    """Sarah J Connor -> ('Sarah', 'J Connor')"""
    # new signup forms will pass us name instead of first & last
    split_name = name.strip().split(None, 1)  # None splits on any whitespace
    # returns (firstname, lastname)
    return tuple(split_name) if len(split_name) == 2 else (name, '')


def rotated(sequence, amount):
    """
    returns generator starting at element[idx] and ending at
    element[idx-1]
    """
    length = len(sequence)
    for idx in range(length):
        yield sequence[(idx + amount) % length]


def idx_dict(iterable):
    return dict(enumerate(iterable))


def decimal_floor(amt, prec):
    return Decimal(int(amt * 10**prec)) / Decimal(10**prec)

def json_strptime(timestamp):
    return datetime.strptime(timestamp, '%Y-%m-%dT%H:%M:%S.%f')

def deep_diff(dict1, dict2):
    diff = {}
    for key, val1 in dict1.items():
        if key not in dict2:
            # keys that don't appear in dict2 will be set to None
            diff[key] = None
        else:
            val2 = dict2[key]
            if isinstance(val1, dict) and isinstance(val2, dict):
                subdiff = deep_diff(val1, val2)
                if subdiff:
                    diff[key] = subdiff
            elif (to_json_str(val1) != to_json_str(val2)):
                diff[key] = val2

    for key, val2 in dict2.items():
        if key not in dict1:
            diff[key] = val2

    return diff


def deep_update(dict1, dict2):
    """
    recursively update a dictionary by merging values at the same path
    in a second dict
    """
    for k, v in dict2.items():
        if isinstance(v, dict):
            r = deep_update(dict1.get(k, {}), v)
            dict1[k] = r
        else:
            dict1[k] = dict2[k]
    return dict1


def autocast(func):
    """
    Tries to cast any parameters with type hints to the type defined.
    Will not act if more than one type is defined.

    Try to avoid using this, instead type-cast within your function to
    the desired types.
    """

    # This function was intented to fix the issue of django field types
    #   being different from the base types when retreived from db, e.g.
    #   DecimalField vs Decimal vs float etc.

    def autocast_wrapper(*args, **kwargs):
        sig = signature(func)

        def convert(arg, param):
            try:
                annotation = sig.parameters[param].annotation
            except KeyError:
                annotation = _empty

            # magic, please comment if you can understand how this works
            if annotation is not _empty and annotation.__class__ is type:
                if not isinstance(arg, annotation):
                    return annotation(arg)
            return arg

        new_args = [
            convert(arg, param)
            for arg, param in zip(args, sig.parameters)
        ]
        new_kwargs = {
            param: convert(arg, param)
            for param, arg in kwargs.items()
        }

        return func(*new_args, **new_kwargs)

    return autocast_wrapper


def get_short_uuid(uuid) -> str:
    """get the first block of a 4-word UUID to use as a short identifier"""
    full_uuid = str(uuid)
    return full_uuid.split('-', 1)[0]

def shorten_uuids(data):
    """recursively shorten all UUIDs in a data structure for debug output"""

    if isinstance(data, dict):
        return {
            shorten_uuids(k): shorten_uuids(v)
            for k, v in data.items()
        }
    elif isinstance(data, (list, tuple)):
        return [shorten_uuids(item) for item in data]
    elif isinstance(data, uuid.UUID):
        return get_short_uuid(data)  # + '...'
    elif isinstance(data, str):
        try:
            return get_short_uuid(uuid.UUID(data))  # + '...'
        except Exception:
            pass
    return data


def syntax_highlight(code: str):
    """rudimentary color coding for JSON syntax symbols"""
    return code\
        .replace('[', '{red}[{reset}'.format(**ANSI))\
        .replace(']', '{red}]{reset}'.format(**ANSI))\
        .replace(',', '{lightyellow},{reset}'.format(**ANSI))\
        .replace('":', '"{green}:{reset}'.format(**ANSI))\
        .replace('"', '{blue}"{reset}'.format(**ANSI))\
        .replace('{', '{red}{{{reset}'.format(**ANSI))\
        .replace('": ', '"{blue}:{reset} '.format(**ANSI))\
        .replace('}', '{red}}}{reset}'.format(**ANSI))

def get_websocket_action_color(action: Optional[str], content: Optional[dict]):
    """get the debug output color for a given websocket action type"""
    if 'LOAD' in action:
        return ANSI['lightblue']
    elif 'NOTIFICATION' in action:
        if content.get('notification', {}).get('style') == 'success':
            return ANSI['green']
        return ANSI['red']
    elif 'SAVED' in action:
        return ANSI['green']
    elif 'UPDATE' in action:
        return ANSI['lightred']
    elif 'PING' in action or 'HELLO' in action:
        return ANSI['black']
    return ANSI['lightyellow']


def debug_print_io(out: bool=True, content: dict=None, unknown: bool=False):
    """log pretty websocket messages to console for easy flow debugging"""
    if not settings.STDOUT_IO_SUMMARY:
        return

    summary = dict(content or {})
    action = summary.get('type', '')
    try:
        del summary['type']
        del summary['TIMESTAMP']
    except KeyError:
        pass

    # color-highlight action keyword based on type of action
    if unknown:
        # highlight unknown incoming messages in red
        arrow = ANSI['red'] + '[>] RECV'
    else:
        arrow = (
            ANSI['green'] + '[<] SENT'
            if out else
            ANSI['blue'] + '[>] RECV'
        )

    # dump json to str with uuids shortened
    str_summary = to_json_str(shorten_uuids(summary))

    # truncate to width of terminal
    if settings.DEBUG:
        term_width = shutil.get_terminal_size((160, 10)).columns
        # 27 is width of "[<] RECV: ACTION_NAME"
        str_summary = str_summary[:term_width - 27]

    message = '{0}: {1}{2}{3}{4}'.format(
        arrow,
        get_websocket_action_color(action, content),
        action.ljust(17),
        syntax_highlight(str_summary) if settings.DEBUG else str_summary,
        ANSI['reset'],
    )

    if settings.DEBUG:
        print(message)

def debug_print_info(content: str=None):
    """log pretty messages to console for easy debugging"""

    # color-highlight
    symbol = ANSI['lightyellow'] + '[I] INFO'

    message = '{0}: {1}{2}'.format(
        symbol,
        content,
        ANSI['reset']
    )

    if settings.DEBUG:
        print(message)

def log_io_message(socket, direction: str, content: dict):
    """write a socket IO log message to the io log for that socket's path"""
    assert direction in ('in', 'out')
    if not socket: return

    if hasattr(socket, 'user'):
        path = socket.path      # single socket
    else:
        path = socket[0].path   # socket queryset
        assert all(s.path == path for s in socket), (
            'When sending messages to a group, all must have the same path')

    # e.g. '/table/abc124234/' to table-abc124234
    assert path and path[0] == '/' and path[-1] == '/', (
                f'expected path w/pattern: "/.../" but got {path}')
    path_to_hyphens = '-'.join(path.split('/')[1:-1])

    io_log_path = settings.SOCKET_IO_LOG.format(path_to_hyphens, direction)

    with open(io_log_path, 'a+') as f:
        # TODO: this has a performance cost on every websocket message as it
        # requires a full disk write and commit before doing anything else
        f.write(to_json_str(content, sort_keys=True))
        f.write('\n')


class StrBasedEnum(Enum):
    @classmethod
    def from_str(cls, string: str):
        return cls._member_map_[string.upper()]

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name


class ExtendedEncoder(DjangoJSONEncoder):
    """
    Extended json serializer that supports serializing several model
    fields and objects
    """

    def default(self, obj):
        cls_name = obj.__class__.__name__

        if isinstance(obj, (DecimalField, CharField)):
            return str(obj)

        elif isinstance(obj, (IntegerField, AutoField)):
            return int(obj)

        elif cls_name in ('Action', 'Event'):
            return obj.name

        elif hasattr(obj, '__json__'):
            return obj.__json__()

        elif isinstance(obj, QuerySet):
            return list(obj)

        elif isinstance(obj, uuid.UUID):
            return str(obj)

        elif isinstance(obj, bytes):
            return obj.decode()

        elif cls_name == 'CallableBool':
            # ^ shouldn't check using isinstance because CallableBools
            #   will eventually be deprecated
            return bool(obj)

        elif cls_name == 'AnonymousUser':
            # ^ cant check using isinstance since models aren't ready
            #   yet when this is called
            return None  # AnonUser should always be represented as null in JS

        elif isinstance(obj, StrBasedEnum):
            return str(obj)

        elif cls_name in ('dict_items', 'dict_keys', 'dict_values'):
            return tuple(obj)

        return DjangoJSONEncoder.default(self, obj)

    @classmethod
    def convert_for_json(cls, obj, recursive=True):
        if recursive:
            if isinstance(obj, dict):
                return {
                    cls.convert_for_json(k): cls.convert_for_json(v)
                    for k, v in obj.items()
                }
            elif isinstance(obj, (list, tuple)):
                return [cls.convert_for_json(i) for i in obj]

        try:
            return cls.convert_for_json(cls().default(obj))
        except TypeError:
            return obj


def round_to_multiple(n, multiple):
    return multiple * round(float(n)/float(multiple))


def to_json_str(obj, indent=None, sort_keys=False, unicode_escape=False):
    '''
    serializes obj to a string using encodings defined in the
    ExtendedEncoder.

    unicode_escape: remove unicode escape characters (allow printing
    of suit symbols and actual tabs instead of '\t')
    '''

    out = json.dumps(
        obj,
        cls=ExtendedEncoder,
        indent=indent,
        sort_keys=sort_keys
    )

    if unicode_escape:
        return bytes(out, 'utf-8').decode('unicode_escape')

    return out


def optional_arg_decorator(fn):
    """
    wrap a decorator so that it can optionally take args/kwargs
    when decorating a func
    """
    # http://stackoverflow.com/a/32292739/2156113
    @wraps(fn)
    def wrapped_decorator(*args, **kwargs):
        is_bound_method = hasattr(args[0], fn.__name__) if args else False

        if is_bound_method:
            klass = args[0]
            args = args[1:]

        # If no arguments were passed...
        if len(args) == 1 and len(kwargs) == 0 and callable(args[0]):
            if is_bound_method:
                return fn(klass, args[0])
            else:
                return fn(args[0])

        else:
            def real_decorator(decoratee):
                if is_bound_method:
                    return fn(klass, decoratee, *args, **kwargs)
                else:
                    return fn(decoratee, *args, **kwargs)
            return real_decorator
    return wrapped_decorator


@optional_arg_decorator
def require_staff(view_func, redirect_url='/', allow_debug=False):
    """decorates a view to redirect when the user is not staff"""

    @wraps(view_func)
    def protected_view_func(self, request, *args, **kwargs):
        if not (request.user.is_staff or (allow_debug and settings.DEBUG)):
            return redirect(redirect_url)
        return view_func(self, request, *args, **kwargs)

    return protected_view_func


@optional_arg_decorator
def require_login(view_func, redirect_url=None):
    """decorates a view to redirect when the user is not authenticated"""

    @wraps(view_func)
    def protected_view_func(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            request_path = redirect_url or request.get_full_path()
            return HttpResponseRedirect(
                f"{reverse('Login')}?{urlencode({'next': request_path})}"
            )
        return view_func(self, request, *args, **kwargs)

    return protected_view_func


class DoesNothing:
    """
    Object who's methods accept arbitrary args and do nothing.
    Userful for mocking/blackholing
    """

    @staticmethod
    def sink(*args, **kwargs):
        pass

    def __getattr__(self, *args, **kwargs):
        """
        Any method called will go to sink
        (good for creating mock APIClients that dont do anything).
        """
        return self.sink

class MockObject:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class TimeOutException(Exception):
    def __init__(self, message, errors=None, signum=None, frame=None):
        super(TimeOutException, self).__init__(message)
        self.errors = errors or []
        self.signum = signum
        self.frame = frame


def timeout_handler(signum, frame, reason=None):
    if reason:
        raise TimeOutException(f'Timed out while {reason}!',
                               signum=signum,
                               frame=frame)

    raise TimeOutException('Timed out!', signum=signum, frame=frame)


def set_timeout(seconds, description=''):
    signal.alarm(0)
    handler_with_description = lambda s, f: timeout_handler(s, f, description)
    signal.signal(signal.SIGALRM, handler_with_description)
    signal.alarm(seconds)


def add_timestamp_and_hash(payload: dict):
    payload_str = to_json_str(payload).encode('utf-8')
    payload_hash = md5(payload_str).hexdigest()
    now_str = str(timezone.now().timestamp() * 1000)
    return {
        **payload,
        'HASH': payload_hash,
        'TIMESTAMP': now_str,
    }


def camelcase_to_capwords(string):
    return capwords(string.replace('_', ' '))


def get_next_filename(path, fn_pattern, extension='.json'):
    """e.g. if path/hh_001.json exists, return hh_002.json"""

    existing_files = [
        filename for filename in os.listdir(path)
        if os.path.isfile(os.path.join(path, filename))
    ]
    conflicting_files = [
        fn for fn in existing_files
        if fnmatch(fn, f'*{fn_pattern}???{extension}')
    ]

    parse_number = lambda fn: int(fn.split('.')[0].split('_')[1])
    number = max([parse_number(fn) for fn in conflicting_files] or [0])

    next_avail_num = number + 1

    return os.path.join(path, f"{fn_pattern}{next_avail_num:03}{extension}")


def notify_zulip(msg, topic='Site Events', stream='analytics'):
    if settings.DEBUG:
        print(f'{ANSI["blue"]}[i] ZULIP MESSAGE #{stream}/{topic}: {msg}{ANSI["reset"]}')

    if not settings.SEND_ZULIP_ALERTS:
        return

    if stream == 'support':
        client = zulip.Client(config_file=f"{settings.REPO_DIR}/etc/zulip/support_bot.ini")
    else:
        client = zulip.Client(email=settings.ZULIP_EMAIL,
                              api_key=settings.ZULIP_API_KEY,
                              site=settings.ZULIP_SERVER)

    client.send_message({
        'type': 'stream',
        'to': stream,
        'subject': topic,
        'content': msg,
    })


def secure_random_number(max_num: int=sys.maxsize) -> int:
    """get cryptographically secure number from the system entropy pool"""

    # https://docs.python.org/3/library/secrets.html

    return secrets.randbelow(max_num)


class TempRandomSeed:
    def __init__(self, seed):
        self.seed_restore = random.randint(0, sys.maxsize)
        self.seed = seed

    def __enter__(self):
        random.seed(self.seed)

    def __exit__(self, *args):
        random.seed(self.seed_restore)


def debug_toolbar_callback(request):
    if settings.ENABLE_DEBUG_TOOLBAR:
        return True
    if settings.ENABLE_DEBUG_TOOLBAR_FOR_STAFF and request.user.is_staff:
        return True
    return False


def date_is_in_season(date: datetime, season: Tuple) -> bool:
    season_start, season_end = season
    return season_start <= date < season_end


def fnv_hash(string):
    # not cryptographically secure.
    # very simple, quick hash for strings based on:
    # https://github.com/Cilyan/stblc/blob/master/STBLWriter.cs#L58
    output = 14695981039346656037
    sixtyfourbits = 18446744073709551616
    for char in string:
        output *= 1099511628211
        output %= sixtyfourbits
        output ^= ord(char)

    return output


def is_testing(func):
    """decorates a function to make sure it can only be use while testing"""
    def wrapper(*args, **kwargs):
        if settings.IS_TESTING:
            return func(*args, **kwargs)
        else:
            raise Exception(
                'This function is not available unless you have '
                '"IS_TESTING" set in your settings.  '
                'It is intended for testing use only.'
            )
    return wrapper
