"""Arranque idempotente: conexión, migraciones versionadas e inicialización."""

import logging
import os
import sys
import time

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()
from django.core.management import call_command
from django.db import OperationalError, connections

from config.settings import flag

log = logging.getLogger(__name__)


def initialize():
    for attempt in range(30):
        try:
            connections["default"].ensure_connection()
            break
        except OperationalError:
            log.info("Esperando conexión a base de datos (%s/30)", attempt + 1)
            if attempt == 29:
                raise
            time.sleep(2)
    if flag("AUTO_MIGRATE", "true"):
        log.info("Aplicando migraciones versionadas")
        call_command("migrate", interactive=False)
    call_command("init_portal")
    log.info("Portal inicializado")


if __name__ == "__main__":
    initialize()
    if "--check" not in sys.argv:
        call_command("collectstatic", interactive=False, verbosity=0)
        if flag("DEBUG"):
            call_command("runserver", "0.0.0.0:8000", use_reloader=False)
        else:
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
