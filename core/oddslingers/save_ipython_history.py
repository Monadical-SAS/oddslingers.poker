import os

from IPython import get_ipython
from django.conf import settings

if settings.IS_SHELL:
    pretty_path = settings.DJANGO_SHELL_LOG.rsplit("oddslingers/", 1)[-1]

    ipython = get_ipython()
    ipython.magic(f'%logstart -q -o -t {settings.DJANGO_SHELL_LOG} append')

    default_conn = f'Logged in user: {settings.DJANGO_USER} (working locally on {settings.HOSTNAME})'

    ssh_info = os.environ.get('SSH_CONNECTION', default_conn)
    conn_str = os.environ.get('CONNECTION_STR', ssh_info)
    print(f'[i] {conn_str}. Activity is logged to {pretty_path}')
