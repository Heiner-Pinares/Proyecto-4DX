"""Arranque idempotente: conexión, migraciones versionadas e inicialización."""

import logging
import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.core.management import call_command
from django.db import DatabaseError, connections

from config.settings import flag

log = logging.getLogger(__name__)


def serve_production():
    """Usa un servidor WSGI compatible con el sistema operativo."""
    if os.name == "nt":
        # Ejecutar dentro del proceso evita que Windows divida rutas con espacios.
        from waitress import serve
        from config.wsgi import application

        log.info("Portal disponible en http://0.0.0.0:8000")
        serve(application, host="0.0.0.0", port=8000, threads=8)
        return
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "gunicorn",
            "config.wsgi:application",
            "--bind",
            "0.0.0.0:8000",
            "--workers",
            "2",
        ],
    )


def initialize():
    retries = int(os.getenv("DB_CONNECT_RETRIES", "30"))
    delay = float(os.getenv("DB_CONNECT_DELAY", "2"))
    for attempt in range(retries):
        try:
            connections["default"].ensure_connection()
            break
        except DatabaseError as error:
            log.warning(
                "Base de datos no disponible (%s/%s): %s",
                attempt + 1,
                retries,
                error.__class__.__name__,
            )
            if attempt == retries - 1:
                raise
            time.sleep(delay)
    if connections["default"].vendor == "oracle":
        log.info("Verificando versión, servicio y privilegios Oracle")
        call_command("verificar_oracle", connection_only=True)
    if flag("AUTO_MIGRATE", "true"):
        log.info("Aplicando migraciones versionadas")
        call_command("migrate", interactive=False)
    if connections["default"].vendor == "oracle":
        call_command("verificar_oracle")
    call_command("init_portal")
    log.info("Portal inicializado")


if __name__ == "__main__":
    initialize()
    if "--check" not in sys.argv:
        call_command("collectstatic", interactive=False, verbosity=0)
        if flag("DEBUG"):
            call_command("runserver", "0.0.0.0:8000", use_reloader=False)
        else:
            serve_production()
