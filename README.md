# Portal de Gestión de Compromisos · 4DX

Aplicación ejecutable en Python 3.12 y Django 5.2 para centralizar compromisos, reprogramaciones, auditoría, indicadores y reportes. Interfaz corporativa en español con Django Templates, CSS y JavaScript vanilla. PostgreSQL es el motor predeterminado; todo acceso a datos de negocio utiliza el ORM.

## Estado de la entrega local

El proyecto está en `/Users/heinerpinares/Documents/4DX`. Se creó un entorno `.venv` con Python 3.12 y una instalación local `.runtime` para no depender del Python 3.9 del sistema ni de archivos temporales. Ambos se excluyen del código distribuible.

La configuración `.env` de esta máquina utiliza **PostgreSQL 18** en `localhost:5432`, base `compromisos_db`. Se migraron desde SQLite 1 usuario, 3 grupos, 4 estados, 7 compromisos y 7 entradas de historial, conservando el hash de contraseña del usuario existente. La contraseña de conexión está únicamente en `.env`, excluido del control de versiones y con permisos de acceso restringidos.

SQLite ya no es la base activa. Se conserva como respaldo en `work/local.sqlite3`, junto a una copia consistente y el archivo de transferencia en el directorio indicado por `work/ultima_migracion.txt`. Estos respaldos contienen información privada y no deben publicarse.

Se verificaron migraciones sobre PostgreSQL vacío, segundo arranque idempotente, coincidencia de los registros trasladados y las 79 pruebas automatizadas sobre PostgreSQL (79 aprobadas). También se comprobaron dashboard, compromisos, indicadores y exportaciones con el usuario trasladado. Docker sigue sin estar instalado; su configuración con PostgreSQL 16 está preparada pero no se ha ejecutado en este equipo.

Para consultar en pgAdmin: servidor `localhost`, puerto `5432`, usuario `postgres`, base `compromisos_db`. Dentro de la base abre **Schemas → public → Tables**. Los compromisos están en `compromisos` y los usuarios en `auth_user`.

## Probar inmediatamente en este equipo

```bash
cd /Users/heinerpinares/Documents/4DX
source .venv/bin/activate
python run.py --check
# Solo si necesitas otro administrador:
# python manage.py createsuperuser
python run.py
```

Abre http://localhost:8000 e ingresa con tu usuario existente (`prueba`) y la contraseña que elegiste. Si el servidor ya está en ejecución, no necesitas iniciarlo otra vez. `createsuperuser` solicita usuario y contraseña mediante el mecanismo nativo de Django. No hay contraseñas incorporadas al código.

Desde **Usuarios**, el administrador puede crear cuentas, asignar roles, editar datos, desactivar accesos y cambiar contraseñas. No necesita usar Django Admin como interfaz cotidiana.

## Instalación con PostgreSQL sin Docker

1. Instala Python 3.12 o posterior y PostgreSQL soportado (la configuración Docker fija PostgreSQL 16).
2. Crea una base PostgreSQL vacía y un usuario propietario mediante pgAdmin o las herramientas del servidor. La aplicación crea las **tablas dentro de una base existente**; no crea el servicio PostgreSQL, sus roles ni la base contenedora.
3. En la carpeta del proyecto:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
cp .env.example .env
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Copia la clave generada a `SECRET_KEY` en `.env` y configura `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST` y `DB_PORT`. No sobrescribas un `.env` con información que quieras conservar; en ese caso edítalo. Para desarrollo local puedes establecer `DEBUG=True`.

```bash
python run.py --check
python manage.py createsuperuser
python run.py
```

`run.py --check` inicializa sin iniciar el servidor. `python run.py` reintenta la conexión hasta 30 veces (2 segundos entre intentos), aplica las migraciones versionadas con `interactive=False`, inicializa roles y estados sin duplicarlos, recopila estáticos y arranca el servidor. Con `DEBUG=False` utiliza Gunicorn, con `DEBUG=True` el servidor de desarrollo de Django. No ejecuta `makemigrations` ni inserta demos al arrancar.

## Ejecución con Docker

Configura `.env` a partir de `.env.example`. Define una `SECRET_KEY` aleatoria y una contraseña PostgreSQL propia antes de ejecutar:

```bash
docker compose up --build
```

Abre http://localhost:8000. Compose crea la base contenedora mediante la imagen oficial `postgres:16`; su healthcheck debe pasar antes de iniciar `web`. El arranque de `web` crea las tablas automáticamente. El puerto de PostgreSQL no se expone al host; los datos persisten en `postgres_data`.

Crea el primer administrador en otra terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

El contenedor de la aplicación se ejecuta como usuario sin privilegios. Usa un único proceso de inicialización por despliegue antes de escalar réplicas: el arranque idempotente no es un coordinador distribuido de migraciones concurrentes.

## Variables de entorno

| Variable | Función |
| --- | --- |
| `DEBUG` | `False` en producción; `True` activa servidor de desarrollo y errores detallados. |
| `SECRET_KEY` | Clave secreta única, larga y aleatoria. Obligatoria. |
| `ALLOWED_HOSTS` | Hosts permitidos, separados por comas. Predeterminado: `localhost,127.0.0.1`. |
| `DB_ENGINE` | `postgresql` por defecto; acepta backend completo de Django. |
| `DB_NAME` | Base existente; en SQLite, ruta del archivo. |
| `DB_USER`, `DB_PASSWORD` | Credenciales del motor. |
| `DB_HOST`, `DB_PORT` | Dirección y puerto; Docker fija `db:5432`. |
| `AUTO_MIGRATE` | `true` aplica migraciones. Con `false`, el esquema debe estar preparado antes del arranque. |
| `CLOSED_STATUS_CODE` | Código de terminado; `T` por defecto. |
| `PENDING_STATUS_CODE` | Código pendiente; `P` por defecto. |
| `IN_PROGRESS_STATUS_CODE` | Código en proceso; `E` por defecto. |
| `DUE_SOON_DAYS` | Horizonte de próximos vencimientos; 7 días, inclusive. |
| `ALLOW_EARLIER_RESCHEDULE` | `false` impide nuevas fechas anteriores a la vigente. |
| `COOKIE_SECURE` | Activa cookies de sesión y CSRF solo sobre HTTPS. |

Zona horaria `America/Lima`, `USE_TZ=True`. El portal presenta fechas como `DD/MM/YYYY`, y horas como `DD/MM/YYYY HH:mm`. Los controles HTML de fecha utilizan el formato interno estándar del navegador.

## Edición como hoja de cálculo y cumplimiento por fechas

En **Compromisos**, haz clic en una celda para editarla. Enter guarda, Tab guarda y avanza, Escape cancela; Shift+Enter agrega una línea en textos largos. También hay botones Guardar/Cancelar. Las flechas permiten recorrer celdas cuando no hay una edición abierta. Se mantienen filtros y paginación; la tabla muestra las columnas originales con desplazamiento horizontal y encabezados fijos.

Los controles validan en servidor y muestran errores sin descartar el texto escrito. Cada fila lleva una versión: si otra persona la modifica, el servidor rechaza la edición obsoleta (HTTP 409) y pide recargar. Las modificaciones son transaccionales, registran usuario e historial y requieren permisos de Editor/Administrador. Consulta sigue siendo solo lectura. Las correcciones de 1ERA/2DA/3RA FECHA solicitan motivo y conservan registros de fechas anteriores.

**PUNTAJE / Cumplimiento % se calcula automáticamente**, sin escritura manual:

| Condición | Puntaje |
| --- | --- |
| Sin fecha real | Sin puntaje (—) |
| Fecha real anterior o igual a 1ERA FECHA | 100 % |
| Fuera de la primera, pero anterior o igual a 2DA FECHA | 80 % |
| Cumplido en tercera fecha o cualquier otro caso con fecha real | 60 % |

Si 1ERA FECHA está vacía, se usa el vencimiento original. Si no hay ninguna fecha objetivo pero sí fecha real, se asigna 60 %. Siempre prevalece la primera fecha que se cumplió: tener segunda o tercera fecha registrada no reduce un cierre que ocurrió a tiempo en la primera. Un cierre tarde sin segunda fecha recibe 60 %.

La tarjeta principal y los gráficos por responsable, tema, iniciativa y mes promedian este puntaje sobre los registros con fecha real, excluyendo suspendidos. Excel y Word incluyen el mismo puntaje. El indicador separado **cumplimiento de meta** conserva la fórmula puntaje/meta; no debe confundirse con el cumplimiento por fechas 100/80/60.

La migración `0002_cumplimiento_fechas` recalcula los datos existentes y deja auditoría de los puntajes que cambian. Antes de aplicarla se creó un respaldo PostgreSQL en `work/antes_edicion_tabla_*.dump`. No se reemplazan las fechas existentes.

La acción Reprogramar conserva el vencimiento original como primera fecha cuando esa casilla está vacía; luego completa la segunda y la tercera. El número del evento de historial es independiente de la posición de la fecha. Los eventos posteriores a la tercera se conservan en el historial.

## Funcionalidades y permisos

- **Administrador**: operaciones completas, papelera, restauración, eliminación definitiva, usuarios, estados, indicadores y reportes. Los superusuarios también tienen estas capacidades.
- **Editor**: crear, consultar, editar, reprogramar, cerrar, suspender, reactivar, registrar notas e indicadores. Puede descargar reportes de la información que ya puede consultar.
- **Consulta**: lectura, indicadores y exportaciones.

Las vistas y servicios verifican permisos; ocultar botones no sustituye la autorización. Todas las pantallas de negocio requieren autenticación. Las modificaciones usan POST con CSRF. El logout también es POST. Django mantiene sesiones y hashes de contraseña. No se concede acceso al admin técnico automáticamente al rol Administrador; un superusuario puede entrar por `/admin/`.

La eliminación normal asigna `deleted_at`, preserva historial y oculta el compromiso del manager normal. Solo un administrador ve `/papelera/`. La eliminación física requiere primero estar en la papelera y escribir literalmente `ELIMINAR`; elimina también el historial asociado. Se registra el evento de purga en logs.

## Reglas de negocio y decisiones

- Se conservan los 17 campos legacy. `mes` se deriva de `fecha_de_compromiso` en español. Solo Django Admin permite corregir el mes legacy manualmente; una posterior edición normal vuelve a derivarlo.
- Los estados se administran en una tabla `Estado`. El código continúa siendo `CharField` para conservar datos legacy. Los nombres y actividad se editan en el portal. Los códigos existentes no se renombran directamente desde esta pantalla para evitar dejar referencias huérfanas; se puede crear un código nuevo y hacer una migración de datos controlada.
- `status` y situación del plazo son conceptos independientes. Suspender cambia `suspendida` y conserva el estado anterior. Cerrar fija el código configurado y guarda fecha real, puntaje y nota en auditoría.
- **Fecha vigente**: tercera fecha, segunda, primera, vencimiento original, en ese orden. Se respeta literalmente la regla solicitada: las reprogramaciones posteriores a la tercera fecha quedan en `Reprogramacion` pero no reemplazan la fecha objetivo legacy. La pantalla lo informa. Esta política puede cambiarse después en el servicio y su expresión ORM, junto con sus pruebas de equivalencia.
- Para registros legacy con fechas previas sin filas de historial, el siguiente número parte de la última posición ocupada. No se sobrescribe una fecha anterior ni se inventa su motivo.
- Reprogramar bloquea la fila dentro de una transacción y mantiene un número único por compromiso. El historial y la actualización de fechas se confirman juntos o se revierten juntos. La concurrencia real debe probarse sobre el motor de producción; SQLite no ofrece el bloqueo de filas de PostgreSQL.
- Suspendido prevalece en la situación calculada. Sin fecha objetivo se muestra `Por definir`, incluso si existe fecha real, porque no hay plazo contra el cual comparar.
- El vencimiento de hoy se considera `Por vencer`. El intervalo es de 0 a `DUE_SOON_DAYS` inclusive.
- La situación se calcula sobre fechas sin sobrescribir automáticamente el estado de negocio.

## Indicadores

Los filtros globales afectan todas las tarjetas, gráficos y tabla por responsable. Se usa agregación en la base mediante ORM; no se descargan todos los registros al navegador para calcular métricas. La tabla de compromisos se pagina en servidor (10, 25, 50 o 100) y conserva filtros.

1. **Cumplimiento de cierre** = terminados no suspendidos / total no suspendidos × 100. Se define expresamente `aplicables` como no suspendidos.
2. **Cumplimiento de plazo** = terminados a tiempo no suspendidos / terminados no suspendidos con fecha real y objetivo × 100.
3. **Cumplimiento de meta individual** = puntaje / meta × 100, solo si meta > 0 y puntaje no es nulo. La tarjeta muestra el promedio de los cocientes válidos. 100 / 95 = **105,26 %**, sin truncarlo a 100 %.

Los porcentajes sin denominador se muestran en 0; promedios sin valores se muestran como `—`. Los contadores generales de terminados y abiertos incluyen suspendidos para que su suma corresponda al total; el denominador de cumplimiento los excluye.

Los ocho gráficos usan SVG y JavaScript locales, con datos alternativos accesibles bajo “Ver datos”; no necesitan CDN. La evolución mensual agrupa por fecha de compromiso y promedia el cumplimiento de fechas de cada cohorte, no snapshots mensuales históricos. Reprogramaciones por mes agrupa la fecha de registro de la reprogramación dentro del conjunto filtrado.

## Reportes y exportaciones

`/reportes/` produce DOCX agrupado por tema e iniciativa, con vencimiento original, fecha vigente, cierre, reprogramaciones, motivos y notas. La fecha de corte **evalúa la situación de los datos actuales**; no reconstruye estados pasados. La auditoría textual por sí sola no constituye un sistema completo de snapshots históricos.

Excel conserva los nombres de las 17 columnas legacy y las fechas como fechas nativas. Los textos se guardan como cadenas, evitando la ejecución de fórmulas introducidas en tareas o notas. Ambos formatos excluyen eliminados y respetan filtros. Los archivos se generan en memoria con nombres controlados; no existe carga/importación de archivos en esta versión.

## Datos de demostración

```bash
python manage.py seed_demo
# En Docker:
docker compose exec web python manage.py seed_demo
```

Comando opcional e idempotente: incluye el registro real de diciembre de 2025 y seis ejemplos de plazo. No crea cuentas y nunca lo ejecuta el arranque de producción.

## Pruebas

```bash
python -m pytest -q
python manage.py check
python manage.py makemigrations --check --dry-run
python run.py --check
python run.py --check
```

`pytest.ini` utiliza SQLite en memoria con `config.test_settings`; la contraseña rápida de pruebas solo vive en esa configuración. Se cubren creación/edición, auditoría, borrado y restauración, purga con confirmación, reprogramaciones 1–5 y legacy, rollback, situaciones y equivalencia con ORM, 105,26 %, filtros, permisos, CSRF, páginas, formularios, paginación y exportaciones.

Para ejecutar las mismas pruebas contra PostgreSQL configurado (el usuario de prueba necesita permiso para crear una base de test):

```bash
python -m pytest --ds=config.settings -q
# O con Compose levantado:
docker compose exec web python -m pytest --ds=config.settings -q
```

Antes de aceptar un despliegue, verificar en PostgreSQL una base vacía, dos arranques consecutivos, login, operaciones, exportaciones y pruebas. Las migraciones y la transferencia ya se verificaron sobre PostgreSQL 18 local. La ejecución mediante Docker con PostgreSQL 16 sigue pendiente.

## Arquitectura y archivos

```text
4DX/
├── manage.py, run.py
├── requirements.txt, requirements.lock.txt, pytest.ini
├── .env.example, .gitignore, .dockerignore
├── Dockerfile, docker-compose.yml
├── README.md
├── config/
│   ├── settings.py, test_settings.py, urls.py, wsgi.py
├── compromisos/
│   ├── models.py             # Esquema portable y propiedades
│   ├── services.py           # Mutaciones transaccionales y auditoría
│   ├── selectors.py          # Filtros y situación calculada en ORM
│   ├── indicators.py         # Agregaciones y fórmulas
│   ├── reports.py            # DOCX y XLSX
│   ├── forms.py, views.py, urls.py
│   ├── accounts.py           # Usuarios y estados del portal
│   ├── permissions.py, admin.py
│   ├── migrations/0001_initial.py
│   ├── management/commands/init_portal.py, seed_demo.py
│   └── tests/test_portal.py
├── templates/
│   ├── base.html, dashboard.html, indicadores.html, reportes.html
│   ├── usuarios.html, estados.html, simple_form.html
│   ├── filters.html, kpis.html, pagination.html, upcoming.html
│   ├── 403.html, 404.html, 500.html
│   ├── registration/login.html
│   └── compromisos/list.html, form.html, detail.html, action.html, trash.html
└── static/css/portal.css, static/js/portal.js
```

`work/`, `.runtime/`, `.venv/` y `staticfiles/` son artefactos locales ignorados. La identidad visual se configura mediante variables en `static/css/portal.css`.

## Migraciones y cambio futuro de motor

Al cambiar modelos en desarrollo:

```bash
python manage.py makemigrations compromisos
python manage.py migrate
python -m pytest -q
```

Versiona las migraciones junto al código. Nunca ejecutes `makemigrations` automáticamente en producción. Con `AUTO_MIGRATE=false`, el operador debe aplicar las migraciones de la versión como paso de despliegue; la aplicación no omite la necesidad de un esquema válido.

Para cambiar motor, instala el driver/backend, ajusta `DB_ENGINE` y conexión en `.env`, revisa sus opciones particulares en `config/settings.py`, aplica migraciones sobre una base nueva, traslada datos con un proceso validado y ejecuta toda la batería sobre ese motor. MySQL y Oracle tienen backends de Django; SQL Server requiere uno de terceros compatible. No basta con copiar el archivo físico de la base. Revisa límites de índices, collation, Unicode, precisión decimal, zona horaria y semántica de bloqueos del nuevo motor.

El dominio no contiene SQL manual, campos exclusivos de PostgreSQL, triggers, arrays ni enums de ese motor. La portabilidad de diseño no sustituye una prueba de aceptación sobre cada backend destino.

## Operación y evolución

Configura HTTPS, `DEBUG=False`, hosts y cookies seguras en producción. Mantén `.env` fuera del control de versiones. Los logs van a salida estándar: arranque, conexión, migraciones, identificadores de acciones, exportaciones y errores. No registran contraseñas ni contenidos de notas. Configura persistencia/rotación de logs y backups del motor en el despliegue.

SSO/Active Directory puede integrarse mediante un backend de autenticación Django que sincronice usuarios y grupos; los servicios siguen recibiendo el usuario autenticado. Quedan para fases posteriores las notificaciones externas, importación legacy, snapshots históricos reproducibles, evaluación con cargas reales y la decisión de usar la última reprogramación sin límite como objetivo vigente.

## Paleta visual corporativa

Se conservan la distribución, los controles y los flujos del portal. La paleta se define en `static/css/portal.css`: rojo `#DA291C`, rosa `#FF67B9`, cyan `#009FDF`, amarillo `#FFCB00`, naranja `#FF7500`, negro `#000000` y blanco `#FFFFFF`. Fondos suaves y separadores son mezclas de estos colores con blanco; los gráficos utilizan las mismas variables. Los botones principales son rojos con texto blanco; las superficies cyan, rosa, amarilla y naranja usan texto negro.

Después de actualizar estáticos durante una publicación ngrok, reinicia el proceso `run_ngrok.py` con la misma URL y recarga el navegador. El túnel de ngrok puede permanecer abierto.


### Vista HTML del correo de seguimiento
En Reportes, el apartado Correo de seguimiento permite elegir el corte, ver el correo, abrirlo en otra pestaña y descargar HTML con estilos incluidos. Respeta los filtros del reporte. Incluye compromisos actualmente abiertos (sin fecha real ni estado cerrado), no suspendidos ni eliminados, cuya fecha de compromiso sea anterior o igual al corte, o esté sin definir. No limita los objetivos futuros: muestra todo el trabajo pendiente iniciado hasta el corte. Evalúa los plazos con las fechas vigentes; no reconstruye estados históricos. Agrupa por tema e iniciativa y resume vencidos, próximos a vencer, en plazo y sin fecha objetivo. No envía correos.


### Estatus y vencimiento automático
Los estatus son EC (En curso, verde #00843D), S (Suspendido, ámbar #FFCB00), T (Terminado, negro) y D (Demorado, rojo). La celda completa muestra el color y conserva el código textual. La columna Suspendida y las acciones de suspensión/reactivación controlan S. Estatus no admite edición manual. El estatus es automático: S si está suspendido, T si tiene fecha real, D si el objetivo vigente es anterior a hoy, EC en los demás casos. Se recalcula al consultar, por lo que el paso de los días no exige editar una fila. El código almacenado se actualiza al guardar; la tabla, filtros, indicadores y exportaciones usan el cálculo vigente.
El vencimiento no se edita: toma tercera_fecha, segunda_fecha o primera_fecha, en ese orden; sin fechas queda vacío. La migración 0003 conserva la fecha inicial anterior en primera_fecha si estaba vacía y registra los cambios de datos en el historial. Los códigos anteriores se normalizan al catálogo actual. El puntaje compara la fecha real con primera_fecha (100%), luego segunda_fecha (80%) y el resto (60%). Reiniciar el portal después de actualizar y recargar el navegador para cargar el CSS y JS nuevos.

Colores de referencia actualizados: EC fondo #CEEED0; S #FCECA6; D #F6C9CE; T negro con texto blanco. Cumplimiento 100% usa #BBAAB6. Estatus y cumplimiento están centrados.
