"""Configuración para una publicación temporal en el dominio HTTPS indicado."""
import os
from urllib.parse import urlsplit

from django.core.exceptions import ImproperlyConfigured

from .settings import *  # noqa: F403

public_url = os.environ.get('NGROK_PUBLIC_URL', '').strip().rstrip('/')
parsed = urlsplit(public_url)
if (parsed.scheme != 'https' or not parsed.hostname or parsed.username
        or parsed.password or parsed.path or parsed.query or parsed.fragment
        or parsed.port not in (None, 443)):
    raise ImproperlyConfigured('NGROK_PUBLIC_URL debe ser la URL HTTPS del túnel, sin rutas ni credenciales.')

DEBUG = False
ALLOWED_HOSTS = [parsed.hostname, 'localhost', '127.0.0.1']
CSRF_TRUSTED_ORIGINS = [public_url]
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
# No conservar HSTS en el navegador para una URL de uso temporal.
SECURE_HSTS_SECONDS = 0
