"""
Settings Usage:
    env SIGNUP_BONUS=1000000 ./manage.py runserver"
    OR
    export SIGNUP_BONUS=1000000
    ./manage.py runserver
Order of precedence for all settings:
    1. Environment variables
    2. env/dev.env  (or prod.env, beta.env, ci.env depending on ODDSLINGERS_ENV)
    3. settings.py defaults (this file)

https://github.com/monadical-sas/oddslingers.poker/wiki/Configuration
"""

import os
import sys
import getpass
import raven

from time import time


from oddslingers.system import (
    check_system_invariants,
    check_django_invariants,
    chown_django_folders,
    log_django_status_line,
    load_env_settings,
)


ODDSLINGERS_ENV = os.getenv('ODDSLINGERS_ENV', 'DEV').upper()
check_system_invariants(ODDSLINGERS_ENV)


################################################################################
### Environment Setup
################################################################################
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_DIR = os.path.dirname(BASE_DIR)

DJANGO_USER = getpass.getuser() or os.getlogin()
HOSTNAME = os.uname()[1]
PID = os.getpid()
START_TIME = time()
IS_TESTING = len(sys.argv) > 1 and sys.argv[1].lower() == "test"
IS_MIGRATING = len(sys.argv) > 1 and sys.argv[1].lower() == "migrate"
IS_SHELL = len(sys.argv) > 1 and sys.argv[1].lower() == 'shell_plus'
GIT_SHA = raven.fetch_git_sha(REPO_DIR).strip()
PY_TYPE = sys.implementation.name        # "cpython" or "pypy"
if hasattr(sys.stdout, 'isatty'):
    CLI_COLOR = sys.stdout.isatty()
else:
    CLI_COLOR = False
_PLACEHOLDER_FOR_UNSET = 'set-this-value-in-secrets.env'


################################################################################
### Core Django Settings
################################################################################
DEBUG = False
SERVE_STATIC = False
DEFAULT_HOST = 'oddslingers.com'
ALLOWED_HOSTS = [DEFAULT_HOST]
INTERNAL_IPS = ['127.0.0.1']
DEFAULT_HTTP_PROTOCOL = 'https'
SECRET_KEY = _PLACEHOLDER_FOR_UNSET
STATIC_URL = '/static/'
SITE_ID = 1
WSGI_APPLICATION = 'oddslingers.wsgi.application'

ENABLE_DEBUG_TOOLBAR = False
ENABLE_DEBUG_TOOLBAR_FOR_STAFF = True
SHELL_PLUS = 'ipython'
SHELL_PLUS_PRINT_SQL = False
IPYTHON_ARGUMENTS = ['--no-confirm-exit', '--no-banner']


################################################################################
### Remote Connection Settings
################################################################################

# Don't change values here, set via environment variable or secrets.env file
POSTGRES_HOST = '127.0.0.1'
POSTGRES_PORT = 5432
POSTGRES_DB = 'oddslingers'
POSTGRES_USER = 'oddslingers'
POSTGRES_PASSWORD = ''

REDIS_HOST = '127.0.0.1'
REDIS_PORT = 6379
REDIS_DB = 0

################################################################################
### Data Location Settings
################################################################################
ENV_DIR = os.path.join(REPO_DIR, 'env')
ENV_SETTINGS_FILE = os.path.join(ENV_DIR, f'{ODDSLINGERS_ENV.lower()}.env')
ENV_SECRETS_FILE = os.path.join(ENV_DIR, 'secrets.env')

DATA_DIR = os.path.abspath(os.path.join(REPO_DIR, 'data'))
STATIC_ROOT = os.path.join(DATA_DIR,'static')

################################################################################
### Process Spawning Settings
################################################################################
ENABLE_DRAMATIQ = not DEBUG
AUTOSTART_BOTBEAT = DEBUG
AUTOSTART_TABLEBEAT = True
ASYNC_TABLEBEAT_START = ENABLE_DRAMATIQ
ENABLE_SUPPORT_BOT = True


################################################################################
### Remote Reporting Settings
################################################################################
SEND_ZULIP_ALERTS = not DEBUG
ENABLE_PIWIK = not DEBUG
ENABLE_SENTRY = not DEBUG
STDOUT_IO_SUMMARY = DEBUG


################################################################################
### Security Settings
################################################################################
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'   # extended by oddslingers.models.UserSession
X_FRAME_OPTIONS = None                                          # old header made obsolete by CSP
SECURE_BROWSER_XSS_FILTER = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = False
SESSION_COOKIE_AGE = 1209600  # 2 weeks
LOGIN_URL = '/accounts/login/'
LOGOUT_REDIRECT_URL = '/'


################################################################################
### Account Validation Settings
################################################################################
EMAIL_VERIFICATION = True
ACCOUNT_AUTHENTICATION_METHOD = 'username_email'                # allow login via either username or email
ACCOUNT_CONFIRM_EMAIL_ON_GET = True
ACCOUNT_EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = '/accounts/email/'
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_DEFAULT_HTTP_PROTOCOL = DEFAULT_HTTP_PROTOCOL
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False
SIGNUP_EMAIL_ENTER_TWICE = False
ACCOUNT_USERNAME_MIN_LENGTH = 2
ACCOUNT_USERNAME_VALIDATORS = 'ui.views.accounts.username_validators'
PASSWORD_RESET_TIMEOUT_DAYS = 3


################################################################################
### 3rd-Party API Services Config
################################################################################
SENTRY_PROJECT_ID = _PLACEHOLDER_FOR_UNSET
SENTRY_DSN_KEY = _PLACEHOLDER_FOR_UNSET
SENTRY_DSN_SECRET = _PLACEHOLDER_FOR_UNSET


ZULIP_SERVER = 'https://zulip.monadical.com/api'
ZULIP_EMAIL = 'prod-events-bot@monadical.zulip.sweeting.me'
ZULIP_API_KEY = _PLACEHOLDER_FOR_UNSET

MAILGUN_API_KEY = _PLACEHOLDER_FOR_UNSET


################################################################################
### Internationalization & Formatting Settings
################################################################################
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = False
USE_L10N = True
USE_TZ = True
SHORT_DATE_FORMAT = 'Y/m/d'
SHORT_DATETIME_FORMAT = 'Y/m/d P'
USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','


################################################################################
### Email Settings
################################################################################
EMAIL_BACKEND = "anymail.backends.mailgun.EmailBackend"
SUPPORT_GIVERS = [
    # 'max+support@oddslingers.com',
    'admin@oddslingers.com',
    # 'ana+support@oddslingers.com',
]


################################################################################
### Heartbeat Settings
################################################################################
REDIS_BOTBEAT_KEY = 'botbeat'
REDIS_TABLEBEAT_KEY = 'tablebeat'
HEARTBEAT_POLL = 5                          # polling delay in seconds


################################################################################
### Game-Related Feature Flags & Poker Settings
################################################################################
SIGNUP_BONUS = 5000
VETERAN_BONUS = 5000
FIRST_TOURNEY_BONUS = 5000
FREE_CHIPS_BONUS = 1000
EMAIL_VERIFIED_BONUS = 3000

TABLES_PAGE_TIME_RANGE = 31                 # feature top games in the last n days
TABLES_PAGE_MINIMUM_TABLES = 24             # Used to keep a minimum number of tables for tables page
LEADERBOARD_PAGE_TIME_RANGE = 7             # feature top players in the last n days
LEADERBOARD_CACHE_PATH = 'leaderboard.json' # file containing old seasons leaderboards that dont change

CURRENT_SEASON = 1
ALLOW_SENDING_CHIPS_BY_EMAIL = True         # whether to allow users to send chips via email

POKER_AI_STUPID = False                     # stupid = low cpu, smart = high cpu
POKER_AI_INSTANT = False                    # True = AI's play at light speed
POKER_INVALID_ACTIONS_WARNINGS = True       # True = invalid/malformed actions are logged to sentry
POKER_REJECTED_ACTIONS_WARNINGS = False     # True = late/out-of-turn actions are logged to sentry
POKER_PAUSE_ON_EXCEPTION = True             # True = suspend gameplay whenever a heartbeat exception occurs
POKER_PAUSE_ON_REPORT_BUG = False           # True = suspend gameplay whenever a user reports a bug

SHOW_VIDEO_STREAMS = False                  # enable/disable video streaming site-wide
INLINE_STATICFILES = False                  # inline JS, and CSS files verbatim instead of inserting a <script> or <link> tag
ENABLE_HOTLOADING = False                   # enable InstantClick and dynamicLoadPage in hotloading.html, turns site into a "SPA"


# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Load Settings Overrides from Environment Config Files
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# settings defined above in this file (settings.py)
SETTINGS_DEFAULTS = load_env_settings(env=globals(), defaults=None)

# settings set via env/ODDSLINGERS_ENV.env
ENV_DEFAULTS = load_env_settings(dotenv_path=ENV_SETTINGS_FILE, defaults=globals())
globals().update(ENV_DEFAULTS)

# settings set via env/secrets.env
ENV_SECRETS = load_env_settings(dotenv_path=ENV_SECRETS_FILE, defaults=globals())
globals().update(ENV_SECRETS)

# settings set via environemtn variables
ENV_OVERRIDES = load_env_settings(env=dict(os.environ), defaults=globals())
globals().update(ENV_OVERRIDES)

SETTINGS_SOURCES = (
    ('settings.py', SETTINGS_DEFAULTS),
    (ENV_SETTINGS_FILE, ENV_DEFAULTS),
    (ENV_SECRETS_FILE, ENV_SECRETS),
    ('os.environ', ENV_OVERRIDES),
)

# print('Setting sources: \n{SETTINGS_SOURCES}')

# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
# Be careful moving things around below this point, settings depend on the above
# !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

# Some config should not be in git and can only be passed via secrets or os.env
SECURE_SETTINGS_SOURCES = (ENV_SECRETS_FILE, 'os.environ')
SECURE_SETTINGS = (
    'POSTGRES_PASSWORD',
    'SECRET_KEY',
    'MAILGUN_API_KEY',
    'ZULIP_API_KEY',
    'SENTRY_DSN_KEY',
)

################################################################################
### Path Settings
################################################################################
EMAIL_LIST_DIR = os.path.join(DATA_DIR, 'newsletters')
SUPPORT_TICKET_DIR = os.path.join(DATA_DIR, 'support_tickets')
GEOIP_DIR = os.path.join(DATA_DIR, 'geoip')
DEBUG_DUMP_DIR = os.path.join(DATA_DIR, 'debug_dumps')
CACHES_DIR = os.path.join(DATA_DIR, 'caches')

TEMPLATES_DIR = os.path.join(BASE_DIR, 'templates')
STATICFILES_DIR = os.path.join(BASE_DIR, 'static')
GEOIP_PATH = GEOIP_DIR

LOGS_DIR = os.path.join(DATA_DIR, 'logs')
RELOADS_LOGS = os.path.join(LOGS_DIR, 'reloads.log')
BOTBEAT_LOG = os.path.join(LOGS_DIR, 'botbeat.log')
TABLEBEAT_LOG = os.path.join(LOGS_DIR, 'heartbeat_{0}.log')
SOCKET_IO_LOG = os.path.join(LOGS_DIR, 'socket_io_{0}_{1}.log')
DJANGO_SHELL_LOG = os.path.join(LOGS_DIR, 'django_shell.log')

DATA_DIRS = [
    LOGS_DIR,
    EMAIL_LIST_DIR,
    GEOIP_DIR,
    SUPPORT_TICKET_DIR,
    DEBUG_DUMP_DIR,
    CACHES_DIR,
]

################################################################################
### Djano Core Setup
################################################################################
BASE_URL = f'{DEFAULT_HTTP_PROTOCOL}://{DEFAULT_HOST}'

AUTH_USER_MODEL = 'oddslingers.User'
ROOT_URLCONF = 'oddslingers.urls'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.sites',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    'django.contrib.sessions',

    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    # 'allauth.socialaccount.providers.facebook',
    # 'allauth.socialaccount.providers.google',
    # 'allauth.socialaccount.providers.twitter',
    # 'allauth.socialaccount.providers.twitch',
    # 'allauth.socialaccount.providers.coinbase',
    'hijack',
    'compat',

    'django_dramatiq',
    'django_extensions',
    'channels',
    'anymail',

    'oddslingers',
    'sockets',
    'ui',
    'poker',
    'banker',
    'rewards',
    'sidebets',
    'linky',
    'support',
    # Some more apps are added when DEBUG=True (see bottom of this file)
]
MIDDLEWARE = [
    'oddslingers.middleware.http2_middleware.HTTP2PushMiddleware',
    'oddslingers.middleware.x_forwarded_for.XForwardedForMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Some more classes are added when DEBUG=True (see bottom of this file)
]
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
]
AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
)
HIJACK_LOGIN_REDIRECT_URL = '/user/'  # Where admins are redirected to after hijacking a user
HIJACK_LOGOUT_REDIRECT_URL = '/user/'  # Where admins are redirected to after releasing a user
HIJACK_USE_BOOTSTRAP = True

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]
STATICFILES_DIRS = [STATICFILES_DIR]
DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'debug_toolbar.panels.profiling.ProfilingPanel',
    'template_timings_panel.panels.TemplateTimings.TemplateTimings',
]
DEBUG_TOOLBAR_CONFIG = {
    'JQUERY_URL': f'{STATIC_URL}js/jquery-2.2.0.min.js',
    'SHOW_TOOLBAR_CALLBACK': 'oddslingers.utils.debug_toolbar_callback',
}

# dont pollute main redis db with test data (will cause major issues if shared)
if IS_TESTING:
    REDIS_DB += 1

REDIS_CONF = {'host': REDIS_HOST, 'port': REDIS_PORT, 'db': REDIS_DB}
REDIS_SOCKET = f'redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'HOST': POSTGRES_HOST,
        'PORT': POSTGRES_PORT,
        'USER': POSTGRES_USER,
        'PASSWORD': POSTGRES_PASSWORD,
        'NAME': POSTGRES_DB,
    }
}
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': REDIS_SOCKET,
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'asgi_redis.RedisChannelLayer',
        'ROUTING': 'ui.urls.socket_routing',
        'CONFIG': {
            'hosts': [REDIS_SOCKET],
        },
    },
}
DRAMATIQ_TASKS_DATABASE = None  # set to 'default' to commit tasks to DB & redis
DRAMATIQ_BROKER = {
    "BROKER": "dramatiq.brokers.redis.RedisBroker",
    "OPTIONS": {
        "host": REDIS_HOST,
        "port": REDIS_PORT,
        "db": REDIS_DB,
    },
    "MIDDLEWARE": [
        # "dramatiq.middleware.Prometheus",
        "dramatiq.middleware.AgeLimit",
        "dramatiq.middleware.TimeLimit",
        "dramatiq.middleware.Retries",
        # "django_dramatiq.middleware.AdminMiddleware",
        "django_dramatiq.middleware.DbConnectionsMiddleware",
    ]
}

SENTRY_JS_URL = f'https://{SENTRY_DSN_KEY}@sentry.io/{SENTRY_PROJECT_ID}'
SENTRY_DSN_FULL = f'https://{SENTRY_DSN_KEY}:{SENTRY_DSN_SECRET}@sentry.io/{SENTRY_PROJECT_ID}'
RAVEN_CONFIG = {
    'dsn': SENTRY_DSN_FULL,
    'release': GIT_SHA,
    'environment': ODDSLINGERS_ENV,
}
PIWIK_SETUP = {
    'tracked_domain': '*.oddslingers.com',
    'base': 'https://nicksweeting.com/piwik/',
    'path': 'piwik.php',
    'site_id': '11',
}
ANYMAIL = {
    "MAILGUN_API_KEY": MAILGUN_API_KEY,
    "MAILGUN_SENDER_DOMAIN": DEFAULT_HOST,
}
DEFAULT_FROM_EMAIL = f'support@{DEFAULT_HOST}'
SERVER_EMAIL = f'server@{DEFAULT_HOST}'

if ENABLE_SENTRY:
    # uncomment to log 404 errors to sentry
    # MIDDLEWARE = [
    #     'raven.contrib.django.raven_compat.middleware.Sentry404CatchMiddleware',
    # ] + MIDDLEWARE

    INSTALLED_APPS = [
        'raven.contrib.django.raven_compat',
    ] + INSTALLED_APPS
else:
    RAVEN_CONFIG['dsn'] = None

if PY_TYPE == 'pypy':
    # Use psycopg2cffi instead of psycopg2 when run with pypy
    from psycopg2cffi import compat
    compat.register()

if IS_TESTING:
    ENABLE_DRAMATIQ = False

if ODDSLINGERS_ENV == 'CI':
    # Save Junit test timing summary for circleci pretty info display
    TEST_RUNNER = 'xmlrunner.extra.djangotestrunner.XMLTestRunner'
    TEST_OUTPUT_DIR = '/tmp/reports/testpy'
    TEST_OUTPUT_FILE_NAME = 'results.xml'

# ANSI Terminal escape sequences for printing colored log messages to terminal
FANCY_STDOUT = CLI_COLOR and DEBUG


if DEBUG:
    # pretty exceptions with context, see https://github.com/Qix-/better-exceptions
    # import better_exceptions  # noqa
    INSTALLED_APPS = [
        'django_pdb',
    ] + INSTALLED_APPS
    MIDDLEWARE = MIDDLEWARE + [
        'django_pdb.middleware.PdbMiddleware'
    ]
    AUTH_PASSWORD_VALIDATORS = []  # don't validate passwords on dev
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'


if ENABLE_DEBUG_TOOLBAR or ENABLE_DEBUG_TOOLBAR_FOR_STAFF:
    INSTALLED_APPS += [
        'debug_toolbar',
        'template_timings_panel',
    ]
    MIDDLEWARE += [
        'debug_toolbar.middleware.DebugToolbarMiddleware',
    ]


LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': ('%(asctime)-24s %(levelname)-8s %(module)s %(message)s')
        },
        'simple': {
            'format': '%(levelname)-8s %(message)s'
        },
        'django.server': {
            '()': 'django.utils.log.ServerFormatter',
            'format': '[%(server_time)s] %(message)s',
        },
        'none': {
            'format': '%(message)s'
        }
    },
    'handlers': {
        'django.server': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'django.server',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'none' if DEBUG else 'verbose',
        },
        'sentry': {
            'level': 'WARNING',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
            'tags': {'ODDSLINGERS_ENV': ODDSLINGERS_ENV, 'DEBUG': DEBUG},
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
        },
    },
    'loggers': {
        'django.server': {
            'handlers': ['django.server'],
            'level': 'INFO',
            'propagate': False,
        },
        'heartbeat': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
            'formatter': 'none',
        },
        'poker': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
            'formatter': 'none',
        },
        'robots': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
            'formatter': 'none',
        },
        'command': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
            'formatter': 'none',
        },
        'django': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
        },
        'sockets': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
        },
        'root': {
            'level': 'INFO',
            'handlers': ['sentry', 'console'] if ENABLE_SENTRY else ['console'],
            'propagate': True,
        },
        'raven': {
            'level': 'INFO',
            'handlers': ['sentry'] if ENABLE_SENTRY else [],
        },
    },
}

FEATURE_FLAGS = {
    'DEBUG': DEBUG,
    'ENABLE_PIWIK': ENABLE_PIWIK,
    'ENABLE_SENTRY': ENABLE_SENTRY,
    'SHOW_VIDEO_STREAMS': SHOW_VIDEO_STREAMS,
    'ENABLE_HOTLOADING': ENABLE_HOTLOADING,
    'ALLOW_SENDING_CHIPS_BY_EMAIL': ALLOW_SENDING_CHIPS_BY_EMAIL,
}

### Assertions about the environment
check_django_invariants()
chown_django_folders()
STATUS_LINE = log_django_status_line()


########################
# UNCOMMENT TO TRACK DOWN PESKY print() STATEMENTS

# import sys
# import traceback

# class TracePrints(object):
#   def __init__(self):
#     self.stdout = sys.stdout
#   def write(self, s):
#     self.stdout.write("Writing %r\n" % s)
#     traceback.print_stack(file=self.stdout)

# sys.stdout = TracePrints()
