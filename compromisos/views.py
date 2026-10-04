from datetime import date, datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count
from django.db.models.functions import TruncMonth, TruncWeek
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin

from .forms import AccionForm, CompromisoForm
from .indicators import agrupados, metricas
from .models import Compromiso, EventoCompromiso
from .permissions import require
from .reports import excel, word, correo_contexto
from .selectors import SITUACIONES, base, filtrar
from .services import guardar, operar


def filtros(request):
    choices = {
        field: Compromiso.objects.order_by(field)
        .values_list(field, flat=True)
        .distinct()
        for field in ["tema", "iniciativa", "responsable_pyp", "mes"]
    }
    return {
        "opciones": choices,
        "jefaturas": Compromiso.JEFATURAS,
        "estados": EventoCompromiso.estados.filter(codigo__in=["EC", "S", "T", "D"]),
        "situaciones": SITUACIONES,
        "f": request.GET,
        "estatus_seleccionados": request.GET.getlist("status"),
        "etapas_fecha": request.GET.getlist("etapa_fecha"),
    }


def pagina(request, qs):
    size = request.GET.get("size", "25")
    size = int(size) if size in ["10", "25", "50", "100"] else 25
    params = request.GET.copy()
    params.pop("page", None)
    return {
        "page_obj": Paginator(qs, size).get_page(request.GET.get("page")),
        "query": params.urlencode(),
        "size": size,
    }


@login_required
def dashboard(request):
    qs = filtrar(request.GET)
    ctx = {
        "title": "Tu avance en un vistazo",
        "k": metricas(qs),
        "proximos": qs.filter(situacion="Por vencer").order_by("objetivo")[:8],
        "vencidos": qs.filter(situacion="Vencido").order_by("objetivo")[:8],
        "today": timezone.localdate(),
    }
    attention = list(qs.filter(situacion__in=["Por vencer", "Vencido"]).order_by("objetivo")[:10])
    for item in attention:
        item.dias = (item.objetivo - ctx["today"]).days
    ctx["atencion"] = attention
    return render(request, "dashboard.html", ctx)


@login_required
def listado(request):
    from .grid import COLUMNS, fila

    qs = filtrar(request.GET)
    sort = request.GET.get("orden", "-created_at")
    sortable = {"jefatura", "responsable_pyp", "iniciativa", "tarea", "fecha_de_compromiso", "primera_fecha", "segunda_fecha", "tercera_fecha", "created_at", "puntaje", "estatus"}
    if sort.lstrip("-") not in sortable:
        sort = "-created_at"
    qs = qs.order_by(sort, "id")
    page = pagina(request, qs)
    rows = [fila(c) for c in page["page_obj"]]

    return render(
        request,
        "compromisos/list.html",
        {
            "title": "Compromisos",
            **filtros(request),
            **page,
            "k": metricas(qs),
            "columns": [{"name": n, "label": l, "kind": k} for n, l, k in COLUMNS],
            "rows": rows,
            "grid_options": list(
                EventoCompromiso.estados.filter(activo=True, codigo__in=["EC", "S", "T", "D"]).values("codigo", "nombre")
            ),
        },
    )


@login_required
def detalle(request, pk):
    c = get_object_or_404(
        base(), pk=pk
    )

    def presentar(value):
        if isinstance(value, datetime):
            return timezone.localtime(value).strftime("%d/%m/%Y %H:%M")
        if isinstance(value, date):
            return value.strftime("%d/%m/%Y")
        if isinstance(value, bool):
            return "Sí" if value else "No"
        return value

    etiquetas = {
        "created_at": "Creado el",
        "updated_at": "Actualizado el",
        "created_by": "Creado por",
        "updated_by": "Actualizado por",
    }
    campos = [
        (
            etiquetas.get(field.name, str(field.verbose_name).capitalize()),
            presentar(c.estatus_actual if field.name == "status" else getattr(c, field.name)),
        )
        for field in c._meta.fields
        if field.name not in ["id", "tarea", "deleted_at"]
    ]
    return render(
        request,
        "compromisos/detail.html",
        {"title": f"Compromiso #{c.pk}", "c": c, "campos": campos},
    )


@login_required
def editar(request, pk=None):
    require(request.user, edit=True)
    c = get_object_or_404(Compromiso, pk=pk) if pk else None
    form = CompromisoForm(
        request.POST if request.method == "POST" else None, instance=c
    )
    if request.method == "POST" and form.is_valid():
        try:
            obj = guardar(form.cleaned_data, request.user, pk)
            messages.success(
                request,
                "Compromiso actualizado correctamente."
                if pk
                else "Compromiso creado correctamente.",
            )
            return redirect("detalle", pk=obj.pk)
        except ValidationError as error:
            form.add_error(None, error)
    return render(
        request,
        "compromisos/form.html",
        {"title": "Editar compromiso" if pk else "Nuevo compromiso", "form": form},
    )


ACCIONES = {
    "reprogramar": "Reprogramar compromiso",
    "cerrar": "Marcar como terminado",
    "suspender": "Suspender compromiso",
    "reactivar": "Reactivar compromiso",
    "eliminar": "Eliminar compromiso",
    "restaurar": "Restaurar compromiso",
    "purgar": "Eliminar definitivamente",
    "nota": "Registrar nota",
}


@login_required
def accion(request, pk, accion):
    if accion not in ACCIONES:
        raise Http404
    require(
        request.user,
        administrative=accion in ["eliminar", "restaurar", "purgar"],
        edit=accion not in ["eliminar", "restaurar", "purgar"],
    )
    c = get_object_or_404(
        Compromiso.all_objects
        if accion in ["restaurar", "purgar"]
        else Compromiso.objects,
        pk=pk,
    )
    form = AccionForm(request.POST if request.method == "POST" else None, accion=accion)
    if request.method == "POST" and form.is_valid():
        try:
            operar(pk, accion, form.cleaned_data, request.user)
            messages.success(request, "Operación realizada correctamente.")
            return redirect(
                "papelera" if accion in ["eliminar", "purgar"] else "detalle",
                **({} if accion in ["eliminar", "purgar"] else {"pk": pk}),
            )
        except ValidationError as error:
            form.add_error(None, error.messages)
    return render(
        request,
        "compromisos/action.html",
        {"title": ACCIONES[accion], "form": form, "c": c, "accion": accion},
    )


@login_required
def papelera(request):
    require(request.user, administrative=True)
    return render(
        request,
        "compromisos/trash.html",
        {
            "title": "Papelera",
            **pagina(request, Compromiso.all_objects.filter(deleted_at__isnull=False)),
        },
    )


@login_required
def indicadores(request):
    qs = filtrar(request.GET)
    responsables = agrupados(qs, "responsable_pyp")
    sort = request.GET.get("orden", "nombre")
    allowed = [
        "nombre",
        "total",
        "terminados",
        "pendientes",
        "vencidos",
        "suspendidos",
        "a_tiempo",
        "cumplimiento",
        "puntaje",
    ]
    if sort.lstrip("-") in allowed:
        responsables.sort(
            key=lambda r: (
                r[sort.lstrip("-")] or 0
                if sort.lstrip("-") != "nombre"
                else r["nombre"]
            ),
            reverse=sort.startswith("-"),
        )
    status = list(
        qs.order_by().values("estatus").annotate(total=Count("id")).order_by("estatus")
    )
    meses = agrupados(qs.annotate(periodo=TruncMonth("fecha_de_compromiso")), "periodo")
    reschedules = list(
        EventoCompromiso.objects.filter(tipo="reprogramacion", compromiso__in=qs)
        .annotate(periodo=TruncMonth("fecha"))
        .values("periodo")
        .annotate(total=Count("id"))
        .order_by("periodo")
    )
    charts = [
        {
            "title": "Compromisos por estado",
            "type": "donut",
            "labels": [r["estatus"] for r in status],
            "values": [r["total"] for r in status],
        },
        {
            "title": "Compromisos por responsable",
            "labels": [r["nombre"] for r in responsables],
            "values": [r["total"] for r in responsables],
        },
        {
            "title": "Cumplimiento de fechas por responsable",
            "labels": [r["nombre"] for r in responsables],
            "values": [r["cumplimiento"] for r in responsables],
        },
    ]
    for field, title in [("tema", "tema"), ("iniciativa", "iniciativa")]:
        rows = agrupados(qs, field)
        charts.append(
            {
                "title": f"Cumplimiento de fechas por {title}",
                "labels": [r["nombre"] for r in rows],
                "values": [r["cumplimiento"] for r in rows],
            }
        )
    charts.extend(
        [
            {
                "title": "Evolución mensual del cumplimiento de fechas",
                "type": "line",
                "labels": [r["nombre"] for r in meses],
                "values": [r["cumplimiento"] for r in meses],
            },
            {
                "title": "Vencidos por responsable",
                "labels": [r["nombre"] for r in responsables],
                "values": [r["vencidos"] for r in responsables],
            },
            {
                "title": "Reprogramaciones por mes",
                "labels": [r["periodo"].strftime("%m/%Y") for r in reschedules],
                "values": [r["total"] for r in reschedules],
            },
        ]
    )
    jefaturas = agrupados(qs, "jefatura")
    completed = list(qs.filter(fecha_real__isnull=False, suspendida=False, cumplimiento_fechas=100).annotate(semana=TruncWeek("fecha_real")).values("semana").annotate(total=Count("id")).order_by("semana"))
    replanned = list(EventoCompromiso.objects.filter(tipo="reprogramacion", compromiso__in=qs).annotate(semana=TruncWeek("fecha")).values("semana").annotate(total=Count("id")).order_by("semana"))
    overview = [
        {"title": "Cumplimiento por jefaturas", "type": "vertical", "unit": "%", "labels": [r["nombre"].replace("Jefatura de ", "") for r in jefaturas], "values": [r["cumplimiento"] for r in jefaturas]},
        {"title": "Estado de los compromisos", "type": "donut", "labels": [dict(Compromiso._meta.get_field("status").choices).get(r["estatus"], r["estatus"]) for r in status], "values": [r["total"] for r in status]},
    ]
    for label, data in [("Evolutivo de compromisos culminados a primera fecha", completed), ("Evolutivo de reprogramaciones", replanned)]:
        overview.append({"title": label, "type": "line", "unit": "", "labels": [r["semana"].strftime("%d/%m/%y") for r in data], "values": [r["total"] for r in data]})
    charts = overview + charts
    return render(
        request,
        "indicadores.html",
        {
            "title": "Indicadores",
            "k": metricas(qs),
            "responsables": responsables,
            "charts": charts,
            **filtros(request),
        },
    )


@login_required
def reportes(request):
    from .correo import token_correo
    try:
        corte = date.fromisoformat(request.GET.get("corte") or timezone.localdate().isoformat())
    except ValueError:
        return HttpResponse("Fecha de corte no válida.", status=400)
    params = request.GET.copy()
    params["corte"] = corte.isoformat()
    params.pop("descargar", None)
    return render(
        request,
        "reportes.html",
        {
            "title": "Reportes ejecutivos",
            "today": corte.isoformat(),
            "correo_query": params.urlencode(),
            "correo_token": token_correo(request.user, params.urlencode()),
            **filtros(request),
        },
    )


@login_required
def exportar(request, formato):
    qs = filtrar(request.GET)
    if formato == "xlsx":
        data, mime, name = (
            excel(qs),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "Compromisos.xlsx",
        )
    elif formato == "docx":
        try:
            corte = date.fromisoformat(
                request.GET.get("corte") or timezone.localdate().isoformat()
            )
        except ValueError:
            return HttpResponse("Fecha de corte no válida.", status=400)
        data, mime, name = (
            word(qs, corte),
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            f"Reporte_Compromisos_{corte:%Y%m%d}.docx",
        )
    else:
        raise Http404
    response = HttpResponse(data, content_type=mime)
    response["Content-Disposition"] = f'attachment; filename="{name}"'
    return response


@login_required
def celda(request, pk):
    import json

    from django.http import JsonResponse

    from .grid import ConflictoEdicion, editar_celda, fila

    require(request.user, edit=True)
    if request.method != "POST":
        return JsonResponse({"error": "Usa POST para guardar."}, status=405)
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict):
            raise ValueError
        c = editar_celda(pk, payload, request.user)
        return JsonResponse({"row": fila(c), "message": "Cambio guardado."})
    except (ValueError, UnicodeDecodeError):
        return JsonResponse({"error": "Solicitud no válida."}, status=400)
    except ValidationError as error:
        return JsonResponse({"error": " ".join(error.messages)}, status=400)
    except ConflictoEdicion as error:
        return JsonResponse({"error": str(error)}, status=409)
    except Compromiso.DoesNotExist:
        return JsonResponse(
            {"error": "El compromiso ya no está disponible."}, status=404
        )


@login_required
@xframe_options_sameorigin
def correo_reporte(request):
    try:
        corte = date.fromisoformat(request.GET.get("corte") or timezone.localdate().isoformat())
    except ValueError:
        return HttpResponse("Fecha de corte no válida.", status=400)
    response = render(request, "correo_compromisos.html", correo_contexto(filtrar(request.GET, corte), corte))
    response["Cache-Control"] = "private, no-store"
    if request.GET.get("descargar") == "1":
        response["Content-Disposition"] = f'attachment; filename="Correo_Compromisos_{corte:%Y%m%d}.html"'
    return response


@login_required
@xframe_options_sameorigin
def resumen_semanal(request):
    from .reports import resumen_jefaturas
    from django.conf import settings
    from django.urls import reverse
    try:
        corte = date.fromisoformat(request.GET.get('corte') or timezone.localdate().isoformat())
    except ValueError:
        return HttpResponse('Fecha de corte no válida.', status=400)
    context = resumen_jefaturas(filtrar(request.GET, corte), corte)
    context['tablero_url'] = (settings.PORTAL_PUBLIC_URL or request.build_absolute_uri('/').rstrip('/')) + reverse('dashboard')
    response = render(request, 'resumen_semanal.html', context)
    response['Cache-Control'] = 'private, no-store'
    if request.GET.get('descargar') == '1':
        response['Content-Disposition'] = f'attachment; filename="Resumen_4DX_{corte:%Y%m%d}.html"'
    return response
