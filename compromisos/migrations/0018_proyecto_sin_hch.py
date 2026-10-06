from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0017_estado_stand_by")]

    operations = [
        migrations.RenameField(
            model_name="compromiso",
            old_name="tema",
            new_name="proyecto",
        ),
        migrations.AlterField(
            model_name="compromiso",
            name="proyecto",
            field=models.CharField(
                db_index=True, max_length=250, verbose_name="Proyecto"
            ),
        ),
        migrations.AlterField(
            model_name="compromiso",
            name="iniciativa",
            field=models.CharField(
                blank=True,
                db_index=True,
                default="",
                max_length=250,
                verbose_name="Iniciativa",
            ),
        ),
        migrations.RemoveField(
            model_name="compromiso",
            name="compromiso_hch",
        ),
    ]
