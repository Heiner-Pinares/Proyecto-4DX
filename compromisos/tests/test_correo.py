from datetime import date

import pytest
from django.contrib.auth.models import User
from django.conf import settings
from django.utils import timezone

from compromisos.models import Compromiso

pytestmark = pytest.mark.django_db


def make(**kwargs):
    fields = dict(tema='Operaciones', iniciativa='Entrega', tarea='Preparar entrega',
                  status='EC', responsable_pyp='Ana', fecha_de_compromiso=date(2026, 9, 1),
                  fecha_de_vencimiento=date(2026, 9, 8))
    fields.update(kwargs)
    return Compromiso.objects.create(**fields)


def login(client):
    client.force_login(User.objects.create_user('lector'))


def test_access_and_invalid_cutoff(client):
    assert client.get('/reportes/correo/').status_code == 302
    login(client)
    for url in ['/reportes/', '/reportes/correo/']:
        assert client.get(url, {'corte': 'invalid'}).status_code == 400


def test_pending_scope_counts_and_escaping(client):
    login(client)
    make(tarea='<script>alert(1)</script>', notas='<img src=x onerror=alert(1)>')
    make(tarea='Vence hoy', fecha_de_vencimiento=date(2026, 9, 10))
    make(tarea='Futuro objetivo', fecha_de_vencimiento=date(2026, 10, 1))
    make(tarea='Sin fechas', fecha_de_compromiso=None, fecha_de_vencimiento=None)
    for fields in [dict(fecha_real=date(2026,9,9)),
                   dict(suspendida=True), dict(deleted_at=timezone.now()),
                   dict(fecha_de_compromiso=date(2026,9,11))]:
        make(tarea='NO INCLUIR', **fields)
    response = client.get('/reportes/correo/', {'corte':'2026-09-10'})
    assert response.status_code == 200
    assert response['X-Frame-Options'] == 'SAMEORIGIN'
    assert response.context['resumen'] == dict(total=4, vencidos=1, por_vencer=1, en_plazo=1, sin_fecha=1)
    html=response.content.decode()
    assert 'NO INCLUIR' not in html
    assert '<script>' not in html and '&lt;script&gt;' in html
    assert '<img src=x' not in html
    assert '2 días de atraso' in html


def test_filters_download_empty_and_report_embed(client):
    login(client)
    make()
    make(responsable_pyp='Luis')
    response=client.get('/reportes/correo/', {'corte':'2026-09-10','responsable_pyp':'Ana','descargar':'1'})
    assert response.context['resumen']['total'] == 1
    assert response['Content-Disposition'].endswith('Correo_Compromisos_20260910.html"')
    assert 'no-store' in response['Cache-Control']
    response=client.get('/reportes/correo/', {'q':'inexistente'})
    assert 'No hay compromisos en proceso' in response.content.decode()
    response=client.get('/reportes/', {'corte':'2026-09-10','responsable_pyp':'Ana'})
    assert response.status_code == 200
    assert 'corte=2026-09-10' in response.context['correo_query']
    assert 'responsable_pyp=Ana' in response.context['correo_query']
    assert '<iframe' in response.content.decode()
