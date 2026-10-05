from io import StringIO

import pytest
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from openpyxl import Workbook

from compromisos.management.commands.importar_usuarios_excel import first_surname
from compromisos.models import EventoCompromiso
from compromisos.profiles import profile_data


pytestmark = pytest.mark.django_db


HEADERS = [
    "Cod. Comunicación",
    "Correo electrónico",
    "Jefe",
    "Nombre completo",
    "Área",
    "Gerencia",
    "Dirección",
]


def workbook(path, codes=("C100", "C200", "C300", "C400")):
    book = Workbook()
    sheet = book.active
    sheet.title = "OPERACIONES"
    sheet.append(HEADERS)
    sheet.append([codes[0], "aperez@claro.com.pe", "JEFA UNO", "ANA MARIA PEREZ SOTO", "Área A", "Gerencia A", "Dirección A"])
    sheet.append([codes[1], "cfarfan@claro.com.pe", "JEFE DOS", "CARLOS VICENTE FARFAN ACHAMISO", "Área B", "Gerencia B", "Dirección B"])
    sheet.append([codes[2], "carlos.farfan@claro.com.pe", "JEFE DOS", "CARLOS EDUARDO FARFAN CASTRO", "Área B", "Gerencia B", "Dirección B"])
    sheet.append([codes[3], "stephanie.delacruz@claro.com.pe", "", "STEPHANIE DE LA CRUZ DOMINGUEZ", "Área C", "", ""])
    book.save(path)


def test_compound_surname_uses_corporate_alias():
    assert first_surname("STEPHANIE DE LA CRUZ DOMINGUEZ", "stephanie.delacruz@claro.com.pe") == "DE LA CRUZ"
    assert first_surname("WENDY JANNINA VELIZ NUÑEZ DEL ARCO", "wendy.veliz@claro.com.pe") == "VELIZ"
    assert first_surname("LUIS GUILLERMO FLORES BROWN", "guillermo.flores@claro.com.pe") == "FLORES"


def test_import_creates_hashed_accounts_profiles_and_resolves_collision(tmp_path):
    path = tmp_path / "usuarios.xlsx"
    workbook(path)
    call_command("init_portal", stdout=StringIO())
    output = StringIO()
    call_command("importar_usuarios_excel", str(path), stdout=output)

    assert User.objects.filter(is_superuser=False).count() == 4
    ana = User.objects.get(username="ana.perez")
    assert ana.check_password("C100")
    assert ana.password != "C100" and "$" in ana.password
    assert list(ana.groups.values_list("name", flat=True)) == ["Consulta"]
    profile = profile_data(EventoCompromiso.perfiles.get(user=ana))
    assert profile == {
        "nombre_completo": "ANA MARIA PEREZ SOTO",
        "area": "Área A",
        "gerencia": "Gerencia A",
        "direccion": "Dirección A",
        "jefe": "JEFA UNO",
    }
    assert User.objects.filter(username="carlos.farfan").exists()
    assert User.objects.filter(username="carlos.farfan2").exists()
    assert User.objects.get(email="stephanie.delacruz@claro.com.pe").last_name == "De La Cruz"
    assert "4 creados" in output.getvalue() and "1 colisión" in output.getvalue()


def test_reimport_updates_profile_without_resetting_password_or_role(tmp_path):
    path = tmp_path / "usuarios.xlsx"
    workbook(path)
    call_command("init_portal", stdout=StringIO())
    call_command("importar_usuarios_excel", str(path), stdout=StringIO())
    ana = User.objects.get(username="ana.perez")
    ana.set_password("contraseña-personal")
    ana.groups.set([Group.objects.get(name="Editor")])
    ana.save()

    workbook(path, codes=("NUEVO", "C200", "C300", "C400"))
    call_command("importar_usuarios_excel", str(path), stdout=StringIO())
    ana.refresh_from_db()
    assert ana.check_password("contraseña-personal")
    assert list(ana.groups.values_list("name", flat=True)) == ["Editor"]
    assert User.objects.filter(email="aperez@claro.com.pe").count() == 1


def test_user_administration_displays_organization(client, tmp_path):
    path = tmp_path / "usuarios.xlsx"
    workbook(path)
    call_command("init_portal", stdout=StringIO())
    call_command("importar_usuarios_excel", str(path), stdout=StringIO())
    admin = User.objects.create_superuser("admin_import", password="test-password")
    client.force_login(admin)
    response = client.get("/usuarios/")
    assert response.status_code == 200
    assert "Área A" in response.content.decode()
    assert "Dirección A" in response.content.decode()
