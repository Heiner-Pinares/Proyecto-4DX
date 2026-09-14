from django.core.exceptions import PermissionDenied


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


def context(request):
    return {"can_edit": editor(request.user), "is_admin": admin(request.user)}
