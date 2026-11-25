import json
from unittest.mock import patch
from urllib.error import URLError

import pytest
from django.contrib.auth.models import Group, User
from django.test import Client
from django.urls import reverse

from compromisos.ai_service import AssistantError, AssistantTimeout, ask, guard


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def reset_guard():
    guard.reset()
    yield
    guard.reset()


@pytest.fixture
def configured(settings):
    settings.AI_ASSISTANT_ENABLED = True
    settings.POWER_AUTOMATE_URL = "https://example.logic.azure.com/workflows/test?sig=private"
    settings.AI_MAX_INPUT_LENGTH = 100
    settings.AI_MAX_HISTORY_MESSAGES = 4
    settings.AI_MAX_RESPONSE_LENGTH = 1000
    settings.AI_RATE_LIMIT_REQUESTS = 3
    settings.AI_RATE_LIMIT_WINDOW = 300
    settings.AI_MAX_CONCURRENT_REQUESTS = 2
    settings.AI_DUPLICATE_CACHE_SECONDS = 15
    settings.AI_ASSISTANT_ALLOWED_GROUPS = set()


def test_chat_requires_session_csrf_and_valid_json(client, configured):
    url = reverse("ai_chat")
    assert client.post(url, data="{}", content_type="application/json").status_code == 401
    user = User.objects.create_user("consulta")
    secure = Client(enforce_csrf_checks=True)
    secure.force_login(user)
    assert secure.post(url, data="{}", content_type="application/json").status_code == 403
    assert client.force_login(user) is None
    assert client.post(url, data="{", content_type="application/json").status_code == 400
    assert client.post(url, data=json.dumps({"pregunta": ""}), content_type="application/json").status_code == 422


def test_chat_plain_text_history_isolation_and_clear(client, configured):
    user = User.objects.create_user("usuario_a")
    client.force_login(user)
    with patch("compromisos.ai_views.ask", side_effect=["Primera respuesta", "Segunda respuesta"]) as mocked:
        first = client.post(
            reverse("ai_chat"),
            data=json.dumps({"pregunta": "¿Qué es Stand By?", "conversation_id": None}),
            content_type="application/json",
        )
        cid = first.json()["conversation_id"]
        second = client.post(
            reverse("ai_chat"),
            data=json.dumps({"pregunta": "¿Cómo se reactiva?", "conversation_id": cid}),
            content_type="application/json",
        )
    assert first.json()["respuesta"] == "Primera respuesta"
    assert second.json()["respuesta"] == "Segunda respuesta"
    assert mocked.call_args_list[1].args[1][-1]["content"] == "Primera respuesta"
    history = client.get(reverse("ai_history")).json()
    assert len(history["messages"]) == 4

    other = Client()
    other.force_login(User.objects.create_user("usuario_b"))
    assert other.get(reverse("ai_history")).json()["messages"] == []
    assert client.post(reverse("ai_clear")).json()["success"] is True
    assert client.get(reverse("ai_history")).json()["messages"] == []


def test_conversation_id_cannot_be_borrowed(client, configured):
    user = User.objects.create_user("propietario")
    client.force_login(user)
    with patch("compromisos.ai_views.ask", return_value="Respuesta"):
        response = client.post(
            reverse("ai_chat"),
            data=json.dumps({"pregunta": "Pregunta", "conversation_id": "ajena"}),
            content_type="application/json",
        )
    assert response.status_code == 403


def test_group_authorization_and_disabled_portal(client, configured, settings):
    settings.AI_ASSISTANT_ALLOWED_GROUPS = {"Editor"}
    user = User.objects.create_user("lector")
    client.force_login(user)
    assert client.get(reverse("ai_history")).status_code == 403
    group = Group.objects.create(name="Editor")
    user.groups.add(group)
    assert client.get(reverse("ai_history")).status_code == 200
    settings.AI_ASSISTANT_ENABLED = False
    assert client.get(reverse("ai_history")).status_code == 503
    response = client.get(reverse("dashboard"))
    assert b"ai-launcher" not in response.content


def test_service_sends_only_pregunta_and_reads_plain_text(configured):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, size): return "Respuesta con tilde: gestión".encode("utf-8")

    class Opener:
        def open(self, request, timeout):
            payload = json.loads(request.data.decode("utf-8"))
            assert set(payload) == {"pregunta"}
            assert "Portal 4DX" in payload["pregunta"]
            assert "Consulta actual" in payload["pregunta"]
            return Response()

    with patch("compromisos.ai_service.build_opener", return_value=Opener()):
        answer = ask("¿Cómo uso el portal?", [], 10)
    assert answer == "Respuesta con tilde: gestión"


def test_service_timeout_connectivity_rate_and_dedup(configured, settings):
    class Opener:
        def open(self, request, timeout): raise URLError(TimeoutError())
    with patch("compromisos.ai_service.build_opener", return_value=Opener()):
        with pytest.raises(AssistantTimeout):
            ask("Pregunta única", [], 1)

    guard.reset()
    settings.AI_RATE_LIMIT_REQUESTS = 1
    with patch("compromisos.ai_service.build_opener", return_value=Opener()):
        with pytest.raises(AssistantError):
            ask("Primera", [], 2)
        with pytest.raises(AssistantError) as limited:
            ask("Segunda", [], 2)
    assert limited.value.status == 429


def test_service_rejects_non_utf8_response(configured):
    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return None
        def read(self, size): return b"\xff\xfe"

    class Opener:
        def open(self, request, timeout): return Response()

    with patch("compromisos.ai_service.build_opener", return_value=Opener()):
        with pytest.raises(AssistantError):
            ask("Consulta", [], 15)


def test_url_never_appears_in_page_or_error(client, configured):
    user = User.objects.create_user("secreto")
    client.force_login(user)
    page = client.get(reverse("dashboard"))
    assert b"sig=private" not in page.content
    with patch("compromisos.ai_views.ask", side_effect=AssistantError):
        response = client.post(
            reverse("ai_chat"),
            data=json.dumps({"pregunta": "Consulta"}),
            content_type="application/json",
        )
    assert response.status_code == 502
    assert "logic.azure.com" not in response.content.decode()
