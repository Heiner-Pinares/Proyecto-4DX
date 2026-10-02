from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0012_nombres_4dx")]

    operations = [
        migrations.RemoveConstraint(
            model_name="eventocompromiso",
            name="evento_origen_unico",
        ),
    ]
