import pytest
from django.contrib.auth.models import User


pytestmark = pytest.mark.django_db


def test_login_design_and_browser_session(client):
    User.objects.create_user("usuario.demo", password="clave-segura")
    page = client.get("/login/")
    assert page.status_code == 200
    html = page.content.decode()
    assert "Portal Claro" in html
    assert "Usuario de acceso" in html
    assert 'name="remember"' in html
    assert "¿Olvidaste tu contraseña?" in html

    response = client.post(
        "/login/", {"username": "usuario.demo", "password": "clave-segura"}
    )
    assert response.status_code == 302
    assert client.session.get_expire_at_browser_close()


def test_remember_me_uses_persistent_session(client):
    User.objects.create_user("usuario.recordado", password="clave-segura")
    response = client.post(
        "/login/",
        {"username": "usuario.recordado", "password": "clave-segura", "remember": "1"},
    )
    assert response.status_code == 302
    assert not client.session.get_expire_at_browser_close()
