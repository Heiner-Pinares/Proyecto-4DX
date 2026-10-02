"""Construcción y validación de la conexión de base de datos del portal."""

import base64
import binascii
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured


def database_config(env, base_dir=None):
    """Devuelve DATABASES['default'] sin exponer secretos en mensajes."""
    engine = (env.get("DB_ENGINE") or "oracle").strip().lower()
    aliases = {
        "oracle": "django.db.backends.oracle",
        "postgres": "django.db.backends.postgresql",
        "postgresql": "django.db.backends.postgresql",
        "sqlite": "django.db.backends.sqlite3",
        "sqlite3": "django.db.backends.sqlite3",
    }
    backend = aliases.get(engine, engine if "." in engine else f"django.db.backends.{engine}")

    if backend == "django.db.backends.oracle":
        user = (env.get("ORACLE_USER") or "USRFACDOC[USRVALCBIO]").strip()
        uses_proxy = "[" in user or "]" in user
        if uses_proxy and not (
            user.count("[") == 1
            and user.count("]") == 1
            and user.index("[") > 0
            and user.endswith("]")
            and user.index("[") < len(user) - 2
        ):
            raise ImproperlyConfigured(
                "ORACLE_USER no tiene un formato proxy válido; se espera "
                "USUARIO_PROXY[USUARIO_SESION]."
            )
        encoded_password = (env.get("ORACLE_PASSWORD_B64") or "").strip()
        if encoded_password:
            try:
                password = base64.b64decode(
                    encoded_password, altchars=b"-_", validate=True
                ).decode("utf-8")
            except (binascii.Error, UnicodeDecodeError) as error:
                raise ImproperlyConfigured(
                    "ORACLE_PASSWORD_B64 no es Base64 UTF-8 válido."
                ) from error
            if not password:
                raise ImproperlyConfigured("ORACLE_PASSWORD_B64 contiene una contraseña vacía.")
        else:
            password = env.get("ORACLE_PASSWORD") or ""
            if not password:
                password_path = Path(
                    env.get("ORACLE_PASSWORD_FILE")
                    or Path(base_dir or ".") / "secrets" / "oracle_password.txt"
                )
                try:
                    password = password_path.read_text(encoding="utf-8").rstrip("\r\n")
                except FileNotFoundError as error:
                    raise ImproperlyConfigured(
                        "Falta la contraseña Oracle. Pégala en "
                        f"{password_path} como una sola línea."
                    ) from error
            if not password:
                raise ImproperlyConfigured("La contraseña Oracle está vacía.")
        dsn = (env.get("ORACLE_DSN") or "").strip()
        if not dsn:
            host = (env.get("ORACLE_HOST") or "scan-odscbio").strip()
            port = (env.get("ORACLE_PORT") or "1521").strip()
            if not port.isdigit() or not 1 <= int(port) <= 65535:
                raise ImproperlyConfigured("ORACLE_PORT debe ser un puerto válido.")
            service = (env.get("ORACLE_SERVICE_NAME") or "ODSCBIO").strip()
            # Replica el descriptor validado en PL/SQL Developer.
            dsn = (
                "(DESCRIPTION=(ADDRESS=(PROTOCOL=TCP)"
                f"(HOST={host})(PORT={port}))"
                "(CONNECT_DATA=(SERVER=DEDICATED)"
                f"(SERVICE_NAME={service})))"
            )
        pool = (env.get("ORACLE_POOL") or "true").lower() == "true"
        # python-oracledb es seguro para uso multihilo de forma predeterminada.
        # `threaded` pertenecía a cx_Oracle y create_pool() ya no lo acepta.
        options = {}
        if pool:
            # La autenticación proxy requiere un pool heterogéneo.
            options["pool"] = {"homogeneous": False} if uses_proxy else True
        return {
            "ENGINE": backend,
            "NAME": dsn,
            "USER": user,
            "PASSWORD": password,
            "CONN_MAX_AGE": 0,
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": options,
        }

    if backend == "django.db.backends.sqlite3":
        return {"ENGINE": backend, "NAME": env.get("DB_NAME", ":memory:")}

    return {
        "ENGINE": backend,
        "NAME": env.get("DB_NAME", "compromisos_db"),
        "USER": env.get("DB_USER", "postgres"),
        "PASSWORD": env.get("DB_PASSWORD", ""),
        "HOST": env.get("DB_HOST", "localhost"),
        "PORT": env.get("DB_PORT", "5432"),
        "CONN_HEALTH_CHECKS": True,
    }
