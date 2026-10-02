# Esquema del portal: 10 tablas físicas

La consolidación mantiene todos los datos del portal en diez tablas físicas. Producción usa Oracle; no utiliza vistas SQL, vistas materializadas, tablas virtuales, modelos proxy, almacenamiento de sesiones en archivos ni cookies como base de datos.

| Tabla | Función |
|---|---|
| compromisos | Datos, fechas, responsables, jefaturas, cumplimiento y papelera |
| registros_portal4dx | Historial, reprogramaciones, estados configurables, envíos, sesiones y auditoría administrativa |
| usuarios_4dx | Usuarios y contraseñas cifradas mediante hash de Django |
| grupos_usuarios_4dx | Roles |
| permisos_4dx | Permisos |
| relacion_grupo_4dx | Permisos por rol |
| grupo_usuarios_4dx | Roles por usuario |
| permisos_usuarios_4dx | Permisos individuales |
| entidades_4dx | Identificadores de entidades usados por los permisos y la auditoría |
| registrodb_4dx | Versiones aplicadas del esquema |

Oracle guarda identificadores no entrecomillados en mayúsculas. En PL/SQL Developer se mostrarán como `COMPROMISOS`, `REGISTROS_PORTAL4DX`, etc.; son las mismas tablas y deben consultarse sin comillas para conservar la compatibilidad con Django.

`registros_portal4dx.tipo` separa `historial`, `reprogramacion`, `estado`, `envio`, `sesion` y `admin`. Los campos de cada tipo tienen restricciones de integridad e índices. Hay columnas que quedan vacías para los otros tipos: es el compromiso de diseño para limitar el esquema a 10 tablas conservando las funciones. El modelo Python mantiene su nombre `EventoCompromiso` para conservar permisos, relaciones e IDs del historial existente.

Los gestores `estados`, `envios`, `sesiones` y `auditoria` son consultas ORM filtradas sobre la misma tabla física. No crean ninguna relación virtual en Oracle.

## Funcionalidades conservadas

- Edición de compromisos, filtros, estatus y cumplimiento automáticos.
- Historial completo, motivos y autores de las reprogramaciones.
- Reportes, vistas HTML y exportaciones Word/Excel.
- Envíos a Teams/correo y protección contra duplicados por `(canal, token)`.
- Inicio y cierre de sesión, expiración, rotación y revocación. Las sesiones anteriores conservan su clave, contenido firmado y vencimiento.
- Usuarios, grupos, permisos y contraseñas mediante Django, sin cambiar su almacenamiento.
- Auditoría de altas/cambios/bajas en el administrador. Los registros de sesión no aparecen en la pantalla de auditoría.
- Edición de estados en el portal y en el administrador, conservando las referencias de sus URLs.

## Migraciones

`0010_registros_portal` prepara las columnas y renombra la tabla de eventos. `0011_consolidar_almacenamiento` copia los datos y retira las tablas de estados/envíos. Las migraciones locales `admin.0004` y `sessions.0002` retiran las tablas anteriores de auditoría y sesiones después de copiarlas. La secuencia está versionada y se aplica con el backend Oracle de Django.

Django usa `config.portal_apps` y las migraciones versionadas de `config/admin_migrations` y `config/sessions_migrations`: la interfaz administrativa y el middleware siguen activos, pero los modelos de almacenamiento antiguos no se registran. No importar `django.contrib.admin.models.LogEntry` ni `django.contrib.sessions.models.Session` en nuevas funciones; utilizar `EventoCompromiso.auditoria` y el backend configurado. Al actualizar Django, revisar estos puntos de integración y ejecutar las pruebas; la versión soportada es 5.2.x.

Los tipos de contenido y permisos históricos se conservan para mantener referencias y accesos. No usar `remove_stale_contenttypes` indiscriminadamente: la administración de estados conserva el espacio de permisos `compromisos.*_estado` aunque ya no tenga una tabla propia.

## Operación y respaldo

Detener el portal antes de migrar y respaldar la base y el código. Aplicar **todas** las migraciones, sin limitar el comando a una app:

```sh
./.venv/bin/python manage.py migrate
./.venv/bin/python manage.py check
```

Limpieza de sesiones vencidas (conserva el resto de registros):

```sh
./.venv/bin/python manage.py clearsessions
```

Para volver al esquema de 14 tablas, con el portal detenido y otro respaldo actualizado:

```sh
./.venv/bin/python manage.py migrate compromisos 0009
```

La reversión reconstruye las tablas retiradas y copia también los registros creados después de consolidar. Restaurar el código de la versión de 14 tablas **antes de iniciar el portal**. Las migraciones nuevas y el backend de 10 tablas no funcionan con el esquema anterior en ejecución.

## Nombres físicos personalizados (octubre de 2026)

Las etiquetas internas de Django siguen siendo `auth`, `contenttypes` y `compromisos`; las URLs, permisos y usuarios no cambian. `config.portal_apps` configura los nombres físicos de los modelos integrados y de sus tres tablas de relación. Las migraciones originales de auth/contenttypes de Django 5.2 están versionadas en `config/auth_migrations` y `config/contenttypes_migrations`, con nuevas migraciones que renombraron las tablas sin copiar ni eliminar sus filas. Al actualizar Django se deben revisar también estas migraciones y configuraciones.

`registrodb_4dx` requiere un tratamiento especial: Django consulta esta tabla antes de ejecutar las migraciones. El comando del proyecto `manage.py migrate` renombra primero el antiguo `django_migrations`, si existe, y conserva todo su historial. En instalaciones nuevas el registro nace directamente con el nombre nuevo. Si existen ambos nombres, el comando se detiene para evitar un historial ambiguo. Ejecutar siempre las migraciones con el código y el comando de este proyecto.

La reversión de las migraciones de renombrado restaura los nombres anteriores de las tablas de aplicación, pero conserva `registrodb_4dx`. Para restaurar además el código anterior, con todos los procesos detenidos, se debe renombrar el registro a `django_migrations` o restaurar el respaldo completo previo. No iniciar el portal con código y esquema de versiones diferentes.
