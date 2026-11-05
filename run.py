"""Arranque idempotente: conexión, migraciones versionadas e inicialización."""

import argparse
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


def positive_port(value):
    """Valida un puerto TCP recibido por argumento o variable de entorno."""
    try:
        port = int(value)
    except (TypeError, ValueError) as error:
        raise argparse.ArgumentTypeError("el puerto debe ser un número") from error
    if not 1 <= port <= 65535:
        raise argparse.ArgumentTypeError("el puerto debe estar entre 1 y 65535")
    return port


def command_line(argv=None):
    parser = argparse.ArgumentParser(description="Inicializa y ejecuta el Portal 4DX")
    parser.add_argument(
        "--check",
        action="store_true",
        help="verifica e inicializa el portal sin abrir el servidor web",
    )
    parser.add_argument(
        "--host",
        default=os.getenv("WEB_BIND_ADDRESS", "0.0.0.0"),
        help="dirección de escucha (WEB_BIND_ADDRESS; 0.0.0.0 por defecto)",
    )
    parser.add_argument(
        "--port",
        type=positive_port,
        default=positive_port(os.getenv("PORTAL_PORT", os.getenv("PORT", "8000"))),
        help="puerto HTTP (PORTAL_PORT o PORT; 8000 por defecto)",
    )
    return parser.parse_args(argv)


def serve_production(host=None, port=None):
    """Usa un servidor WSGI compatible con el sistema operativo."""
    host = host or os.getenv("WEB_BIND_ADDRESS", "0.0.0.0")
    port = positive_port(port or os.getenv("PORTAL_PORT", os.getenv("PORT", "8000")))
    if os.name == "nt":
        # Ejecutar dentro del proceso evita que Windows divida rutas con espacios.
        from waitress import serve
        from config.wsgi import application

        log.info("Portal disponible en http://%s:%s", host, port)
        serve(application, host=host, port=port, threads=8)
        return
    os.execv(
        sys.executable,
        [
            sys.executable,
            "-m",
            "gunicorn",
            "config.wsgi:application",
            "--bind",
            f"{host}:{port}",
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
    args = command_line()
    initialize()
    if not args.check:
        call_command("collectstatic", interactive=False, verbosity=0)
        if flag("DEBUG"):
            call_command("runserver", f"{args.host}:{args.port}", use_reloader=False)
        else:
            serve_production(args.host, args.port)
