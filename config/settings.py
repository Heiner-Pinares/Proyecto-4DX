import os
from pathlib import Path

from dotenv import load_dotenv

from .database import database_config
from .runtime_secrets import secret_key

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def flag(name, default="false"):
    return os.getenv(name, default).lower() == "true"


DEBUG = flag("DEBUG")
SECRET_KEY = secret_key(os.environ, BASE_DIR)
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "*").split(",") if host.strip()]
INSTALLED_APPS = [
    "config.portal_apps.PortalAdminConfig",
    "config.portal_apps.PortalAuthConfig",
    "config.portal_apps.PortalContentTypesConfig",
    "config.portal_apps.PortalSessionsConfig",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "config.portal_apps.PortalCompromisosConfig",
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
DATABASES = {"default": database_config(os.environ, BASE_DIR)}
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

# URL secreta del flujo Teams; nunca se publica en el navegador.
from dotenv import dotenv_values
_teams_config = dotenv_values(BASE_DIR / ".env")
TEAMS_WEBHOOK_URL = (_teams_config.get("TEAMS_WEBHOOK_URL") or os.getenv("TEAMS_WEBHOOK_URL", "")).strip()
PORTAL_PUBLIC_URL = (os.getenv("PORTAL_PUBLIC_URL") or _teams_config.get("PORTAL_PUBLIC_URL", "")).strip().rstrip("/")

# Conexión del relay corporativo usada por el botón de correo. Los valores del
# entorno siguen teniendo prioridad, pero los campos vacíos de .env no anulan
# la configuración funcional incluida para el servidor 4DX.
CORREO_SSH_HOST = os.getenv("CORREO_SSH_HOST") or "172.19.30.62"
CORREO_SSH_USER = os.getenv("CORREO_SSH_USER") or "usr_mds"
CORREO_SSH_PASSWORD = os.getenv("CORREO_SSH_PASSWORD") or "Usr_mds"
CORREO_PARA = os.getenv("CORREO_PARA") or "c27826@claro.com.pe"
CORREO_COPIA = os.getenv("CORREO_COPIA") or "c28171@claro.com.pe"

SESSION_ENGINE = "compromisos.session_backend"
MIGRATION_MODULES = {"admin": "config.admin_migrations", "sessions": "config.sessions_migrations"}

MIGRATION_MODULES.update({"auth": "config.auth_migrations", "contenttypes": "config.contenttypes_migrations"})

# Servidor directo o proxy inverso HTTPS.
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]
SECURE_SSL_REDIRECT = flag("SECURE_SSL_REDIRECT")
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = flag("SECURE_HSTS_INCLUDE_SUBDOMAINS")
SECURE_HSTS_PRELOAD = flag("SECURE_HSTS_PRELOAD")
# Activar únicamente cuando el proxy elimina y establece esta cabecera.
if flag("TRUST_PROXY_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
