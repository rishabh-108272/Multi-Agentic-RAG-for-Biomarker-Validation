import os 
from pathlib import Path
from dotenv import load_dotenv 

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / "pipeline" / ".env")


# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure--jtndq+2+ohkn8jsga!sy#9%^*ri+ve9un$nq=%@jero=dg%p8'

# SECURITY WARNING: don't run with debug turned on in production!
# Local: defaults to True. Render sets RENDER; Railway sets RAILWAY_ENVIRONMENT — then default
# is False unless you set DJANGO_DEBUG=true explicitly.
# Hugging Face Spaces sets SPACE_AUTHOR_NAME / SPACE_REPO_NAME (see HF Spaces docs).
_is_hf_space = bool(os.getenv("SPACE_AUTHOR_NAME") or os.getenv("SPACE_REPO_NAME"))
_is_deployed = bool(
    os.getenv("RENDER") or os.getenv("RAILWAY_ENVIRONMENT") or _is_hf_space
)
DEBUG = os.getenv(
    "DJANGO_DEBUG",
    "false" if _is_deployed else "true",
).lower() in ("1", "true", "yes")

ALLOWED_HOSTS = ['*']



# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'channels',
    'pipeline'
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'lung_cancer_api.urls'

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

WSGI_APPLICATION = 'lung_cancer_api.wsgi.application'
ASGI_APPLICATION = 'lung_cancer_api.asgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
# Comma-separated list, e.g. "https://my-app.vercel.app,https://preview-xyz.vercel.app"
_cors_extra = os.getenv("CORS_ALLOWED_ORIGINS", "")
if _cors_extra:
    CORS_ALLOWED_ORIGINS.extend(
        [origin.strip() for origin in _cors_extra.split(",") if origin.strip()]
    )

# Vercel production + preview URLs (https://*.vercel.app). Custom domains: set CORS_ALLOWED_ORIGINS on the host (e.g. Render).
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https://.*\.vercel\.app$",
    r"^https://.*\.hf\.space$",
]

# WebSocket channel layer: Redis is optional. HF Spaces and many PaaS images have no local Redis;
# InMemory avoids startup/runtime failures for API-only deployments.
_use_redis_channel_layer = os.getenv("CHANNEL_LAYER_REDIS", "").lower() in (
    "1",
    "true",
    "yes",
)
if _use_redis_channel_layer:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [
                    (
                        os.getenv("REDIS_HOST", "127.0.0.1"),
                        int(os.getenv("REDIS_PORT", "6379")),
                    )
                ]
            },
        },
    }
else:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }

REST_FRAMEWORK = {
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10
}

# Celery should be configured from environment in cloud deploys.
# Example (Render Redis internal URL): redis://:<password>@<host>:6379/0
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", CELERY_BROKER_URL)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
HUGGINGFACE_REPO_ID = os.getenv("HUGGINGFACE_REPO_ID")
LUNG_CLASSIFIER_FALLBACK = os.getenv("LUNG_CLASSIFIER_FALLBACK", "")

FILE_UPLOAD_MAX_MEMORY_SIZE = 52428800

# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

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


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_URL = 'static/'

# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
