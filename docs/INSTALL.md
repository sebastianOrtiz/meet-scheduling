# Instalación de meet_scheduling

Esta app NO tiene un archivo `install.py` ni hooks `before_install`/`after_install`. Toda la configuración se hace vía fixtures durante `bench migrate`.

---

## Pre-requisitos

1. **bench** funcional (Frappe Framework >= v15).
2. **`common_configurations` instalado primero** (declarado en `required_apps`).
3. Python >= 3.10.

---

## Instalación

```bash
cd $PATH_TO_YOUR_BENCH

# 1. Obtener la app
bench get-app meet_scheduling https://github.com/<org>/meet_scheduling --branch main

# 2. Instalar en el site
bench --site <site-name> install-app meet_scheduling

# 3. Migrar (sincroniza fixtures)
bench --site <site-name> migrate

# 4. (Opcional) Reiniciar el scheduler
bench restart
```

---

## Qué se instala automáticamente

### Roles (fixture `Role`)

Definidos en `meet_scheduling/fixtures/role.json`:

| Name | role_name | desk_access | is_custom | disabled |
|---|---|---|---|---|
| `Meet Scheduling Manager` | Meet Scheduling Manager | 1 | 0 | 0 |
| `Appointment User` | Appointment User | 0 | 0 | 0 |

> `Meet Scheduling Manager` tiene acceso al desk (`desk_access=1`). `Appointment User` no — está pensado para `User contact` autenticados vía token desde el Service Portal.

### Tool Types (fixture `Tool Type`)

Definidos en `meet_scheduling/fixtures/tool_type.json`:

| name | tool_label | app_name | icon | is_active |
|---|---|---|---|---|
| `meet_scheduling` | Agendamiento de Citas | meet_scheduling | Calendar | 1 |
| `my_appointments` | Mis Citas | meet_scheduling | ClipboardList | 1 |

### Custom Fields (fixture `Custom Field`)

Definidos en `meet_scheduling/fixtures/custom_field.json`:

| Name | dt | fieldname | fieldtype | options | depends_on |
|---|---|---|---|---|---|
| `Service Portal Tool-calendar_resource` | Service Portal Tool | calendar_resource | Link | Calendar Resource | `eval:doc.tool_type=='meet_scheduling'` |

### DocTypes

Frappe automáticamente registra todos los DocTypes en `meet_scheduling/meet_scheduling/doctype/`:

- `Appointment`
- `Calendar Resource`
- `Calendar Resource Notification User` (child)
- `Availability Plan`
- `Availability Slot` (child)
- `Calendar Exception`
- `Video Call Profile`
- `Provider Account`

### Scheduler events

Registrado en `hooks.py:185-191`:

- `cron */15 * * * *` → `meet_scheduling.meet_scheduling.scheduling.tasks.cleanup_expired_drafts`

Para que se ejecute, el scheduler debe estar habilitado:

```bash
bench --site <site-name> enable-scheduler
```

---

## Configuración post-instalación (manual)

1. **Configurar Email Account** (`/app/email-account`):
   - Crear o activar una cuenta con `Enable Outgoing = 1` para que se envíen las notificaciones.

2. **Crear Availability Plan** (`/app/availability-plan/new`):
   - `plan_name`: ej. "Horario Consultorio 2026".
   - `availability_slots`: agregar filas por día de la semana.

3. **Crear Calendar Resource** (`/app/calendar-resource/new`):
   - `resource_name`: ej. "Dr. Juan Pérez".
   - `timezone`: ej. `America/Bogota`.
   - `slot_duration_minutes`, `capacity`, `draft_expiration_minutes`.
   - `availability_plan`: link al plan creado.
   - `send_email_notification` y `notification_users` si se quiere email.

4. **(Opcional) Crear Video Call Profile** (`/app/video-call-profile/new`):
   - Si `link_mode = manual_only`: setear `default_meeting_url` con un enlace fijo.
   - Si `link_mode = auto_generate`: requiere `Provider Account` conectada (OAuth).

5. **(Opcional) Crear Provider Account**:
   - Solo necesario para `link_mode != manual_only`.
   - **NOTA**: el flujo OAuth real no está implementado. El status quedará en `Pending`.

6. **Configurar Service Portal** (de `common_configurations`):
   - Crear un `Service Portal`.
   - En `tools`, agregar fila con `tool_type = meet_scheduling` y seleccionar el `calendar_resource`.
   - (Opcional) Agregar fila con `tool_type = my_appointments`.

---

## Instalación de apps complementarias (lex_app / logbook)

Si se quiere la integración:

### lex_app

```bash
bench get-app lex_app https://github.com/<org>/lex_app
bench --site <site-name> install-app lex_app
bench --site <site-name> migrate
```

`lex_app/install.py` crea los custom fields:
- `Calendar Resource.create_case_log` (Check)
- Otros custom fields en `API Service` (de common_configurations).

Después: en cada `Calendar Resource` marcar `create_case_log = 1` para activar la creación de Case Log automática.

### logbook

```bash
bench get-app logbook https://github.com/<org>/logbook
bench --site <site-name> install-app logbook
bench --site <site-name> migrate
```

`logbook/install.py` crea los custom fields:
- `Calendar Resource.create_logbook_entry` (Check)
- `Calendar Resource.logbook_availability` (Link, depends_on)
- `Service Portal Tool.logbook_availability` (Link, depends_on)

Después: en cada `Calendar Resource` marcar `create_logbook_entry = 1` y seleccionar `logbook_availability` para activar la creación automática de Logbook Entry.

---

## Verificación de la instalación

Después de instalar, verificar:

```bash
# Listar apps instaladas en el site
bench --site <site-name> list-apps

# Sincronizar DocTypes
bench --site <site-name> migrate

# Verificar fixtures importadas
bench --site <site-name> console
>>> import frappe
>>> frappe.db.get_all("Role", filters={"name": ["like", "%Meet%"]})
>>> frappe.db.get_all("Tool Type", filters={"app_name": "meet_scheduling"})
>>> frappe.db.get_value("Custom Field", "Service Portal Tool-calendar_resource", "fieldname")
```

---

## Desinstalación

```bash
bench --site <site-name> uninstall-app meet_scheduling
```

> **Cuidado**: esto elimina los DocTypes definidos por la app (`Appointment`, `Calendar Resource`, etc.). Si hay datos importantes, hacer backup primero.

---

## Migración entre sitios

Para mover los datos (Appointments, Calendar Resources, etc.) de un site a otro:

```bash
# Origen
bench --site src export-fixtures
# Copia los JSONs generados al destino, luego:
bench --site dst migrate
```

Las fixtures de roles, tool types y custom fields se sincronizan automáticamente. Los datos transaccionales (Appointment, Calendar Resource, etc.) NO se exportan por fixture; usar `frappe.db.dump` o el export del desk.

---

## Deuda técnica

1. **Sin `install.py`**: la creación de roles, tool types y custom fields depende 100% de fixtures. Si las fixtures fallan al sincronizarse, no hay fallback.
2. **Sin `after_install` que valide el setup**: no hay nada que verifique post-install que el `Email Account` esté configurado, por ejemplo.
3. **El custom field `Service Portal Tool-calendar_resource` solo se crea vía fixture**: si alguien instala primero `meet_scheduling` sin haber sincronizado fixtures, el formulario `Service Portal Tool` no mostrará el campo y la tool no funcionará correctamente. Idealmente, un `install.py` que cree el campo si no existe (como hace `lex_app/install.py` con sus propios fields).
4. **No hay migration scripts en `patches.txt`** específicos (el archivo existe pero está casi vacío). Si en el futuro hay cambios de schema, faltarán patches.
