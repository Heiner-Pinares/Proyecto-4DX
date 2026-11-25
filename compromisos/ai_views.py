"""API interna del asistente: autenticación, sesión y respuestas JSON seguras."""

import json
import uuid

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .ai_service import AssistantError, ask
from .permissions import ai_access


SESSION_KEY = "ai_assistant_conversation"


def _error(message, status):
    return JsonResponse({"success": False, "error": message}, status=status)


def _access(request):
    if not request.user.is_authenticated:
        return _error("Debes iniciar sesión para utilizar el asistente.", 401)
    if not ai_access(request.user):
        return _error("Tu cuenta no tiene permiso para utilizar el asistente.", 403)
    if not settings.AI_ASSISTANT_ENABLED or not settings.POWER_AUTOMATE_URL:
        return _error("El asistente no está disponible temporalmente.", 503)
    return None


def _conversation(request, create=False):
    conversation = request.session.get(SESSION_KEY)
    if not isinstance(conversation, dict) or conversation.get("user_id") != request.user.pk:
        conversation = None
    if conversation is None and create:
        conversation = {"id": str(uuid.uuid4()), "user_id": request.user.pk, "messages": []}
        request.session[SESSION_KEY] = conversation
    return conversation


@require_POST
def chat(request):
    denied = _access(request)
    if denied:
        return denied
    if request.content_type != "application/json":
        return _error("La solicitud debe enviarse como JSON.", 400)
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return _error("La solicitud JSON no es válida.", 400)
    if not isinstance(payload, dict):
        return _error("La solicitud debe ser un objeto JSON.", 400)
    question = payload.get("pregunta")
    if not isinstance(question, str) or not question.strip():
        return _error("Escribe una consulta antes de enviarla.", 422)
    question = question.strip()
    if len(question) > settings.AI_MAX_INPUT_LENGTH:
        return _error(f"La consulta supera el máximo de {settings.AI_MAX_INPUT_LENGTH} caracteres.", 422)
    conversation = _conversation(request, create=True)
    requested_id = payload.get("conversation_id")
    if requested_id is not None and requested_id != conversation["id"]:
        return _error("La conversación indicada no pertenece a esta sesión.", 403)
    history = list(conversation.get("messages") or [])[-settings.AI_MAX_HISTORY_MESSAGES :]
    try:
        answer = ask(question, history, request.user.pk)
    except AssistantError as error:
        return _error(error.public_message, error.status)
    messages = history + [
        {"role": "user", "content": question},
        {"role": "assistant", "content": answer},
    ]
    conversation["messages"] = messages[-settings.AI_MAX_HISTORY_MESSAGES :]
    request.session[SESSION_KEY] = conversation
    request.session.modified = True
    return JsonResponse(
        {
            "success": True,
            "respuesta": answer,
            "conversation_id": conversation["id"],
        }
    )


@require_GET
def history(request):
    denied = _access(request)
    if denied:
        return denied
    conversation = _conversation(request)
    return JsonResponse(
        {
            "success": True,
            "conversation_id": conversation["id"] if conversation else None,
            "messages": conversation.get("messages", []) if conversation else [],
        }
    )


@require_POST
def clear(request):
    denied = _access(request)
    if denied:
        return denied
    request.session.pop(SESSION_KEY, None)
    request.session.modified = True
    return JsonResponse({"success": True, "conversation_id": None, "messages": []})
