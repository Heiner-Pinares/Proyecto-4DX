"""Django UI with application-owned session and audit persistence.

Do not import the retired concrete Session/LogEntry models: their replacements
are in registros_portal4dx. Historical models remain available to migrations.
"""
from django.contrib.admin.apps import AdminConfig
from django.apps import AppConfig


class PortalAdminConfig(AdminConfig):
    default_site = 'compromisos.admin_storage.PortalAdminSite'

    def import_models(self):
        self.models = self.apps.all_models[self.label]


class PortalSessionsConfig(AppConfig):
    name = 'django.contrib.sessions'
    verbose_name = 'Sesiones'

    def import_models(self):
        self.models = self.apps.all_models[self.label]


from django.contrib.auth.apps import AuthConfig
from django.contrib.contenttypes.apps import ContentTypesConfig


class PortalAuthConfig(AuthConfig):
    def import_models(self):
        super().import_models()
        names = {"user": "usuarios_4dx", "group": "grupos_usuarios_4dx", "permission": "permisos_4dx"}
        for model, table in names.items():
            self.models[model]._meta.db_table = table
            self.models[model]._meta.original_attrs["db_table"] = table
        for model, field, table in [
            ("group", "permissions", "relacion_grupo_4dx"),
            ("user", "groups", "grupo_usuarios_4dx"),
            ("user", "user_permissions", "permisos_usuarios_4dx"),
        ]:
            relation = self.models[model]._meta.get_field(field)
            relation.db_table = table
            relation.remote_field.through._meta.db_table = table


class PortalContentTypesConfig(ContentTypesConfig):
    def import_models(self):
        super().import_models()
        self.models["contenttype"]._meta.db_table = "entidades_4dx"
        self.models["contenttype"]._meta.original_attrs["db_table"] = "entidades_4dx"


class PortalCompromisosConfig(AppConfig):
    name = "compromisos"

    def ready(self):
        # Django's migration recorder is not a normal migrated application model.
        from django.db.migrations.recorder import MigrationRecorder
        MigrationRecorder.Migration._meta.db_table = "registrodb_4dx"
