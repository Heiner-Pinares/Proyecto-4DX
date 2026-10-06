from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

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


class Activos(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(deleted_at__isnull=True)


class Compromiso(models.Model):
    codigo_fuente = models.CharField(
        "Código de origen",
        max_length=100,
        null=True,
        blank=True,
        unique=True,
        editable=False,
    )
    proyecto = models.CharField("Proyecto", max_length=250, db_index=True)
    iniciativa = models.CharField(
        "Iniciativa", max_length=250, blank=True, default="", db_index=True
    )
    tarea = models.TextField("Tarea")
    status = models.CharField("Estatus", max_length=30, db_index=True, choices=[("EC", "En curso"), ("S", "Stand By"), ("T", "Terminado"), ("D", "Demorado")])
    meta = models.DecimalField(
        "Meta",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
    )
    responsable_pyp = models.CharField("Responsable", max_length=150, db_index=True)
    JEFATURAS = [
        (nombre, nombre) for nombre in [
            "Jefatura de Facturacion a Clientes",
            "Jefatura de Soporte Oper Post Facturacion",
            "Jefatura de Control y Mejoras de Facturacion",
        ]
    ]
    jefatura = models.CharField("Jefatura", max_length=150, blank=True, default="", choices=JEFATURAS)
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
    suspendida = models.BooleanField("Stand By", default=False, db_index=True)
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
    def historial(self):
        return self.eventos.filter(tipo="historial")

    @property
    def reprogramaciones(self):
        return self.eventos.filter(tipo="reprogramacion").order_by("numero_reprogramacion")

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



class TipoManager(models.Manager):
    """Consultas filtradas a la única tabla física de registros auxiliares."""
    def __init__(self, tipo):
        self.tipo = tipo
        super().__init__()

    def get_queryset(self):
        return super().get_queryset().filter(tipo=self.tipo)

    def create(self, **kwargs):
        return super().create(**{**kwargs, "tipo": self.tipo})

    def get_or_create(self, defaults=None, **kwargs):
        return super().get_or_create(defaults=defaults, **{**kwargs, "tipo": self.tipo})

    def update_or_create(self, defaults=None, create_defaults=None, **kwargs):
        return super().update_or_create(defaults=defaults, create_defaults=create_defaults, **{**kwargs, "tipo": self.tipo})


class EventoCompromiso(models.Model):
    """Registros tipificados del portal, almacenados en una sola tabla física."""
    TIPOS = [(v, label) for v, label in [
        ("historial", "Historial"), ("reprogramacion", "Reprogramación"),
        ("estado", "Estado configurable"), ("envio", "Envío"),
        ("sesion", "Sesión"), ("admin", "Auditoría administrativa"),
        ("perfil", "Perfil de usuario"),
    ]]
    tipo = models.CharField(max_length=20, choices=TIPOS, default="historial", db_index=True)
    compromiso = models.ForeignKey(Compromiso, null=True, blank=True, on_delete=models.CASCADE, related_name="eventos")
    origen_id = models.PositiveBigIntegerField(null=True, editable=False)
    accion = models.CharField(max_length=30, blank=True)
    descripcion = models.TextField(blank=True)
    usuario = models.CharField(max_length=150, blank=True)
    fecha = models.DateTimeField(default=timezone.now)
    numero_reprogramacion = models.PositiveIntegerField(null=True, blank=True)
    reprogramacion_clave = models.CharField(
        max_length=80, null=True, blank=True, unique=True, editable=False
    )
    fecha_anterior = models.DateField(null=True, blank=True)
    fecha_nueva = models.DateField(null=True, blank=True)
    motivo = models.TextField(blank=True)
    # State IDs remain stable for existing administration links.
    estado_id = models.PositiveBigIntegerField(null=True, unique=True, editable=False)
    codigo = models.CharField(max_length=30, null=True, blank=True, unique=True)
    nombre = models.CharField(max_length=100, blank=True)
    activo = models.BooleanField(default=True)
    canal = models.CharField(max_length=10, blank=True, choices=[("teams", "Teams"), ("correo", "Correo")])
    token = models.UUIDField(null=True, editable=False)
    corte = models.DateField(null=True, blank=True)
    total = models.PositiveIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=30, blank=True)
    session_key = models.CharField(max_length=40, null=True, unique=True, editable=False)
    session_data = models.TextField(blank=True, editable=False)
    expire_date = models.DateTimeField(null=True, blank=True, db_index=True)
    user = models.ForeignKey('auth.User', null=True, blank=True, on_delete=models.CASCADE, related_name='registros_admin')
    content_type = models.ForeignKey('contenttypes.ContentType', null=True, blank=True, on_delete=models.SET_NULL, related_name='registros_admin')
    object_id = models.TextField(null=True, blank=True)
    object_repr = models.CharField(max_length=200, blank=True)
    action_flag = models.PositiveSmallIntegerField(null=True, blank=True)
    change_message = models.TextField(blank=True)
    objects = models.Manager()
    estados = TipoManager('estado')
    envios = TipoManager('envio')
    sesiones = TipoManager('sesion')
    auditoria = TipoManager('admin')
    perfiles = TipoManager('perfil')

    class Meta:
        db_table = "registros_portal4dx"
        verbose_name = "registro del portal"
        verbose_name_plural = "registros del portal"
        ordering = ["-fecha", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["canal", "token"], name="registro_envio_unico"),
            models.CheckConstraint(condition=(
                models.Q(tipo="historial", compromiso__isnull=False, numero_reprogramacion__isnull=True)
                | models.Q(tipo="reprogramacion", compromiso__isnull=False, numero_reprogramacion__isnull=False, fecha_nueva__isnull=False)
                | models.Q(tipo="estado", codigo__isnull=False)
                | models.Q(tipo="envio", canal__in=["teams", "correo"], token__isnull=False, corte__isnull=False)
                | models.Q(tipo="sesion", session_key__isnull=False, expire_date__isnull=False)
                | models.Q(tipo="admin", user__isnull=False, action_flag__in=[1, 2, 3])
                | models.Q(tipo="perfil", user__isnull=False)
            ), name="registro_tipo_campos_validos"),
        ]

    def save(self, *args, **kwargs):
        self.reprogramacion_clave = (
            f"{self.compromiso_id}:{self.numero_reprogramacion}"
            if self.tipo == "reprogramacion"
            and self.compromiso_id is not None
            and self.numero_reprogramacion is not None
            else None
        )
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {
                "reprogramacion_clave"
            }
        if self.tipo == 'envio' and not self.estado:
            self.estado = 'en_curso'
        if self.tipo == 'estado' and self.estado_id is None:
            from django.db import transaction
            from django.db.models import Max
            # Serialize reference allocation while preserving historic state URLs.
            with transaction.atomic():
                list(type(self).estados.select_for_update().order_by('pk').values_list('pk', flat=True))
                super().save(*args, **kwargs)
                self.estado_id = max(self.pk, (type(self).estados.aggregate(n=Max('estado_id'))['n'] or 0) + 1)
                type(self).objects.filter(pk=self.pk).update(estado_id=self.estado_id)
            return
        super().save(*args, **kwargs)

    def __str__(self):
        if self.tipo == 'estado':
            return f"{self.codigo} · {self.nombre}"
        if self.tipo == 'admin':
            return self.object_repr
        return f"{self.get_tipo_display()} #{self.pk}"

    @property
    def created_at(self):
        return self.fecha

    @property
    def creado(self):
        return self.fecha

    @property
    def created_by(self):
        return self.usuario

    @property
    def action_time(self):
        return self.fecha

    def is_addition(self):
        return self.action_flag == 1

    def is_change(self):
        return self.action_flag == 2

    def is_deletion(self):
        return self.action_flag == 3

    def get_change_message(self):
        from .admin_storage import change_message
        return change_message(self.change_message)

    def get_admin_url(self):
        from django.urls import reverse, NoReverseMatch
        from django.contrib.admin.utils import quote
        if self.content_type and self.object_id:
            try:
                return reverse(f'admin:{self.content_type.app_label}_{self.content_type.model}_change', args=[quote(self.object_id)])
            except NoReverseMatch:
                return None

    def get_edited_object(self):
        if self.content_type and self.content_type.app_label == 'compromisos' and self.content_type.model == 'estado':
            return type(self).estados.get(estado_id=self.object_id)
        return self.content_type.get_object_for_this_type(pk=self.object_id)
