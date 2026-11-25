from django.core.exceptions import PermissionDenied
from django.conf import settings


def admin(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name="Administrador").exists()
    )


def editor(user):
    return admin(user) or (
        user.is_authenticated and user.has_perm("compromisos.change_compromiso")
    )


def require(user, edit=False, administrative=False):
    if (
        not user.is_authenticated
        or (administrative and not admin(user))
        or (edit and not editor(user))
    ):
        raise PermissionDenied


def ai_access(user):
    if not user.is_authenticated or not user.is_active:
        return False
    allowed = settings.AI_ASSISTANT_ALLOWED_GROUPS
    return not allowed or user.is_superuser or user.groups.filter(name__in=allowed).exists()


def context(request):
    return {
        "can_edit": editor(request.user),
        "is_admin": admin(request.user),
        "ai_assistant_visible": bool(
            settings.AI_ASSISTANT_ENABLED
            and settings.POWER_AUTOMATE_URL
            and ai_access(request.user)
        ),
        "ai_max_input_length": settings.AI_MAX_INPUT_LENGTH,
    }
