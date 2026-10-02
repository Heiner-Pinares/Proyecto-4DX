# Envío del resumen semanal por correo

En Reportes → Resumen semanal por jefatura, actualizar corte y filtros y pulsar «Enviar resumen por correo». Usa exactamente la plantilla HTML de la vista previa, regenerada con los datos actuales al pulsar el botón.

Destinatarios fijos, tanto en encabezados como en el sobre sendmail:
- Para: c27826@claro.com.pe
- Cc: c28171@claro.com.pe
- Remitente: 4DX Facturación <4dx@claro.com.pe>

Se adaptó el mecanismo SSH/sendmail del script entregado. El mensaje MIME se transmite por entrada estándar; no se suben archivos temporales ni se agregan los adjuntos del ejemplo. Las credenciales recibidas se guardaron únicamente en .env con permisos 600 mediante CORREO_SSH_HOST, CORREO_SSH_USER y CORREO_SSH_PASSWORD. Requiere acceso a la red corporativa o VPN y permiso para ejecutar sendmail en ese servidor.

SSH confía en la identidad presentada en la primera conexión al servidor configurado y la conserva en work/correo_known_hosts. Las conexiones posteriores rechazan una identidad cambiada. Los errores de conexión no muestran contraseñas.

Solo administradores y editores pueden enviar. POST con protección CSRF, solicitud firmada ligada a usuario/corte/filtros y registro persistente para impedir repetir la misma solicitud. No hay reintentos automáticos: ante una respuesta incierta revisar recepción y cola antes de repetir. El estado aceptado significa salida 0 de sendmail, no entrega confirmada al buzón.

El enlace al tablero usa PORTAL_PUBLIC_URL o la URL de ngrok del proceso y exige autenticación. Reiniciar el portal después de instalar la actualización.
