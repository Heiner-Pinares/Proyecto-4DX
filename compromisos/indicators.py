"""Aplicables = no suspendidos. Plazo = cerrados no suspendidos con objetivo y fecha real.
Meta = promedio de cocientes individuales válidos; nunca se limita a 100%.
"""

from collections import defaultdict

from django.conf import settings
from django.db.models import Avg, Count, ExpressionWrapper, F, FloatField, Q
from django.db.models.functions import Cast

from .models import EventoCompromiso


MESES_CORTOS = [
    "",
    "Ene",
    "Feb",
    "Mar",
    "Abr",
    "May",
    "Jun",
    "Jul",
    "Ago",
    "Sep",
    "Oct",
    "Nov",
    "Dic",
]


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
            Q(segunda_fecha__isnull=False)
            | Q(tercera_fecha__isnull=False)
            | Q(eventos__tipo="reprogramacion")
        )
        .order_by()
        .values("pk")
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


def evolucion_mensual(qs, max_meses=12):
    """Comparativo mensual según la primera fecha objetivo del compromiso.

    Un compromiso reprogramado es aquel con segunda/tercera fecha o con evento
    de reprogramación. La primera fecha por sí sola es el vencimiento inicial.
    """
    rows = list(
        qs.order_by().values(
            "id",
            "primera_fecha",
            "fecha_de_vencimiento",
            "segunda_fecha",
            "tercera_fecha",
            "fecha_real",
            "suspendida",
            "meta",
        )
    )
    ids = [row["id"] for row in rows]
    with_event = set(
        EventoCompromiso.objects.filter(
            tipo="reprogramacion", compromiso_id__in=ids
        ).values_list("compromiso_id", flat=True)
    )
    months = defaultdict(
        lambda: {"total": 0, "cumplidos": 0, "reprogramados": 0, "metas": []}
    )
    for row in rows:
        first_due = row["primera_fecha"] or row["fecha_de_vencimiento"]
        if not first_due or row["suspendida"]:
            continue
        key = (first_due.year, first_due.month)
        bucket = months[key]
        bucket["total"] += 1
        if row["fecha_real"] and row["fecha_real"] <= first_due:
            bucket["cumplidos"] += 1
        if (
            row["segunda_fecha"]
            or row["tercera_fecha"]
            or row["id"] in with_event
        ):
            bucket["reprogramados"] += 1
        if row["meta"] is not None and row["meta"] > 0:
            bucket["metas"].append(float(row["meta"]))

    ordered = sorted(months.items())[-max_meses:]
    labels = [f"{MESES_CORTOS[month]} {year}" for (year, month), _ in ordered]
    totals = [values["total"] for _, values in ordered]
    completed = [values["cumplidos"] for _, values in ordered]
    rescheduled = [values["reprogramados"] for _, values in ordered]
    compliance = [
        round(values["cumplidos"] * 100 / values["total"], 1)
        if values["total"]
        else 0
        for _, values in ordered
    ]
    all_targets = [value for _, values in ordered for value in values["metas"]]
    target = round(sum(all_targets) / len(all_targets), 1) if all_targets else 95.0
    latest = (
        {
            "label": labels[-1],
            "total": totals[-1],
            "cumplidos": completed[-1],
            "reprogramados": rescheduled[-1],
            "cumplimiento": compliance[-1],
            "meta": target,
            "brecha": round(target - compliance[-1], 1),
        }
        if labels
        else None
    )
    return {
        "labels": labels,
        "totales": totals,
        "cumplidos": completed,
        "reprogramados": rescheduled,
        "cumplimiento": compliance,
        "meta": target,
        "ultimo": latest,
    }
