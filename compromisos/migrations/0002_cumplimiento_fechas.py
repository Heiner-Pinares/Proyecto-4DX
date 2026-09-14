from django.db import migrations


def recalcular(apps, schema_editor):
    Compromiso = apps.get_model("compromisos", "Compromiso")
    Historial = apps.get_model("compromisos", "HistorialCompromiso")
    alias = schema_editor.connection.alias
    for c in Compromiso._base_manager.using(alias).all().iterator():
        first = c.primera_fecha or c.fecha_de_vencimiento
        score = (
            None
            if not c.fecha_real
            else 100
            if first and c.fecha_real <= first
            else 80
            if c.segunda_fecha and c.fecha_real <= c.segunda_fecha
            else 60
        )
        if c.puntaje != score:
            Historial.objects.using(alias).create(
                compromiso_id=c.pk,
                accion="ACTUALIZADO",
                descripcion=f"Nueva regla de cumplimiento por fechas: puntaje {c.puntaje} → {score}.",
                usuario="sistema",
            )
            Compromiso._base_manager.using(alias).filter(pk=c.pk).update(puntaje=score)


class Migration(migrations.Migration):
    dependencies = [("compromisos", "0001_initial")]
    operations = [migrations.RunPython(recalcular)]
