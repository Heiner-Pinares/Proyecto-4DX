# Pase a producción con Oracle

El portal usa Django 5.2 y `python-oracledb` en modo Thin, por lo que no necesita Oracle Instant Client. El servidor sí debe resolver `scan-odscbio`, alcanzar TCP/1521 y tener una ruta de red hacia ODSCBIO. Oracle debe ser 19c o posterior.

## Único dato que debes completar

La conexión ya incorpora `scan-odscbio`, puerto `1521`, servicio `ODSCBIO`, usuario `USRFACDOC`, pool y backend Oracle. El usuario recibido como `USRFACDOC]` tenía un corchete accidental y se corrigió a `USRFACDOC`.

Dentro de la carpeta `secrets`, crea `oracle_password.txt` y pega únicamente la contraseña en su primera línea:

```text
TU_CONTRASEÑA_REAL
```

No agregues comillas ni `ORACLE_PASSWORD=`. Ese archivo está excluido de Git y de la imagen Docker. La clave interna de Django se crea y conserva automáticamente en el volumen privado `portal_runtime`; tampoco tienes que configurarla.

La aplicación construye automáticamente `scan-odscbio:1521/ODSCBIO`, una cadena Easy Connect con *service name* apropiada para el host SCAN. `.env` queda disponible solo para cambios avanzados futuros, como un dominio HTTPS o un descriptor RAC distinto.

## Preparación por el DBA

El esquema de la conexión debe ser propietario de las tablas del portal y tener cuota en su tablespace. Para que Django cree las diez tablas necesita `CREATE SESSION`, `CREATE TABLE`, `CREATE SEQUENCE`, `CREATE PROCEDURE` y `CREATE TRIGGER`. El ejemplo revisable está en `deploy/permisos_oracle.sql.example`; el DBA debe ajustar el tablespace según la infraestructura.

Usar un esquema dedicado. Si `USRFACDOC` contiene tablas de otros sistemas, las migraciones no las eliminan, pero compartir propietario complica respaldos, permisos y recuperación. El DBA debe confirmar el uso del esquema antes del primer `migrate`.

## Instalación con Docker

Docker Compose contiene solo la aplicación; Oracle es un servicio externo. Después de clonar el repositorio, agrega la contraseña en `secrets/oracle_password.txt` y arranca:

```bash
git clone URL_DEL_REPOSITORIO portal-4dx
cd portal-4dx
docker compose up --build -d
docker compose logs -f web
```

No hay comando de configuración previo. `run.py` comprueba automáticamente versión, servicio y privilegios Oracle; aplica las migraciones, verifica las diez tablas e inicializa roles y estados. Si algo de Oracle está mal, el contenedor se detiene y deja el motivo en `docker compose logs web`.

Solo la primera cuenta administrativa requiere definir usuario y contraseña:

```bash
docker compose exec web python manage.py createsuperuser
```

El healthcheck consulta `/login/`. No escalar `web` durante una migración: aplicar migraciones con una sola instancia y luego aumentar réplicas.

## Instalación sin Docker en Linux

```bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.lock.txt
# Crear secrets/oracle_password.txt y pegar allí la contraseña.
python run.py --check
python manage.py createsuperuser
python run.py
```

`run.py` realiza automáticamente la verificación y las migraciones. Con `DEBUG=False` ejecuta Gunicorn en `0.0.0.0:8000`. Administrar el proceso mediante systemd, Supervisor o el mecanismo del servidor. Gunicorn no funciona de forma nativa en Windows; allí usar Docker con contenedores Linux o un servidor WSGI compatible.

## HTTPS y URL pública

Para un proxy HTTPS:

```dotenv
DEBUG=False
ALLOWED_HOSTS=portal.tu-dominio
PORTAL_PUBLIC_URL=https://portal.tu-dominio
CSRF_TRUSTED_ORIGINS=https://portal.tu-dominio
COOKIE_SECURE=true
SECURE_SSL_REDIRECT=true
TRUST_PROXY_HTTPS=true
SECURE_HSTS_SECONDS=31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS=false
SECURE_HSTS_PRELOAD=false
WEB_BIND_ADDRESS=127.0.0.1
```

El proxy debe reemplazar `X-Forwarded-Proto` con el protocolo real, conservar `Host` y ser el único que alcance el puerto 8000. `ALLOWED_HOSTS` no lleva protocolo. `PORTAL_PUBLIC_URL` y `CSRF_TRUSTED_ORIGINS` sí. `PORTAL_PUBLIC_URL` es opcional: si se omite, el enlace de Teams se obtiene de la solicitud HTTPS recibida.

## Trasladar los datos actuales

Git transfiere código y migraciones, no usuarios ni compromisos. En la instalación PostgreSQL de origen, con el portal detenido:

```bash
# Solo si ese entorno aún no tiene el controlador PostgreSQL:
python -m pip install -r requirements-postgresql-transfer.txt
python manage.py exportar_portal /ruta/segura/portal_4dx.json
```

El archivo contiene datos privados y hashes de contraseñas; excluye sesiones activas para que todos vuelvan a iniciar sesión. Protegerlo durante el traslado.

En Oracle nuevo, antes de arrancar `run.py` por primera vez:

```bash
python manage.py migrate --noinput
python manage.py loaddata /ruta/segura/portal_4dx.json
python manage.py init_portal
python manage.py verificar_oracle
```

Con Docker, el equivalente monta el respaldo solo durante la importación:

```bash
docker compose run --rm web python manage.py migrate --noinput
docker compose run --rm \
  --volume /ruta/segura/portal_4dx.json:/tmp/portal_4dx.json:ro \
  web python manage.py loaddata /tmp/portal_4dx.json
docker compose run --rm web python manage.py init_portal
docker compose run --rm web python manage.py verificar_oracle
```

Después arrancar el servicio y validar conteos, login, alta/edición, reprogramación, indicadores y exportaciones. Borrar de forma segura el JSON cuando el respaldo corporativo esté confirmado. Si ya se ejecutó `init_portal` en el destino, restaurar un esquema Oracle vacío antes de importar para evitar conflictos de claves únicas.

## Actualizaciones y recuperación

Antes de cada actualización, crear un respaldo Oracle del esquema y conservar la versión de código desplegada. Luego:

```bash
docker compose build
docker compose run --rm web python manage.py migrate --noinput
docker compose up -d web
docker compose exec web python manage.py verificar_oracle
```

No usar `makemigrations` en producción. `AUTO_MIGRATE=false` permite separar la migración del arranque, pero entonces el operador debe ejecutar `migrate` antes. Teams y correo requieren sus secretos propios en `.env`; no afectan la conexión Oracle.

La conexión real no puede validarse fuera de la red corporativa ni sin la contraseña. La aceptación final exige ejecutar `verificar_oracle`, las migraciones sobre un esquema vacío y las pruebas funcionales en el servidor objetivo.
