"""Exporta datos portables para trasladarlos a un esquema Oracle nuevo."""

from itertools import chain
from pathlib import Path

from django.contrib.auth.models import Group, User
from django.core import serializers
from django.core.management.base import BaseCommand, CommandError

from compromisos.models import Compromiso, EventoCompromiso


class Command(BaseCommand):
    help = "Exporta usuarios, roles y datos 4DX; excluye sesiones activas."

    def add_arguments(self, parser):
        parser.add_argument("output", help="Archivo JSON nuevo que se creará.")

    def handle(self, *args, **options):
        output = Path(options["output"]).expanduser().resolve()
        if output.exists():
            raise CommandError(f"El archivo ya existe: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        objects = chain(
            Group.objects.order_by("pk").iterator(),
            User.objects.order_by("pk").iterator(),
            Compromiso.all_objects.order_by("pk").iterator(),
            EventoCompromiso.objects.exclude(tipo="sesion").order_by("pk").iterator(),
        )
        try:
            with output.open("x", encoding="utf-8") as stream:
                serializers.serialize(
                    "json",
                    objects,
                    stream=stream,
                    indent=2,
                    use_natural_foreign_keys=True,
                )
        except Exception:
            output.unlink(missing_ok=True)
            raise
        try:
            output.chmod(0o600)
        except OSError:
            pass
        self.stdout.write(
            self.style.SUCCESS(
                f"Datos exportados a {output}. Contiene información privada; protégelo y bórralo al terminar."
            )
        )
