"""Vistas de autenticación propias del portal."""

from django.conf import settings
from django.contrib.auth.views import LoginView


class PortalLoginView(LoginView):
    """Acceso normal con sesión de navegador o persistente a elección del usuario."""

    template_name = "registration/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)
        if self.request.POST.get("remember"):
            self.request.session.set_expiry(settings.SESSION_COOKIE_AGE)
        else:
            self.request.session.set_expiry(0)
        return response
