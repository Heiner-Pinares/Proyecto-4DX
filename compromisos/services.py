"""Operaciones de negocio atómicas, independientes de vistas y motor de datos."""

import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import Compromiso, EventoCompromiso
from .permissions import require

log = logging.getLogger(__name__)


def fecha_objetivo(c):
    return (
        c.tercera_fecha or c.segunda_fecha or c.primera_fecha or c.fecha_de_vencimiento
    )


def situacion(c, hoy=None):
    hoy = hoy or timezone.localdate()
    objetivo = fecha_objetivo(c)
    if c.suspendida:
        return "Suspendido"
    if not objetivo:
        return "Por definir"
    if c.fecha_real:
        return (
            "Cumplido a tiempo"
            if c.fecha_real <= objetivo
            else "Cumplido fuera de plazo"
        )
    dias = (objetivo - hoy).days
    return (
        "Vencido"
        if dias < 0
        else "Por vencer"
        if dias <= settings.DUE_SOON_DAYS
        else "En plazo"
    )


def audit(c, accion, detalle, user):
    EventoCompromiso.objects.create(
        compromiso=c, accion=accion, descripcion=detalle, usuario=user.get_username()
    )
    log.info("Compromiso %s: %s por %s", c.pk, accion, user.pk)


@transaction.atomic
def guardar(data, user, pk=None):
    require(user, edit=True)
    c = (
        Compromiso.objects.select_for_update().get(pk=pk)
        if pk
        else Compromiso(created_by=user.get_username())
    )
    cambios = []
    puntaje_anterior = c.puntaje
    for key, value in data.items():
        if key in ["puntaje", "status"]:
            continue  # El puntaje depende de las fechas, nunca de un valor ingresado.
        if getattr(c, key) != value:
            cambios.append(
                f"{c._meta.get_field(key).verbose_name}: {getattr(c, key)} → {value}"
            )
        setattr(c, key, value)
    c.updated_by = user.get_username()
    c.full_clean()
    c.save()
    if c.puntaje != puntaje_anterior:
        cambios.append(f"Cumplimiento recalculado: {puntaje_anterior} → {c.puntaje} %")
    audit(
        c,
        "ACTUALIZADO" if pk else "CREADO",
        "\n".join(cambios) or "Sin cambios de campos.",
        user,
    )
    return c


@transaction.atomic
def operar(pk, accion, data, user):
    require(
        user,
        edit=accion not in ["restaurar", "eliminar", "purgar"],
        administrative=accion in ["restaurar", "eliminar", "purgar"],
    )
    c = Compromiso.all_objects.select_for_update().get(pk=pk)
    if c.deleted_at and accion not in ["restaurar", "purgar"]:
        raise ValidationError("El compromiso está en la papelera.")
    detalle = data.get("motivo", "") or data.get("nota", "")
    if accion == "reprogramar":
        nueva = data.get("fecha_nueva")
        anterior = fecha_objetivo(c)
        if not nueva or not detalle.strip():
            raise ValidationError("Debe indicar nueva fecha y motivo.")
        if anterior and nueva < anterior and not settings.ALLOW_EARLIER_RESCHEDULE:
            raise ValidationError("La nueva fecha no puede ser anterior a la vigente.")
        # La primera fecha es el compromiso inicial; reprogramar ocupa la segunda.
        if not c.primera_fecha and c.fecha_de_vencimiento:
            c.primera_fecha = c.fecha_de_vencimiento
        slot = next(
            (
                field
                for field in ["primera_fecha", "segunda_fecha", "tercera_fecha"]
                if not getattr(c, field)
            ),
            None,
        )
        numero = (
            c.reprogramaciones.aggregate(n=Max("numero_reprogramacion"))["n"] or 0
        ) + 1
        EventoCompromiso.objects.create(
            compromiso=c,
            tipo="reprogramacion",
            numero_reprogramacion=numero,
            fecha_anterior=anterior,
            fecha_nueva=nueva,
            motivo=detalle,
            usuario=user.get_username(),
        )
        if slot:
            setattr(c, slot, nueva)
        detalle = f"Fecha anterior: {anterior}. Nueva fecha: {nueva}. Motivo: {detalle}"
    elif accion == "cerrar":
        if not data.get("fecha_real"):
            raise ValidationError("Debe indicar la fecha real.")
        c.fecha_real = data["fecha_real"]
        from .scoring import calcular_puntaje

        c.puntaje = calcular_puntaje(c)
        c.status = settings.CLOSED_STATUS_CODE
        c.suspendida = False
        detalle = f"Fecha real: {c.fecha_real}. Puntaje: {c.puntaje}. {detalle}"
    elif accion == "suspender":
        if not detalle.strip():
            raise ValidationError("Debe indicar un motivo.")
        c.suspendida = True
        c.status = "S"
    elif accion == "reactivar":
        c.suspendida = False
        c.status = "T" if c.fecha_real else "EC"
    elif accion == "eliminar":
        c.deleted_at = timezone.now()
    elif accion == "restaurar":
        c.deleted_at = None
    elif accion == "purgar":
        if not c.deleted_at or data.get("confirmacion") != "ELIMINAR":
            raise ValidationError(
                "Escriba ELIMINAR para confirmar la eliminación definitiva desde la papelera."
            )
        log.info(
            "Eliminación definitiva de compromiso %s por usuario %s", c.pk, user.pk
        )
        c.delete()
        return
    elif accion == "nota":
        if not detalle.strip():
            raise ValidationError("Escriba una nota.")
        c.notas = (c.notas + "\n" + detalle).strip()
    else:
        raise ValidationError("Acción no válida.")
    c.updated_by = user.get_username()
    c.full_clean()
    c.save()
    acciones = {
        "reprogramar": "REPROGRAMADO",
        "cerrar": "CERRADO",
        "suspender": "SUSPENDIDO",
        "reactivar": "REACTIVADO",
        "eliminar": "ELIMINADO",
        "restaurar": "RESTAURADO",
        "nota": "ACTUALIZADO",
    }
    audit(c, acciones[accion], detalle or acciones[accion].capitalize(), user)
    return c
