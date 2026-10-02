from datetime import date
import pytest
from django.contrib.auth.models import User
from compromisos.models import Compromiso
from compromisos.reports import resumen_jefaturas
from compromisos.selectors import filtrar
pytestmark = pytest.mark.django_db


def test_week_and_scores(client):
    corte=date(2026,9,29)
    def add(**extra):
        data=dict(tema='Tema', iniciativa='I', tarea='Tarea real', responsable_pyp='Ana', primera_fecha=corte, jefatura=Compromiso.JEFATURAS[0][0])
        data.update(extra)
        return Compromiso.objects.create(**data)
    add()
    add(primera_fecha=date(2026,10,5),jefatura='')
    add(primera_fecha=date(2026,10,6))
    add(primera_fecha=date(2026,9,28))
    add(suspendida=True)
    add(fecha_real=corte)
    add(fecha_real=date(2026,10,1))
    ctx=resumen_jefaturas(filtrar({},corte),corte)
    assert ctx['total_proximos']==2
    assert ctx['general']==100 and ctx['cerrados']==1
    assert len(ctx['grupos'])==4
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
