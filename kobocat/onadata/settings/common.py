# vim: set fileencoding=utf-8
# this system uses structured settings as defined in
# http://www.slideshare.net/jacobian/the-best-and-worst-of-django
#
# this is the base settings.py -- which contains settings common to all
# implementations of ona: edit it at last resort
#
# local customizations should be done in several files each of which in turn
# imports this one.
# The local files should be used as the value for your DJANGO_SETTINGS_FILE
# environment variable as needed.
from __future__ import print_function
import logging
import multiprocessing
import os
import subprocess  # nopep8, used by included files
import sys  # nopep8, used by included files

from celery.signals import after_setup_logger
from django.core.exceptions import SuspiciousOperation
from django.utils.log import AdminEmailHandler
import djcelery
from pymongo import MongoClient

djcelery.setup_loader()

KOBO_SERVER = os.environ.get('KOBO_SERVER_HOST')
WEB_SERVER = os.environ.get('KOBO_SERVER_HOST')
FORM_RENDERER_SERVER = os.environ.get('KOBO_RENDERER_HOST')
WEB_SERVER = os.environ.get('KOBO_SERVER_HOST')
KOBO_MODULE_URL = os.environ.get('KOBO_SERVER_HOST')
DEBUG = os.environ.get('DJANGO_DEBUG') == 'True'



####################
CURRENT_FILE = os.path.abspath(__file__)
PROJECT_ROOT = os.path.realpath(
    os.path.join(os.path.dirname(CURRENT_FILE), '..//'))

#print("project root")

#print(PROJECT_ROOT)
############################
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
ONADATA_DIR = BASE_DIR
#PROJECT_ROOT= os.path.abspath(os.path.join(ONADATA_DIR, '..'))

PRINT_EXCEPTION = False

TEMPLATED_EMAIL_TEMPLATE_DIR = 'templated_email/'

ADMINS = (
    # ('Your Name', 'your_email@example.com'),
)
MANAGERS = ADMINS


DEFAULT_FROM_EMAIL = 'noreply@ona.io'
SHARE_PROJECT_SUBJECT = '{} Ona Project has been shared with you.'
DEFAULT_SESSION_EXPIRY_TIME = 21600  # 6 hours

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'America/New_York'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

ugettext = lambda s: s

SITE_ID = os.environ.get('DJANGO_SITE_ID', '1')

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = False

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash.
# Examples: "http://media.lawrence.com/media/", "http://example.com/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')
MEDIA_URL = '/media/'

# Absolute path to the directory static files should be collected to.
# Don't put anything in this directory yourself; store your static files
# in apps' "static/" subdirectories and in STATICFILES_DIRS.
# Example: "/home/media/media.lawrence.com/static/"
#STATIC_ROOT = os.path.join(ONADATA_DIR, 'static')
STATIC_ROOT = os.path.join(PROJECT_ROOT, 'static')

# URL prefix for static files.
# Example: "http://media.lawrence.com/static/"
STATIC_URL = '/static/'

# Enketo URL.
# Configurable settings.
ENKETO_URL = os.environ.get('ENKETO_URL', 'https://enketo.kobotoolbox.org')
KOBOCAT_URL = os.environ.get('KOBOCAT_URL', 'https://kc.kobotoolbox.org')


ENKETO_URL= ENKETO_URL.rstrip('/')
ENKETO_API_TOKEN = os.environ.get('ENKETO_API_TOKEN', 'enketorules')
ENKETO_VERSION= os.environ.get('ENKETO_VERSION', 'Legacy').lower()
assert ENKETO_VERSION in ['legacy', 'express']
# Constants.
ENKETO_API_ENDPOINT_ONLINE_SURVEYS = '/survey'
ENKETO_API_ENDPOINT_OFFLINE_SURVEYS = '/survey/offline'
ENKETO_API_ENDPOINT_INSTANCE= '/instance'
ENKETO_API_ENDPOINT_INSTANCE_IFRAME= '/instance/iframe'
# Computed settings.
if ENKETO_VERSION == 'express':
    ENKETO_API_ROOT= '/api/v2'
    ENKETO_OFFLINE_SURVEYS= os.environ.get('ENKETO_OFFLINE_SURVEYS', 'True').lower() == 'true'
    ENKETO_API_ENDPOINT_PREVIEW= '/preview'
    ENKETO_API_ENDPOINT_SURVEYS= ENKETO_API_ENDPOINT_OFFLINE_SURVEYS if ENKETO_OFFLINE_SURVEYS \
            else ENKETO_API_ENDPOINT_ONLINE_SURVEYS
else:
    ENKETO_API_ROOT= '/api_v1'
    ENKETO_API_ENDPOINT_PREVIEW= '/webform/preview'
    ENKETO_OFFLINE_SURVEYS= False
    ENKETO_API_ENDPOINT_SURVEYS= ENKETO_API_ENDPOINT_ONLINE_SURVEYS
ENKETO_API_SURVEY_PATH = ENKETO_API_ROOT + ENKETO_API_ENDPOINT_SURVEYS
ENKETO_API_INSTANCE_PATH = ENKETO_API_ROOT + ENKETO_API_ENDPOINT_INSTANCE
ENKETO_PREVIEW_URL = ENKETO_URL + ENKETO_API_ENDPOINT_PREVIEW
ENKETO_API_INSTANCE_IFRAME_URL = ENKETO_URL + ENKETO_API_ROOT + ENKETO_API_ENDPOINT_INSTANCE_IFRAME

KPI_URL = os.environ.get('KPI_URL', False)

# specifically for site urls sent to enketo for form retrieval
# `ENKETO_PROTOCOL` variable is overridden when internal domain name is used.
# All internal communications between containers must be HTTP only.
ENKETO_PROTOCOL = os.environ.get('ENKETO_PROTOCOL', 'https')

# These 2 variables are needed to detect whether the ENKETO_PROTOCOL should overwritten or not.
# See method `_get_form_url` in `onadata/libs/utils/viewer_tools.py`
KOBOCAT_INTERNAL_HOSTNAME = "{}.{}".format(
    os.environ.get("KOBOCAT_PUBLIC_SUBDOMAIN", "kc"),
    os.environ.get("INTERNAL_DOMAIN_NAME", "docker.internal"))
KOBOCAT_PUBLIC_HOSTNAME = "{}.{}".format(
    os.environ.get("KOBOCAT_PUBLIC_SUBDOMAIN", "kc"),
    os.environ.get("PUBLIC_DOMAIN_NAME", "kobotoolbox.org"))

# Default value for the `UserProfile.require_auth` attribute. Even though it's
# set in kc_environ, include it here as well to support legacy installations
REQUIRE_AUTHENTICATION_TO_SEE_FORMS_AND_SUBMIT_DATA_DEFAULT = False

# Login URLs
#LOGIN_URL = '/accounts/login/'
#LOGIN_REDIRECT_URL = '/login_redirect/'
LOGIN_URL = '/usermodule/login/'
LOGIN_REDIRECT_URL = '/usermodule/login/'
# set project related table prefix
PROJECT_KEY_NAME = 'bahis'
FORM_TABLE_SCHEMA = 'core'
# Set it True if there exist branch under organization, otherwise set False
IS_EXIST_BRANCH = True

# URL prefix for admin static files -- CSS, JavaScript and images.
# Make sure to use a trailing slash.
# Examples: "http://foo.com/static/admin/", "/static/admin/".
ADMIN_MEDIA_PREFIX = '/static/admin/'

# Additional locations of static files
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    # 'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)
TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.static',
    'django.core.context_processors.tz',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'readonly.context_processors.readonly',
    'onadata.apps.main.context_processors.google_analytics',
    'onadata.apps.main.context_processors.site_name',
    'onadata.apps.main.context_processors.base_url',
    'onadata.apps.usermodule.context_processors.additional_menu_items',
    'onadata.apps.usermodule.context_processors.can_configure',
    'onadata.apps.usermodule.context_processors.is_admin',
    'onadata.apps.usermodule.context_processors.care_viewer',
)

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    # 'django.template.loaders.eggs.Loader',
)

MIDDLEWARE_CLASSES = (
    "debug_toolbar.middleware.DebugToolbarMiddleware",
    'reversion.middleware.RevisionMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'onadata.libs.utils.middleware.LocaleMiddlewareWithTweaks',
    # BrokenClientMiddleware must come before AuthenticationMiddleware
    'onadata.libs.utils.middleware.BrokenClientMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # Django 1.8 removes TransactionMiddleware (was deprecated in 1.6). See:
    # https://docs.djangoproject.com/en/1.6/topics/db/transactions/#transaction-middleware
    #'django.middleware.transaction.TransactionMiddleware',
    'onadata.libs.utils.middleware.HTTPResponseNotAllowedMiddleware',
    'readonly.middleware.DatabaseReadOnlyMiddleware',
)
LOCALE_PATHS = (os.path.join(PROJECT_ROOT, 'onadata.apps.main', 'locale'), )


ROOT_URLCONF = 'onadata.apps.main.urls'
USE_TZ = True

TEMPLATE_DIRS = (
    os.path.join(PROJECT_ROOT, 'libs/templates'),
    # Put strings here, like "/home/html/django_templates"
    # or "C:/www/django/templates".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# needed by guardian
ANONYMOUS_USER_ID = -1

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'django.contrib.admin',
    'django.contrib.admindocs',
    'django.contrib.gis',
    'registration',
    'reversion',
    'django_nose',
    'django_digest',
    'debug_toolbar',
    'corsheaders',
    'oauth2_provider',
    'rest_framework',
    'rest_framework.authtoken',
    'taggit',
    'readonly',
    'onadata.apps.logger',
    'onadata.apps.viewer',
    'onadata.apps.main',
    'onadata.apps.restservice',
    'onadata.apps.api',
    'guardian',
    'djcelery',
    'onadata.apps.stats',
    'onadata.apps.sms_support',
    'onadata.libs',
    'onadata.apps.survey_report',
    'onadata.apps.export',
    'pure_pagination',
    'onadata.apps.usermodule',
    'django_unused',
    'onadata.apps.bh_module',
'onadata.apps.formmodule',
'onadata.apps.reportsmodule',
)

MONGO_DATABASE = {
    'HOST': os.environ.get('MONGO_DB_HOST'),
    'PORT': 27017,
    'NAME': os.environ.get('MONGO_DB_NAME'),
    'USER': os.environ.get('MONGO_DB_USER'),
    'PASSWORD': os.environ.get('MONGO_DB_PASSWORD')
}



DATABASES = {
    'default' : {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'OPTIONS': {
            'options': '-c search_path=public,instance,core,custom'
        },
        'NAME': os.environ.get('KOBO_PSQL_DB_NAME'),
        'USER': os.environ.get('KOBO_PSQL_DB_USER'),
        'PASSWORD': os.environ.get('KOBO_PSQL_DB_PASS'),
        'HOST': os.environ.get('KOBO_PSQL_DB_HOST'),
        'PORT': '5432',
    }
}

OAUTH2_PROVIDER = {
    # this is the list of available scopes
    'SCOPES': {
        'read': 'Read scope',
        'write': 'Write scope',
        'groups': 'Access to your groups'}
}

REST_FRAMEWORK = {
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    'DEFAULT_MODEL_SERIALIZER_CLASS':
    'rest_framework.serializers.HyperlinkedModelSerializer',

    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.AllowAny',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'onadata.libs.authentication.DigestAuthentication',
        'oauth2_provider.ext.rest_framework.OAuth2Authentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.TokenAuthentication',
        'onadata.libs.authentication.HttpsOnlyBasicAuthentication',
    ),
    'DEFAULT_RENDERER_CLASSES': (
        # Keep JSONRenderer at the top "in order to send JSON responses to
        # clients that do not specify an Accept header." See
        # http://www.django-rest-framework.org/api-guide/renderers/#ordering-of-renderer-classes
        'rest_framework.renderers.JSONRenderer',
        'rest_framework_jsonp.renderers.JSONPRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
        'rest_framework_xml.renderers.XMLRenderer',
        'rest_framework_csv.renderers.CSVRenderer',
    ),
    'VIEW_NAME_FUNCTION': 'onadata.apps.api.tools.get_view_name',
    'VIEW_DESCRIPTION_FUNCTION': 'onadata.apps.api.tools.get_view_description',
}

SWAGGER_SETTINGS = {
    "exclude_namespaces": [],    # List URL namespaces to ignore
    "api_version": '1.0',  # Specify your API's version (optional)
    "enabled_methods": [         # Methods to enable in UI
        'get',
        'post',
        'put',
        'patch',
        'delete'
    ],
}

CORS_ORIGIN_ALLOW_ALL = True
CORS_ALLOW_CREDENTIALS = True
CORS_ORIGIN_WHITELIST = (
    'dev.ona.io',
)

USE_THOUSAND_SEPARATOR = True

COMPRESS = True

# extra data stored with users
AUTH_PROFILE_MODULE = 'onadata.apps.main.UserProfile'

# case insensitive usernames -- DISABLED for KoBoForm compatibility
AUTHENTICATION_BACKENDS = (
    #'onadata.apps.main.backends.ModelBackend',
    'django.contrib.auth.backends.ModelBackend',
    'guardian.backends.ObjectPermissionBackend',
)

# All registration should be done through KPI, so Django Registration should
# never be enabled here. It'd be best to remove all references to the
# `registration` app in the future.
REGISTRATION_OPEN = False
ACCOUNT_ACTIVATION_DAYS = 1

# MongoDB
if MONGO_DATABASE.get('USER') and MONGO_DATABASE.get('PASSWORD'):
    MONGO_CONNECTION_URL = (
        "mongodb://%(USER)s:%(PASSWORD)s@%(HOST)s:%(PORT)s") % MONGO_DATABASE
else:
    MONGO_CONNECTION_URL = "mongodb://%(HOST)s:%(PORT)s" % MONGO_DATABASE

print("== === == ===== === = ===== = = == =  === ")
print("== === == ===== === = ===== = = == =  === ")
print("== === == ===== === = ===== = = == =  === ")
print("Connecting to MONGO BONGO")
print("== === == ===== === = ===== = = == =  === ")
print("== === == ===== === = ===== = = == =  === ")
print(MONGO_CONNECTION_URL)
print("== === == ===== === = ===== = = == =  === ")
print("== === == ===== === = ===== = = == =  === ")

MONGO_CONNECTION = MongoClient(
    MONGO_CONNECTION_URL, safe=True, j=True, tz_aware=True)
MONGO_DB = MONGO_CONNECTION[MONGO_DATABASE['NAME']]


def skip_suspicious_operations(record):
    """Prevent django from sending 500 error
    email notifications for SuspiciousOperation
    events, since they are not true server errors,
    especially when related to the ALLOWED_HOSTS
    configuration

    background and more information:
    http://www.tiwoc.de/blog/2013/03/django-prevent-email-notification-on-susp\
    iciousoperation/
    """
    if record.exc_info:
        exc_value = record.exc_info[1]
        if isinstance(exc_value, SuspiciousOperation):
            return False
    return True

# A sample logging configuration. The only tangible logging
# performed by this configuration is to send an email to
# the site admins on every HTTP 500 error.
# See http://docs.djangoproject.com/en/dev/topics/logging for
# more details on how to customize your logging configuration.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s' +
                      ' %(process)d %(thread)d %(message)s'
        },
        'simple': {
            'format': '%(levelname)s %(message)s'
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        },
        # Define filter for suspicious urls
        'skip_suspicious_operations': {
            '()': 'django.utils.log.CallbackFilter',
            'callback': skip_suspicious_operations,
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false', 'skip_suspicious_operations'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
            'stream': sys.stdout
        },
        'audit': {
            'level': 'DEBUG',
            'class': 'onadata.libs.utils.log.AuditLogHandler',
            'formatter': 'verbose',
            'model': 'onadata.apps.main.models.audit.AuditLog'
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins', 'console'],
            'level': 'DEBUG',
            'propagate': True,
        },
        'console_logger': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True
        },
        'audit_logger': {
            'handlers': ['audit'],
            'level': 'DEBUG',
            'propagate': True
        }
    }
}


def configure_logging(logger, **kwargs):
    admin_email_handler = AdminEmailHandler()
    admin_email_handler.setLevel(logging.ERROR)
    logger.addHandler(admin_email_handler)

after_setup_logger.connect(configure_logging)

GOOGLE_STEP2_URI = 'http://ona.io/gwelcome'
GOOGLE_CLIENT_ID = '617113120802.onadata.apps.googleusercontent.com'
GOOGLE_CLIENT_SECRET = '9reM29qpGFPyI8TBuB54Z4fk'

THUMB_CONF = {
    'large': {'size': 1280, 'suffix': '-large'},
    'medium': {'size': 640, 'suffix': '-medium'},
    'small': {'size': 240, 'suffix': '-small'},
}
# order of thumbnails from largest to smallest
THUMB_ORDER = ['large', 'medium', 'small']
IMG_FILE_TYPE = 'jpg'

# celery
BROKER_BACKEND = "librabbitmq"
BROKER_URL = 'amqp://guest:guest@rabbitmq:5672/'
CELERY_RESULT_BACKEND = "amqp"  # telling Celery to report results to RabbitMQ
CELERY_ALWAYS_EAGER = False

# Celery defaults to having as many workers as there are cores. To avoid
# excessive resource consumption, don't spawn more than 6 workers by default
# even if there more than 6 cores.
CELERYD_MAX_CONCURRENCY = int(os.environ.get('CELERYD_MAX_CONCURRENCY', 6))
if multiprocessing.cpu_count() > CELERYD_MAX_CONCURRENCY:
    CELERYD_CONCURRENCY = CELERYD_MAX_CONCURRENCY

# Replace a worker after it completes 7 tasks by default. This allows the OS to
# reclaim memory allocated during large tasks
CELERYD_MAX_TASKS_PER_CHILD = int(os.environ.get(
    'CELERYD_MAX_TASKS_PER_CHILD', 7))

# Default to a 30-minute soft time limit and a 35-minute hard time limit
CELERYD_TASK_TIME_LIMIT = int(os.environ.get('CELERYD_TASK_TIME_LIMIT', 2100))
CELERYD_TASK_SOFT_TIME_LIMIT = int(os.environ.get(
    'CELERYD_TASK_SOFT_TIME_LIMIT', 1800))

# duration to keep zip exports before deletion (in seconds)
ZIP_EXPORT_COUNTDOWN = 24 * 60 * 60

# default content length for submission requests
DEFAULT_CONTENT_LENGTH = 10000000

TEST_RUNNER = 'django_nose.NoseTestSuiteRunner'
NOSE_ARGS = ['--with-fixture-bundling']

# fake endpoints for testing
TEST_HTTP_HOST = 'testserver.com'
TEST_USERNAME = 'bob'

# re-captcha in registrations
REGISTRATION_REQUIRE_CAPTCHA = False
RECAPTCHA_USE_SSL = False
RECAPTCHA_PRIVATE_KEY = ''
RECAPTCHA_PUBLIC_KEY = '6Ld52OMSAAAAAJJ4W-0TFDTgbznnWWFf0XuOSaB6'

# specify the root folder which may contain a templates folder and a static
# folder used to override templates for site specific details
TEMPLATE_OVERRIDE_ROOT_DIR = None

# Use 1 or 0 for multiple selects instead of True or False for csv, xls exports
BINARY_SELECT_MULTIPLES = False

# Use 'n/a' for empty values by default on csv exports
NA_REP = 'n/a'

# Set wsgi url scheme to HTTPS
os.environ['wsgi.url_scheme'] = 'https'

SUPPORTED_MEDIA_UPLOAD_TYPES = [
    'image/jpeg',
    'image/png',
    'image/svg+xml',
    'audio/mpeg',
    'video/3gpp',
    'audio/wav',
    'audio/x-m4a',
    'audio/mp3',
    'text/csv',
    'application/zip'
]

# legacy setting for old sites who still use a local_settings.py file and have
# not updated to presets/
try:
    from local_settings import *  # nopep8
except ImportError:
    pass

if isinstance(TEMPLATE_OVERRIDE_ROOT_DIR, basestring):
    # site templates overrides
    TEMPLATE_DIRS = (
        os.path.join(ONADATA_DIR, TEMPLATE_OVERRIDE_ROOT_DIR, 'templates'),
    ) + TEMPLATE_DIRS
    # site static files path
    STATICFILES_DIRS += (
        os.path.join(ONADATA_DIR, TEMPLATE_OVERRIDE_ROOT_DIR, 'static'),
    )

# Transition from South to native migrations
try:
    from django.db import migrations
except ImportError:
    # Native migrations unavailable; use South instead
    INSTALLED_APPS += ('south',)

SOUTH_MIGRATION_MODULES = {
    'taggit': 'taggit.south_migrations',
    'reversion': 'reversion.south_migrations',
    'onadata.apps.restservice': 'onadata.apps.restservice.south_migrations',
    'onadata.apps.api': 'onadata.apps.api.south_migrations',
    'onadata.apps.main': 'onadata.apps.main.south_migrations',
    'onadata.apps.stats': 'onadata.apps.stats.south_migrations',
    'onadata.apps.logger': 'onadata.apps.logger.south_migrations',
    'onadata.apps.viewer': 'onadata.apps.viewer.south_migrations',
}

DEFAULT_VALIDATION_STATUSES = [
    {
        'uid': 'validation_status_not_approved',
        'color': '#ff0000',
        'label': 'Not Approved'
    },
    {
        'uid': 'validation_status_approved',
        'color': '#00ff00',
        'label': 'Approved'
    },
    {
        'uid': 'validation_status_on_hold',
        'color': '#0000ff',
        'label': 'On Hold'
    },
]

ALLOWED_HOSTS = '*'

SYSTEM_TABLE = ['geo_cluster']

if DEBUG:
    # requried for django debug toolbar inside dockers
    import socket  # only if you haven't already imported this
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS = [ip[: ip.rfind(".")] + ".1" for ip in ips] + ["127.0.0.1", "10.0.2.2"]
    print(INTERNAL_IPS)

    DEBUG_TOOLBAR_PANELS = [
        # 'debug_toolbar.panels.versions.VersionsPanel',
        # 'debug_toolbar.panels.timer.TimerPanel',
        # 'debug_toolbar.panels.settings.SettingsPanel',
        # 'debug_toolbar.panels.headers.HeadersPanel',
        # 'debug_toolbar.panels.request.RequestPanel',
        'debug_toolbar.panels.sql.SQLPanel',
        # 'debug_toolbar.panels.staticfiles.StaticFilesPanel',
        # 'debug_toolbar.panels.templates.TemplatesPanel',
        # 'debug_toolbar.panels.cache.CachePanel',
        # 'debug_toolbar.panels.signals.SignalsPanel',
        # 'debug_toolbar.panels.logging.LoggingPanel',
        # 'debug_toolbar.panels.redirects.RedirectsPanel',
    ]

    DEBUG_TOOLBAR_CONFIG = {
        # Panel options
        'SQL_WARNING_THRESHOLD': 100,   # milliseconds
    }
