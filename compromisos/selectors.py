from datetime import date, timedelta

from django.conf import settings
from django.db.models import Case, CharField, F, OuterRef, Q, Subquery, Value, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import Compromiso, Estado
from .scoring import expresion_puntaje
from .status import expresion_estatus

SITUACIONES = [
    "Suspendido",
    "Por definir",
    "Cumplido a tiempo",
    "Cumplido fuera de plazo",
    "Vencido",
    "Por vencer",
    "En plazo",
]


def base(hoy=None):
    hoy = hoy or timezone.localdate()
    return Compromiso.objects.annotate(
        objetivo=Coalesce(
            "tercera_fecha", "segunda_fecha", "primera_fecha", "fecha_de_vencimiento"
        )
    ).annotate(estatus=expresion_estatus(hoy)).annotate(
        cumplimiento_fechas=expresion_puntaje(),
        estado_nombre=Coalesce(
            Subquery(
                Estado.objects.filter(codigo=OuterRef("estatus")).values("nombre")[:1]
            ),
            F("estatus"),
        ),
        situacion=Case(
            When(suspendida=True, then=Value("Suspendido")),
            When(objetivo__isnull=True, then=Value("Por definir")),
            When(fecha_real__lte=F("objetivo"), then=Value("Cumplido a tiempo")),
            When(fecha_real__gt=F("objetivo"), then=Value("Cumplido fuera de plazo")),
            When(objetivo__lt=hoy, then=Value("Vencido")),
            When(
                objetivo__lte=hoy + timedelta(days=settings.DUE_SOON_DAYS),
                then=Value("Por vencer"),
            ),
            default=Value("En plazo"),
            output_field=CharField(),
        ),
    )


def filtrar(params, hoy=None):
    qs = base(hoy)
    if params.get("q"):
        q = Q()
        for field in ["tema", "iniciativa", "tarea", "responsable_pyp", "notas"]:
            q |= Q(**{field + "__icontains": params["q"]})
        qs = qs.filter(q)
    for field in [
        "tema",
        "iniciativa",
        "responsable_pyp",
        "status",
        "mes",
        "situacion",
    ]:
        if params.get(field):
            qs = qs.filter(**{"estatus" if field == "status" else field: params[field]})
    for field in ["compromiso_hch", "suspendida"]:
        if params.get(field) in ["true", "false"]:
            qs = qs.filter(**{field: params[field] == "true"})
    if params.get("anio", "").isdigit() and 1 <= int(params["anio"]) <= 9999:
        qs = qs.filter(fecha_de_compromiso__year=int(params["anio"]))
    for key, lookup in [("desde", "objetivo__gte"), ("hasta", "objetivo__lte")]:
        try:
            if params.get(key):
                qs = qs.filter(**{lookup: date.fromisoformat(params[key])})
        except ValueError:
            pass
    return qs
