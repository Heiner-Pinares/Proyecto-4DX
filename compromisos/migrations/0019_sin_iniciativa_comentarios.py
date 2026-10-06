from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0018_proyecto_sin_hch")]

    operations = [
        migrations.RemoveField(
            model_name="compromiso",
            name="iniciativa",
        ),
        migrations.AlterField(
            model_name="compromiso",
            name="notas",
            field=models.TextField(blank=True, verbose_name="Comentarios"),
        ),
    ]
