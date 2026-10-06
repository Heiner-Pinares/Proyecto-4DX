from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

from compromisos.models import EventoCompromiso


class Command(BaseCommand):
    help = "Crea estados y roles idempotentemente, sin usuarios ni datos demo."

    def handle(self, *args, **kwargs):
        for code, label in [
            ("EC", "En curso"),
            ("D", "Demorado"),
            (settings.CLOSED_STATUS_CODE, "Terminado"),
            ("S", "Stand By"),
        ]:
            EventoCompromiso.estados.update_or_create(codigo=code, defaults={"nombre": label, "activo": True})
        EventoCompromiso.estados.exclude(codigo__in=["EC", "S", "T", "D"]).update(activo=False)
        for name in ["Administrador", "Editor", "Consulta"]:
            group, _ = Group.objects.get_or_create(name=name)
            if name == "Administrador":
                permissions = Permission.objects.filter(
                    content_type__app_label__in=["compromisos", "auth"]
                )
            else:
                codes = [
                    "view_compromiso",
                    "view_eventocompromiso",
                    "view_estado",
                ]
                if name == "Editor":
                    codes += ["add_compromiso", "change_compromiso"]
                permissions = Permission.objects.filter(
                    content_type__app_label="compromisos", codename__in=codes
                )
            group.permissions.add(*permissions)
        self.stdout.write("Roles y estados inicializados.")
