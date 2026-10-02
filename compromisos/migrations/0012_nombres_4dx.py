from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0011_consolidar_almacenamiento"), ("auth", "0013_nombres_4dx")]
    operations = [migrations.AlterModelTable(name="eventocompromiso", table="registros_portal4dx")]
