"""Autenticación corporativa del portal 4DX contra Active Directory.

Los códigos C/E se validan con LDAP/NTLM. La contraseña nunca se guarda en el
portal; tras un acceso correcto solo se sincronizan los datos públicos del
directorio en ``usuarios_4dx`` y el perfil existente en
``registros_portal4dx``.
"""

from __future__ import annotations

import logging
import re
import ssl
from dataclasses import dataclass

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend, ModelBackend
from django.contrib.auth.models import Group
from django.db import transaction

log = logging.getLogger(__name__)

CODIGO_DOMINIO_RE = re.compile(r"^[CE]\d{5}$", re.IGNORECASE)


class DominioNoDisponible(Exception):
    """El directorio no pudo atender la validación."""


@dataclass(frozen=True)
class ResultadoDominio:
    ok: bool
    motivo: str
    nombres: str = ""
    apellidos: str = ""
    correo: str = ""


def normalizar_codigo(valor):
    return str(valor or "").strip().upper()


def _codigo_desde_identificador(identificador):
    """Resuelve código C/E directo o correo corporativo ya sincronizado."""
    valor = str(identificador or "").strip()
    codigo = normalizar_codigo(valor)
    if CODIGO_DOMINIO_RE.fullmatch(codigo):
        return codigo
    if "@" not in valor:
        return None
    correo = valor.casefold()
    dominio = correo.rsplit("@", 1)[-1]
    if dominio not in settings.DOMINIOS_CORREO_CLARO:
        return None
    local = normalizar_codigo(correo.split("@", 1)[0])
    if CODIGO_DOMINIO_RE.fullmatch(local):
        return local
    users = get_user_model().objects.filter(email__iexact=correo).only("username")
    user = next(
        (item for item in users if CODIGO_DOMINIO_RE.fullmatch(item.username)),
        None,
    )
    return normalizar_codigo(user.username) if user else None


def es_identificador_corporativo(identificador):
    valor = str(identificador or "").strip()
    if CODIGO_DOMINIO_RE.fullmatch(normalizar_codigo(valor)):
        return True
    if "@" not in valor:
        return False
    return valor.casefold().rsplit("@", 1)[-1] in settings.DOMINIOS_CORREO_CLARO


class ValidadorLDAP:
    """Valida la clave y lee nombre/correo con ldap3, sin persistir la clave."""

    SUBCODIGOS = {
        "775": "CUENTA_BLOQUEADA",
        "533": "CUENTA_DESHABILITADA",
        "701": "CUENTA_DESHABILITADA",
        "532": "CLAVE_VENCIDA",
        "773": "CLAVE_VENCIDA",
        "52e": "CREDENCIALES",
        "525": "CREDENCIALES",
    }

    def validar(self, codigo, clave):
        try:
            from ldap3 import NTLM, Connection, Server, Tls
            from ldap3.core.exceptions import LDAPException
            from ldap3.utils.conv import escape_filter_chars
        except ImportError as exc:
            log.error("Falta la dependencia ldap3 para autenticar contra el dominio")
            raise DominioNoDisponible("LDAP_NO_INSTALADO") from exc

        modo = settings.LDAP_MODO
        tls = None
        if modo in {"starttls", "ldaps"}:
            tls = Tls(
                validate=ssl.CERT_REQUIRED,
                ca_certs_file=settings.LDAP_CA_CERT or None,
            )
        servidor = Server(
            settings.LDAP_HOST,
            port=636 if modo == "ldaps" else 389,
            use_ssl=modo == "ldaps",
            tls=tls,
            connect_timeout=settings.LDAP_TIMEOUT_CONEXION,
        )
        conexion = Connection(
            servidor,
            user=f"{settings.LDAP_DOMINIO_NETBIOS}\\{codigo}",
            password=clave,
            authentication=NTLM,
            receive_timeout=settings.LDAP_TIMEOUT_RESPUESTA,
            auto_bind=False,
            raise_exceptions=False,
        )
        try:
            conexion.open()
            if modo == "starttls" and not conexion.start_tls():
                raise DominioNoDisponible("LDAP_STARTTLS")
            if not conexion.bind():
                mensaje = str((conexion.result or {}).get("message", "")).lower()
                motivo = next(
                    (valor for codigo_ad, valor in self.SUBCODIGOS.items() if f"data {codigo_ad}" in mensaje),
                    "CREDENCIALES",
                )
                return ResultadoDominio(False, motivo)
            if not conexion.search(
                settings.LDAP_BASE_DN,
                f"(sAMAccountName={escape_filter_chars(codigo)})",
                attributes=["givenName", "sn", "mail", "displayName", "userAccountControl"],
            ) or not conexion.entries:
                return ResultadoDominio(False, "USUARIO_NO_ENCONTRADO")
            entrada = conexion.entries[0]

            def valor(atributo):
                return (getattr(entrada, atributo).value if atributo in entrada else None) or ""

            if int(valor("userAccountControl") or 0) & 2:
                return ResultadoDominio(False, "CUENTA_DESHABILITADA")
            nombres = str(valor("givenName")).strip()
            apellidos = str(valor("sn")).strip()
            if not nombres:
                partes = str(valor("displayName")).strip().split()
                nombres = partes[0] if partes else ""
                apellidos = " ".join(partes[1:])
            return ResultadoDominio(
                True,
                "OK",
                nombres=nombres,
                apellidos=apellidos,
                correo=str(valor("mail")).strip().lower(),
            )
        except DominioNoDisponible:
            raise
        except (LDAPException, OSError, ssl.SSLError) as exc:
            log.warning("Active Directory no disponible: %s", type(exc).__name__)
            raise DominioNoDisponible(type(exc).__name__) from None
        finally:
            try:
                conexion.unbind()
            except Exception:
                pass


def validador_dominio():
    return ValidadorLDAP()


class ClaroDirectoryBackend(BaseBackend):
    """Backend para códigos C/E y correos corporativos de Claro."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identificador = username or kwargs.get("identificador")
        codigo = _codigo_desde_identificador(identificador)
        if not codigo:
            return None
        resultado = validador_dominio().validar(codigo, password or "")
        if not resultado.ok:
            return None
        return self._sincronizar(codigo, resultado)

    @staticmethod
    def _sincronizar(codigo, resultado):
        User = get_user_model()
        with transaction.atomic():
            user, creado = User.objects.select_for_update().get_or_create(
                username=codigo,
                defaults={"is_active": True},
            )
            campos = []
            if resultado.nombres and user.first_name != resultado.nombres[:150]:
                user.first_name = resultado.nombres[:150]
                campos.append("first_name")
            if resultado.apellidos and user.last_name != resultado.apellidos[:150]:
                user.last_name = resultado.apellidos[:150]
                campos.append("last_name")
            if resultado.correo and user.email != resultado.correo[:254]:
                user.email = resultado.correo[:254]
                campos.append("email")
            if creado or user.has_usable_password():
                user.set_unusable_password()
                campos.append("password")
            if campos:
                user.save(update_fields=list(dict.fromkeys(campos)))
            if creado or not user.groups.exists():
                consulta, _ = Group.objects.get_or_create(name="Consulta")
                user.groups.add(consulta)

            # El nombre se sincroniza en el perfil tipificado existente sin
            # borrar área, gerencia, dirección ni jefe cargados por el portal.
            from .models import EventoCompromiso
            from .profiles import profile_data, save_profile

            perfil = profile_data(
                EventoCompromiso.perfiles.filter(user=user).order_by("pk").first()
            )
            save_profile(
                user,
                nombre_completo=user.get_full_name().strip() or codigo,
                area=perfil["area"],
                gerencia=perfil["gerencia"],
                direccion=perfil["direccion"],
                jefe=perfil["jefe"],
            )
        return user

    def get_user(self, user_id):
        try:
            user = get_user_model().objects.get(pk=user_id)
        except get_user_model().DoesNotExist:
            return None
        return user if user.is_active else None


class PortalLocalBackend(ModelBackend):
    """Conserva usuarios locales, pero nunca acepta una clave local para C/E."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        identificador = username or kwargs.get(get_user_model().USERNAME_FIELD)
        if es_identificador_corporativo(identificador):
            return None
        return super().authenticate(request, username=username, password=password, **kwargs)
