from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0014_compromiso_codigo_fuente")]

    operations = [
        migrations.RemoveConstraint(
            model_name="eventocompromiso",
            name="registro_tipo_campos_validos",
        ),
        migrations.AlterField(
            model_name="eventocompromiso",
            name="tipo",
            field=models.CharField(
                choices=[
                    ("historial", "Historial"),
                    ("reprogramacion", "Reprogramación"),
                    ("estado", "Estado configurable"),
                    ("envio", "Envío"),
                    ("sesion", "Sesión"),
                    ("admin", "Auditoría administrativa"),
                    ("perfil", "Perfil de usuario"),
                ],
                db_index=True,
                default="historial",
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name="eventocompromiso",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(tipo="historial", compromiso__isnull=False, numero_reprogramacion__isnull=True)
                    | models.Q(tipo="reprogramacion", compromiso__isnull=False, numero_reprogramacion__isnull=False, fecha_nueva__isnull=False)
                    | models.Q(tipo="estado", codigo__isnull=False)
                    | models.Q(tipo="envio", canal__in=["teams", "correo"], token__isnull=False, corte__isnull=False)
                    | models.Q(tipo="sesion", session_key__isnull=False, expire_date__isnull=False)
                    | models.Q(tipo="admin", user__isnull=False, action_flag__in=[1, 2, 3])
                    | models.Q(tipo="perfil", user__isnull=False)
                ),
                name="registro_tipo_campos_validos",
            ),
        ),
    ]
