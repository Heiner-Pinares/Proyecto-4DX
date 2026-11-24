"""Métricas ejecutivas calculadas sin crear tablas ni instantáneas artificiales.

Los cortes reconstruyen el estado observable a una fecha usando las fechas de
compromiso, cierre y reprogramación existentes. Los atributos organizacionales
y Stand By reflejan su valor vigente, porque el modelo consolidado no guarda
una copia completa de esos campos por cada semana.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta

from django.utils import timezone

from .indicators import MESES_CORTOS
from .models import EventoCompromiso


def ultimo_viernes(day: date) -> date:
    return day - timedelta(days=(day.weekday() - 4) % 7)


def opciones_corte(today: date | None = None, cantidad: int = 9):
    today = today or timezone.localdate()
    friday = ultimo_viernes(today)
    options = [{"value": today.isoformat(), "label": f"Semana en curso (al {today:%d/%m})", "current": True}]
    for index in range(cantidad):
        cut = friday - timedelta(days=index * 7)
        if cut == today:
            continue
        options.append({"value": cut.isoformat(), "label": f"vie {cut:%d/%m/%Y}", "current": False})
    return options


def _mover_mes(day: date, offset: int) -> date:
    index = day.year * 12 + day.month - 1 + offset
    return date(index // 12, index % 12 + 1, 1)


def opciones_periodo(today: date | None = None, cantidad: int = 9, ventana: int = 6):
    today = today or timezone.localdate()
    options = []
    for index in range(cantidad):
        month_start = _mover_mes(today, -index)
        end = today if index == 0 else _mover_mes(month_start, 1) - timedelta(days=1)
        start = _mover_mes(month_start, -(ventana - 1))
        label = (
            f"{MESES_CORTOS[start.month]}–{MESES_CORTOS[end.month]} {end.year}"
            if start.year == end.year
            else f"{MESES_CORTOS[start.month]} {start.year}–{MESES_CORTOS[end.month]} {end.year}"
        )
        options.append({"value": end.isoformat(), "label": label})
    return options


def resolver_corte(value: str | None, today: date | None = None) -> date:
    today = today or timezone.localdate()
    default = ultimo_viernes(today)
    if not value:
        return default
    try:
        parsed = date.fromisoformat(value)
    except (TypeError, ValueError):
        return default
    return min(parsed, today)


def _objective(commitment):
    return (
        commitment.tercera_fecha
        or commitment.segunda_fecha
        or commitment.primera_fecha
        or commitment.fecha_de_vencimiento
    )


def _closed_by(commitment, cut: date):
    return bool(commitment.fecha_real and commitment.fecha_real <= cut)


def _on_time_by(commitment, cut: date):
    objective = _objective(commitment)
    return bool(objective and _closed_by(commitment, cut) and commitment.fecha_real <= objective)


def _summary(items, cut: date):
    due = [item for item in items if not item.suspendida and _objective(item) and _objective(item) <= cut]
    on_time = [item for item in due if _on_time_by(item, cut)]
    overdue = [item for item in due if not _closed_by(item, cut)]
    compliance = round(len(on_time) * 100 / len(due), 1) if due else 0
    return {"due": due, "on_time": on_time, "overdue": overdue, "compliance": compliance}


def datos_corte(qs, cut: date):
    items = list(qs)
    previous = cut - timedelta(days=7)
    next_cut = cut + timedelta(days=7)
    current = _summary(items, cut)
    before = _summary(items, previous)
    upcoming = sorted(
        [
            item
            for item in items
            if not item.suspendida
            and not _closed_by(item, cut)
            and _objective(item)
            and cut < _objective(item) <= next_cut
        ],
        key=_objective,
    )
    standby = sorted(
        [item for item in items if item.suspendida],
        key=lambda item: item.updated_at or item.created_at,
    )
    closed_since = [item for item in items if item.fecha_real and previous < item.fecha_real <= cut]
    newly_overdue = [
        item
        for item in items
        if not item.suspendida
        and _objective(item)
        and previous < _objective(item) <= cut
        and not _closed_by(item, cut)
    ]
    ids = [item.pk for item in items]
    rescheduled = EventoCompromiso.objects.filter(
        tipo="reprogramacion",
        compromiso_id__in=ids,
        fecha__date__gt=previous,
        fecha__date__lte=cut,
    ).count()

    offices = []
    office_names = dict(items[0].JEFATURAS) if items else {}
    for value in office_names:
        group = [item for item in items if item.jefatura == value]
        summary = _summary(group, cut)
        office_upcoming = [item for item in upcoming if item.jefatura == value]
        reasons = []
        if summary["overdue"]:
            max_delay = max((cut - _objective(item)).days for item in summary["overdue"])
            reasons.append(f"{len(summary['overdue'])} vencido{'s' if len(summary['overdue']) != 1 else ''} · +{max_delay} d")
        if office_upcoming:
            reasons.append(f"{len(office_upcoming)} por vencer")
        offices.append(
            {
                "value": value,
                "name": office_names.get(value, value).replace("Jefatura de ", ""),
                "overdue": len(summary["overdue"]),
                "upcoming": len(office_upcoming),
                "on_time": len(summary["on_time"]),
                "due": len(summary["due"]),
                "compliance": summary["compliance"],
                "reason": " · ".join(reasons) or "Sin alertas",
                "tone": "green" if not summary["overdue"] else "red",
            }
        )

    return {
        "cut": cut,
        "previous_cut": previous,
        "next_cut": next_cut,
        "compliance": current["compliance"],
        "previous_compliance": before["compliance"],
        "variation": round(current["compliance"] - before["compliance"], 1),
        "due_count": len(current["due"]),
        "on_time_count": len(current["on_time"]),
        "overdue": current["overdue"],
        "upcoming": upcoming,
        "standby": standby,
        "closed_since": len(closed_since),
        "newly_overdue": len(newly_overdue),
        "rescheduled": rescheduled,
        "offices": offices,
    }


def evolucion_cortes(qs, cut: date, cantidad: int = 8):
    items = list(qs)
    cuts = [cut - timedelta(days=7 * index) for index in reversed(range(cantidad))]
    return {
        "labels": [value.strftime("%d/%m") for value in cuts],
        "values": [_summary(items, value)["compliance"] for value in cuts],
        "cuts": [value.isoformat() for value in cuts],
    }


def vencimientos_siguientes(qs, cut: date, cantidad: int = 4):
    items = list(qs)
    labels, counts, risks = [], [], []
    for index in range(cantidad):
        end = cut + timedelta(days=7 * (index + 1))
        start = cut + timedelta(days=7 * index)
        due = [
            item
            for item in items
            if not item.suspendida
            and not _closed_by(item, cut)
            and _objective(item)
            and start < _objective(item) <= end
        ]
        risky = [
            item
            for item in due
            if _objective(item) <= start + timedelta(days=3)
            or item.segunda_fecha
            or item.tercera_fecha
        ]
        labels.append(end.strftime("%d/%m"))
        counts.append(len(due))
        risks.append(len(risky))
    return {"labels": labels, "counts": counts, "risks": risks}


def antiguedad_vencidos(qs, cut: date):
    buckets = [0, 0, 0, 0]
    for item in _summary(list(qs), cut)["overdue"]:
        days = (cut - _objective(item)).days
        index = 0 if days <= 7 else 1 if days <= 15 else 2 if days <= 30 else 3
        buckets[index] += 1
    return {"labels": ["1–7 días", "8–15 días", "16–30 días", "Más de 30 días"], "values": buckets}


def historico_mensual(qs, max_months: int = 6, end_date: date | None = None):
    items = list(qs)
    reprogrammed_ids = set(
        EventoCompromiso.objects.filter(tipo="reprogramacion", compromiso_id__in=[item.pk for item in items])
        .values_list("compromiso_id", flat=True)
    )
    groups = defaultdict(list)
    for item in items:
        first = item.primera_fecha or item.fecha_de_vencimiento
        if first and not item.suspendida:
            groups[(first.year, first.month)].append(item)
    ordered = sorted(
        key for key in groups if end_date is None or key <= (end_date.year, end_date.month)
    )[-max_months:]
    years = {year for year, month in ordered}
    labels = [
        MESES_CORTOS[month] if len(years) == 1 else f"{MESES_CORTOS[month]} {year}"
        for year, month in ordered
    ]
    compliance, reschedule_rate = [], []
    for key in ordered:
        month_items = groups[key]
        on_time = sum(bool(item.fecha_real and item.fecha_real <= (item.primera_fecha or item.fecha_de_vencimiento)) for item in month_items)
        rescheduled = sum(bool(item.segunda_fecha or item.tercera_fecha or item.pk in reprogrammed_ids) for item in month_items)
        compliance.append(round(on_time * 100 / len(month_items), 1))
        reschedule_rate.append(round(rescheduled * 100 / len(month_items), 1))

    offices = []
    office_names = dict(items[0].JEFATURAS) if items else {}
    for value, label in office_names.items():
        values = []
        for key in ordered:
            month_items = [item for item in groups[key] if item.jefatura == value]
            on_time = sum(bool(item.fecha_real and item.fecha_real <= (item.primera_fecha or item.fecha_de_vencimiento)) for item in month_items)
            values.append(round(on_time * 100 / len(month_items), 1) if month_items else None)
        offices.append({"name": label.replace("Jefatura de ", ""), "values": values})
    total = sum(len(groups[key]) for key in ordered)
    total_on_time = sum(
        bool(item.fecha_real and item.fecha_real <= (item.primera_fecha or item.fecha_de_vencimiento))
        for key in ordered
        for item in groups[key]
    )
    return {
        "labels": labels,
        "compliance": compliance,
        "reschedule_rate": reschedule_rate,
        "offices": offices,
        "accumulated": round(total_on_time * 100 / total, 1) if total else 0,
    }
