# Recordatorios al chat grupal 4DX

## Configuración única
1. En Teams abre **Flujos de trabajo / Workflows**. Busca **Enviar alertas de webhook a un chat** (Send webhook alerts to a chat).
2. Inicia sesión dentro de Microsoft y selecciona el chat grupal **4DX** como destino. El nombre en el portal es una etiqueta: el destino real lo determina este flujo, así que comprueba el chat antes de guardar.
3. Para esta integración el desencadenador debe admitir **Cualquiera / Anyone**: el portal usa la URL secreta, no un token OAuth de Microsoft. No elijas las variantes “personas específicas” u “organización”. Si tu organización impide esta modalidad, se necesita configurar una integración autenticada con su administrador; no basta con una contraseña personal.
4. Guarda el flujo y copia la URL HTTP del webhook. Conserva el flujo activo y su conexión de Teams válida.
5. Crea `.env` a partir de `.env.example` y pega la URL completa, sin modificar su firma, después de `TEAMS_WEBHOOK_URL=`. No compartas esta URL ni la subas a Git: permite enviar mensajes mediante tu flujo.
6. Abre el portal mediante su dirección HTTPS pública. El sistema detecta automáticamente ese dominio para el enlace incluido en la tarjeta.
7. Reinicia el proceso del portal. El botón de Reportes se habilitará cuando el webhook esté configurado.

No se necesita guardar tu usuario ni contraseña de Teams en el portal.

## Uso
En Reportes aplica los filtros y actualiza la vista previa con la fecha de corte deseada. Pulsa **Enviar recordatorio a Teams · 4DX**. Editores y administradores pueden enviar; Consulta no puede.
El mensaje contiene totales, hasta 10 compromisos (proyecto, tarea, responsable, objetivo y situación) y un enlace al reporte HTML completo. El enlace exige iniciar sesión en el portal y refleja los datos actuales: no es una copia inmutable. El servidor y su dirección pública deben estar disponibles para abrirlo.
El HTML del correo no se inserta literalmente en Teams; se adapta a una tarjeta de recordatorio.
El botón envía una vez por clic. No hay programación recurrente ni envío al abrir la página.
La respuesta “aceptado” significa que el flujo recibió la solicitud, no que Teams haya confirmado la publicación. Revisa la primera publicación en el chat y el historial de ejecuciones en Workflows. Si hay un timeout, revisa ambos antes de volver a enviar: no hay reintentos automáticos.
Cada intento se registra en `compromisos_envioteams` con usuario, corte, cantidad y resultado, sin almacenar el webhook.

## Referencias oficiales
- https://support.microsoft.com/es-es/workflows/send-messages-in-teams-using-incoming-webhooks
- https://learn.microsoft.com/en-us/microsoftteams/platform/webhooks-and-connectors/how-to/add-incoming-webhook
