"""Estatus derivado de suspensión, fecha real y plazo vigente."""
from django.utils import timezone
from django.db.models import Case, When, Value, CharField


def calcular_estatus(c, hoy=None):
    hoy = hoy or timezone.localdate()
    objetivo = c.tercera_fecha or c.segunda_fecha or c.primera_fecha or c.fecha_de_vencimiento
    if c.suspendida:
        return "S"
    if c.fecha_real:
        return "T"
    return "D" if objetivo and objetivo < hoy else "EC"


def expresion_estatus(hoy):
    return Case(
        When(suspendida=True, then=Value("S")),
        When(fecha_real__isnull=False, then=Value("T")),
        When(objetivo__lt=hoy, then=Value("D")),
        default=Value("EC"), output_field=CharField(),
    )
