"""Rename the migration ledger before Django loads its migration history."""
from django.core.management.commands.migrate import Command as DjangoMigrate
from django.core.management.base import CommandError
from django.db import connections, transaction


class Command(DjangoMigrate):
    def handle(self, *args, **options):
        connection = connections[options["database"]]
        tables = set(connection.introspection.table_names())
        if "django_migrations" in tables:
            if "registrodb_4dx" in tables:
                raise CommandError("Existen ambos registros de migraciones. Revisar antes de continuar.")
            if options.get("plan") or options.get("check_unapplied"):
                raise CommandError("La base conserva django_migrations. Ejecuta migrate sin --plan/--check para renombrar el registro primero.")
            with transaction.atomic(using=connection.alias):
                with connection.cursor() as cursor:
                    cursor.execute("ALTER TABLE %s RENAME TO %s" % (connection.ops.quote_name("django_migrations"), connection.ops.quote_name("registrodb_4dx")))
            self.stdout.write("Registro de migraciones renombrado a registrodb_4dx.")
        return super().handle(*args, **options)
