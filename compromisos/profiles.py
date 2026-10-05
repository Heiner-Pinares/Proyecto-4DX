"""Datos organizacionales de usuarios sin añadir una tabla física al portal."""

import json

from .models import EventoCompromiso


PROFILE_FIELDS = ("nombre_completo", "area", "gerencia", "direccion", "jefe")


def profile_data(record):
    if not record:
        return {field: "" for field in PROFILE_FIELDS}
    try:
        raw = json.loads(record.descripcion or "{}")
    except (TypeError, ValueError):
        raw = {}
    return {field: str(raw.get(field) or "").strip() for field in PROFILE_FIELDS}


def profiles_for(users):
    users = list(users)
    records = {
        row.user_id: row
        for row in EventoCompromiso.perfiles.filter(user_id__in=[u.pk for u in users])
        .order_by("user_id", "pk")
    }
    return {user.pk: profile_data(records.get(user.pk)) for user in users}


def save_profile(user, **values):
    data = {field: str(values.get(field) or "").strip() for field in PROFILE_FIELDS}
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True)
    record = EventoCompromiso.perfiles.filter(user=user).order_by("pk").first()
    if record:
        record.descripcion = payload
        record.nombre = data["area"][:100]
        record.usuario = user.get_username()
        record.save(update_fields=["descripcion", "nombre", "usuario"])
        EventoCompromiso.perfiles.filter(user=user).exclude(pk=record.pk).delete()
        return record
    return EventoCompromiso.perfiles.create(
        user=user,
        usuario=user.get_username(),
        nombre=data["area"][:100],
        descripcion=payload,
    )
