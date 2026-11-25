# Asistente IA corporativo del Portal 4DX

El asistente usa el flujo existente **API - Asistente IA Corporativo** de Power Automate y AI Builder. La comunicación sale exclusivamente desde Django. El navegador solo llama al endpoint interno autenticado del portal y nunca recibe la URL firmada.

## Configuración

En el `.env` privado del servidor agrega:

```dotenv
AI_ASSISTANT_ENABLED=true
POWER_AUTOMATE_URL=PEGAR_AQUI_LA_URL_HTTPS_FIRMADA
AI_REQUEST_TIMEOUT=90
AI_MAX_INPUT_LENGTH=4000
AI_MAX_HISTORY_MESSAGES=10
AI_MAX_RESPONSE_LENGTH=12000
AI_RATE_LIMIT_REQUESTS=10
AI_RATE_LIMIT_WINDOW=300
AI_MAX_CONCURRENT_REQUESTS=2
AI_DUPLICATE_CACHE_SECONDS=15
AI_ASSISTANT_ALLOWED_GROUPS=
```

`AI_ASSISTANT_ALLOWED_GROUPS` vacío habilita a todos los usuarios autenticados. Para limitarlo, usa nombres exactos separados por comas, por ejemplo `Consulta,Editor,Administrador`.

La URL debe mantenerse fuera de Git, capturas, logs y documentación compartida. Antes de producción, el desencadenador HTTP configurado como “Cualquiera” requiere autorización corporativa o un método de autenticación aprobado.

## Publicación en Windows

No hay dependencias nuevas ni migraciones. Después de actualizar el repositorio:

```powershell
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py collectstatic --noinput
.\scripts\portal.cmd restart
.\scripts\portal.cmd status
```

El chequeo impide iniciar con el asistente activado si falta la URL o si no es HTTPS.

## Funcionamiento y seguridad

- `POST /api/ai/chat/` recibe la pregunta y responde JSON.
- El contexto y el historial se incorporan en el backend al único campo `pregunta` que espera Power Automate.
- La memoria vive en la sesión Django existente y se valida contra el usuario autenticado.
- No se crean tablas y el modelo no tiene acceso a Oracle.
- La respuesta se renderiza mediante nodos de texto; no se inserta HTML del modelo.
- Se aplican CSRF, longitud máxima, rate limiting, límite de concurrencia y deduplicación corta.
- Los logs incluyen identificador numérico de usuario, latencia y errores técnicos; nunca preguntas, respuestas o la URL secreta.
- El portal continúa operativo si Power Automate falla.

## Desactivar o revertir

Para desactivar inmediatamente el asistente:

```dotenv
AI_ASSISTANT_ENABLED=false
```

Reinicia el portal. El botón y los endpoints quedarán deshabilitados, mientras el resto de módulos seguirá funcionando. Para revertir el código, elimina las rutas `api/ai`, el include de `ai_assistant.html` y los archivos `ai_service.py`, `ai_views.py`, `ai_assistant.html`, `ai_assistant.js` y sus estilos.

## Verificación sin consumir créditos

Las pruebas automatizadas sustituyen la comunicación externa mediante mocks:

```powershell
.\.venv\Scripts\python.exe -m pytest compromisos\tests\test_ai_assistant.py -q
.\.venv\Scripts\python.exe -m pytest -q
```

Una prueba real contra Power Automate debe realizarse únicamente cuando la URL, los créditos y el mecanismo de acceso hayan sido autorizados.
