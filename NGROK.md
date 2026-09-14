# Publicación temporal con ngrok

ngrok está instalado para tu usuario de macOS en `/Users/heinerpinares/.local/bin/ngrok` (Apple Silicon). No requiere Homebrew. La descarga procede de https://ngrok.com/download/mac-os.

## 1. Vincular tu cuenta (una sola vez)

Inicia sesión en https://dashboard.ngrok.com/get-started/your-authtoken y copia tu authtoken. En Terminal, dentro del proyecto, ejecuta el siguiente comando reemplazando `TU_AUTHTOKEN`. No es la contraseña de PostgreSQL ni la del portal.

```bash
cd /Users/heinerpinares/Documents/4DX
~/.local/bin/ngrok config add-authtoken "TU_AUTHTOKEN" --config "$PWD/work/ngrok.yml"
chmod 600 work/ngrok.yml
```

La configuración queda en `work/ngrok.yml`, excluida del control de versiones. No hace falta pegar el token en un chat.

## 2. Abrir el túnel cuando quieras publicar

En una Terminal:

```bash
cd /Users/heinerpinares/Documents/4DX
~/.local/bin/ngrok http 8002 --inspect=false --config "$PWD/work/ngrok.yml"
```

Copia la dirección **HTTPS** que aparece en `Forwarding`. El túnel estará activo, pero aún no servirá el portal hasta iniciar el siguiente paso.

## 3. Arrancar el portal temporal

En otra Terminal, reemplaza la URL de ejemplo por la dirección HTTPS exacta que muestra ngrok:

```bash
cd /Users/heinerpinares/Documents/4DX
./.venv/bin/python run_ngrok.py https://TU-DOMINIO.ngrok-free.app
```

Este arranque aplica migraciones, sirve archivos estáticos con Gunicorn y escucha únicamente en `127.0.0.1:8002`. No modifica `.env` ni ocupa el puerto 8000 de tu sesión local. Usa la misma base PostgreSQL: los cambios hechos por visitantes autenticados son cambios reales del portal.

La configuración temporal activa `DEBUG=False`, cookies HTTPS, redirección HTTPS, reconocimiento del proxy y permisos de Host/CSRF restringidos a la dirección indicada. No utiliza comodines de dominios ni desactiva CSRF. Entra con los usuarios del portal. Para personas que solo deban ver información, utiliza el rol Consulta.

Comparte únicamente la URL HTTPS. El servidor de base de datos y pgAdmin no se publican por este túnel.

## 4. Detener la publicación

Presiona **Control + C en ambas terminales**: la de ngrok y la del portal temporal. PostgreSQL conserva los datos. Si ngrok cambia de URL en otra sesión, inicia `run_ngrok.py` con la nueva dirección.

## Comprobaciones sin publicar

```bash
~/.local/bin/ngrok version
./.venv/bin/python run_ngrok.py https://revision.ngrok-free.app --check
```

La segunda orden valida la configuración sin arrancar el túnel ni el servidor. La publicación real y la conexión con la cuenta requieren un authtoken válido.
