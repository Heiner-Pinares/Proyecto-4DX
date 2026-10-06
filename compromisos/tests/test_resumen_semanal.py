from datetime import date
import pytest
from django.contrib.auth.models import User
from django.http import QueryDict
from compromisos.models import Compromiso
from compromisos.indicators import metricas
from compromisos.reports import resumen_jefaturas
from compromisos.selectors import filtrar
pytestmark = pytest.mark.django_db


def test_week_and_scores(client):
    corte=date(2026,9,29)
    def add(**extra):
        data=dict(proyecto='Proyecto', iniciativa='I', tarea='Tarea real', responsable_pyp='Ana', primera_fecha=corte, jefatura=Compromiso.JEFATURAS[0][0])
        data.update(extra)
        return Compromiso.objects.create(**data)
    add()
    add(primera_fecha=date(2026,10,5),fecha_de_compromiso=date(2026,10,5),jefatura='')
    add(primera_fecha=date(2026,10,4),fecha_de_compromiso=date(2026,10,4),jefatura='')
    add(primera_fecha=date(2026,10,7))
    add(primera_fecha=date(2026,9,28))
    add(suspendida=True)
    add(fecha_real=corte)
    add(fecha_real=date(2026,10,1))
    qs = filtrar({}, corte)
    ctx=resumen_jefaturas(qs,corte)
    assert ctx['total_proximos']==3
    assert ctx['total_proximos'] == metricas(qs)['proximos']
    assert ctx['general']==100 and ctx['cerrados']==1
    assert len(ctx['grupos'])==4
    sin_jefatura = next(g for g in ctx['grupos'] if g['nombre'] == 'Sin jefatura asignada')
    assert len(sin_jefatura['proximos']) == 2
    assert client.get('/reportes/semanal/').status_code==302
    client.force_login(User.objects.create_user('semanal'))
    response=client.get('/reportes/semanal/?corte=2026-09-29&descargar=1')
    assert response.status_code==200
    assert response['X-Frame-Options']=='SAMEORIGIN'
    assert 'attachment' in response['Content-Disposition']
    assert 'Jefatura de Facturacion a Clientes' in response.content.decode()
    assert client.get('/reportes/semanal/?corte=bad').status_code==400
    assert client.get('/reportes/semanal/?q=ausente').context['total_proximos']==0
    assert client.get('/reportes/').status_code==200


def test_multiple_status_filter_is_preserved(client):
    corte = date(2026, 10, 4)
    Compromiso.objects.create(
        proyecto='A', iniciativa='A', tarea='Terminada', responsable_pyp='Ana',
        primera_fecha=corte, fecha_real=corte,
    )
    Compromiso.objects.create(
        proyecto='B', iniciativa='B', tarea='Suspendida', responsable_pyp='Ana',
        primera_fecha=corte, suspendida=True,
    )
    Compromiso.objects.create(
        proyecto='C', iniciativa='C', tarea='En curso', responsable_pyp='Ana',
        primera_fecha=date(2026, 10, 10),
    )
    params = QueryDict('status=T&status=S')
    assert set(filtrar(params, corte).values_list('estatus', flat=True)) == {'T', 'S'}

    client.force_login(User.objects.create_user('multistatus'))
    response = client.get('/compromisos/?status=T&status=S')
    assert response.context['estatus_seleccionados'] == ['T', 'S']
    assert response.context['query'] == 'status=T&status=S'
    html = response.content.decode()
    assert 'name="status" value="T" checked' in html
    assert 'name="status" value="S" checked' in html
