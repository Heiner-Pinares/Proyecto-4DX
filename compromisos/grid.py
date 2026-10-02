"""Contrato de columnas compartido por la tabla y el endpoint de edición."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max

from .models import Compromiso, EventoCompromiso
from .permissions import require
from .services import audit

COLUMNS = [
    ("compromiso_hch", "HCH", "boolean"),
    ("tema", "Tema", "text"),
    ("iniciativa", "Iniciativa", "text"),
    ("tarea", "Tarea", "textarea"),
    ("status", "Estatus", "readonly"),
    ("meta", "Meta", "number"),
    ("responsable_pyp", "Responsable", "text"),
    ("jefatura", "Jefatura", "select"),
    ("mes", "Mes", "readonly"),
    ("fecha_de_compromiso", "Fecha de compromiso", "date"),
    ("fecha_de_vencimiento", "Vencimiento", "readonly"),
    ("fecha_real", "Fecha real", "date"),
    ("puntaje", "Cumplimiento %", "readonly"),
    ("primera_fecha", "1ERA FECHA", "date"),
    ("segunda_fecha", "2DA FECHA", "date"),
    ("tercera_fecha", "3RA FECHA", "date"),
    ("notas", "Notas", "textarea"),
    ("suspendida", "Suspendida", "boolean"),
    ("situacion_plazo", "Situación", "readonly"),
]
EDITABLE = {name: kind for name, _, kind in COLUMNS if kind != "readonly"}
DEADLINES = ["primera_fecha", "segunda_fecha", "tercera_fecha"]


class ConflictoEdicion(Exception):
    pass


def fila(c):
    cells = []
    for name, label, kind in COLUMNS:
        value = c.estatus_actual if name == "status" else getattr(c, name)
        raw = (
            value.isoformat()
            if isinstance(value, date)
            else str(value)
            if isinstance(value, Decimal)
            else value
        )
        display = (
            value.strftime("%d/%m/%Y")
            if isinstance(value, date)
            else "Sí"
            if value is True
            else "No"
            if value is False
            else str(value)
            if value is not None and value != ""
            else "—"
        )
        if name == "puntaje" and value is not None:
            display = f"{int(value)} %"
        cells.append(
            {
                "name": name,
                "label": label,
                "kind": kind,
                "value": raw,
                "display": display,
                "editable": name in EDITABLE,
                "options": ([{"codigo": "", "nombre": "Sin asignar"}] + [{"codigo": code, "nombre": label} for code, label in Compromiso.JEFATURAS]) if name == "jefatura" else None,
            }
        )
    return {"id": c.pk, "version": c.updated_at.isoformat(), "cells": cells}


@transaction.atomic
def editar_celda(pk, payload, user):
    require(user, edit=True)
    c = Compromiso.objects.select_for_update().get(pk=pk)
    if payload.get("version") != c.updated_at.isoformat():
        raise ConflictoEdicion(
            "Esta fila cambió desde que la abriste. Recarga la tabla antes de volver a editar."
        )
    name = payload.get("field")
    if not isinstance(name, str) or name not in EDITABLE:
        raise ValidationError(
            "Esta columna se calcula automáticamente o no es editable."
        )
    value = payload.get("value")
    if isinstance(value, (list, dict)):
        raise ValidationError("Valor no válido.")
    if EDITABLE[name] == "boolean":
        if not isinstance(value, bool):
            raise ValidationError("Selecciona Sí o No.")
    else:
        field = c._meta.get_field(name).formfield()
        value = field.clean(value)
    if (
        name == "status"
        and value != c.status
        and not EventoCompromiso.estados.filter(codigo=value, activo=True).exists()
    ):
        raise ValidationError("Selecciona un estado activo.")
    previous = getattr(c, name)
    if previous == value:
        return c
    reason = str(payload.get("reason") or "").strip()
    if name in DEADLINES and not reason:
        raise ValidationError("Indica el motivo del cambio de fecha.")
    score_before = c.puntaje
    setattr(c, name, value)
    if name == "suspendida":
        c.status = "S" if value else ("T" if c.fecha_real else "EC")
    elif name == "status":
        c.suspendida = value == "S"
    first = c.primera_fecha or c.fecha_de_vencimiento
    if name in DEADLINES + ["fecha_de_vencimiento"]:
        if c.segunda_fecha and first and c.segunda_fecha < first:
            raise ValidationError(
                "La segunda fecha no puede ser anterior a la primera."
            )
        if c.tercera_fecha and c.tercera_fecha < (
            c.segunda_fecha or first or c.tercera_fecha
        ):
            raise ValidationError(
                "La tercera fecha no puede ser anterior a la fecha previa."
            )
    c.full_clean()
    c.updated_by = user.get_username()
    c.save()
    detail = f"{dict((n, l) for n, l, _ in COLUMNS)[name]}: {previous} → {value}."
    if reason:
        detail += f" Motivo: {reason}."
    if name in DEADLINES and value:
        number = (
            c.reprogramaciones.aggregate(n=Max("numero_reprogramacion"))["n"] or 0
        ) + 1
        EventoCompromiso.objects.create(
            compromiso=c,
            tipo="reprogramacion",
            numero_reprogramacion=number,
            fecha_anterior=previous,
            fecha_nueva=value,
            motivo=f"{name}: {reason}",
            usuario=user.get_username(),
        )
    if c.puntaje != score_before:
        detail += f" Cumplimiento recalculado: {score_before} → {c.puntaje} %."
    audit(c, "REPROGRAMADO" if name in DEADLINES else "ACTUALIZADO", detail, user)
    return c
