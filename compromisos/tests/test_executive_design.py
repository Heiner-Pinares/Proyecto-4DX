from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from compromisos.executive import datos_corte, historico_mensual, opciones_periodo
from compromisos.models import Compromiso, EventoCompromiso


pytestmark = pytest.mark.django_db


def compromiso(nombre, vencimiento, **overrides):
    values = {
        "proyecto": f"Proyecto {nombre}",
        "tarea": nombre,
        "status": "EC",
        "responsable_pyp": "Responsable Demo",
        "jefatura": "Jefatura de Facturacion a Clientes",
        "fecha_de_compromiso": vencimiento - timedelta(days=14),
        "fecha_de_vencimiento": vencimiento,
        "primera_fecha": vencimiento,
    }
    values.update(overrides)
    return Compromiso.objects.create(**values)


def test_datos_corte_calcula_resumen_y_jefaturas():
    cut = timezone.localdate()
    compromiso("Cerrado a tiempo", cut - timedelta(days=2), fecha_real=cut - timedelta(days=3))
    compromiso("Vencido", cut - timedelta(days=1))
    compromiso("Próximo", cut + timedelta(days=4))
    compromiso("En espera", cut + timedelta(days=15), suspendida=True, status="S")

    result = datos_corte(Compromiso.objects.all(), cut)

    assert result["due_count"] == 2
    assert result["on_time_count"] == 1
    assert result["compliance"] == 50
    assert [item.tarea for item in result["overdue"]] == ["Vencido"]
    assert [item.tarea for item in result["upcoming"]] == ["Próximo"]
    assert [item.tarea for item in result["standby"]] == ["En espera"]
    assert result["offices"][0]["overdue"] == 1


def test_historico_distingue_meses_de_anios_distintos():
    compromiso("Diciembre", timezone.datetime(2025, 12, 10).date(), fecha_real=timezone.datetime(2025, 12, 9).date())
    compromiso("Noviembre", timezone.datetime(2026, 11, 10).date(), fecha_real=timezone.datetime(2026, 11, 9).date())

    result = historico_mensual(Compromiso.objects.all())

    assert result["labels"] == ["Dic 2025", "Nov 2026"]
    assert result["compliance"] == [100, 100]


def test_periodos_historicos_son_mensuales_y_filtran_el_fin():
    options = opciones_periodo(timezone.datetime(2026, 11, 24).date(), cantidad=2)
    assert options == [
        {"value": "2026-11-24", "label": "Jun–Nov 2026"},
        {"value": "2026-10-31", "label": "May–Oct 2026"},
    ]
    compromiso("Octubre", timezone.datetime(2026, 10, 10).date(), fecha_real=timezone.datetime(2026, 10, 9).date())
    compromiso("Noviembre", timezone.datetime(2026, 11, 10).date(), fecha_real=timezone.datetime(2026, 11, 9).date())
    result = historico_mensual(
        Compromiso.objects.all(), end_date=timezone.datetime(2026, 10, 31).date()
    )
    assert result["labels"] == ["Oct"]


def test_nuevas_vistas_y_comentario_rapido(client):
    user = get_user_model().objects.create_superuser("ejecutivo", "ejecutivo@example.com", "demo")
    client.force_login(user)
    today = timezone.localdate()
    item = compromiso("Compromiso visible", today - timedelta(days=1))

    dashboard = client.get(reverse("dashboard"), {"corte": today.isoformat()})
    assert dashboard.status_code == 200
    assert "Resumen ejecutivo del corte" in dashboard.content.decode()
    assert "Compromiso visible" in dashboard.content.decode()

    listing = client.get(reverse("listado"), {"vista": "accion", "seleccion": item.pk})
    assert listing.status_code == 200
    assert "Hoja completa editable" in listing.content.decode()

    target = f"{reverse('listado')}?vista=accion&seleccion={item.pk}"
    response = client.post(
        reverse("comentario_rapido", args=[item.pk]),
        {"motivo": "Comentario desde el panel", "next": target},
    )
    assert response.status_code == 302
    assert response.url == target
    item.refresh_from_db()
    assert "Comentario desde el panel" in item.notas
    assert EventoCompromiso.objects.filter(compromiso=item, accion="ACTUALIZADO").exists()

    gestion = client.get(reverse("indicadores"), {"vista": "gestion"})
    historico = client.get(reverse("indicadores"), {"vista": "historico"})
    assert gestion.status_code == historico.status_code == 200
    assert "Evolución por corte" in gestion.content.decode()
    assert "Cumplimiento en primera fecha por mes" in historico.content.decode()
