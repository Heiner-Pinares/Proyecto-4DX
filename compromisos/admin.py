from django.contrib import admin

from .models import Compromiso, EventoCompromiso
from .services import audit
from .admin_storage import RegistroAdminMixin
from django.contrib.auth.models import User, Group
from django.contrib.auth.admin import UserAdmin, GroupAdmin


@admin.register(Compromiso)
class CompromisoAdmin(RegistroAdminMixin, admin.ModelAdmin):
    list_display = ["id", "tema", "iniciativa", "responsable_pyp", "status", "mes"]
    search_fields = ["tarea", "tema", "responsable_pyp"]
    readonly_fields = [
        "puntaje",
        "status",
        "fecha_de_vencimiento",
        "created_at",
        "updated_at",
        "created_by",
        "updated_by",
        "deleted_at",
        "primera_fecha",
        "segunda_fecha",
        "tercera_fecha",
    ]

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user.get_username()
        if not change:
            obj.created_by = obj.updated_by
        obj.save(legacy_mes="mes" in form.changed_data)
        audit(
            obj,
            "ACTUALIZADO" if change else "CREADO",
            "Administración: " + ", ".join(form.changed_data),
            request.user,
        )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EventoCompromiso)
class AuditAdmin(RegistroAdminMixin, admin.ModelAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(tipo__in=["historial", "reprogramacion"])

    list_display = ["id", "compromiso", "tipo", "accion", "usuario", "fecha"]
    list_filter = ["tipo", "accion"]
    search_fields = ["descripcion", "motivo", "compromiso__tarea"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        # Allow only the audit cascade when deleting a user; logs are absent from this admin queryset.
        return obj is not None and obj.tipo == "admin" and request.user.has_perm("auth.delete_user")


# Keep Django user/group forms, actions and password controls with the shared audit store.
admin.site.unregister(User)
admin.site.unregister(Group)

@admin.register(User)
class PortalUserAdmin(RegistroAdminMixin, UserAdmin):
    pass

@admin.register(Group)
class PortalGroupAdmin(RegistroAdminMixin, GroupAdmin):
    pass

admin.site.site_header = "Soporte técnico del portal"
