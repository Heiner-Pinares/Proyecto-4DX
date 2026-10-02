"""Comprueba la conexión y, opcionalmente, el esquema Oracle del portal."""

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


EXPECTED_TABLES = {
    "compromisos",
    "registros_portal4dx",
    "usuarios_4dx",
    "grupos_usuarios_4dx",
    "permisos_4dx",
    "relacion_grupo_4dx",
    "grupo_usuarios_4dx",
    "permisos_usuarios_4dx",
    "entidades_4dx",
    "registrodb_4dx",
}


class Command(BaseCommand):
    help = "Valida conexión, servicio, tablas y migraciones de Oracle sin mostrar secretos."

    def add_arguments(self, parser):
        parser.add_argument(
            "--connection-only",
            action="store_true",
            help="Comprueba la conexión antes de crear el esquema.",
        )

    def handle(self, *args, **options):
        if connection.vendor != "oracle":
            raise CommandError(
                f"La conexión activa es {connection.vendor!r}; configura DB_ENGINE=oracle."
            )
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT SYS_CONTEXT('USERENV','SERVICE_NAME'), "
                "SYS_CONTEXT('USERENV','CURRENT_SCHEMA') FROM DUAL"
            )
            service, schema = cursor.fetchone()
            cursor.execute("SELECT PRIVILEGE FROM SESSION_PRIVS")
            privileges = {row[0] for row in cursor.fetchall()}
        version = connection.oracle_version
        if version < (19,):
            raise CommandError(
                f"Oracle {'.'.join(map(str, version))} no es compatible; Django 5.2 requiere Oracle 19c o posterior."
            )
        required = {
            "CREATE SESSION",
            "CREATE TABLE",
            "CREATE SEQUENCE",
            "CREATE PROCEDURE",
            "CREATE TRIGGER",
        }
        missing_privileges = sorted(required - privileges)
        if missing_privileges:
            raise CommandError(
                "Faltan privilegios para crear/migrar el portal: "
                + ", ".join(missing_privileges)
            )
        self.stdout.write(
            self.style.SUCCESS(
                f"Oracle {'.'.join(map(str, version))} conectado: servicio={service}, esquema={schema}."
            )
        )
        if options["connection_only"]:
            return

        tables = set(connection.introspection.table_names())
        missing = sorted(EXPECTED_TABLES - tables)
        if missing:
            raise CommandError("Faltan tablas del portal: " + ", ".join(missing))

        executor = MigrationExecutor(connection)
        pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if pending:
            names = ", ".join(f"{migration.app_label}.{migration.name}" for migration, _ in pending)
            raise CommandError("Hay migraciones pendientes: " + names)
        self.stdout.write(self.style.SUCCESS("Las 10 tablas del portal existen y no hay migraciones pendientes."))
