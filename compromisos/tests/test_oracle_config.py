import json
import base64

import pytest
from django.contrib.auth.models import Group, User
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.utils import timezone

from config.database import database_config
from config.runtime_secrets import secret_key
from compromisos.models import Compromiso, EventoCompromiso


def oracle_env(**changes):
    values = {
        "DB_ENGINE": "oracle",
        "ORACLE_HOST": "scan-odscbio",
        "ORACLE_PORT": "1521",
        "ORACLE_SERVICE_NAME": "ODSCBIO",
        "ORACLE_USER": "USRFACDOC",
        "ORACLE_PASSWORD": "secret",
    }
    values.update(changes)
    return values


def test_oracle_uses_service_name_easy_connect_and_pool():
    config = database_config(oracle_env())
    assert config["ENGINE"] == "django.db.backends.oracle"
    assert config["NAME"] == "scan-odscbio:1521/ODSCBIO"
    assert config["USER"] == "USRFACDOC"
    assert config["PASSWORD"] == "secret"
    assert config["CONN_MAX_AGE"] == 0
    assert config["OPTIONS"] == {"pool": True}


def test_oracle_dsn_override_and_pool_disable():
    config = database_config(
        oracle_env(ORACLE_DSN="(DESCRIPTION=example)", ORACLE_POOL="false")
    )
    assert config["NAME"] == "(DESCRIPTION=example)"
    assert config["OPTIONS"] == {}


def test_oracle_pool_does_not_forward_legacy_threaded_argument():
    config = database_config(oracle_env())
    assert "threaded" not in config["OPTIONS"]


def test_oracle_decodes_base64_password_without_dotenv_interpolation():
    raw = "p#a ss${HOME}'"
    encoded = base64.b64encode(raw.encode()).decode()
    config = database_config(
        oracle_env(ORACLE_PASSWORD="", ORACLE_PASSWORD_B64=encoded)
    )
    assert config["PASSWORD"] == raw


@pytest.mark.parametrize(
    "change,message",
    [
        ({"ORACLE_PASSWORD": "", "ORACLE_PASSWORD_FILE": "/missing/password"}, "Falta la contraseña"),
        ({"ORACLE_USER": "USRFACDOC]"}, "termina en ']'"),
        ({"ORACLE_PORT": "abc"}, "ORACLE_PORT"),
    ],
)
def test_oracle_rejects_incomplete_or_suspicious_configuration(change, message):
    with pytest.raises(ImproperlyConfigured, match=message.replace("[", "\\[")):
        database_config(oracle_env(**change))


def test_only_password_file_is_required_for_default_oracle_connection(tmp_path):
    password_file = tmp_path / "oracle_password.txt"
    password_file.write_text("special# password$\n")
    config = database_config(
        {"DB_ENGINE": "oracle", "ORACLE_PASSWORD_FILE": str(password_file)},
        tmp_path,
    )
    assert config["NAME"] == "scan-odscbio:1521/ODSCBIO"
    assert config["USER"] == "USRFACDOC"
    assert config["PASSWORD"] == "special# password$"


def test_django_secret_is_created_once_and_reused(tmp_path):
    first = secret_key({}, tmp_path)
    second = secret_key({}, tmp_path)
    assert first == second
    assert len(first) >= 64
    assert (tmp_path / "runtime-config" / "django_secret_key.txt").exists()


def test_startup_verifies_and_migrates_oracle_automatically(monkeypatch):
    import run

    class FakeConnection:
        vendor = "oracle"

        def ensure_connection(self):
            return None

    calls = []
    monkeypatch.setattr(run, "connections", {"default": FakeConnection()})
    monkeypatch.setattr(
        run,
        "call_command",
        lambda name, *args, **kwargs: calls.append((name, kwargs)),
    )
    monkeypatch.setattr(run, "flag", lambda name, default="false": True)

    run.initialize()

    assert calls == [
        ("verificar_oracle", {"connection_only": True}),
        ("migrate", {"interactive": False}),
        ("verificar_oracle", {}),
        ("init_portal", {}),
    ]


@pytest.mark.django_db
def test_portable_export_excludes_active_sessions(tmp_path):
    group = Group.objects.create(name="Exportados")
    user = User.objects.create_user("exportado")
    user.groups.add(group)
    commitment = Compromiso.objects.create(tarea="Dato portable")
    event = EventoCompromiso.objects.create(
        compromiso=commitment, accion="NOTA", descripcion="Conservar"
    )
    EventoCompromiso.sesiones.create(
        session_key="x" * 32,
        session_data="privado",
        expire_date=timezone.now(),
    )
    path = tmp_path / "portal.json"

    call_command("exportar_portal", str(path), verbosity=0)

    rows = json.loads(path.read_text())
    models = [row["model"] for row in rows]
    assert "auth.group" in models
    assert "auth.user" in models
    assert "compromisos.compromiso" in models
    assert any(row["pk"] == event.pk for row in rows if row["model"] == "compromisos.eventocompromiso")
    assert not any(
        row["fields"].get("tipo") == "sesion"
        for row in rows
        if row["model"] == "compromisos.eventocompromiso"
    )

    EventoCompromiso.objects.all().delete()
    Compromiso.all_objects.all().delete()
    User.objects.all().delete()
    Group.objects.all().delete()
    call_command("loaddata", str(path), verbosity=0)
    restored = User.objects.get(username="exportado")
    assert restored.pk == user.pk
    assert restored.groups.get().name == "Exportados"
    assert Compromiso.all_objects.get().tarea == "Dato portable"
    assert EventoCompromiso.objects.get(tipo="historial").descripcion == "Conservar"
