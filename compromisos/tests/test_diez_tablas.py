from datetime import date, timedelta
from uuid import uuid4

import pytest
from django.contrib.auth.models import User, Group
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.backends.db import SessionStore as OldStore
from django.utils import timezone
from compromisos.models import Compromiso, EventoCompromiso as R
from compromisos.session_backend import SessionStore


@pytest.mark.django_db
def test_only_ten_physical_tables():
    names = connection.introspection.table_names()
    assert len(names) == 10
    assert set(names) == {
        'compromisos', 'registros_portal4dx', 'usuarios_4dx',
        'grupos_usuarios_4dx', 'permisos_4dx', 'relacion_grupo_4dx',
        'grupo_usuarios_4dx', 'permisos_usuarios_4dx', 'entidades_4dx', 'registrodb_4dx',
    }
    assert not {'django_session','django_admin_log','compromisos_estado','compromisos_envionotificacion'} & set(names)
    with connection.cursor() as cursor:
        assert all(t.type == 't' for t in connection.introspection.get_table_list(cursor))


@pytest.mark.django_db
def test_session_compatibility_logout_race_and_expiry(client):
    user = User.objects.create_user('legacy', password='password-test')
    key = 'a'*32
    data = {'_auth_user_id':str(user.pk), '_auth_user_backend':'django.contrib.auth.backends.ModelBackend', '_auth_user_hash':user.get_session_auth_hash()}
    R.sesiones.create(session_key=key, session_data=OldStore().encode(data), expire_date=timezone.now()+timedelta(days=1))
    client.cookies['sessionid'] = key
    assert client.get('/compromisos/').status_code == 200
    concurrent = SessionStore(key); assert concurrent['_auth_user_id'] == str(user.pk)
    assert client.post('/logout/').status_code == 302
    assert not R.sesiones.filter(session_key=key).exists()
    concurrent['x'] = 1
    with pytest.raises(UpdateError):
        concurrent.save()
    assert client.get('/compromisos/').status_code == 302
    store = SessionStore(); store['x'] = 2; store.save()
    R.sesiones.filter(session_key=store.session_key).update(expire_date=timezone.now()-timedelta(seconds=1))
    assert SessionStore(store.session_key).load() == {}
    state = R.estados.create(codigo='TEST',nombre='Test')
    sent = R.envios.create(canal='teams', token=uuid4(), corte=date.today(), total=1)
    call_command('clearsessions')
    assert not R.sesiones.exists()
    assert R.estados.filter(pk=state.pk).exists() and R.envios.filter(pk=sent.pk).exists()


@pytest.mark.django_db
def test_session_rotation_and_deactivation(client):
    user = User.objects.create_user('login',password='test-password')
    assert client.login(username='login',password='test-password')
    key = client.session.session_key
    s=client.session; s.cycle_key()
    assert not R.sesiones.filter(session_key=key).exists()
    assert R.sesiones.filter(session_key=s.session_key).exists()
    client.cookies['sessionid']=s.session_key
    user.is_active=False;user.save()
    assert client.get('/compromisos/').status_code==302


@pytest.mark.django_db
def test_native_admin_users_groups_history_and_state_crud(client):
    admin = User.objects.create_superuser('audit_admin',password='test-password')
    client.force_login(admin)
    response=client.post('/admin/auth/group/add/', {'name':'Audit group','permissions':[],'_save':'Guardar'})
    assert response.status_code==302
    group=Group.objects.get(name='Audit group')
    assert R.auditoria.filter(object_id=str(group.pk),action_flag=1).exists()
    assert client.post(f'/admin/auth/group/{group.pk}/change/',{'name':'Renamed group','permissions':[],'_save':'Guardar'}).status_code==302
    history=client.get(f'/admin/auth/group/{group.pk}/history/')
    assert history.status_code==200 and b'audit_admin' in history.content
    assert client.get('/admin/').status_code==200
    assert client.post(f'/admin/auth/group/{group.pk}/delete/',{'post':'yes'}).status_code==302
    assert R.auditoria.filter(object_id=str(group.pk),action_flag=3).exists()
    assert client.post('/admin/compromisos/estado/add/',{'codigo':'CUSTOM','nombre':'Custom','activo':'on'}).status_code==302
    state=R.estados.get(codigo='CUSTOM')
    assert client.post(f'/admin/compromisos/estado/{state.estado_id}/change/',{'codigo':'CUSTOM','nombre':'Actualizado','activo':'on'}).status_code==302
    assert b'Actualizado' in client.get('/admin/compromisos/estado/').content
    assert client.get(f'/admin/compromisos/estado/{state.estado_id}/history/').status_code==200
    assert client.post(f'/admin/compromisos/estado/{state.estado_id}/delete/').status_code==302
    assert not R.estados.filter(codigo='CUSTOM').exists()
    # Deleting a user must not query the retired django_admin_log relation.
    victim=User.objects.create_user('victim')
    R.auditoria.create(user=victim, action_flag=1, object_repr='Example')
    assert client.post(f'/admin/auth/user/{victim.pk}/delete/',{'post':'yes'}).status_code==302
    assert not User.objects.filter(pk=victim.pk).exists()


@pytest.mark.django_db
def test_readonly_event_admin_does_not_expose_sessions(client):
    call_command('init_portal')
    user=User.objects.create_user('staff_reader',is_staff=True)
    user.groups.add(Group.objects.get(name='Consulta'))
    client.force_login(user)
    c=Compromiso.objects.create(tarea='Visible')
    R.objects.create(compromiso=c,accion='NOTA',descripcion='Visible audit')
    secret=R.sesiones.create(session_key='s'*32,session_data='PRIVATE_SESSION',expire_date=timezone.now()+timedelta(days=1))
    response=client.get('/admin/compromisos/eventocompromiso/')
    assert response.status_code==200 and b'PRIVATE_SESSION' not in response.content
    assert client.get(f'/admin/compromisos/eventocompromiso/{secret.pk}/change/').status_code==302
    assert client.post('/admin/compromisos/estado/add/',{'codigo':'NO','nombre':'No'}).status_code==403
    state=R.estados.first()
    assert client.get(f'/admin/compromisos/estado/{state.estado_id}/change/').status_code==200
    assert client.post(f'/admin/compromisos/estado/{state.estado_id}/change/',{'codigo':state.codigo,'nombre':'No'}).status_code==403


@pytest.mark.django_db(transaction=True)
def test_ten_table_migration_preserves_records_and_reverses():
    old=[('compromisos','0009_consolidar_tablas')]
    executor=MigrationExecutor(connection); latest=executor.loader.graph.leaf_nodes();executor.migrate(old)
    targets=old+[('admin','0003_logentry_add_action_flag_choices'),('sessions','0001_initial')]
    apps=executor.loader.project_state(targets).apps
    moment=timezone.now()-timedelta(days=2)
    user=apps.get_model('auth','User').objects.create(username='migration-user')
    state=apps.get_model('compromisos','Estado').objects.create(codigo='MIG',nombre='Migración',activo=False)
    c=apps.get_model('compromisos','Compromiso').objects.create(tarea='Preservar',tema='',iniciativa='',responsable_pyp='',status='EC')
    event=apps.get_model('compromisos','EventoCompromiso').objects.create(compromiso=c,accion='CREADO',descripcion='Sin pérdida',usuario='Ana',origen_id=9)
    apps.get_model('compromisos','EventoCompromiso').objects.filter(pk=event.pk).update(fecha=moment)
    token=uuid4()
    send=apps.get_model('compromisos','EnvioNotificacion').objects.create(canal='teams',token=token,usuario='Ana',corte=date.today(),total=3,estado='aceptado')
    apps.get_model('compromisos','EnvioNotificacion').objects.filter(pk=send.pk).update(creado=moment)
    data=OldStore().encode({'message':'keep-signed-data'})
    expiry=timezone.now()+timedelta(days=2)
    apps.get_model('sessions','Session').objects.create(session_key='m'*32,session_data=data,expire_date=expiry)
    log=apps.get_model('admin','LogEntry').objects.create(user=user,object_id=str(c.pk),object_repr='Preservar',action_flag=2,change_message='Cambio original',action_time=moment)
    try:
        executor=MigrationExecutor(connection);executor.migrate(latest)
        assert R.objects.get(pk=event.pk).descripcion=='Sin pérdida'
        assert R.objects.get(pk=event.pk).fecha==moment
        assert R.estados.get(estado_id=state.pk).activo is False
        assert R.envios.get(token=token).fecha==moment
        assert R.auditoria.get(origen_id=log.pk).change_message=='Cambio original'
        assert R.sesiones.get(session_key='m'*32).session_data==data
        assert SessionStore('m'*32)['message']=='keep-signed-data'
        extra=R.estados.create(codigo='NEW',nombre='Nuevo')
        R.envios.create(canal='correo',token=token,usuario='Ana',corte=date.today())
        executor=MigrationExecutor(connection);executor.migrate(old)
        apps=executor.loader.project_state(targets).apps
        assert apps.get_model('compromisos','Estado').objects.get(pk=state.pk).nombre=='Migración'
        assert apps.get_model('compromisos','Estado').objects.get(pk=extra.estado_id).codigo=='NEW'
        assert apps.get_model('compromisos','EnvioNotificacion').objects.get(pk=send.pk).creado==moment
        assert apps.get_model('compromisos','EnvioNotificacion').objects.filter(token=token).count()==2
        assert apps.get_model('sessions','Session').objects.get(pk='m'*32).session_data==data
        assert apps.get_model('admin','LogEntry').objects.get(pk=log.pk).action_time==moment
    finally:
        MigrationExecutor(connection).migrate(latest)
