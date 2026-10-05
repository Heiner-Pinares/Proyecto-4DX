from django.db import migrations, models


def completar_claves(apps, schema_editor):
    Registro = apps.get_model("compromisos", "EventoCompromiso")
    alias = schema_editor.connection.alias
    rows = Registro.objects.using(alias).filter(
        tipo="reprogramacion",
        compromiso_id__isnull=False,
        numero_reprogramacion__isnull=False,
    )
    for row in rows.iterator():
        row.reprogramacion_clave = (
            f"{row.compromiso_id}:{row.numero_reprogramacion}"
        )
        row.save(using=alias, update_fields=["reprogramacion_clave"])


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0015_perfil_usuario")]

    operations = [
        migrations.AddField(
            model_name="eventocompromiso",
            name="reprogramacion_clave",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=80,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(completar_claves, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="eventocompromiso",
            name="evento_numero_unico",
        ),
    ]
