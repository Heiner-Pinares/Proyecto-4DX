"""Envío SSH/sendmail de reportes 4DX con destinatarios configurados."""
import socket
import shlex
import uuid
from datetime import date
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, formatdate, getaddresses, make_msgid
from pathlib import Path

import paramiko
from django.conf import settings
from django.core import signing
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import validate_email
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import HttpResponse
from django.shortcuts import redirect
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.utils import timezone

from .models import EventoCompromiso
from .permissions import require
from .reports import correo_contexto, resumen_jefaturas
from .selectors import filtrar

PARA = 'c27826@claro.com.pe'
COPIA = 'c28171@claro.com.pe'
SALT = '4dx-correo-semanal'


def _lista_correos(valor, nombre, requerido=False):
    correos = []
    for correo in str(valor or '').replace(';', ',').split(','):
        correo = correo.strip()
        if not correo:
            continue
        try:
            validate_email(correo)
        except ValidationError as error:
            raise ImproperlyConfigured(
                f'{nombre} contiene una dirección de correo no válida.'
            ) from error
        if correo not in correos:
            correos.append(correo)
    if requerido and not correos:
        raise ImproperlyConfigured(f'{nombre} debe incluir al menos un correo.')
    return correos


def destinatarios():
    """Destinatarios definidos por el servidor, nunca por el navegador."""
    return (
        _lista_correos(getattr(settings, 'CORREO_PARA', PARA), 'CORREO_PARA', True),
        _lista_correos(getattr(settings, 'CORREO_COPIA', COPIA), 'CORREO_COPIA'),
    )


def token_correo(user, query, tipo='semanal'):
    return signing.dumps(
        {'user': user.pk, 'query': query, 'tipo': tipo, 'id': str(uuid.uuid4())},
        salt=SALT,
    )


def construir_mensaje(html, corte, tipo='semanal'):
    para, copia = destinatarios()
    msg = EmailMessage(policy=SMTP)
    msg['From'] = formataddr(('4DX Facturación', '4dx@claro.com.pe'))
    msg['To'] = ', '.join(para)
    if copia:
        msg['Cc'] = ', '.join(copia)
    if tipo == 'seguimiento':
        msg['Subject'] = f'Seguimiento de compromisos 4DX · Corte {corte:%d/%m/%Y}'
        texto = 'Recordatorio de compromisos 4DX. Abre este mensaje en un cliente compatible con HTML para consultar el detalle.'
    else:
        msg['Subject'] = f'Resumen semanal 4DX por jefatura · Corte {corte:%d/%m/%Y}'
        texto = 'Resumen semanal de compromisos 4DX. Abre este mensaje en un cliente compatible con HTML para ver el detalle por jefatura.'
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='claro.com.pe')
    msg.set_content(texto)
    msg.add_alternative(html,subtype='html')
    return msg


def enviar_remoto(msg):
    correos = []
    for _, correo in getaddresses(
        [str(valor) for nombre in ('To', 'Cc') for valor in msg.get_all(nombre, [])]
    ):
        correo = correo.strip()
        if correo and correo not in correos:
            try:
                validate_email(correo)
            except ValidationError as error:
                raise ImproperlyConfigured(
                    'El mensaje contiene un destinatario no válido.'
                ) from error
            correos.append(correo)
    if not correos:
        raise ImproperlyConfigured('El mensaje no contiene destinatarios.')
    ssh = paramiko.SSHClient()
    known = Path(settings.BASE_DIR) / 'work' / 'correo_known_hosts'
    known.parent.mkdir(exist_ok=True)
    known.touch(mode=0o600,exist_ok=True)
    ssh.load_host_keys(str(known))
    # Primera conexión: confiar en el servidor interno configurado; cambios posteriores se rechazan.
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(hostname=settings.CORREO_SSH_HOST,username=settings.CORREO_SSH_USER,
                    password=settings.CORREO_SSH_PASSWORD,timeout=10,banner_timeout=10,
                    auth_timeout=10,allow_agent=False,look_for_keys=False)
        known.chmod(0o600)
        # El sobre replica únicamente los encabezados validados de la configuración privada.
        comando = 'sendmail -i ' + ' '.join(shlex.quote(correo) for correo in correos)
        stdin, stdout, stderr = ssh.exec_command(comando,timeout=20)
        stdin.write(msg.as_bytes())
        stdin.flush()
        stdin.channel.shutdown_write()
        code = stdout.channel.recv_exit_status()
        if code != 0:
            raise RuntimeError('sendmail rechazó el correo. Solicita revisar la cola y los permisos del servidor de correo.')
    finally:
        ssh.close()


@login_required
@require_POST
def enviar_resumen(request):
    return _enviar_reporte(request, 'semanal')


@login_required
@require_POST
def enviar_seguimiento(request):
    return _enviar_reporte(request, 'seguimiento')


def _enviar_reporte(request, tipo):
    require(request.user,edit=True)
    query = request.GET.urlencode()
    destination = reverse('reportes') + '?' + query
    try:
        claim = signing.loads(request.POST.get('token',''),salt=SALT,max_age=3600)
        if claim['user'] != request.user.pk or claim['query'] != query or claim.get('tipo') != tipo:
            return HttpResponse('Actualiza el resumen antes de enviar.',status=400)
        corte = date.fromisoformat(request.GET.get('corte') or timezone.localdate().isoformat())
    except (signing.BadSignature,ValueError,KeyError):
        return HttpResponse('Solicitud vencida o no válida. Actualiza el resumen.',status=400)
    if not all([settings.CORREO_SSH_HOST,settings.CORREO_SSH_USER,settings.CORREO_SSH_PASSWORD]):
        messages.error(request,'Falta configurar la conexión SSH de correo en .env.')
        return redirect(destination)
    qs = filtrar(request.GET, corte)
    if tipo == 'seguimiento':
        context = correo_contexto(qs, corte)
        template = 'correo_compromisos.html'
    else:
        context = resumen_jefaturas(qs, corte)
        context['tablero_url'] = (settings.PORTAL_PUBLIC_URL or request.build_absolute_uri('/').rstrip('/')) + reverse('dashboard')
        template = 'resumen_semanal.html'
    html = render_to_string(template, context)
    try:
        msg = construir_mensaje(html, corte, tipo)
    except ImproperlyConfigured as error:
        messages.error(request, str(error))
        return redirect(destination)
    try:
        with transaction.atomic():
            record = EventoCompromiso.envios.create(canal='correo', token=claim['id'],usuario=request.user.get_username(),corte=corte)
    except IntegrityError:
        messages.info(request,'Este envío ya fue procesado o está en curso; no se ha repetido.')
        return redirect(destination)
    try:
        enviar_remoto(msg)
    except paramiko.AuthenticationException:
        record.estado = 'rechazado'
        messages.error(request,'El servidor de correo rechazó las credenciales SSH. Revisa la configuración privada.')
    except paramiko.BadHostKeyException:
        record.estado = 'rechazado'
        messages.error(request,'Cambió la identidad SSH del servidor. Debe revisarla el administrador.')
    except RuntimeError as error:
        record.estado = 'rechazado'
        messages.error(request,str(error))
    except (OSError,paramiko.SSHException):
        record.estado = 'sin_confirmacion'
        messages.error(request,'No se pudo confirmar el envío. Comprueba la conexión a la red corporativa o VPN y revisa el correo antes de reintentar.')
    else:
        record.estado = 'aceptado'
        nombre = 'recordatorio de seguimiento' if tipo == 'seguimiento' else 'resumen semanal'
        para, copia = destinatarios()
        copia_texto = f", con copia a {', '.join(copia)}" if copia else ''
        messages.success(request,f"El servidor de correo aceptó el {nombre} para {', '.join(para)}{copia_texto}. La entrega final depende del servidor de correo.")
    record.save(update_fields=['estado'])
    return redirect(destination)
