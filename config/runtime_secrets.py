"""Secretos locales persistentes que nunca se incorporan al repositorio."""

import os
import secrets
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def secret_key(env, base_dir):
    configured = (env.get("SECRET_KEY") or "").strip()
    if configured and configured != "change-me":
        return configured

    path = Path(env.get("SECRET_KEY_FILE") or base_dir / "runtime-config" / "django_secret_key.txt")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, "w") as stream:
                    stream.write(secrets.token_urlsafe(64))
            except FileExistsError:
                # Otra instancia terminó de crearla entre la comprobación y el alta.
                pass
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ImproperlyConfigured(f"El archivo de clave está vacío: {path}")
        return value
    except OSError as error:
        raise ImproperlyConfigured(
            f"No se pudo leer o crear la clave privada en {path}."
        ) from error
