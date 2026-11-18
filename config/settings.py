"""
Django settings for Dashboards Fonda (repo dashboards_fonda_FAR).

Same conventions as the sibling apps (Central de Reportes, ControlPresupuestos_AP):
env-driven, _DEV suffix for the dev database, optional URL prefix when
reverse-proxied, WhiteNoise + Waitress in production. The .env lives at
config/.env (gitignored); config/.env.example documents every variable.

Metric code is NOT written here: it is Central de Reportes' engine
(`central.motor`), included as a git submodule pinned to one commit in
vendor/central and imported as a library (see dashboards/motor_central.py).
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(dotenv_path=BASE_DIR / "config" / ".env")

# Central de Reportes' repo (git submodule). APPENDED, never prepended: that
# repo also has a `config` package, and ours must win. Only `central.motor`
# is imported from it; Central's Django apps are NOT installed here.
CENTRAL_DIR = BASE_DIR / "vendor" / "central"
if str(CENTRAL_DIR) not in sys.path:
    sys.path.append(str(CENTRAL_DIR))

ENV = os.getenv("ENV", "prod").lower()

# No insecure fallback on purpose: set DJANGO_SECRET_KEY in config/.env.
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Where indicator DATA is read from (Wansoft, Presupuestos AP): "prod" or "dev".
# Read by Central's engine (central.motor.fuentes.conexiones). Independent of
# ENV so the app can run in dev while reading the production sources
# (read-only sessions). Defaults to ENV.
FUENTES_ENV = os.getenv("FUENTES_ENV", ENV).lower()

DEBUG = os.getenv("DJANGO_DEBUG", "true" if ENV == "dev" else "false").lower() == "true"

ALLOWED_HOSTS = [h.strip() for h in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]

# Set only when reverse-proxied under a URL prefix (Apache:
# http://187.251.203.223:8088/dashboards_fonda/ -> this app). Blank in dev.
FORCE_SCRIPT_NAME = os.getenv("DJANGO_FORCE_SCRIPT_NAME") or None

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "dashboards",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "dashboards.context_processors.version_motor",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# This app's OWN database (users, groups, cache). Indicator data is read
# elsewhere (Wansoft MySQL, Presupuestos AP, Odoo), never written.
_DB_SUFFIX = "_DEV" if ENV == "dev" else ""

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "HOST": os.getenv(f"DASHBOARDS_DB_HOST{_DB_SUFFIX}"),
        "PORT": os.getenv(f"DASHBOARDS_DB_PORT{_DB_SUFFIX}", "3306"),
        "USER": os.getenv(f"DASHBOARDS_DB_USER{_DB_SUFFIX}"),
        "PASSWORD": os.getenv(f"DASHBOARDS_DB_PASSWORD{_DB_SUFFIX}"),
        "NAME": os.getenv(f"DASHBOARDS_DB_NAME{_DB_SUFFIX}"),
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": "SET sql_mode='STRICT_TRANS_TABLES'",
        },
    }
}

# Indicator results are cached one hour (owner, 2026-11-17: live data + 1 h
# cache). Database cache: shared by every Waitress thread, survives restarts.
# Table created by `python manage.py createcachetable`.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "dashboards_cache",
        "TIMEOUT": 60 * 60,
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "es-mx"
TIME_ZONE = "America/Mexico_City"
USE_I18N = True
USE_TZ = True

STATIC_URL = f"{FORCE_SCRIPT_NAME or ''}/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_AGE = 60 * 60 * 8  # 8 hours
_SECURE = os.getenv("DJANGO_SECURE_COOKIES", "false").lower() == "true"
SESSION_COOKIE_SECURE = _SECURE
CSRF_COOKIE_SECURE = _SECURE
CSRF_TRUSTED_ORIGINS = [o.strip() for o in os.getenv("DJANGO_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{asctime} {levelname} {name} {message}", "style": "{"},
    },
    "handlers": {
        "file": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "django.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 5,
            "formatter": "verbose",
        },
        "console": {"level": "INFO", "class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
