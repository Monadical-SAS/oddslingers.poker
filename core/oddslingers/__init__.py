import os
import sys
import signal
import subprocess

from .utils import ANSI
from .system import kill_all_heartbeats

from django.utils import autoreload
from django.conf import settings



# Override django runserver reloader to kill heartbeats when restarting
#   or Ctrl-C'ed
def django_restart_with_reloader():
    """this must exactly match the contents of:
            django.utils.autoreload.restart_with_reloader
            without the first `while True:` at the top

        update this with every django update
        (or just fix it when it breaks, sorry future dev who reads this)
        (glitches in this code only affect the dev environment)
    """

    args = [sys.executable] + ['-W%s' % o for o in sys.warnoptions] + sys.argv
    new_environ = os.environ.copy()
    new_environ["RUN_MAIN"] = 'true'
    exit_code = subprocess.call(args, env=new_environ)
    if exit_code != 3:
        return exit_code
    return 0

def restart_with_reloader():
    """kill heartbeats whenever django gets reloaded"""

    t = settings.AUTOSTART_TABLEBEAT
    b = settings.AUTOSTART_BOTBEAT

    print(f'{ANSI["green"]}'
          '[+] Starting Django runserver with automatic '
          f'{"tablebeat" if t else ""}'
          f'{" and " if t or b else ""}'
          f'{"botbeat" if b else ""}'
          f'{" loading" if t or b else " loading turned off"}'
          f'{ANSI["reset"]}')

    def sigterm_handler(_signo, _stack_frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, sigterm_handler)
    try:
        while True:
            exit_code = django_restart_with_reloader()
            kill_all_heartbeats()
            if exit_code != 0:
                return exit_code

    finally:
        kill_all_heartbeats()



### Monkey Patches

if settings.DEBUG:
    # Monkey patch django's auto-reloader to our patched version with
    #   heartbeat reloading
    autoreload.restart_with_reloader = restart_with_reloader

if not settings.ENABLE_DRAMATIQ:
    # monkey patch dramatiq.actor to execute async actors synchronously
    # should only be used on dev machines, dramatiq is always enabled on prod
    import dramatiq

    original_actor_decorator = dramatiq.actor

    def forced_synchronous_actor(*args, **kwargs):
        async_actor = original_actor_decorator(*args, **kwargs)

        def execute_immediately(*args, **kwargs):
            return async_actor(*args, **kwargs)

        # normally .send() sends the message to the dramatiq queue, where it's
        # processed asynchronously, if dramatiq is disabled we just execute it
        # inline immediately instead
        async_actor.send = execute_immediately
        return async_actor

    dramatiq.actor = forced_synchronous_actor
