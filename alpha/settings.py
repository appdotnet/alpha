import os
import django
import socket
import time
import sys

import dj_database_url

DJANGO_ROOT = os.path.dirname(os.path.realpath(django.__file__))
SITE_ROOT = os.path.dirname(os.path.realpath(__file__))
STATIC_DOC_ROOT = os.path.join(SITE_ROOT, 'static')
ENVIRONMENT = 'dev'

gettext = lambda s: s

DEBUG = True
TEMPLATE_DEBUG = DEBUG

SERVER_HOSTNAME = socket.getfqdn()

# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'tapp_dev',
#         'USER': 'tapp_dev',
#         'PASSWORD': 'AnXsjB39pYjlJfVa',
#         'HOST': 'defjam.int.sfo01.mml',
#         'PORT': 3306,
#     }
# }

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'stream': sys.stdout
        },
    },
    'alpha': {
        'handlers': ['console', ],
        'level': 'INFO'
    },
    'django': {
        'handlers': ['console', ],
        'level': 'INFO'
    },
}

database_url = os.environ.get('DATABASE_URL')
DATABASES = {'default': dj_database_url.parse(database_url or 'sqlite:////tmp/devdb')}

AUTH_USER_MODEL = 'pau.User'

# Local time zone for this installation. Choices can be found here:
# http://en.wikipedia.org/wiki/List_of_tz_zones_by_name
# although not all choices may be available on all operating systems.
# On Unix systems, a value of None will cause Django to use the same
# timezone as the operating system.
# If running in a Windows environment this must be set to the same as your
# system time zone.
TIME_ZONE = 'UTC'

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-us'

SITE_ID = 1

# If you set this to False, Django will make some optimizations so as not
# to load the internationalization machinery.
USE_I18N = True

# If you set this to False, Django will not format dates, numbers and
# calendars according to the current locale
USE_L10N = True

# Absolute path to the directory that holds media.
# Example: "/home/media/media.lawrence.com/"
MEDIA_ROOT = ''

# URL that handles the media served from MEDIA_ROOT. Make sure to use a
# trailing slash if there is a path component (optional in other cases).
# Examples: "http://media.lawrence.com", "http://example.com/media/"
MEDIA_URL = ''

# URL prefix for admin media -- CSS, JavaScript and images. Make sure to use a
# trailing slash.
# Examples: "http://foo.com/media/", "/media/".
STATIC_URL = '/static/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = os.environ.get('SECRET_KEY', '')

ROOT_URLCONF = 'alpha.urls'

# This is used when running tests it looks like (even though it's not in the django settings docs any more)
TEMP_DIR = '/var/tmp'

JINJA2_TEMPLATE_PACKAGES = (
    'pau',
)

JINJA2_TEMPLATE_DIRS = (
    os.path.join(SITE_ROOT, 'templates-jinja2'),
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.contrib.messages.context_processors.messages',
    'paucore.web.context_processors.default_jscontext',
    'pau.context_processors.url_for',
    'social.apps.django_app.context_processors.backends',
    'social.apps.django_app.context_processors.login_redirect',
)

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    'django.contrib.humanize',
    'social.apps.django_app.default',
    'django.contrib.admin',
    'pau',
)

INTERNAL_IPS = (
    '127.0.0.1',
)

UNIT_TESTING = False

JINJA2_TEMPLATE_LOADER = 'paucore.web.jinja2_django.Loader'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    JINJA2_TEMPLATE_LOADER,
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

MIDDLEWARE_CLASSES = (
    # local mml warning:
    # when adding middleware classes, make sure they do not
    # need to be wrapped in an state exemption class
    'paucore.web.middleware.NoCacheMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.http.ConditionalGetMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'pau.middleware.AlphaAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'social.apps.django_app.middleware.SocialAuthExceptionMiddleware',
)

PASSWORD_HASHERS = (
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
)

AUTHENTICATION_BACKENDS = (
    'paucore.web.auth_backend.MXMLAppDotNetOAuth2',
    'django.contrib.auth.backends.ModelBackend',
)

BUILD_INFO = 'tapp-dev-%d' % int(time.time())

# Pau settings
SESSION_COOKIE_NAME = 'mt_pau_sessionid'
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# when unauthenticated users access the alpha app what app token should be used
# API settings for alpha, we set this separately for smoketests, if this changes, update in settings_smoketest

SSL_ONLY = False

ALPHA_API_ROOT = os.environ.get('ALPHA_API_ROOT', 'https://api.app.net')
PUBLIC_API_ROOT = os.environ.get('PUBLIC_API_ROOT', 'https://api.app.net')
SOCIAL_AUTH_APPDOTNET_OAUTH_BASE = os.environ.get('SOCIAL_AUTH_APPDOTNET_OAUTH_BASE', 'https://account.app.net')
SOCIAL_AUTH_APPDOTNET_KEY = os.environ.get('SOCIAL_AUTH_APPDOTNET_KEY')
SOCIAL_AUTH_APPDOTNET_SECRET = os.environ.get('SOCIAL_AUTH_APPDOTNET_SECRET')
PARENT_HOST = os.environ.get('PARENT_HOST', 'app.net')

# When users aren't authroized this app token is the fallback token used for API calls
APP_TOKEN = os.environ.get('APP_TOKEN')

try:
    from alpha.local_settings import *
except ImportError:
    pass

if not all([SOCIAL_AUTH_APPDOTNET_KEY, SOCIAL_AUTH_APPDOTNET_SECRET, APP_TOKEN]):
    raise Exception("You must set SOCIAL_AUTH_APPDOTNET_KEY, SOCIAL_AUTH_APPDOTNET_SECRET, and APP_TOKEN in settings.py before you run alpha")

SOCIAL_AUTH_APPDOTNET_SCOPE = ['stream', 'follow', 'write_post']
LOGIN_REDIRECT_URL = 'home'
LOGIN_URL = 'login'
LOGOUT_URL = 'logout'
