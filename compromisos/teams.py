"""Recordatorios a un chat configurado mediante Teams Workflows."""
import json
import uuid
from datetime import date
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from django.conf import settings
from django.core import signing
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import EventoCompromiso
from .permissions import require
from .reports import correo_contexto
from .selectors import filtrar

SALT = '4dx-teams-send'


def configurado():
    return bool(settings.TEAMS_WEBHOOK_URL)


def token_envio(user, query):
    return signing.dumps({'user': user.pk, 'query': query, 'id': str(uuid.uuid4())}, salt=SALT)


def validar_config(public_url):
    hook = urlsplit(settings.TEAMS_WEBHOOK_URL)
    public = urlsplit(public_url)
    if (hook.scheme != 'https' or not hook.hostname or hook.username or hook.password
            or hook.port not in (None, 443) or hook.fragment
            or not any(hook.hostname.endswith(suffix) for suffix in ('.logic.azure.com', '.api.powerplatform.com', '.environment.api.powerplatform.com'))):
        raise ValueError('Configura una URL HTTPS válida de Teams Workflows en TEAMS_WEBHOOK_URL.')
    if (public.scheme != 'https' or not public.hostname or public.username or public.password
            or public.query or public.fragment or public.path not in ('', '/')
            or public.hostname in ('localhost', '127.0.0.1')):
        raise ValueError('Abre el portal mediante su dirección HTTPS pública antes de enviar a Teams.')


def tarjeta(contexto, query, public_url):
    summary = contexto['resumen']
    def block(text, **extra):
        return {'type': 'TextBlock', 'text': text, 'wrap': True, **extra}
    body = [block('4DX · Recordatorio de compromisos', weight='Bolder', size='Large'),
            block(f"Corte: {contexto['corte']:%d/%m/%Y}"),
            block(f"Pendientes: {summary['total']} · Vencidos: {summary['vencidos']} · Por vencer: {summary['por_vencer']} · En plazo: {summary['en_plazo']} · Sin fecha: {summary['sin_fecha']}"),
            block('Por favor, actualizar el avance, las fechas y las observaciones en el portal.')]
    # Campos acotados: la tarjeta es un recordatorio; el enlace contiene el reporte completo.
    for row in contexto['rows'][:10]:
        objetivo = row.objetivo.strftime('%d/%m/%Y') if row.objetivo else 'Por definir'
        referencia = row.proyecto[:80] + (f" / {row.iniciativa[:80]}" if row.iniciativa else "")
        body.append(block(f"#{row.pk} · {referencia}\n{row.tarea[:350]}\nResponsable: {row.responsable_pyp[:100]} · Objetivo: {objetivo} · {row.situacion}", separator=True))
    body.append(block(f"Se muestran {min(summary['total'], 10)} de {summary['total']} pendientes. Datos actuales y filtros del reporte; no reconstruye estados históricos.", size='Small'))
    url = public_url.rstrip('/') + reverse('correo_reporte') + '?' + query
    card = {'type':'AdaptiveCard', 'version':'1.2', '$schema':'http://adaptivecards.io/schemas/adaptive-card.json',
            'body':body, 'actions':[{'type':'Action.OpenUrl','title':'Ver reporte completo (iniciar sesión)','url':url}]}
    return {'type':'message','attachments':[{'contentType':'application/vnd.microsoft.card.adaptive','contentUrl':None,'content':card}]}


class SinRedireccion(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def enviar(payload):
    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    if len(data) > 24000:
        raise ValueError('El resumen supera el tamaño permitido. Aplica más filtros antes de enviar.')
    req = Request(settings.TEAMS_WEBHOOK_URL, data=data, headers={'Content-Type':'application/json'}, method='POST')
    with build_opener(SinRedireccion()).open(req, timeout=15) as response:
        if not 200 <= response.status < 300:
            raise ValueError('Teams no aceptó la solicitud.')


@login_required
@require_POST
def enviar_recordatorio(request):
    require(request.user, edit=True)
    try:
        claim = signing.loads(request.POST.get('token', ''), salt=SALT, max_age=3600)
        query = request.GET.urlencode()
        if claim['user'] != request.user.pk or claim['query'] != query:
            raise ValueError('Actualiza la vista previa antes de enviar.')
        public_url = settings.PORTAL_PUBLIC_URL or request.build_absolute_uri('/').rstrip('/')
        validar_config(public_url)
        corte = date.fromisoformat(request.GET.get('corte') or timezone.localdate().isoformat())
        context = correo_contexto(filtrar(request.GET, corte), corte)
        if not context['rows']:
            raise ValueError('No hay compromisos pendientes para enviar con estos filtros.')
        payload = tarjeta(context, query, public_url)
    except signing.BadSignature:
        return HttpResponse('La solicitud venció o no es válida. Recarga Reportes.', status=400)
    except (ValueError, KeyError) as error:
        messages.error(request, str(error))
        return redirect(reverse('reportes') + '?' + request.GET.urlencode())
    try:
        with transaction.atomic():
            record = EventoCompromiso.envios.create(canal='teams', token=claim['id'], usuario=request.user.get_username(), corte=corte, total=context['resumen']['total'])
    except IntegrityError:
        messages.info(request, 'Este envío ya fue procesado o sigue en curso. No se ha repetido.')
        return redirect(reverse('reportes') + '?' + query)
    try:
        enviar(payload)
    except HTTPError:
        record.estado = 'rechazado'
        messages.error(request, 'El flujo rechazó la solicitud. Revisa la configuración y el historial de Workflows.')
    except (URLError, TimeoutError, OSError):
        record.estado = 'sin_confirmacion'
        messages.error(request, 'No se pudo confirmar la recepción. Revisa el chat y el historial de Workflows antes de volver a enviar.')
    except ValueError as error:
        record.estado = 'rechazado'
        messages.error(request, str(error))
    else:
        record.estado = 'aceptado'
        messages.success(request, 'El flujo de Teams aceptó el recordatorio para 4DX. Comprueba su publicación en el chat.')
    record.save(update_fields=['estado'])
    return redirect(reverse('reportes') + '?' + query)
