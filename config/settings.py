import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def flag(name, default="false"):
    return os.getenv(name, default).lower() == "true"


DEBUG = flag("DEBUG")
SECRET_KEY = os.environ["SECRET_KEY"]
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "compromisos",
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
                "compromisos.permissions.context",
            ]
        },
    }
]
WSGI_APPLICATION = "config.wsgi.application"
engine = os.getenv("DB_ENGINE", "postgresql")
DATABASES = {
    "default": {
        "ENGINE": engine if "." in engine else "django.db.backends." + engine,
        "NAME": os.getenv("DB_NAME", "compromisos_db"),
    }
}
if engine != "sqlite3":
    DATABASES["default"].update(
        {
            key: os.getenv("DB_" + key, default)
            for key, default in [
                ("USER", "postgres"),
                ("PASSWORD", ""),
                ("HOST", "localhost"),
                ("PORT", "5432"),
            ]
        }
    )
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation." + name}
    for name in [
        "UserAttributeSimilarityValidator",
        "MinimumLengthValidator",
        "CommonPasswordValidator",
        "NumericPasswordValidator",
    ]
]
LANGUAGE_CODE = "es-pe"
TIME_ZONE = "America/Lima"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
CLOSED_STATUS_CODE = os.getenv("CLOSED_STATUS_CODE", "T")
PENDING_STATUS_CODE = "EC"
IN_PROGRESS_STATUS_CODE = "EC"
DUE_SOON_DAYS = int(os.getenv("DUE_SOON_DAYS", "7"))
ALLOW_EARLIER_RESCHEDULE = flag("ALLOW_EARLIER_RESCHEDULE")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = flag("COOKIE_SECURE")
CSRF_COOKIE_SECURE = flag("COOKIE_SECURE")
SECURE_CONTENT_TYPE_NOSNIFF = True
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
