import pytest
from django.contrib.auth.models import User
from compromisos.models import Compromiso
from compromisos.forms import CompromisoForm

pytestmark = pytest.mark.django_db


def test_jefatura_edit_detail_and_clear(client):
    user=User.objects.create_superuser('jefatura_admin', password='test')
    client.force_login(user)
    c=Compromiso.objects.create(proyecto='Proyecto', iniciativa='Iniciativa', tarea='Tarea', responsable_pyp='Ana')
    assert c.jefatura == ''
    assert 'jefatura' in CompromisoForm().fields
    for value in [nombre for nombre, _ in Compromiso.JEFATURAS] + ['']:
        result=client.post(f'/compromisos/{c.pk}/celda/', {'field':'jefatura','value':value,'version':c.updated_at.isoformat()},content_type='application/json')
        assert result.status_code == 200
        c.refresh_from_db()
        assert c.jefatura == value
        assert 'Jefatura' in c.historial.first().descripcion
        detail=client.get(f'/compromisos/{c.pk}/')
        assert ('Jefatura', value) in detail.context['campos']
        assert b'Jefatura' in client.get('/compromisos/').content
    result=client.post(f'/compromisos/{c.pk}/celda/', {'field':'jefatura','value':'Otra jefatura','version':c.updated_at.isoformat()},content_type='application/json')
    assert result.status_code == 400


def test_grid_jefatura_has_only_department_choices():
    from compromisos.grid import fila
    c = Compromiso.objects.create(proyecto="Proyecto", iniciativa="I", tarea="T", responsable_pyp="Ana")
    cell = next(cell for cell in fila(c)["cells"] if cell["name"] == "jefatura")
    assert cell["kind"] == "select"
    assert [item["codigo"] for item in cell["options"]] == [""] + [code for code, _ in Compromiso.JEFATURAS]
    assert not {"EC", "D", "T", "S"}.intersection(item["codigo"] for item in cell["options"])
