from django.db import migrations
from django.utils import timezone


def recalcular(apps, schema_editor):
    C = apps.get_model("compromisos", "Compromiso")
    H = apps.get_model("compromisos", "HistorialCompromiso")
    alias = schema_editor.connection.alias
    hoy = timezone.localdate()
    for c in C._base_manager.using(alias).all().iterator():
        objetivo = c.tercera_fecha or c.segunda_fecha or c.primera_fecha or c.fecha_de_vencimiento
        status = "S" if c.suspendida else "T" if c.fecha_real else "D" if objetivo and objetivo < hoy else "EC"
        if c.status != status:
            H.objects.using(alias).create(compromiso_id=c.pk, accion="ACTUALIZADO", usuario="sistema",
                descripcion=f"Estatus automático según suspensión, fecha real y vencimiento: {c.status} → {status}.")
            C._base_manager.using(alias).filter(pk=c.pk).update(status=status, updated_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0003_alter_compromiso_fecha_de_vencimiento_and_more")]
    operations = [migrations.RunPython(recalcular)]
