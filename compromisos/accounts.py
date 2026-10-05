from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import EventoCompromiso
from .permissions import require
from .profiles import profile_data, profiles_for, save_profile


PROFILE_FORM_FIELDS = {
    "area": "Área",
    "gerencia": "Gerencia",
    "direccion": "Dirección",
    "jefe": "Jefe",
}


def add_profile_fields(form):
    for name, label in PROFILE_FORM_FIELDS.items():
        form.fields[name] = forms.CharField(label=label, max_length=250, required=False)


def save_form_profile(user, cleaned_data, current=None):
    current = current or {}
    save_profile(
        user,
        nombre_completo=current.get("nombre_completo") or user.get_full_name(),
        **{name: cleaned_data.get(name, "") for name in PROFILE_FORM_FIELDS},
    )


class UsuarioForm(UserCreationForm):
    rol = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=["Administrador", "Editor", "Consulta"]),
        label="Rol",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "rol"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_profile_fields(self)


class UsuarioEditForm(forms.ModelForm):
    rol = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=["Administrador", "Editor", "Consulta"]),
        label="Rol",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active", "rol"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        add_profile_fields(self)


class EstadoForm(forms.ModelForm):
    codigo = forms.CharField(max_length=30, label="Código")
    nombre = forms.CharField(max_length=100, label="Nombre")

    class Meta:
        model = EventoCompromiso
        fields = ["codigo", "nombre", "activo"]
        labels = {"codigo": "Código", "nombre": "Nombre", "activo": "Activo"}


@login_required
def usuarios(request):
    require(request.user, administrative=True)
    form = UsuarioForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            user.groups.set([form.cleaned_data["rol"]])
            save_form_profile(user, form.cleaned_data)
        messages.success(request, "Usuario creado correctamente.")
        return redirect("usuarios")
    users = list(User.objects.prefetch_related("groups").order_by("username"))
    profiles = profiles_for(users)
    for user in users:
        user.perfil_4dx = profiles[user.pk]
    query = request.GET.get("q", "").strip()
    if query:
        needle = query.casefold()
        users = [
            user
            for user in users
            if needle
            in " ".join(
                [
                    user.username,
                    user.first_name,
                    user.last_name,
                    user.email,
                    *user.perfil_4dx.values(),
                    *(group.name for group in user.groups.all()),
                ]
            ).casefold()
        ]
    return render(
        request,
        "usuarios.html",
        {
            "title": "Usuarios",
            "form": form,
            "usuarios": users,
            "q": query,
            "total_usuarios": len(users),
        },
    )


@login_required
def usuario_editar(request, pk):
    require(request.user, administrative=True)
    target = get_object_or_404(User, pk=pk)
    current_profile = profile_data(EventoCompromiso.perfiles.filter(user=target).order_by("pk").first())
    form = UsuarioEditForm(
        request.POST if request.method == "POST" else None,
        instance=target,
        initial={"rol": target.groups.first(), **current_profile},
    )
    if request.method == "POST" and form.is_valid():
        if target.pk == request.user.pk and (
            not form.cleaned_data["is_active"]
            or form.cleaned_data["rol"].name != "Administrador"
        ):
            form.add_error(None, "No puede quitarse su propio acceso administrativo.")
        elif target.is_superuser and not request.user.is_superuser:
            form.add_error(
                None, "Solo un superusuario puede modificar a otro superusuario."
            )
        else:
            with transaction.atomic():
                user = form.save()
                user.groups.set([form.cleaned_data["rol"]])
                save_form_profile(user, form.cleaned_data, current_profile)
            messages.success(request, "Usuario actualizado.")
            return redirect("usuarios")
    return render(
        request,
        "simple_form.html",
        {"title": "Editar usuario: " + target.username, "form": form},
    )


@login_required
def password(request, pk):
    require(request.user, administrative=True)
    target = get_object_or_404(User, pk=pk)
    if target.is_superuser and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied

        raise PermissionDenied
    form = SetPasswordForm(target, request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Contraseña actualizada.")
        return redirect("usuarios")
    return render(
        request,
        "simple_form.html",
        {"title": "Cambiar contraseña: " + target.username, "form": form},
    )


@login_required
def estados(request, pk=None):
    require(request.user, administrative=True)
    obj = get_object_or_404(EventoCompromiso.estados, estado_id=pk) if pk else None
    form = EstadoForm(request.POST if request.method == "POST" else None, instance=obj or EventoCompromiso(tipo="estado"))
    if obj:
        form.fields["codigo"].disabled = True
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Estado guardado.")
        return redirect("estados")
    return render(
        request,
        "estados.html",
        {
            "title": "Administración de estados",
            "form": form,
            "estados_lista": EventoCompromiso.estados.all(),
        },
    )
