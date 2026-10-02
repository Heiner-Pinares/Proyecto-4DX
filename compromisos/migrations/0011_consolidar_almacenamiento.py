from django.db import migrations


def adelante(apps, schema_editor):
    alias = schema_editor.connection.alias
    R = apps.get_model('compromisos', 'EventoCompromiso')
    CT = apps.get_model('contenttypes','ContentType')
    P = apps.get_model('auth','Permission')
    ct, _ = CT.objects.using(alias).get_or_create(app_label='compromisos', model='estado')
    for action in ['view','add','change','delete']:
        P.objects.using(alias).get_or_create(content_type=ct, codename=action+'_estado', defaults={'name':action+' estado'})
    for row in apps.get_model('compromisos','Estado').objects.using(alias).all().iterator():
        R.objects.using(alias).update_or_create(
            tipo='estado', estado_id=row.pk,
            defaults=dict(origen_id=row.pk, codigo=row.codigo, nombre=row.nombre, activo=row.activo),
        )
    for row in apps.get_model('compromisos','EnvioNotificacion').objects.using(alias).all().iterator():
        R.objects.using(alias).update_or_create(
            tipo='envio', canal=row.canal, token=row.token,
            defaults=dict(origen_id=row.pk, usuario=row.usuario, corte=row.corte, total=row.total, estado=row.estado, fecha=row.creado),
        )
    for origin, row in enumerate(apps.get_model('sessions','Session').objects.using(alias).all().iterator(), start=1):
        R.objects.using(alias).update_or_create(
            tipo='sesion', session_key=row.session_key,
            defaults=dict(origen_id=origin, session_data=row.session_data, expire_date=row.expire_date),
        )
    for row in apps.get_model('admin','LogEntry').objects.using(alias).all().iterator():
        R.objects.using(alias).update_or_create(
            tipo='admin', origen_id=row.pk,
            defaults=dict(user_id=row.user_id, content_type_id=row.content_type_id, object_id=row.object_id, object_repr=row.object_repr, action_flag=row.action_flag, change_message=row.change_message, fecha=row.action_time),
        )
    for tipo, app, name in [('estado','compromisos','Estado'),('envio','compromisos','EnvioNotificacion'),('sesion','sessions','Session'),('admin','admin','LogEntry')]:
        if R.objects.using(alias).filter(tipo=tipo).count() != apps.get_model(app,name).objects.using(alias).count():
            raise RuntimeError('No coincide el total migrado: '+tipo)


def atras(apps, schema_editor):
    from django.core.management.color import no_style
    alias = schema_editor.connection.alias
    R = apps.get_model('compromisos', 'EventoCompromiso')
    restored = []
    for tipo, app, name in [('estado','compromisos','Estado'),('envio','compromisos','EnvioNotificacion'),('sesion','sessions','Session'),('admin','admin','LogEntry')]:
        Model = apps.get_model(app,name)
        rows = R.objects.using(alias).filter(tipo=tipo)
        if tipo in ['envio', 'admin']:
            next_id = max(rows.exclude(origen_id=None).values_list('origen_id', flat=True), default=0) + 1
        for row in rows.iterator():
            if tipo == 'estado':
                fields = dict(id=row.estado_id, codigo=row.codigo, nombre=row.nombre, activo=row.activo)
            elif tipo == 'sesion':
                fields = dict(session_key=row.session_key, session_data=row.session_data, expire_date=row.expire_date)
            else:
                pk = row.origen_id
                if pk is None:
                    pk, next_id = next_id, next_id + 1
                if tipo == 'envio':
                    fields = dict(id=pk, canal=row.canal, token=row.token, usuario=row.usuario, corte=row.corte, total=row.total, estado=row.estado)
                else:
                    fields = dict(id=pk, user_id=row.user_id, content_type_id=row.content_type_id, object_id=row.object_id, object_repr=row.object_repr, action_flag=row.action_flag, change_message=row.change_message)
            obj = Model.objects.using(alias).create(**fields)
            if tipo in ['envio','admin']:
                field = 'creado' if tipo == 'envio' else 'action_time'
                Model.objects.using(alias).filter(pk=obj.pk).update(**{field:row.fecha})
        restored.append(Model)
        rows.delete()
    with schema_editor.connection.cursor() as cursor:
        for sql in schema_editor.connection.ops.sequence_reset_sql(no_style(), restored):
            cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [('compromisos', '0010_registros_portal')]
    operations = [
        migrations.RunPython(adelante, atras),
        migrations.DeleteModel(
            name='EnvioNotificacion',
        ),
        migrations.DeleteModel(
            name='Estado',
        ),
    ]
