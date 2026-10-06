from datetime import date, timedelta

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from compromisos.models import Compromiso, EventoCompromiso


class Command(BaseCommand):
    help = "Inserta ejemplos opcionales sin crear usuarios ni contraseñas."

    def handle(self, *args, **kwargs):
        call_command("init_portal")
        c, created = Compromiso.all_objects.get_or_create(
            tarea="Desarrollar de formatos PDD y SDR para proyectos internos",
            created_by="seed_demo",
            defaults=dict(
                proyecto="Proyectos",
                status=settings.CLOSED_STATUS_CODE,
                meta=95,
                responsable_pyp="HP",
                fecha_de_compromiso=date(2025, 12, 1),
                fecha_de_vencimiento=date(2025, 12, 1),
                fecha_real=date(2025, 12, 1),
                puntaje=100,
                primera_fecha=date(2025, 12, 1),
            ),
        )
        if created:
            EventoCompromiso.objects.create(
                compromiso=c,
                accion="CREADO",
                descripcion="Registro de demostración legacy.",
                usuario="seed_demo",
            )
        for index, task in enumerate(
            [
                "Validar el plan de implementación",
                "Consolidar indicadores de operaciones",
                "Revisar acuerdos del comité",
                "Publicar formatos de seguimiento",
                "Coordinar integración con TI",
                "Definir alcance del proyecto",
            ]
        ):
            c, created = Compromiso.all_objects.get_or_create(
                tarea=task,
                created_by="seed_demo",
                defaults=dict(
                    proyecto=["Proyectos", "Operaciones"][index % 2],
                    responsable_pyp=["HP", "MR", "LC"][index % 3],
                    status=settings.PENDING_STATUS_CODE
                    if index % 2
                    else settings.IN_PROGRESS_STATUS_CODE,
                    fecha_de_compromiso=timezone.localdate() - timedelta(days=15),
                    fecha_de_vencimiento=timezone.localdate()
                    + timedelta(days=index * 3 - 5)
                    if index != 5
                    else None,
                    meta=95,
                    suspendida=index == 4,
                ),
            )
            if created:
                EventoCompromiso.objects.create(
                    compromiso=c,
                    accion="CREADO",
                    descripcion="Registro de demostración.",
                    usuario="seed_demo",
                )
        self.stdout.write(self.style.SUCCESS("Demostración disponible."))
