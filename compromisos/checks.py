"""Comprobaciones de despliegue para la autenticación corporativa."""

from pathlib import Path

from django.conf import settings
from django.core.checks import Error, Warning, register


@register()
def comprobar_directorio(app_configs, **kwargs):
    resultados = []
    try:
        import ldap3  # noqa: F401
    except ImportError:
        resultados.append(
            Error(
                "Falta ldap3; los códigos C/E no podrán iniciar sesión.",
                hint="Instala requirements.lock.txt dentro del entorno virtual.",
                id="compromisos.E001",
            )
        )
    try:
        from Crypto.Hash import MD4  # noqa: F401
    except ImportError:
        resultados.append(
            Error(
                "Falta pycryptodome; Python no puede calcular la respuesta NTLM requerida por LDAP.",
                hint="Instala requirements.lock.txt dentro del entorno virtual.",
                id="compromisos.E004",
            )
        )
    if not settings.LDAP_HOST or not settings.LDAP_DOMINIO_NETBIOS or not settings.LDAP_BASE_DN:
        resultados.append(
            Error(
                "La configuración de Active Directory está incompleta.",
                hint="Revisa LDAP_HOST, LDAP_DOMINIO_NETBIOS y LDAP_BASE_DN.",
                id="compromisos.E002",
            )
        )
    if settings.LDAP_MODO == "plano" and not settings.DEBUG:
        resultados.append(
            Warning(
                "LDAP está configurado en el puerto 389 sin TLS.",
                hint="Solicita a TI LDAPS o StartTLS y configura LDAP_CA_CERT.",
                id="compromisos.W001",
            )
        )
    if settings.LDAP_CA_CERT and not Path(settings.LDAP_CA_CERT).is_file():
        resultados.append(
            Error(
                f"No existe el certificado LDAP configurado: {settings.LDAP_CA_CERT}",
                id="compromisos.E003",
            )
        )
    return resultados
