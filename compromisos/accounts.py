from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm
from django.contrib.auth.models import Group, User
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render

from .models import Estado
from .permissions import require


class UsuarioForm(UserCreationForm):
    rol = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=["Administrador", "Editor", "Consulta"]),
        label="Rol",
    )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "rol"]


class UsuarioEditForm(forms.ModelForm):
    rol = forms.ModelChoiceField(
        queryset=Group.objects.filter(name__in=["Administrador", "Editor", "Consulta"]),
        label="Rol",
    )

    class Meta:
        model = User
        fields = ["first_name", "last_name", "email", "is_active", "rol"]


class EstadoForm(forms.ModelForm):
    class Meta:
        model = Estado
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
        messages.success(request, "Usuario creado correctamente.")
        return redirect("usuarios")
    return render(
        request,
        "usuarios.html",
        {
            "title": "Usuarios",
            "form": form,
            "usuarios": User.objects.prefetch_related("groups").order_by("username"),
        },
    )


@login_required
def usuario_editar(request, pk):
    require(request.user, administrative=True)
    target = get_object_or_404(User, pk=pk)
    form = UsuarioEditForm(
        request.POST if request.method == "POST" else None,
        instance=target,
        initial={"rol": target.groups.first()},
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
    obj = get_object_or_404(Estado, pk=pk) if pk else None
    form = EstadoForm(request.POST if request.method == "POST" else None, instance=obj)
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
            "estados_lista": Estado.objects.all(),
        },
    )
