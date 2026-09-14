"""Cumplimiento de fechas: primera 100, segunda 80, demás cierres 60.
Sin fecha real no se asigna puntaje. La primera fecha usa el vencimiento
original como respaldo. Las comparaciones incluyen el día comprometido.
"""

from django.db.models import Case, F, IntegerField, Value, When
from django.db.models.functions import Coalesce


def calcular_puntaje(c):
    if not c.fecha_real:
        return None
    primera = c.primera_fecha
    if primera and c.fecha_real <= primera:
        return 100
    if c.segunda_fecha and c.fecha_real <= c.segunda_fecha:
        return 80
    return 60


def expresion_puntaje():
    return Case(
        When(fecha_real__isnull=True, then=Value(None)),
        When(
            fecha_real__lte=F("primera_fecha"),
            then=Value(100),
        ),
        When(fecha_real__lte=F("segunda_fecha"), then=Value(80)),
        default=Value(60),
        output_field=IntegerField(),
    )
