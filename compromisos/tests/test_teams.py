from datetime import date
from unittest.mock import patch
from urllib.error import URLError
import json

import pytest
from django.contrib.auth.models import User
from django.test import Client
from compromisos.models import Compromiso, EventoCompromiso
from compromisos.teams import token_envio

pytestmark = pytest.mark.django_db


@pytest.fixture
def setup(client, settings):
    settings.TEAMS_WEBHOOK_URL = 'https://test.logic.azure.com/workflows/test?sig=secret'
    settings.PORTAL_PUBLIC_URL = 'https://portal.example.com'
    user = User.objects.create_superuser('teams_admin', password='test')
    client.force_login(user)
    Compromiso.objects.create(tema='Proyecto', iniciativa='Iniciativa', tarea='Pendiente', responsable_pyp='Ana', primera_fecha=date(2026,9,1))
    query='corte=2026-09-24'
    return user, query


def test_send_once_and_filter_binding(client, setup):
    user, query = setup
    token=token_envio(user, query)
    with patch('compromisos.teams.enviar') as send:
        assert client.post('/reportes/teams/?'+query, {'token':token}).status_code == 302
        assert client.post('/reportes/teams/?'+query, {'token':token}).status_code == 302
        assert send.call_count == 1
        payload=send.call_args.args[0]
        assert payload['attachments'][0]['content']['actions'][0]['url'].endswith(query)
    assert EventoCompromiso.envios.get(canal="teams").estado == 'aceptado'


def test_send_derives_public_url_from_secure_request(client, setup, settings):
    user, query = setup
    settings.PORTAL_PUBLIC_URL = ''
    settings.ALLOWED_HOSTS = ['portal.example.com']
    with patch('compromisos.teams.enviar') as send:
        response = client.post(
            '/reportes/teams/?' + query,
            {'token': token_envio(user, query)},
            secure=True,
            HTTP_HOST='portal.example.com',
        )
    assert response.status_code == 302
    url = send.call_args.args[0]['attachments'][0]['content']['actions'][0]['url']
    assert url.startswith('https://portal.example.com/')


def test_permissions_csrf_and_no_get(client, setup):
    user, query=setup
    assert client.get('/reportes/teams/').status_code == 405
    secure=Client(enforce_csrf_checks=True);secure.force_login(user)
    assert secure.post('/reportes/teams/?'+query).status_code == 403
    reader=User.objects.create_user('reader');client.force_login(reader)
    with patch('compromisos.teams.enviar') as send:
        assert client.post('/reportes/teams/?'+query).status_code == 403
        send.assert_not_called()


def test_bad_config_token_filters_and_empty(client, setup, settings):
    user, query=setup
    with patch('compromisos.teams.enviar') as send:
        assert client.post('/reportes/teams/?'+query, {'token':'bad'}).status_code == 400
        client.post('/reportes/teams/?'+query+'&q=other', {'token':token_envio(user, query)})
        empty=query+'&q=absent'
        client.post('/reportes/teams/?'+empty, {'token':token_envio(user, empty)})
        settings.TEAMS_WEBHOOK_URL='http://localhost/test'
        client.post('/reportes/teams/?'+query, {'token':token_envio(user, query)})
        send.assert_not_called()
    assert not EventoCompromiso.envios.exists()


def test_timeout_does_not_expose_secret(client, setup):
    user, query=setup
    with patch('compromisos.teams.enviar', side_effect=URLError('secret-url')):
        response=client.post('/reportes/teams/?'+query, {'token':token_envio(user, query)}, follow=True)
    assert EventoCompromiso.envios.get(canal="teams").estado == 'sin_confirmacion'
    assert b'secret-url' not in response.content
    assert b'No se pudo confirmar' in response.content


def test_template_does_not_expose_webhook(client, setup, settings):
    response=client.get('/reportes/?corte=2026-09-24')
    assert b'Enviar recordatorio a Teams' in response.content
    assert settings.TEAMS_WEBHOOK_URL.encode() not in response.content
