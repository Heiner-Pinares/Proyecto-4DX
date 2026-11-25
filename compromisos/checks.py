"""Comprobaciones de despliegue para la autenticación corporativa."""

from pathlib import Path
from urllib.parse import urlsplit

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


@register()
def comprobar_asistente(app_configs, **kwargs):
    if not settings.AI_ASSISTANT_ENABLED:
        return []
    resultados = []
    if not settings.POWER_AUTOMATE_URL:
        resultados.append(
            Error(
                "AI_ASSISTANT_ENABLED está activo, pero falta POWER_AUTOMATE_URL.",
                hint="Configura la URL firmada únicamente en el .env del servidor o desactiva el asistente.",
                id="compromisos.E010",
            )
        )
    else:
        parsed = urlsplit(settings.POWER_AUTOMATE_URL)
        if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
            resultados.append(
                Error(
                    "POWER_AUTOMATE_URL debe ser una URL HTTPS válida sin credenciales embebidas ni fragmento.",
                    id="compromisos.E011",
                )
            )
    numeric = {
        "AI_REQUEST_TIMEOUT": settings.AI_REQUEST_TIMEOUT,
        "AI_MAX_INPUT_LENGTH": settings.AI_MAX_INPUT_LENGTH,
        "AI_MAX_HISTORY_MESSAGES": settings.AI_MAX_HISTORY_MESSAGES,
        "AI_MAX_RESPONSE_LENGTH": settings.AI_MAX_RESPONSE_LENGTH,
        "AI_RATE_LIMIT_REQUESTS": settings.AI_RATE_LIMIT_REQUESTS,
        "AI_RATE_LIMIT_WINDOW": settings.AI_RATE_LIMIT_WINDOW,
        "AI_MAX_CONCURRENT_REQUESTS": settings.AI_MAX_CONCURRENT_REQUESTS,
    }
    invalid = [name for name, value in numeric.items() if value <= 0]
    if invalid:
        resultados.append(
            Error(
                "La configuración numérica del asistente debe contener valores positivos.",
                hint="Revisa: " + ", ".join(invalid),
                id="compromisos.E012",
            )
        )
    return resultados
