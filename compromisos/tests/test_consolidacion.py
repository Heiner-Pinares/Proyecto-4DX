from datetime import date
from uuid import uuid4

import pytest
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
def test_migration_preserves_data_grants_and_roundtrip():
    old = [('compromisos', '0008_enviocorreo')]
    new = [('compromisos', '0009_consolidar_tablas')]
    executor = MigrationExecutor(connection)
    executor.migrate(old)
    # Auth is explicitly included because the earlier application migration had no auth dependency.
    targets = old + [('auth', '0012_alter_user_first_name_max_length'), ('contenttypes', '0002_remove_content_type_name')]
    apps = executor.loader.project_state(targets).apps
    C = apps.get_model('compromisos', 'Compromiso')
    H = apps.get_model('compromisos', 'HistorialCompromiso')
    R = apps.get_model('compromisos', 'Reprogramacion')
    c = C.objects.create(tarea='Conservar evidencia', tema='Prueba', iniciativa='Prueba', status='EC', responsable_pyp='Ana')
    timestamp = timezone.now().replace(year=2024)
    h = H.objects.create(id=42, compromiso=c, accion='CREADO', descripcion='Detalle íntegro', usuario='Ana')
    H.objects.filter(pk=h.pk).update(fecha=timestamp)
    r = R.objects.create(id=42, compromiso=c, numero_reprogramacion=1, fecha_anterior=date(2026,9,1), fecha_nueva=date(2026,9,9), motivo='Motivo íntegro', created_by='Ana')
    R.objects.filter(pk=r.pk).update(created_at=timestamp)
    token = uuid4()
    for model in ['EnvioTeams', 'EnvioCorreo']:
        M = apps.get_model('compromisos', model)
        fields = dict(id=token, usuario='Ana', corte=date(2026,9,9), estado='sin_confirmacion')
        if model == 'EnvioTeams':
            fields['total'] = 7
        M.objects.create(**fields)
        M.objects.filter(pk=token).update(creado=timestamp)
    CT = apps.get_model('contenttypes', 'ContentType')
    P = apps.get_model('auth', 'Permission')
    G = apps.get_model('auth', 'Group')
    U = apps.get_model('auth', 'User')
    ct, _ = CT.objects.get_or_create(app_label='compromisos', model='historialcompromiso')
    permission, _ = P.objects.get_or_create(content_type=ct, codename='view_historialcompromiso', defaults={'name':'Ver historial'})
    group = G.objects.create(name='Migracion'); group.permissions.add(permission)
    user = U.objects.create(username='migracion'); user.user_permissions.add(permission)
    try:
        executor = MigrationExecutor(connection); executor.migrate(new)
        apps = executor.loader.project_state(new).apps
        E = apps.get_model('compromisos', 'EventoCompromiso')
        S = apps.get_model('compromisos', 'EnvioNotificacion')
        assert E.objects.filter(compromiso_id=c.pk).count() == 2
        assert E.objects.get(tipo='historial', origen_id=42).descripcion == 'Detalle íntegro'
        assert E.objects.get(tipo='reprogramacion', origen_id=42).fecha == timestamp
        assert S.objects.filter(token=token, creado=timestamp).count() == 2
        assert S.objects.get(token=token, canal='teams').total == 7
        for model, pk, relation in [('Group', group.pk, 'permissions'), ('User', user.pk, 'user_permissions')]:
            obj = apps.get_model('auth', model).objects.get(pk=pk)
            assert getattr(obj, relation).filter(codename='view_eventocompromiso').exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            S.objects.create(canal='teams', token=token, usuario='Ana', corte=date(2026,9,9))
        E.objects.create(compromiso_id=c.pk, tipo='historial', accion='NOTA', descripcion='Después', usuario='Ana')
        executor = MigrationExecutor(connection); executor.migrate(old)
        apps = executor.loader.project_state(targets).apps
        assert apps.get_model('compromisos','HistorialCompromiso').objects.get(pk=42).fecha == timestamp
        assert apps.get_model('compromisos','HistorialCompromiso').objects.filter(compromiso_id=c.pk).count() == 2
        assert apps.get_model('compromisos','Reprogramacion').objects.get(pk=42).motivo == 'Motivo íntegro'
        for model in ['EnvioTeams','EnvioCorreo']:
            assert apps.get_model('compromisos',model).objects.get(pk=token).creado == timestamp
    finally:
        MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())
