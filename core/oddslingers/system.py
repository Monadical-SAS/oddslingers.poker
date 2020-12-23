"""
Functions for managing configuration and sytem setup.

Do not import any django code in this file, if you must, inline the imports
in the function, not at the top!!!
"""

import os
import sys
import getpass

import psutil
import shutil
import subprocess
from time import time

from dotenv import dotenv_values

from typing import Optional, Iterable, Tuple, Union


### Environment and Config Management

EnvSettingTypes = (str, bool, int, float, list)
EnvSetting = Union[str, bool, int, float, list]


def get_env_value(env: dict, key: str, default: EnvSetting=None):
    """get & cast a given value from a dictionary, or return the default"""
    if key in env:
        value = env[key]
    else:
        return default

    ExpectedType = type(default)
    assert ExpectedType in EnvSettingTypes, (
        f'Tried to set unsupported environemnt variable {key} to {ExpectedType}')

    def raise_typerror():
        raise TypeError(f'Got bad environment variable {key}={value}'
                        f' (expected {ExpectedType})')

    if ExpectedType is str:
        return value
    elif ExpectedType is bool:
        if value.lower() == 'true':
            return True
        elif value.lower() == 'false':
            return False
        else:
            raise_typerror()
    elif ExpectedType is int:
        if value.isdigit():
            return int(value)
        else:
            raise_typerror()
    elif ExpectedType is float:
        try:
            return float(value)
        except ValueError:
            raise_typerror()
    elif ExpectedType is list:
        return value.split(',')


def unique_env_settings(env: dict, defaults: dict) -> dict:
    """return all the new valid env settings in a dictionary of settings"""
    existing_settings = {
        setting_name: val
        for setting_name, val in (defaults or env).items()
        if not setting_name.startswith('_') and setting_name.isupper()
    }
    if not defaults:
        return existing_settings

    new_settings = {}
    for setting_name, default_val in existing_settings.items():
        loaded_val = get_env_value(env, setting_name, default_val)

        if loaded_val != default_val:
            new_settings[setting_name] = loaded_val

    return new_settings


def load_env_settings(dotenv_path: str=None, env: dict=None, defaults: dict=None) -> dict:
    """load settings from a dotenv file or os.environ by default"""
    assert not (dotenv_path and env), 'Only pass env or dotenv_path, not both'

    env_values = (env or {}).copy()
    defaults = (defaults or {}).copy()
    if dotenv_path:
        env_values = dotenv_values(dotenv_path=dotenv_path)

    return unique_env_settings(env_values, defaults)


def get_setting_source(sources: Iterable[Tuple[str, dict]], key: str) -> str:
    """determine which file a specific setting was loaded from"""
    for source_name, settings in reversed(sources):
        if key in settings:
            return source_name

    source_names = ", ".join(name for name, vals in sources)
    raise ValueError(f'Setting {key} is not in any of {source_names})')


def check_system_invariants(ODDSLINGERS_ENV):
    """Check basic system setup and throw if there is any misconfiguration"""

    ALLOWED_ENVS = ('DEV', 'CI', 'BETA', 'PROD')
    DJANGO_USER = getpass.getuser() or os.getlogin()

    assert ODDSLINGERS_ENV in ALLOWED_ENVS, (
        f'ODDSLINGERS_ENV={ODDSLINGERS_ENV} is not one of the allowed values: '
        f'{",".join(ALLOWED_ENVS)}')

    assert sys.version_info >= (3, 5)
    assert sys.implementation.name in ('cpython', 'pypy')

    # running as root even once will corrupt the permissions on all the DATA_DIRS
    assert DJANGO_USER != 'root', 'Django should never be run as root!'

    # python -O strips asserts from our code, but we use them for critical logic
    try:
        assert not __debug__
        print('Never run oddslingers with python -O, asserts are needed in production.')
        raise SystemExit(1)
    except AssertionError:
        pass

    if hasattr(sys.stderr, 'encoding'):
        assert sys.stderr.encoding.upper() == sys.stdout.encoding.upper() == 'UTF-8', (
            f'Bad shell encoding setting "{sys.stdout.encoding}". '
            'System, Shell, and Python system locales must be set to '
            '(uppercase) "UTF-8" to run properly.')


def check_django_invariants():
    """Check basic django setup and throw if there is any misconfiguration"""

    from django.conf import settings as s

    # DEBUG features and permissions mistakes must be forbidden on production boxes
    if 'oddslingers-prod' in s.HOSTNAME:
        assert s.ODDSLINGERS_ENV == 'PROD', 'oddslingers-prod must run in ENV=PROD mode'
        assert s.DJANGO_USER == 'www-data', 'Django can only be run as user www-data'
        assert not s.DEBUG, 'DEBUG=True is never allowed on prod and beta!'
        assert not s.ENABLE_DEBUG_TOOLBAR, 'Debug toolbar is never allowed on prod!'
        assert s.DEFAULT_HTTP_PROTOCOL == 'https', 'https is required on prod servers'
        assert s.TIME_ZONE == 'UTC', 'Prod servers must always be set to UTC timezone'
        repo_dir_prod = s.REPO_DIR == '/opt/oddslingers' or s.REPO_DIR == '/opt/oddslingers.poker'
        assert repo_dir_prod, 'Repo must be in /opt/oddslingers on prod'

        # tests can pollute the data dir and use lots of CPU / Memory
        # only disable this check if you're 100% confident it's safe and have a
        # very good reason to run tests on production. remember to try beta first
        assert not s.IS_TESTING, 'Tests should not be run on prod machines'

    elif 'oddslingers-beta' in s.HOSTNAME:
        assert s.ODDSLINGERS_ENV == 'BETA', 'oddslingers-beta must run in ENV=BETA mode'
        assert s.DJANGO_USER == 'www-data', 'Django can only be run as user www-data'
        assert not s.DEBUG, 'DEBUG=True is never allowed on prod and beta!'
        assert s.DEFAULT_HTTP_PROTOCOL == 'https', 'https is required on prod servers'
        assert s.TIME_ZONE == 'UTC', 'Prod servers must always be set to UTC timezone'
        assert s.REPO_DIR == '/opt/oddslingers', 'Repo must be in /opt/oddslingers on prod'

    # make sure all security-sensitive settings are coming from safe sources
    for setting_name in s.SECURE_SETTINGS:
        defined_in = get_setting_source(s.SETTINGS_SOURCES, setting_name)

        if s.ODDSLINGERS_ENV in ('PROD', 'BETA'):
            assert defined_in in s.SECURE_SETTINGS_SOURCES, (
                'Security-sensitive settings must only be defined in secrets.env!\n'
                f'    Missing setting: {setting_name} in secrets.env\n'
                f'    Found in: {defined_in}'
            )

        if s.ODDSLINGERS_ENV == 'PROD':
            # make sure settings are not defaults on prod
            assert getattr(s, setting_name) != s._PLACEHOLDER_FOR_UNSET, (
                'Security-sensitive settings must be defined in secrets.env\n'
                f'    Missing setting: {setting_name} in secrets.env'
            )

    if s.IS_TESTING:
        assert s.REDIS_DB != s.SETTINGS_DEFAULTS['REDIS_DB'], (
            'Tests must be run with a different redis db than the main redis')


def django_status_line(fancy: bool=False, truncate: bool=False) -> str:
    """the status line with process info printed every time django starts"""
    from django.conf import settings

    cli_arguments = " ".join(sys.argv[1:])

    # DEV=settings.py 👤 squash  🆔 24781  📅 1523266746  💾 oddslingers@localhost
    sections = (
        ('env=', '| ⚙️  '),   # normal mode, fancy mode
        ('debug=', ''),
        ('usr=', '👤  '),
        ('pid=', ' 🆔  '),
        ('ts=', ' 🕐  '),
        ('db=', '🗄  '),
        ('data=', '📂  '),
        ('git=', '#️⃣  '),
    )
    icn = lambda idx: sections[idx][fancy]

    debug_str = ("","👾 ")[settings.DEBUG] if fancy else str(settings.DEBUG)
    pytype_str = " PYPY" if settings.PY_TYPE == "pypy" else ""

    status_line = ''.join((
        '\033[01;33m' if fancy else '',  # yellow
        '> ./manage.py ',
        '\033[01;34m' if fancy else '',  # blue
        cli_arguments,
        '\033[00;00m' if fancy else '',  # reset
        f' {icn(0)}../env/{settings.ODDSLINGERS_ENV}.env',
        f' {icn(1)}{debug_str}{pytype_str}',
        f' {icn(2)}{settings.DJANGO_USER}',
        f' {icn(3)}{settings.PID}',
        f' {icn(4)}{int(time())}',
        f' {icn(5)}{settings.POSTGRES_HOST}/{settings.POSTGRES_DB}',
        f' {icn(6)}{settings.DATA_DIR.replace(settings.REPO_DIR + "/", "../")}',
        f' {icn(7)}{settings.GIT_SHA[:7]}',
    ))

    if truncate:
        term_width = shutil.get_terminal_size((160, 10)).columns
        control_characters = 24 if fancy else 0
        status_line = status_line[:term_width + control_characters]

    if fancy:
        return f"{status_line}\033[00;00m"
    else:
        return status_line


def log_django_status_line():
    """print and log the django status line to stdout and the reloads log"""
    from django.conf import settings

    plain_status = django_status_line()
    fancy_status = django_status_line(fancy=settings.FANCY_STDOUT,
                                      truncate=settings.FANCY_STDOUT)

    # Log django process launch to reloads log
    with open(settings.RELOADS_LOGS, 'a+') as f:
        f.write(f'{plain_status}\n')

    print(fancy_status)
    return plain_status


### File and folder management

def mkchown(path: str, user: str):
    """create and chown a directory to make sure a user can write to it"""

    try:
        os.makedirs(path, exist_ok=True)
        if sys.platform == 'darwin':
            # on mac, just chown as the user
            shutil.chown(path, user=user)
        else:
            # on linux, chown as user:group
            shutil.chown(path, user=user, group=user)
    except FileExistsError:
        # sshfs folders can trigger a FileExistsError if permissions
        # are not set up to allow user to access fuse filesystems
        print(
            f'Unwritable file existed where folder {path} was expected (if '
            f'using sshfs, make sure allow_other is passed and {user} '
            'is a member of the "fuse" user group)'
        )
        raise
    except PermissionError:
        print(f'[!] Django user "{user}" must have permission to modify '
              f'the data dir: {path}')
        raise


def chown_django_folders():
    """set the proper permissions on all the data folders used by django"""

    from django.conf import settings

    mkchown(settings.DATA_DIR, settings.DJANGO_USER)
    for path in settings.DATA_DIRS:
        mkchown(path, settings.DJANGO_USER)


### Process Management

def ps_aux(pattern: str=None):
    """find all processes matching a given str pattern"""
    return [
        line for line in subprocess.Popen(
            ['ps', 'axw'],
            stdout=subprocess.PIPE,
        ).stdout
        if (pattern and pattern in line) or not pattern
    ]


def kill(pid_lines: list):
    """for each process line produced by ps_aux, kill the process"""
    for line in pid_lines:
        pid = line.decode().strip().split()[0]
        assert pid.isdigit(), 'Found invalid text when expecting PID'
        subprocess.Popen(['kill', pid])


def kill_all_heartbeats():
    """send a SIGTERM to all running tablebeat and botbeats"""
    from oddslingers.utils import ANSI

    term_width = shutil.get_terminal_size((160, 10)).columns - 3
    print(term_width * '=')
    heartbeat_procs = ps_aux(b'table_heartbeat')
    botbeat_proc = ps_aux(b'bot_heartbeat')

    print(f'{ANSI["red"]}'
          f'[X] Killing {len(heartbeat_procs)} tablebeats and {len(botbeat_proc)} botbeats...'
          f'{ANSI["reset"]}')
    kill(heartbeat_procs)
    kill(botbeat_proc)


def matching_pids(match_func) -> Iterable[int]:
    """yield all pids that match using a given function match function"""
    for proc in psutil.process_iter():      # python api for ps -aux
        with proc.oneshot():
            try:
                cmd = proc.cmdline()
            except Exception:
                continue

            # ['python', './manage.py', 'table_heartbeat', '6a7d6689']
            if len(cmd) >= 3 and match_func(proc, cmd):
                yield proc.pid


def find_process(mgmt_command: str, *args,
                 exact=False, exclude_pid=None) -> Optional[int]:
    """find the pid for a given management command thats running"""

    def pid_matches(proc, cmd):
        if not cmd[2] == mgmt_command:
            return False

        if exact:
            return cmd[3:] == args
        else:
            return all(arg in cmd for arg, cmd in zip(args, cmd[3:]))

    pids = list(matching_pids(pid_matches))
    if pids and pids[0] != exclude_pid:
        return pids[0]

    return None


def stop_process(pid: int, block: bool=True) -> bool:
    """stop the process identified by pid, optionally block until it's dead"""
    if not pid:
        return False

    proc = psutil.Process(pid)
    proc.terminate()
    if block:
        proc.wait()
    return True


def DOUBLE_FORK():
    """
    Perform a UNIX double-fork to detach, and re attach process to
    init so it's not a child of web worker
    """
    # do the UNIX double-fork magic, see Stevens' "Advanced
    # Programming in the UNIX Environment" for details (ISBN 0201563177)
    try:
        pid = os.fork()
        if pid > 0:
            # exit first parent
            sys.exit(0)
    except OSError as e:
        print("fork #1 failed: %d (%s)" % (e.errno, e.strerror))
        sys.exit(1)

    # decouple from parent environment
    os.setsid()
    os.umask(0)

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            # exit from second parent, print eventual PID before
            sys.exit(0)
    except OSError as e:
        print("fork #2 failed: %d (%s)" % (e.errno, e.strerror))
        sys.exit(1)


### Load Management


MAX_LOAD = {
    'PROD': {
        'CPU': 70,
        'Number of Processes': 90,
        'Memory': 90,
        'Disk Space': 95,
    },
    'BETA': {
        'CPU': 80,
        'Number of Processes': 80,
        'Memory': 80,
        'Disk Space': 70,
    },
    # dev limits are not enforced because we run tons of other programs
    'DEV': {
        'CPU': 1000,
        'Number of Processes': 1000,
        'Memory': 1000,
        'Disk Space': 1000,
    },
}

# All return integer percentages 0 - 100%


def cpu_usage() -> int:
    num_cpus = os.cpu_count() or 1
    load_avg = os.getloadavg()[1]  # get 5min load level of [1min 5min 15min]
    cpu_use_pct = int((load_avg / num_cpus) * 100)
    return cpu_use_pct


def proc_usage() -> int:
    num_procs = len(list(psutil.process_iter()))
    max_procs = 300
    return int((num_procs / max_procs) * 100)


def mem_usage() -> int:
    memory_use_pct = psutil.virtual_memory()._asdict()['percent']
    return int(memory_use_pct)


def disk_usage() -> int:
    disk_use = psutil.disk_usage('/')
    return int((disk_use.used / disk_use.total) * 100)


def io_usage() -> int:
    # TODO
    # io_use = psutil.disk_io_counters()
    # some math here to figure out rate of use / capacity
    raise NotImplementedError()


def net_usage() -> int:
    # TODO
    # net_use = psutil.net_io_counters()
    # some math here to figure out rate of use / capacity
    raise NotImplementedError()


def load_summary() -> dict:
    """Get system load as 0-100 integer percentages of total capacity in use"""
    return {
        'CPU': cpu_usage(),
        'Number of Processes': proc_usage(),
        'Memory': mem_usage(),
        'Disk Space': disk_usage(),
        # 'Disk IO': io_usage(),
        # 'Network IO': net_usage(),
    }
