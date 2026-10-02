"""Estatus derivado de suspensión, fecha real y plazo vigente."""
from django.utils import timezone
from django.db.models import Case, CharField, Value, When
from django.db.models.functions import Cast


def calcular_estatus(c, hoy=None):
    hoy = hoy or timezone.localdate()
    objetivo = c.tercera_fecha or c.segunda_fecha or c.primera_fecha or c.fecha_de_vencimiento
    if c.suspendida:
        return "S"
    if c.fecha_real:
        return "T"
    return "D" if objetivo and objetivo < hoy else "EC"


def expresion_estatus(hoy):
    # Oracle almacena los CharField de Django como NVARCHAR2. Sin el CAST, el
    # CASE puede resolverse como VARCHAR2 y después fallar al compararse con
    # columnas NVARCHAR2 (ORA-12704).
    return Cast(
        Case(
            When(suspendida=True, then=Value("S")),
            When(fecha_real__isnull=False, then=Value("T")),
            When(objetivo__lt=hoy, then=Value("D")),
            default=Value("EC"),
            output_field=CharField(max_length=2),
        ),
        CharField(max_length=2),
    )
