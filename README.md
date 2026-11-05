# Portal de Gestión de Compromisos · 4DX

Aplicación ejecutable en Python 3.12 y Django 5.2 para centralizar compromisos, reprogramaciones, auditoría, indicadores y reportes. Interfaz corporativa en español con Django Templates, CSS y JavaScript vanilla. Oracle 19c o posterior es el motor de producción; todo acceso a datos de negocio utiliza el ORM.

## Estado de la entrega local

El proyecto está en `/Users/heinerpinares/Documents/4DX`. Se creó un entorno `.venv` con Python 3.12 y una instalación local `.runtime` para no depender del Python 3.9 del sistema ni de archivos temporales. Ambos se excluyen del código distribuible.

La configuración `.env` de esta Mac conserva **PostgreSQL 18** únicamente como origen local de los datos actuales. Producción y Docker están configurados para Oracle mediante `python-oracledb`; la contraseña Oracle se lee de `secrets/oracle_password.txt`, excluido del control de versiones y de la imagen.

SQLite ya no es la base activa. Se conserva como respaldo en `work/local.sqlite3`, junto a una copia consistente y el archivo de transferencia en el directorio indicado por `work/ultima_migracion.txt`. Estos respaldos contienen información privada y no deben publicarse.

La batería portable se ejecuta con SQLite en memoria y la configuración local continúa permitiendo verificar el origen PostgreSQL. La conexión, los permisos, las migraciones y la operación sobre Oracle deben validarse dentro de la red corporativa con `python manage.py verificar_oracle`; no se dispone de la contraseña ni de acceso a ODSCBIO desde este equipo.

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

## Inicio de sesión corporativo

Los códigos corporativos con formato `C12345` o `E12345` validan su contraseña
directamente contra el Active Directory de Claro mediante LDAP/NTLM. El portal
no guarda esa contraseña ni su hash: después de una validación correcta obtiene
del directorio nombres, apellidos y correo, y los sincroniza en la tabla
`usuarios_4dx`. El área, gerencia, dirección y jefe ya registrados se conservan
en el perfil de `registros_portal4dx`.

Si el código ya existe, conserva sus grupos y permisos. Si es su primer ingreso,
el portal crea la fila en `usuarios_4dx` y le asigna el grupo `Consulta`. El
administrador puede cambiarlo posteriormente a `Editor` o `Administrador`. Los
usuarios cuyo identificador no sea un código C/E ni un correo de Claro continúan
usando su contraseña local con hash de Django.

Al publicar esta versión, las sesiones abiertas con el backend anterior se
cierran una sola vez y las personas deben volver a iniciar sesión. Esto impide
que un código C/E conserve accidentalmente una vía de acceso mediante una
contraseña local antigua. La pantalla de Usuarios tampoco ofrece restablecer la
contraseña de una cuenta C/E, porque esa clave pertenece al dominio corporativo.

La configuración predeterminada replica el directorio corporativo conocido:

```dotenv
LDAP_HOST=claro.pe
LDAP_DOMINIO_NETBIOS=CLARO
LDAP_BASE_DN=dc=claro,dc=pe
LDAP_MODO=plano
DOMINIOS_CORREO_CLARO=claro.com.pe
```

`LDAP_MODO=plano` conserva la compatibilidad actual de la red. Para producción,
usar `starttls` o `ldaps` cuando TI entregue el certificado raíz y guardar su
ruta en `LDAP_CA_CERT`. Un correo corporativo puede utilizarse después del primer
ingreso con código, cuando el portal ya conoce la relación entre correo y código.

## Instalación con Oracle sin Docker

1. Instala Python 3.12. Oracle Instant Client no es necesario porque `python-oracledb` usa modo Thin.
2. El DBA debe preparar un esquema Oracle 19c o posterior con cuota y permisos de creación. La aplicación crea las **tablas dentro de ese esquema existente**; no crea la instancia, el servicio ni el usuario Oracle.
3. En la carpeta del proyecto instala dependencias y crea `secrets/oracle_password.txt` con la contraseña como única línea:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.lock.txt
```

Host, puerto, servicio y usuario ya están incorporados. La clave interna de Django se genera y persiste automáticamente. `.env` solo se necesita si luego deseas reemplazar valores avanzados como dominio, HTTPS o DSN.

```bash
python run.py --check
python manage.py createsuperuser
python run.py
```

`run.py --check` inicializa sin iniciar el servidor. `python run.py` reintenta la conexión hasta 30 veces (2 segundos entre intentos), aplica las migraciones versionadas con `interactive=False`, inicializa roles y estados sin duplicarlos, recopila estáticos y arranca el servidor. Con `DEBUG=False` utiliza Gunicorn en Linux/macOS y Waitress en Windows; con `DEBUG=True` utiliza el servidor de desarrollo de Django. No ejecuta `makemigrations` ni inserta demos al arrancar.

## Producción en Windows con Waitress

El controlador de Windows ejecuta siempre el portal con `DEBUG=False`, por lo que `run.py` usa **Waitress** y escucha en `0.0.0.0`. El puerto predeterminado es **8000** para conservar el comportamiento existente; se puede sustituir con `PORTAL_PORT` en `.env` o con `-Port` en cada comando. El método de desarrollo (`python manage.py runserver`) no cambia.

En PowerShell, desde la raíz del repositorio, instala una sola vez:

```powershell
cd "D:\RUTA CON ESPACIOS\Proyecto-4DX"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.lock.txt

# Solo si aún no existe .env:
Copy-Item .env.example .env
```

Completa la configuración real de base de datos en `.env` sin copiar secretos de otros portales. Para Oracle, la alternativa recomendada es crear `secrets\oracle_password.txt` con la contraseña como única línea y conceder lectura únicamente a la cuenta de servicio. No agregues ese archivo al repositorio. El controlador valida el entorno virtual, la configuración, la conexión a la base, las migraciones, los permisos de escritura, el puerto y los archivos estáticos antes de abrir Waitress.

La operación diaria no requiere abrir PowerShell como administrador:

```powershell
.\scripts\portal.cmd start
.\scripts\portal.cmd status
.\scripts\portal.cmd logs
.\scripts\portal.cmd restart
.\scripts\portal.cmd stop
```

Para usar otro puerto en una ejecución:

```powershell
.\scripts\portal.cmd start -Port 8104
.\scripts\portal.cmd status -Port 8104
.\scripts\portal.cmd logs -Tail 150
.\scripts\portal.cmd stop -Port 8104
```

Usa el mismo puerto en todos los comandos. `start` ejecuta `check`, comprueba la base de datos, aplica las migraciones versionadas, ejecuta `collectstatic`, verifica que el puerto esté libre e inicia Waitress sin mantener una consola abierta. `stop` lee el PID privado y compara el ejecutable y la ruta absoluta de `run.py` antes de detenerlo; si no coinciden, se niega a terminar el proceso. Así no detiene otros portales ni otros procesos Python.

Los archivos de esta instancia son independientes:

```text
.runtime\windows-portal\portal.pid
.runtime\windows-portal\portal.json
.runtime\windows-portal\logs\portal.stdout.log
.runtime\windows-portal\logs\portal.stderr.log
staticfiles\
```

Las rutas se pueden cambiar mediante `PORTAL_RUNTIME_DIR` y `STATIC_ROOT`, incluso a rutas absolutas. No deben apuntar a carpetas usadas por otro portal; el controlador escribe un marcador de propietario y rechaza una carpeta marcada por otra instalación. La cuenta que arranca el proceso necesita lectura sobre el proyecto y secretos, y modificación sobre esas dos carpetas, `runtime-config` y, cuando se usa el correo SSH, `work`. Si `logs` no puede leer un archivo por permisos, muestra la ruta y un ejemplo de `icacls` sin ocultar el error original.

### Inicio automático al encender Windows

Abre **PowerShell como administrador** únicamente para registrar o actualizar la tarea programada y ejecuta:

```powershell
cd "D:\RUTA CON ESPACIOS\Proyecto-4DX"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\publicar_portal_windows.ps1" `
  -ServiceAccount "DOMINIO\USUARIO" `
  -PublicUrl "http://IP_DEL_SERVIDOR:8000" `
  -Port 8000 `
  -TaskName "Portal 4DX - Inicio automático" `
  -AllowInternalHttp
```

El script solicita la contraseña con `Read-Host -AsSecureString`; no la muestra, imprime ni guarda en archivos. Antes de registrar la tarea ejecuta todas las validaciones. Después la inicia bajo la cuenta de servicio y comprueba que el proceso quede activo. Si la prueba falla, elimina la tarea nueva o restaura la definición anterior. Volver a ejecutar el mismo comando actualiza la tarea existente.

`-AllowInternalHttp` confirma que la URL HTTP se usará solo dentro de la red interna. Para producción detrás de un proxy HTTPS, omite ese parámetro y usa la URL HTTPS:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\publicar_portal_windows.ps1" `
  -ServiceAccount "DOMINIO\USUARIO" `
  -PublicUrl "https://portal4dx.interno.claro" `
  -Port 8000 `
  -TaskName "Portal 4DX - Inicio automático"
```

En este segundo ejemplo el proxy recibe HTTPS en 443 y reenvía a Waitress en el puerto interno 8000. `PublicUrl` y `Port` pueden ser diferentes precisamente por ese motivo. Waitress no debe quedar accesible directamente desde Internet. El publicador no crea reglas de firewall. Si la política corporativa requiere abrir el puerto a la LAN, un administrador debe limitar la regla a la subred interna, por ejemplo:

```powershell
New-NetFirewallRule -DisplayName "Portal 4DX interno" -Direction Inbound `
  -Protocol TCP -LocalPort 8000 -RemoteAddress LocalSubnet -Action Allow
```

Para una comprobación previa que no inicia el servidor:

```powershell
.\scripts\portal.cmd validate -Port 8000
```

Las advertencias de `check --deploy` se distinguen de los errores bloqueantes. Algunas son esperables durante una publicación HTTP interna; para acceso por proxy deben resolverse con cookies seguras, hosts explícitos y HTTPS.

## Ejecución con Docker

Después de crear `secrets/oracle_password.txt`, ejecuta:

```bash
docker compose up --build -d
```

Abre `http://IP_DEL_SERVIDOR:8000`. Compose se conecta al servicio Oracle externo. El arranque comprueba Oracle, crea o actualiza las tablas y verifica el esquema automáticamente.

Crea el primer administrador en otra terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

El contenedor de la aplicación se ejecuta como usuario sin privilegios. Usa un único proceso de inicialización por despliegue antes de escalar réplicas: el arranque idempotente no es un coordinador distribuido de migraciones concurrentes.

## Variables de entorno

| Variable | Función |
| --- | --- |
| `DEBUG` | `False` en producción; `True` activa servidor de desarrollo y errores detallados. |
| `SECRET_KEY` | Opcional; si falta se genera y conserva automáticamente. |
| `ALLOWED_HOSTS` | Hosts permitidos, separados por comas. El arranque directo acepta cualquier host salvo que se restrinja aquí. |
| `WEB_BIND_ADDRESS` | Dirección de escucha; `0.0.0.0` por defecto y obligatoria en el controlador de Windows. |
| `PORTAL_PORT` | Puerto de Waitress/Gunicorn; 8000 por defecto. `-Port` tiene prioridad en el controlador. |
| `STATIC_ROOT` | Carpeta exclusiva generada por `collectstatic`; `staticfiles` por defecto. |
| `PORTAL_RUNTIME_DIR` | Carpeta exclusiva del PID, metadata y logs en Windows. |
| `DB_ENGINE` | `oracle` en producción. |
| `ORACLE_HOST`, `ORACLE_PORT` | Host SCAN y puerto; preparados como `scan-odscbio:1521`. |
| `ORACLE_SERVICE_NAME` | Servicio Oracle; preparado como `ODSCBIO`. |
| `ORACLE_USER` | Usuario proxy y sesión; `USRFACDOC[USRVALCBIO]` por defecto. |
| `ORACLE_PASSWORD_FILE` | Archivo privado; por defecto `secrets/oracle_password.txt`. |
| `ORACLE_PASSWORD` | Alternativa avanzada para inyectar el secreto desde el entorno. |
| `ORACLE_PASSWORD_B64` | Alternativa Base64 para preservar caracteres especiales; completar solo esta o `ORACLE_PASSWORD`. |
| `ORACLE_DSN` | Descriptor completo opcional; reemplaza host/puerto/servicio cuando tiene valor. |
| `ORACLE_POOL` | `true` activa el pool nativo de Django 5.2/python-oracledb. |
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

La tarjeta principal y los gráficos por responsable, proyecto y mes promedian este puntaje sobre los registros con fecha real, excluyendo suspendidos. Excel y Word incluyen el mismo puntaje. El indicador separado **cumplimiento de meta** conserva la fórmula puntaje/meta; no debe confundirse con el cumplimiento por fechas 100/80/60.

La migración `0002_cumplimiento_fechas` recalcula los datos existentes y deja auditoría de los puntajes que cambian. No se reemplazan las fechas existentes.

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
- Reprogramar bloquea la fila dentro de una transacción y mantiene un número único por compromiso. El historial y la actualización de fechas se confirman juntos o se revierten juntos. La concurrencia real debe probarse sobre Oracle; SQLite no reproduce su bloqueo de filas.
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

`/reportes/` produce DOCX agrupado por proyecto, con vencimiento original, fecha vigente, cierre, reprogramaciones, motivos y notas. La fecha de corte **evalúa la situación de los datos actuales**; no reconstruye estados pasados. La auditoría textual por sí sola no constituye un sistema completo de snapshots históricos.

Excel conserva las 15 columnas operativas y las fechas como fechas nativas. Los textos se guardan como cadenas, evitando la ejecución de fórmulas introducidas en tareas o notas. Ambos formatos excluyen eliminados y respetan filtros. Los archivos se generan en memoria con nombres controlados.

## Importar compromisos desde la matriz 4DX

El comando `importar_compromisos_excel` lee la hoja `Hoja1` del formato oficial. La simulación es el comportamiento predeterminado y no escribe nada:

```powershell
.\.venv\Scripts\python.exe manage.py importar_compromisos_excel ".\importaciones\20260928_4DX_GERENCIA_FACTURACION.xlsx"
```

Después de revisar el resumen, la carga se aplica explícitamente:

```powershell
.\.venv\Scripts\python.exe manage.py importar_compromisos_excel ".\importaciones\20260928_4DX_GERENCIA_FACTURACION.xlsx" --aplicar
```

Cada registro usa como clave `Nro Proy. + ID Actividad`; volver a ejecutar el comando omite lo ya importado. Para refrescar esos registros con una versión posterior de la matriz, agrega `--actualizar-existentes`. La operación completa es transaccional: ante un error no guarda filas parciales. No crea tablas adicionales; la migración `0014` agrega a `compromisos` un código de origen único.

Para sustituir todos los compromisos por una matriz nueva, primero ejecute una simulación. Esta valida el archivo y muestra cuántos registros actuales se eliminarían, sin modificar la base de datos:

```powershell
.\.venv\Scripts\python.exe manage.py importar_compromisos_excel ".\importaciones\NUEVA_MATRIZ_4DX.xlsx" --reemplazar-todo
```

Después de revisar el resultado, aplique el reemplazo con confirmación explícita:

```powershell
.\.venv\Scripts\python.exe manage.py importar_compromisos_excel ".\importaciones\NUEVA_MATRIZ_4DX.xlsx" --reemplazar-todo --aplicar --confirmar REEMPLAZAR
```

El archivo completo se valida antes de eliminar y el borrado más la nueva carga se ejecutan en una única transacción. Si una fila falla, la base conserva todos los compromisos anteriores. El reemplazo elimina también el historial y las reprogramaciones vinculadas a los compromisos sustituidos, pero mantiene usuarios, roles, estados y configuración del portal.

La importación mapea la columna Proyecto del Excel directamente a Proyecto en el portal, Actividad a Tarea y las tres fechas del Excel a primera/segunda/tercera fecha. Para una actividad cerrada, el archivo no ofrece una fecha real separada; se usa la última fecha comprometida como fecha real y se deja constancia en Notas. Los responsables vacíos quedan como `Por asignar` y las jefaturas vacías permanecen sin asignar.

Los Excel operativos no se versionan. Copia el archivo a `importaciones` directamente en el servidor (carpeta compartida, RDP o SCP) y conserva en Git solamente el importador.

## Importar cuentas desde el padrón de Operaciones Comerciales

El comando `importar_usuarios_excel` procesa la hoja `OPERACIONES` y exige las columnas `Cod. Comunicación`, `Correo electrónico`, `Jefe`, `Nombre completo`, `Área`, `Gerencia` y `Dirección`. Antes de escribir en Oracle, valida el archivo en el servidor:

```powershell
.\.venv\Scripts\python.exe manage.py importar_usuarios_excel ".\importaciones\Operaciones Comerciales.xlsx" --solo-validar
```

Si la validación termina correctamente, crea las cuentas y sus perfiles organizacionales:

```powershell
.\.venv\Scripts\python.exe manage.py importar_usuarios_excel ".\importaciones\Operaciones Comerciales.xlsx"
```

El usuario de acceso se forma con el primer nombre y el primer apellido, en minúsculas y separados por punto, por ejemplo `ana.torres`. Cuando dos personas producen el mismo usuario, el comando agrega un número de forma determinista (`carlos.farfan2`). La contraseña inicial es `Cod. Comunicación` y se guarda exclusivamente mediante el hash seguro de Django; el código original no se almacena en el perfil ni aparece en la salida del comando.

Las cuentas nuevas reciben el rol **Consulta**. Área, gerencia, dirección y jefe se guardan como perfiles dentro de la tabla consolidada `registros_portal4dx`, por lo que la importación no crea una tabla física adicional. El Excel contiene datos personales y contraseñas iniciales: cópialo directamente a `importaciones` en el servidor y no lo agregues a Git.

Volver a ejecutar el comando actualiza nombres y datos organizacionales, pero conserva la contraseña y el rol de las cuentas existentes. Usa `--restablecer-contrasenas` solo si deseas volver a asignar los códigos del archivo como contraseñas, y `--actualizar-rol --rol Editor` o `--actualizar-rol --rol Admin` únicamente cuando se haya autorizado ese cambio de permisos.

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

Para ejecutar las pruebas contra Oracle se necesita un esquema de pruebas separado y los privilegios adicionales documentados por Django; nunca apuntarlas al esquema productivo:

```bash
python -m pytest --ds=config.settings -q
# O con Compose levantado:
docker compose exec web python -m pytest --ds=config.settings -q
```

Antes de aceptar el despliegue, verificar en Oracle un esquema vacío, dos arranques consecutivos, login, operaciones, exportaciones y conteos trasladados. Consulta `SERVIDOR.md` para el procedimiento exacto.

## Arquitectura y archivos

```text
4DX/
├── manage.py, run.py
├── requirements.txt, requirements.lock.txt, requirements-postgresql-transfer.txt, pytest.ini
├── .env.example, .gitignore, .dockerignore
├── Dockerfile, docker-compose.yml
├── README.md
├── scripts/
│   ├── portal.cmd, portal.ps1
│   └── publicar_portal_windows.ps1
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

La configuración de producción usa el backend Oracle incluido en Django y `python-oracledb`. No basta con copiar archivos físicos de PostgreSQL: el traslado se hace mediante `exportar_portal` y `loaddata`, con validación de conteos y funciones en el destino.

El dominio no contiene campos exclusivos de PostgreSQL, arrays ni enums de ese motor. La consulta de reprogramados evita `DISTINCT` sobre `NCLOB`, y el único DDL manual usa el cotizador del backend. Esta preparación no sustituye una prueba de aceptación contra ODSCBIO.

## Operación y evolución

Configura HTTPS, `DEBUG=False`, hosts y cookies seguras en producción. Mantén `.env` fuera del control de versiones. En Windows el controlador guarda salida y errores en `.runtime/windows-portal/logs`; en otros despliegues los logs van a salida estándar. Incluyen arranque, conexión, migraciones, identificadores de acciones, exportaciones y errores, sin registrar contraseñas ni contenidos de notas. Configura rotación de logs y backups del motor según la política del servidor.

SSO/Active Directory puede integrarse mediante un backend de autenticación Django que sincronice usuarios y grupos; los servicios siguen recibiendo el usuario autenticado. Quedan para fases posteriores los snapshots históricos reproducibles, la evaluación con cargas reales y la decisión de usar la última reprogramación sin límite como objetivo vigente.

## Paleta visual corporativa

Se conservan la distribución, los controles y los flujos del portal. La paleta se define en `static/css/portal.css`: rojo `#DA291C`, rosa `#FF67B9`, cyan `#009FDF`, amarillo `#FFCB00`, naranja `#FF7500`, negro `#000000` y blanco `#FFFFFF`. Fondos suaves y separadores son mezclas de estos colores con blanco; los gráficos utilizan las mismas variables. Los botones principales son rojos con texto blanco; las superficies cyan, rosa, amarilla y naranja usan texto negro.

Después de actualizar estáticos, ejecuta `python manage.py collectstatic --noinput`, reinicia el servicio del portal y recarga el navegador. Consulta SERVIDOR.md para la configuración de despliegue.


### Vista HTML del correo de seguimiento
En Reportes, el apartado Correo de seguimiento permite elegir el corte, ver el correo, abrirlo en otra pestaña y descargar HTML con estilos incluidos. Respeta los filtros del reporte. Incluye compromisos actualmente abiertos (sin fecha real ni estado cerrado), no suspendidos ni eliminados, cuya fecha de compromiso sea anterior o igual al corte, o esté sin definir. No limita los objetivos futuros: muestra todo el trabajo pendiente iniciado hasta el corte. Evalúa los plazos con las fechas vigentes; no reconstruye estados históricos. Agrupa por proyecto y resume vencidos, próximos a vencer, en plazo y sin fecha objetivo. No envía correos.


### Estatus y vencimiento automático
Los estatus son EC (En curso, amarillo), S (Stand By, gris), T (Terminado, verde) y D (Demorado, rojo). La celda completa muestra el color y conserva el código textual. La columna Stand By y las acciones de pausa/reactivación controlan S. Estatus no admite edición manual. El estatus es automático: S si está en Stand By, T si tiene fecha real, D si el objetivo vigente es anterior a hoy, EC en los demás casos. Se recalcula al consultar, por lo que el paso de los días no exige editar una fila. El código almacenado se actualiza al guardar; la tabla, filtros, indicadores y exportaciones usan el cálculo vigente.
El vencimiento no se edita: toma tercera_fecha, segunda_fecha o primera_fecha, en ese orden; sin fechas queda vacío. La migración 0003 conserva la fecha inicial anterior en primera_fecha si estaba vacía y registra los cambios de datos en el historial. Los códigos anteriores se normalizan al catálogo actual. El puntaje compara la fecha real con primera_fecha (100%), luego segunda_fecha (80%) y el resto (60%). Reiniciar el portal después de actualizar y recargar el navegador para cargar el CSS y JS nuevos.

Colores de referencia actualizados: EC fondo #CEEED0; S #FCECA6; D #F6C9CE; T negro con texto blanco. Cumplimiento 100% usa #BBAAB6. Estatus y cumplimiento están centrados.
