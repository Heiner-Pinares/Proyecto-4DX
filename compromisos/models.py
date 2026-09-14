from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

MESES = [
    "",
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]


class Estado(models.Model):
    codigo = models.CharField(max_length=30, unique=True)
    nombre = models.CharField(max_length=100)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.codigo} · {self.nombre}"


class Activos(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Compromiso(models.Model):
    compromiso_hch = models.BooleanField("Compromisos de HCH", default=False)
    tema = models.CharField("Tema", max_length=150, db_index=True)
    iniciativa = models.CharField("Iniciativa", max_length=250, db_index=True)
    tarea = models.TextField("Tarea")
    status = models.CharField("Estatus", max_length=30, db_index=True, choices=[("EC", "En curso"), ("S", "Suspendido"), ("T", "Terminado"), ("D", "Demorado")])
    meta = models.DecimalField(
        "Meta",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    responsable_pyp = models.CharField("Responsable", max_length=150, db_index=True)
    mes = models.CharField("Mes", max_length=30, blank=True, db_index=True)
    fecha_de_compromiso = models.DateField("Fecha de compromiso", null=True, blank=True)
    fecha_de_vencimiento = models.DateField(
        "Vencimiento", null=True, blank=True, db_index=True
    )
    fecha_real = models.DateField("Fecha real", null=True, blank=True, db_index=True)
    puntaje = models.DecimalField(
        "Puntaje",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    primera_fecha = models.DateField(null=True, blank=True)
    segunda_fecha = models.DateField(null=True, blank=True)
    tercera_fecha = models.DateField(null=True, blank=True)
    notas = models.TextField("Notas", blank=True)
    suspendida = models.BooleanField("Suspendida", default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.CharField(max_length=150, null=True, blank=True)
    updated_by = models.CharField(max_length=150, null=True, blank=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    objects = Activos()
    all_objects = models.Manager()

    class Meta:
        db_table = "compromisos"
        ordering = ["-created_at"]
        permissions = [
            ("restore_compromiso", "Puede restaurar compromisos"),
            ("purge_compromiso", "Puede eliminar definitivamente"),
        ]

    def clean_fields(self, exclude=None):
        from .status import calcular_estatus
        self.status = calcular_estatus(self)
        super().clean_fields(exclude=exclude)

    def clean(self):
        if self.segunda_fecha and self.primera_fecha and self.segunda_fecha < self.primera_fecha:
            raise ValidationError({"primera_fecha": "La primera fecha no puede ser posterior a la segunda."})
        previa = self.segunda_fecha or self.primera_fecha
        if self.tercera_fecha and previa and self.tercera_fecha < previa:
            raise ValidationError({"primera_fecha": "La tercera fecha no puede ser anterior a las fechas previas."})
        if (
            self.fecha_real
            and self.fecha_de_compromiso
            and self.fecha_real < self.fecha_de_compromiso
        ):
            raise ValidationError(
                {
                    "fecha_real": "La fecha real no puede ser anterior a la fecha de compromiso."
                }
            )

    def save(self, *args, **kwargs):
        legacy_mes = kwargs.pop("legacy_mes", False)
        from .status import calcular_estatus
        self.status = calcular_estatus(self)
        # Compatibilidad de altas legacy: conservar la fecha inicial antes de derivar.
        if self._state.adding and not any([self.primera_fecha, self.segunda_fecha, self.tercera_fecha]):
            self.primera_fecha = self.fecha_de_vencimiento
        self.fecha_de_vencimiento = self.tercera_fecha or self.segunda_fecha or self.primera_fecha
        self.status = calcular_estatus(self)
        if not legacy_mes:
            d = self.fecha_de_compromiso
            self.mes = f"{MESES[d.month]} {d.year}" if d else ""
        from .scoring import calcular_puntaje

        self.puntaje = calcular_puntaje(self)
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"puntaje", "mes", "status", "suspendida", "fecha_de_vencimiento", "primera_fecha"}
        super().save(*args, **kwargs)

    @property
    def estatus_actual(self):
        from .status import calcular_estatus
        return getattr(self, "estatus", None) or calcular_estatus(self)

    @property
    def fecha_objetivo_vigente(self):
        from .services import fecha_objetivo

        return fecha_objetivo(self)

    @property
    def situacion_plazo(self):
        from .services import situacion

        return situacion(self)

    @property
    def cumplimiento_meta(self):
        return (
            (self.puntaje / self.meta * 100).quantize(Decimal(".01"))
            if self.meta and self.meta > 0 and self.puntaje is not None
            else None
        )

    def __str__(self):
        return self.tarea[:100]


class Reprogramacion(models.Model):
    compromiso = models.ForeignKey(
        Compromiso, on_delete=models.CASCADE, related_name="reprogramaciones"
    )
    numero_reprogramacion = models.PositiveIntegerField()
    fecha_anterior = models.DateField(null=True, blank=True)
    fecha_nueva = models.DateField()
    motivo = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=150)

    class Meta:
        ordering = ["numero_reprogramacion"]
        constraints = [
            models.UniqueConstraint(
                fields=["compromiso", "numero_reprogramacion"],
                name="reprogramacion_numero_unico",
            )
        ]


class HistorialCompromiso(models.Model):
    compromiso = models.ForeignKey(
        Compromiso, on_delete=models.CASCADE, related_name="historial"
    )
    accion = models.CharField(max_length=30)
    descripcion = models.TextField()
    usuario = models.CharField(max_length=150)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]
