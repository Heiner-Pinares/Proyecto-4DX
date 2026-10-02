from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("contenttypes", "0002_remove_content_type_name"), ("compromisos", "0011_consolidar_almacenamiento")]
    operations = [migrations.AlterModelTable(name="contenttype", table="entidades_4dx")]
