from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("auth", "0012_alter_user_first_name_max_length"), ("contenttypes", "0003_nombre_4dx")]
    operations = [
        migrations.AlterModelTable(name="user", table="usuarios_4dx"),
        migrations.AlterModelTable(name="group", table="grupos_usuarios_4dx"),
        migrations.AlterModelTable(name="permission", table="permisos_4dx"),
        migrations.AlterField(model_name="group", name="permissions", field=models.ManyToManyField(blank=True, to="auth.permission", verbose_name="permissions", db_table="relacion_grupo_4dx")),
        migrations.AlterField(model_name="user", name="groups", field=models.ManyToManyField(blank=True, to="auth.group", verbose_name="groups", related_name="user_set", related_query_name="user", help_text="The groups this user belongs to. A user will get all permissions granted to each of their groups.", db_table="grupo_usuarios_4dx")),
        migrations.AlterField(model_name="user", name="user_permissions", field=models.ManyToManyField(blank=True, to="auth.permission", verbose_name="user permissions", related_name="user_set", related_query_name="user", help_text="Specific permissions for this user.", db_table="permisos_usuarios_4dx")),
    ]
