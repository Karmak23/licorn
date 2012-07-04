# -*- coding: utf-8 -*-
# Django settings for Licorn® WMI project.

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = (
    ('Licorn© Administrator', 'licorn@licorn.org'),
)

MANAGERS = ADMINS

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3', # Add 'postgresql_psycopg2', 'postgresql', 'mysql', 'sqlite3' or 'oracle'.
        'NAME': '/var/cache/licorn/wmi/wmi.db',                      # Or path to database file if using sqlite3.
        'USER': '',                      # Not used with sqlite3.
        'PASSWORD': '',                  # Not used with sqlite3.
        'HOST': '',                      # Set to empty string for localhost. Not used with sqlite3.
        'PORT': '',                      # Set to empty string for default. Not used with sqlite3.
    }
}

# None > same as operating system, on Unix
TIME_ZONE = None

# Language code for this installation. All choices can be found here:
# http://www.i18nguy.com/unicode/language-identifiers.html
LANGUAGE_CODE = 'en-US'

LANGUAGES = (
    ('en', 'English'),
    ('fr', 'Français'),
)

SITE_ID = 1
USE_I18N = True
USE_L10N = True

# see http://www.muhuk.com/2009/05/serving-static-media-in-django-development-server/
MEDIA_ROOT = '/usr/share/licorn/wmi/media/'
MEDIA_URL = '/media/'

LOGIN_URL = '/login/'
#LOGIN_REDIRECT_URL = '/ident_success/'

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'wj*3@)tfey8&huca0g&=s96*ky_#-&9$9u+!pi5)505jvlts0#'

TEMPLATE_LOADERS = (
    'djinja.template.loaders.Loader',
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS =(
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
)

MIDDLEWARE_CLASSES = (
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
)

ROOT_URLCONF = 'wmi.urls'

TEMPLATE_DIRS = (
    '/usr/share/licorn/wmi/templates',
    'templates',
)

AUTHENTICATION_BACKENDS = (
    'wmi.libs.licornd_auth.LicorndAuthBackend',
    #'django.contrib.auth.backends.ModelBackend',
    )

INSTALLED_APPS = (
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.sites',
    'django.contrib.messages',
    # this 'wmi' is a hack to support a global `djangojs` translation mechanism.
    # see http://stackoverflow.com/q/1963517
    'wmi',
    # end hack
    'wmi.system',
    'wmi.users',
    'wmi.groups',
    # NOTE: the following apps will be dynamically imported,
    # based on various licorn settings and conditions. Do not
    # activate them here.
    #'wmi.machines',
    #'wmi.backup',
    #'wmi.shares',
)

JINJA2_GLOBALS = {
    'dynsidebars'       : 'wmi.libs.utils.dynsidebars',
    'dynstatuses'       : 'wmi.libs.utils.dynstatuses',
    'dyninfos'          : 'wmi.libs.utils.dyninfos',
    'dyndata_merge'     : 'wmi.libs.utils.dyndata_merge',
    'now'               : 'wmi.libs.utils.now',
    'config'            : 'wmi.libs.utils.config',
    'djsettings'        : 'wmi.libs.utils.djsettings',
    'licorn_setting'    : 'wmi.libs.utils.licorn_setting',
    'get_lmc'           : 'wmi.libs.utils.get_lmc',
    'server_address'    : 'wmi.libs.utils.server_address',
    'version_html'      : 'wmi.libs.utils.version_html',
    'url_for'           : 'django.core.urlresolvers.reverse',
    'unique_hash'       : 'licorn.foundations.pyutils.unique_hash',
    'bytes_to_human'    : 'licorn.foundations.pyutils.bytes_to_human',
    'format_time_delta' : 'licorn.foundations.pyutils.format_time_delta',
    'time'              : 'time.time',
}

JINJA2_FILTERS = (
#    'libs.meta_it.noaccents',
#    'libs.meta_it.model_reload',
#    'libs.meta_it.Decimal',
#    'libs.meta_it.htmlEncode',
#    'libs.meta_it.htmlDecode',
#    'libs.meta_it.urlencode',
#    'libs.meta_it.url_noencode',
#    'libs.meta_it.url',
#    'libs.meta_it.get_lang',
#    'libs.meta_it.timesince',
#    'libs.meta_it.timeuntil',
#    'libs.meta_it.truncate',
)

JINJA2_EXTENSIONS = (
    'jinja2.ext.i18n',
    'jinja2.ext.do',
    'jinja2.ext.loopcontrols',
    'jinja2.ext.with_',
)

INTERNAL_IPS = ('127.0.0.1', )

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {
            'format': '%(asctime)s %(levelname)s %(message)s'
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'formatter': 'simple',
            'filename': '/var/log/licornd-wmi.log',
            'maxBytes': '4096',
            'backupCount': '5'
        },
        'console': {
            'level':'DEBUG',
            'class':'logging.StreamHandler',
            'formatter': 'simple'
        }
    },
    'loggers': {
        'licorn.interfaces.wmi': {
            'handlers': ['file', 'console', ],
            'level': 'INFO',
        },
    }
}

TEST_RUNNER = 'wmi.libs.tsutils.NoDbTestRunner'
