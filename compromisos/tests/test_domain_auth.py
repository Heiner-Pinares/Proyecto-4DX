from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User

from compromisos.domain_auth import DominioNoDisponible, ResultadoDominio
from compromisos.models import EventoCompromiso
from compromisos.profiles import profile_data, save_profile


@pytest.mark.django_db
def test_codigo_dominio_crea_usuario_consulta_y_sincroniza_perfil(client):
    validador = Mock()
    validador.validar.return_value = ResultadoDominio(
        True,
        "OK",
        nombres="Ana María",
        apellidos="Pérez Soto",
        correo="ana.perez@claro.com.pe",
    )
    with patch("compromisos.domain_auth.validador_dominio", return_value=validador):
        response = client.post(
            "/login/", {"username": "c12345", "password": "secreto-dominio"}
        )

    assert response.status_code == 302
    user = User.objects.get(username="C12345")
    assert (user.first_name, user.last_name, user.email) == (
        "Ana María",
        "Pérez Soto",
        "ana.perez@claro.com.pe",
    )
    assert not user.has_usable_password()
    assert user.groups.get().name == "Consulta"
    perfil = profile_data(EventoCompromiso.perfiles.get(user=user))
    assert perfil["nombre_completo"] == "Ana María Pérez Soto"
    validador.validar.assert_called_once_with("C12345", "secreto-dominio")


@pytest.mark.django_db
def test_sincronizacion_conserva_rol_y_datos_organizacionales():
    editor = Group.objects.create(name="Editor")
    user = User.objects.create_user("E54321", password="clave-local-antigua")
    user.groups.add(editor)
    save_profile(
        user,
        nombre_completo="Nombre anterior",
        area="Facturación",
        gerencia="Gerencia Comercial",
        direccion="Operaciones",
        jefe="Jefa Actual",
    )
    validador = Mock()
    validador.validar.return_value = ResultadoDominio(
        True, "OK", "Nombre", "Actualizado", "nombre@claro.com.pe"
    )

    with patch("compromisos.domain_auth.validador_dominio", return_value=validador):
        authenticated = authenticate(
            username="E54321", password="contraseña-de-windows"
        )

    user.refresh_from_db()
    assert authenticated == user
    assert list(user.groups.values_list("name", flat=True)) == ["Editor"]
    assert not user.has_usable_password()
    perfil = profile_data(EventoCompromiso.perfiles.get(user=user))
    assert perfil == {
        "nombre_completo": "Nombre Actualizado",
        "area": "Facturación",
        "gerencia": "Gerencia Comercial",
        "direccion": "Operaciones",
        "jefe": "Jefa Actual",
    }


@pytest.mark.django_db
def test_codigo_corporativo_nunca_acepta_password_local():
    User.objects.create_user("C11111", password="password-local")
    validador = Mock()
    validador.validar.return_value = ResultadoDominio(False, "CREDENCIALES")

    with patch("compromisos.domain_auth.validador_dominio", return_value=validador):
        assert authenticate(username="C11111", password="password-local") is None


@pytest.mark.django_db
def test_usuario_local_existente_sigue_funcionando():
    user = User.objects.create_user("usuario.local", password="password-local")
    assert authenticate(username="usuario.local", password="password-local") == user


@pytest.mark.django_db
def test_correo_claro_usa_codigo_sincronizado():
    user = User.objects.create_user("C22222", email="persona@claro.com.pe")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    validador = Mock()
    validador.validar.return_value = ResultadoDominio(
        True, "OK", "Persona", "Claro", "persona@claro.com.pe"
    )

    with patch("compromisos.domain_auth.validador_dominio", return_value=validador):
        assert authenticate(
            username="persona@claro.com.pe", password="clave-dominio"
        ).pk == user.pk
    validador.validar.assert_called_once_with("C22222", "clave-dominio")


@pytest.mark.django_db
def test_directorio_no_disponible_muestra_mensaje_controlado(client):
    validador = Mock()
    validador.validar.side_effect = DominioNoDisponible("timeout")
    with patch("compromisos.domain_auth.validador_dominio", return_value=validador):
        response = client.post(
            "/login/", {"username": "C33333", "password": "secreto"}
        )
    assert response.status_code == 200
    assert "No pudimos validar tu contraseña de dominio" in response.content.decode()
