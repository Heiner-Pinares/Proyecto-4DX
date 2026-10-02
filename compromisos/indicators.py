"""Aplicables = no suspendidos. Plazo = cerrados no suspendidos con objetivo y fecha real.
Meta = promedio de cocientes individuales válidos; nunca se limita a 100%.
"""

from django.conf import settings
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q
from django.db.models.functions import Cast


def metricas(qs):
    closed = Q(estatus=settings.CLOSED_STATUS_CODE)
    applicable = Q(suspendida=False)
    result = qs.aggregate(
        promedio_fechas=Avg("cumplimiento_fechas", filter=Q(suspendida=False)),
        total=Count("id"),
        terminados=Count("id", filter=closed),
        abiertos=Count("id", filter=~closed),
        pendientes=Count("id", filter=Q(estatus=settings.PENDING_STATUS_CODE)),
        proceso=Count("id", filter=Q(estatus=settings.IN_PROGRESS_STATUS_CODE)),
        vencidos=Count("id", filter=Q(situacion="Vencido")),
        proximos=Count("id", filter=Q(situacion="Por vencer")),
        suspendidos=Count("id", filter=Q(suspendida=True)),
        a_tiempo=Count("id", filter=Q(situacion="Cumplido a tiempo")),
        fuera_plazo=Count("id", filter=Q(situacion="Cumplido fuera de plazo")),
        sin_fecha=Count("id", filter=Q(situacion="Por definir")),
        aplicables=Count("id", filter=applicable),
        cerrados_aplicables=Count("id", filter=applicable & closed),
        cerrados_fecha=Count(
            "id",
            filter=applicable
            & closed
            & Q(fecha_real__isnull=False, objetivo__isnull=False),
        ),
        cerrados_tiempo=Count("id", filter=closed & Q(situacion="Cumplido a tiempo")),
        puntaje_promedio=Avg("puntaje"),
        meta_promedio=Avg("meta"),
        cumplimiento_meta=Avg(
            ExpressionWrapper(
                Cast(F("puntaje"), FloatField()) * 100.0 / F("meta"),
                output_field=FloatField(),
            ),
            filter=Q(meta__gt=0, puntaje__isnull=False),
        ),
    )
    result["cumplimiento_fechas"] = result.pop("promedio_fechas")
    result["puntaje"] = result.pop("puntaje_promedio")
    result["meta"] = result.pop("meta_promedio")
    result["reprogramados"] = (
        qs.filter(
            Q(primera_fecha__isnull=False)
            | Q(segunda_fecha__isnull=False)
            | Q(tercera_fecha__isnull=False)
            | Q(eventos__tipo="reprogramacion")
        )
        .distinct()
        .count()
    )
    result["cumplimiento_cierre"] = (
        result["cerrados_aplicables"] / result["aplicables"] * 100
        if result["aplicables"]
        else 0
    )
    result["cumplimiento_plazo"] = (
        result["cerrados_tiempo"] / result["cerrados_fecha"] * 100
        if result["cerrados_fecha"]
        else 0
    )
    for name in ["terminados", "vencidos", "proximos", "suspendidos", "proceso"]:
        result[name + "_porcentaje"] = result[name] * 100 / result["total"] if result["total"] else 0
    return result


def agrupados(qs, field):
    rows = list(
        qs.order_by()
        .values(field)
        .annotate(
            total=Count("id"),
            terminados=Count("id", filter=Q(estatus=settings.CLOSED_STATUS_CODE)),
            pendientes=Count("id", filter=Q(estatus=settings.PENDING_STATUS_CODE)),
            vencidos=Count("id", filter=Q(situacion="Vencido")),
            suspendidos=Count("id", filter=Q(suspendida=True)),
            a_tiempo=Count("id", filter=Q(situacion="Cumplido a tiempo")),
            aplicables=Count("id", filter=Q(suspendida=False)),
            cerrados=Count(
                "id", filter=Q(suspendida=False, estatus=settings.CLOSED_STATUS_CODE)
            ),
            puntaje=Avg("puntaje"),
            cumplimiento_fechas_promedio=Avg(
                "cumplimiento_fechas", filter=Q(suspendida=False)
            ),
        )
        .order_by(field)
    )
    for row in rows:
        row["nombre"] = str(row[field] or "Sin definir")
        row["cumplimiento_cierre"] = (
            round(row["cerrados"] / row["aplicables"] * 100, 2)
            if row["aplicables"]
            else 0
        )
        row["cumplimiento"] = round(row["cumplimiento_fechas_promedio"] or 0, 2)
    return rows
