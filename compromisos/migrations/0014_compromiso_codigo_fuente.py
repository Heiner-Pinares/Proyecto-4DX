from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0013_remove_evento_origen_unico")]

    operations = [
        migrations.AddField(
            model_name="compromiso",
            name="codigo_fuente",
            field=models.CharField(
                blank=True,
                editable=False,
                max_length=100,
                null=True,
                unique=True,
                verbose_name="Código de origen",
            ),
        ),
    ]
