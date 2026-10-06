from django import forms
from django.utils import timezone

from .models import Compromiso, EventoCompromiso


class CompromisoForm(forms.ModelForm):
    class Meta:
        model = Compromiso
        fields = [
            "proyecto",
            "iniciativa",
            "tarea",
            "responsable_pyp",
            "jefatura",
            "suspendida",
            "meta",
            "fecha_de_compromiso",
            "primera_fecha",
            "fecha_real",
            "notas",
        ]
        widgets = {
            name: forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})
            for name in ["fecha_de_compromiso", "primera_fecha", "fecha_real"]
        }
        widgets.update(
            {
                "tarea": forms.Textarea(attrs={"rows": 3}),
                "notas": forms.Textarea(attrs={"rows": 3}),
            }
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["primera_fecha"].label = "1ra fecha comprometida"
        self.fields["primera_fecha"].help_text = "El vencimiento se calcula automáticamente. Las reprogramaciones se editan en la tabla o con la acción Reprogramar."


class AccionForm(forms.Form):
    def __init__(self, *args, accion, **kwargs):
        super().__init__(*args, **kwargs)
        if accion in ["reprogramar", "cerrar"]:
            name = "fecha_nueva" if accion == "reprogramar" else "fecha_real"
            self.fields[name] = forms.DateField(
                label="Nueva fecha" if accion == "reprogramar" else "Fecha real",
                initial=timezone.localdate,
                widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
            )
        if accion == "cerrar":
            self.fields["nota"] = forms.CharField(
                label="Nota opcional", required=False, widget=forms.Textarea
            )
        if accion in ["reprogramar", "suspender", "nota"]:
            self.fields["motivo"] = forms.CharField(
                label="Nota" if accion == "nota" else "Motivo", widget=forms.Textarea
            )
        if accion == "purgar":
            self.fields["confirmacion"] = forms.CharField(
                label="Escriba ELIMINAR para confirmar"
            )
