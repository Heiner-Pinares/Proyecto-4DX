from django.contrib import admin

from .models import Compromiso, Estado, HistorialCompromiso, Reprogramacion
from .services import audit


@admin.register(Compromiso)
class CompromisoAdmin(admin.ModelAdmin):
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


@admin.register(Reprogramacion, HistorialCompromiso)
class AuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Estado)
admin.site.site_header = "Soporte técnico del portal"
