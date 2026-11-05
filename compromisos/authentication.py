"""Formulario y vista de autenticación propios del portal."""

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.exceptions import ValidationError

from .domain_auth import DominioNoDisponible


class PortalAuthenticationForm(AuthenticationForm):
    """Muestra errores seguros y distingue una caída del directorio."""

    error_messages = {
        "invalid_login": "Usuario o contraseña incorrectos.",
        "inactive": "Esta cuenta no tiene el acceso habilitado.",
        "directory_unavailable": (
            "No pudimos validar tu contraseña de dominio en este momento. "
            "Intenta nuevamente en unos minutos."
        ),
    }

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username is not None and password:
            try:
                self.user_cache = authenticate(
                    self.request, username=username, password=password
                )
            except DominioNoDisponible as exc:
                raise ValidationError(
                    self.error_messages["directory_unavailable"],
                    code="directory_unavailable",
                ) from exc
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class PortalLoginView(LoginView):
    """Acceso normal con sesión de navegador o persistente a elección del usuario."""

    template_name = "registration/login.html"
    authentication_form = PortalAuthenticationForm

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("remember"):
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            self.request.session.set_expiry(0)
        return response
