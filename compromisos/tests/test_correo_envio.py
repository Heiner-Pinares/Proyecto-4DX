from datetime import date
from unittest.mock import patch, MagicMock
import pytest
from django.contrib.auth.models import User
from django.test import Client
from compromisos.correo import token_correo, construir_mensaje, enviar_remoto, PARA, COPIA
from compromisos.models import Compromiso, EventoCompromiso
pytestmark=pytest.mark.django_db


def test_recipients_html_and_duplicate(client,settings):
    settings.CORREO_SSH_HOST='internal';settings.CORREO_SSH_USER='user';settings.CORREO_SSH_PASSWORD='secret'
    user=User.objects.create_superuser('correo_test',password='test');client.force_login(user)
    query='corte=2026-09-29';token=token_correo(user,query,'semanal')
    with patch('compromisos.correo.enviar_remoto') as send:
        result=client.post('/reportes/correo/enviar/?'+query,{'token':token,'to':'other@example.com','cc':'other@example.com'})
        assert result.status_code==302
        msg=send.call_args.args[0]
        assert msg['To']==PARA and msg['Cc']==COPIA and msg['Bcc'] is None
        html=msg.get_body(preferencelist=('html',)).get_content()
        assert 'Estado general de cumplimiento' in html and '29/09/2026' in html
        client.post('/reportes/correo/enviar/?'+query,{'token':token})
        assert send.call_count==1
    assert EventoCompromiso.envios.get(canal="correo").estado=='aceptado'
    assert client.get('/reportes/correo/enviar/').status_code==405
    assert client.post('/reportes/correo/enviar/?'+query,{'token':'bad'}).status_code==400
    secure=Client(enforce_csrf_checks=True);secure.force_login(user)
    assert secure.post('/reportes/correo/enviar/?'+query,{'token':token}).status_code==403
    client.force_login(User.objects.create_user('lector_correo'))
    assert client.post('/reportes/correo/enviar/?'+query,{'token':token}).status_code==403


def test_followup_button_sends_its_own_dynamic_html(client, settings):
    settings.CORREO_SSH_HOST='internal';settings.CORREO_SSH_USER='user';settings.CORREO_SSH_PASSWORD='secret'
    user=User.objects.create_superuser('seguimiento_test', password='test');client.force_login(user)
    Compromiso.objects.create(
        jefatura='Jefatura de Facturacion a Clientes', tema='Proyecto 4DX', iniciativa='Portal',
        tarea='Validar el nuevo correo', responsable_pyp='Ana', status='EC',
        fecha_de_compromiso=date(2026, 9, 1), fecha_de_vencimiento=date(2026, 9, 28),
    )
    query='corte=2026-09-29'; token=token_correo(user, query, 'seguimiento')
    page=client.get('/reportes/?'+query).content.decode()
    assert '/reportes/correo/seguimiento/enviar/' in page
    assert '/reportes/correo/enviar/' in page
    with patch('compromisos.correo.enviar_remoto') as send:
        response=client.post('/reportes/correo/seguimiento/enviar/?'+query, {'token':token})
        assert response.status_code == 302
        msg=send.call_args.args[0]
        assert msg['To']==PARA and msg['Cc']==COPIA
        assert msg['Subject']=='Seguimiento de compromisos 4DX · Corte 29/09/2026'
        html=msg.get_body(preferencelist=('html',)).get_content()
        assert 'Recordatorio de compromisos' in html
        assert 'Validar el nuevo correo' in html
        assert 'Jefatura de Facturacion a Clientes' in html
        assert 'Estado general de cumplimiento' not in html
    wrong=token_correo(user, query, 'semanal')
    assert client.post('/reportes/correo/seguimiento/enviar/?'+query, {'token':wrong}).status_code == 400


def test_sendmail_fixed_envelope_and_failure(settings,tmp_path):
    settings.BASE_DIR=tmp_path
    (tmp_path/'work').mkdir()
    with patch('compromisos.correo.paramiko.SSHClient') as factory:
        ssh=factory.return_value
        stdin,stdout,stderr=MagicMock(),MagicMock(),MagicMock()
        ssh.exec_command.return_value=(stdin,stdout,stderr)
        stdout.channel.recv_exit_status.return_value=1
        with pytest.raises(RuntimeError):
            enviar_remoto(construir_mensaje('<p>Prueba</p>',date(2026,9,29)))
        assert ssh.exec_command.call_args.args[0]=='sendmail -i c27826@claro.com.pe c28171@claro.com.pe'
        ssh.close.assert_called_once()
