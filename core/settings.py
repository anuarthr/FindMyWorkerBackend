from decouple import config, Csv
from pathlib import Path
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
# Set SECRET_KEY in the environment for any non-local deployment.
# The insecure default only exists so local dev works out of the box.
SECRET_KEY = config(
    'SECRET_KEY',
    default='django-insecure-3#&tpg%)le)2!0ss#roaj68hkoo*xljz$4fn0oug^wovvoq&dv',
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=True, cast=bool)

# Hosts permitidos para acceder a la aplicación.
# En producción: ALLOWED_HOSTS=tu-app.onrender.com,api.tudominio.com
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    default='127.0.0.1,localhost,testserver',
    cast=Csv(),
)

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.gis',
    'django_filters',
    'users',
    'orders',
    'corsheaders',
    'channels',
    'rest_framework',
    'rest_framework_simplejwt'
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    # WhiteNoise serves collected static files in production (no-op when USE_S3).
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

# Database.
# Prefer a single DATABASE_URL (e.g. Supabase / Render) when present, else fall
# back to discrete DB_* vars. The GIS PostGIS engine is forced in both cases.
DATABASE_URL = config('DATABASE_URL', default='')

if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=config('DB_CONN_MAX_AGE', default=600, cast=int),
            ssl_require=config('DB_SSL_REQUIRE', default=not DEBUG, cast=bool),
        )
    }
    DATABASES['default']['ENGINE'] = 'django.contrib.gis.db.backends.postgis'
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.contrib.gis.db.backends.postgis',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST'),
            'PORT': config('DB_PORT', cast=int),
            'CONN_MAX_AGE': config('DB_CONN_MAX_AGE', default=600, cast=int),
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'es'

TIME_ZONE = 'America/Bogota'

USE_I18N = True

USE_TZ = True

LANGUAGES = [
    ('es', _('Spanish')),
    ('en', _('English')),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]

# ============================================================================
# STATIC FILES CONFIGURATION
# ============================================================================

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Only include the project static dir if it actually exists, otherwise Django
# (and collectstatic) emit staticfiles.W004.
STATICFILES_DIRS = [
    BASE_DIR / 'static',
] if (BASE_DIR / 'static').exists() else []

# ============================================================================
# MEDIA FILES & AWS S3 CONFIGURATION (HU4)
# ============================================================================

# Toggle between S3 and local storage. Use decouple (not os.getenv) so the
# value is actually read from .env in local dev — os.getenv only sees real OS
# env vars, not python-decouple's .env loader.
USE_S3 = config('USE_S3', default=False, cast=bool)

if USE_S3:
    # AWS S3 Configuration
    AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID', default='')
    AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY', default='')
    AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME', default='')
    AWS_S3_REGION_NAME = config('AWS_S3_REGION_NAME', default='us-east-1')
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False  # Public URLs without query string tokens
    # Modern virtual-hosted style endpoint. The legacy "{bucket}.s3.amazonaws.com"
    # only resolves for us-east-1; include the region so every bucket works.
    # Allow override (e.g. CloudFront) via AWS_S3_CUSTOM_DOMAIN.
    AWS_S3_CUSTOM_DOMAIN = config(
        'AWS_S3_CUSTOM_DOMAIN',
        default=f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com",
    )
    # Browser cache for static/media served from S3 (1 day).
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

    # Django 4.2+ STORAGES configuration.
    # media -> user uploads (avatars, portfolio); static -> collectstatic output.
    # Separate `location` prefixes keep them from colliding in the same bucket.
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "custom_domain": AWS_S3_CUSTOM_DOMAIN,
                "file_overwrite": AWS_S3_FILE_OVERWRITE,
                "querystring_auth": AWS_QUERYSTRING_AUTH,
                "location": "media",
            },
        },
        "staticfiles": {
            "BACKEND": "storages.backends.s3.S3StaticStorage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                "custom_domain": AWS_S3_CUSTOM_DOMAIN,
                "file_overwrite": True,  # collectstatic overwrites existing assets
                "location": "static",
            },
        },
    }

    # Public base URLs (include the location prefix)
    MEDIA_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/media/"
    STATIC_URL = f"https://{AWS_S3_CUSTOM_DOMAIN}/static/"
else:
    # Local filesystem media + WhiteNoise for static.
    # Static uses the plain backend in DEBUG (avoids manifest lookups during
    # runserver) and the compressed manifest backend in production.
    _static_backend = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": _static_backend,
        },
    }

    # Media files configuration (local)
    MEDIA_URL = "/media/"
    MEDIA_ROOT = BASE_DIR / "media"

# ============================================================================
# DJANGO CONFIGURATION
# ============================================================================

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'users.User'

# Configuración de Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    # Paginación
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,  # Default: 10 items por página
    # Formato de respuesta JSON por defecto
    'DEFAULT_RENDERER_CLASSES': (
        'rest_framework.renderers.JSONRenderer',
    ),
    # Parser por defecto (las vistas con carga de archivos añaden MultiPartParser)
    'DEFAULT_PARSER_CLASSES': (
        'rest_framework.parsers.JSONParser',
        'rest_framework.parsers.MultiPartParser',
        'rest_framework.parsers.FormParser',
    ),
    # Throttling (Rate Limiting) para prevenir abuso
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',    # Usuarios no autenticados
        'user': '1000/hour',   # Usuarios autenticados (general)
        'reviews': '10/hour',  # Específico para crear reviews
        # Throttling para sistema de recomendación (HU2)
        'recommendation_search': '60/min',       # Búsquedas de recomendación
        'recommendation_search_anon': '20/min',  # Búsquedas anónimas
        'recommendation_analytics': '30/min',    # Analytics/métricas
        'recommendation_health': '10/min',       # Health checks
    }
}

# Configuración de JWT (JSON Web Tokens)
from datetime import timedelta

SIMPLE_JWT = {
    # Duración del token de acceso
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    # Duración del token de refresco
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    # Rotar refresh token al usarlo
    'ROTATE_REFRESH_TOKENS': True,
    # Blacklist de refresh tokens usados
    'BLACKLIST_AFTER_ROTATION': True,
    # Algoritmo de encriptación
    'ALGORITHM': 'HS256',
    # Claims adicionales
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
}

ASGI_APPLICATION = 'core.asgi.application'

# Redis backs both the Channels transport and the Django cache (TF-IDF model).
# It is OPTIONAL: on a single-instance deployment (Render free tier runs with
# WEB_CONCURRENCY=1, i.e. one process) the in-memory channel layer and the
# local-memory cache work reliably without an external Redis, removing a failure
# point. Set USE_REDIS=True (and provide REDIS_URL) only when scaling to multiple
# workers/instances, where the in-memory backends can't share state.
USE_REDIS = config('USE_REDIS', default=False, cast=bool)
REDIS_URL = config('REDIS_URL', default='')

if USE_REDIS:
    # Managed free tiers often expose only db 0 and forbid SELECT, so URL mode
    # shares one db and relies on key prefixes to stay separate.
    if REDIS_URL:
        _channel_hosts = [REDIS_URL]
        _cache_location = REDIS_URL
    else:
        _redis_host = config('REDIS_HOST', default='127.0.0.1')
        _redis_port = config('REDIS_PORT', default=6379, cast=int)
        _channel_hosts = [(_redis_host, _redis_port)]
        _cache_location = f"redis://{_redis_host}:{_redis_port}/1"

    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG': {
                'hosts': _channel_hosts,
                'prefix': 'findmyworker:asgi',
            },
        },
    }
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': _cache_location,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
            },
            'KEY_PREFIX': 'findmyworker',
            'TIMEOUT': 86400,  # Default: 24 horas
        }
    }
else:
    # In-memory backends — no external Redis required. Valid only for a single
    # process; chat groups and the TF-IDF cache live in that process's memory.
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        },
    }
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'findmyworker-locmem',
            'TIMEOUT': 86400,  # Default: 24 horas
        }
    }

# Configuración de CORS (Cross-Origin Resource Sharing).
# En producción: CORS_ALLOWED_ORIGINS=https://tu-frontend.com
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    default='http://localhost:5173,http://127.0.0.1:5173',
    cast=Csv(),
)

# Orígenes confiables para CSRF (necesario para el admin de Django tras un proxy
# HTTPS como Render). Debe incluir el esquema: https://tu-app.onrender.com
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='', cast=Csv())

# Permitir cookies en peticiones CORS
CORS_ALLOW_CREDENTIALS = True

# Headers permitidos en peticiones CORS
CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Configuración de logging para producción y debugging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'maxBytes': 1024 * 1024 * 10,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'orders': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
        'users': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Configuraciones de seguridad adicionales para producción
if not DEBUG:
    # Render/Heroku/etc. terminan TLS en un proxy y reenvían por HTTP interno.
    # Sin esto, SECURE_SSL_REDIRECT entraría en un bucle de redirección infinito.
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

    # Forzar HTTPS
    SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # Protección HSTS (HTTP Strict Transport Security)
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

    # Otras configuraciones de seguridad
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'