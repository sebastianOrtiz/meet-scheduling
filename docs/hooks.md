# hooks.py de meet_scheduling

Archivo: `meet_scheduling/hooks.py`. 288 líneas.

Documenta todos los hooks declarados, agrupados por sección.

---

## Metadata de la app

```python
app_name = "meet_scheduling"
app_title = "Meet Scheduling"
app_publisher = "Sebastian Ortiz Valencia"
app_description = "Aplicacion para configurar disopniblidad y agendamiento de citas"
app_email = "sebastianortiz989@gmail.com"
app_license = "mit"
```

> Typo en `app_description`: "disopniblidad" → "disponibilidad".

---

## `required_apps`

```python
required_apps = ["common_configurations"]
```

Frappe valida esto al instalar: no se puede instalar `meet_scheduling` sin `common_configurations`. Ver [COMMON_CONFIGURATIONS.md](integration/COMMON_CONFIGURATIONS.md).

---

## `fixtures`

`hooks.py:13-26`:

```python
fixtures = [
    {
        "doctype": "Role",
        "filters": [["name", "in", ["Meet Scheduling Manager", "Appointment User"]]]
    },
    {
        "doctype": "Tool Type",
        "filters": [["app_name", "=", "meet_scheduling"]]
    },
    {
        "doctype": "Custom Field",
        "filters": [["dt", "=", "Service Portal Tool"], ["fieldname", "=", "calendar_resource"]]
    }
]
```

Tres fixtures:

| DocType | Filtro | Qué exporta/importa |
|---|---|---|
| `Role` | `name in ("Meet Scheduling Manager", "Appointment User")` | Los dos roles que la app necesita. Archivo: `fixtures/role.json`. |
| `Tool Type` | `app_name = "meet_scheduling"` | Los dos tool types: `meet_scheduling` y `my_appointments`. Archivo: `fixtures/tool_type.json`. |
| `Custom Field` | `dt = "Service Portal Tool" AND fieldname = "calendar_resource"` | El campo Link agregado al child DocType `Service Portal Tool`. Archivo: `fixtures/custom_field.json`. |

Las fixtures se sincronizan automáticamente con `bench migrate` o `bench export-fixtures`.

---

## Hooks extensibles que la app DEFINE

`hooks.py:33-45`:

```python
# Appointment Notification Hooks
appointment_email_context = []
appointment_email_recipients = []
```

`meet_scheduling` declara estos dos hooks **vacíos** para que otras apps los extiendan. El comentario en el archivo (`hooks.py:34-45`) lo explica:

> Other apps can extend appointment email notifications by registering functions that return additional context (dict) or recipients (list of emails).

Quién los implementa actualmente:

| Hook | App | Función |
|---|---|---|
| `appointment_email_context` | `lex_app` | `lex_app.lex_app.events.appointment.get_appointment_email_context` (devuelve `case_log_*`) |
| `appointment_email_context` | `logbook` | `logbook.logbook.events.appointment.get_appointment_email_context` (devuelve `logbook_entry_*`) |
| `appointment_email_recipients` | `lex_app` | `lex_app.lex_app.events.appointment.get_appointment_email_recipients` (agrega lawyer + supervisor) |
| `appointment_email_recipients` | `logbook` | `logbook.logbook.events.appointment.get_appointment_email_recipients` (agrega assigned_to) |

Ver [features/EMAIL_NOTIFICATIONS.md](features/EMAIL_NOTIFICATIONS.md) para el detalle.

---

## `scheduler_events`

`hooks.py:185-191`:

```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": [
            "meet_scheduling.meet_scheduling.scheduling.tasks.cleanup_expired_drafts"
        ]
    }
}
```

Cada 15 minutos, ejecuta `cleanup_expired_drafts` (ver [services/TASKS.md](services/TASKS.md)) que cancela Drafts con `draft_expires_at < now()`.

> Requiere `bench enable-scheduler` y un worker corriendo.

---

## `doc_events`

**No declarados** por `meet_scheduling`. Los `doc_events` sobre Appointment son declarados por:

- `lex_app/hooks.py` — `Appointment.on_submit` → crear Case Log.
- `logbook/hooks.py` — `Appointment.on_submit` → crear Logbook Entry.

`meet_scheduling` orquesta la lógica directamente en el `Appointment.on_submit` del controller (`appointment.py:54-71`), sin pasar por `doc_events`. Los `doc_events` de otras apps se disparan tras esto.

---

## Hooks COMENTADOS (no usados, pero presentes en el archivo)

El resto del archivo contiene plantillas comentadas para hooks que podrían ser útiles a futuro:

| Hook (comentado) | Línea | Para qué serviría |
|---|---|---|
| `add_to_apps_screen` | 48-56 | Mostrar la app en la apps page de Frappe. |
| `app_include_css`, `app_include_js` | 62-63 | CSS/JS globales del desk. |
| `home_page` | 94 | Override del home page. |
| `role_home_page` | 97-99 | Home page por rol. |
| `jinja` (methods, filters) | 110-113 | Agregar funciones a Jinja. |
| `before_install`, `after_install` | 119-120 | Lifecycle install. |
| `before_app_install`, `after_app_install` | 133-134 | Lifecycle cuando otras apps se instalan. |
| `notification_config` | 148 | Notificaciones de desk. |
| `permission_query_conditions`, `has_permission` | 154-160 | Permisos scripted. |
| `override_doctype_class` | 166-168 | Override controllers de otros DocTypes. |
| `auto_cancel_exempted_doctypes` | 233 | Excluir DocTypes del auto-cancel. |
| `ignore_links_on_delete` | 238 | Ignorar Links al borrar. |
| `before_request`, `after_request` | 242-243 | Hooks de request. |
| `before_job`, `after_job` | 247-248 | Hooks de job. |
| `user_data_fields` | 253-272 | GDPR data fields. |
| `auth_hooks` | 277-279 | Hooks de autenticación. |

Todos están **comentados**. Si se necesita activarlos en el futuro, descomentar y poblar la ruta.

---

## Hook NO declarado pero relacionado: `permission_query_conditions`

Para que un `Appointment User` solo vea sus propias citas en queries, sería razonable agregar:

```python
permission_query_conditions = {
    "Appointment": "meet_scheduling.permissions.get_appointment_query_conditions"
}
```

Actualmente esto **NO está implementado**. La protección viene de:
- Permisos `if_owner: 1` en el JSON del DocType.
- Validación de ownership en los endpoints API (`validate_user_contact_ownership`).

Sin `permission_query_conditions`, un `Appointment User` con desk access podría ver todos los appointments en list views (en teoría — en la práctica no tiene `desk_access` según el fixture `role.json`).

---

## Resumen visual

```
hooks.py
├─ metadata (app_name, version, etc.)
├─ fixtures: Role, Tool Type, Custom Field
├─ required_apps: common_configurations
├─ appointment_email_context = []     ← extensible para terceros
├─ appointment_email_recipients = []  ← extensible para terceros
├─ scheduler_events.cron[*/15 * * * *] → cleanup_expired_drafts
└─ (el resto comentado / placeholders)
```

---

## Deuda técnica

1. **Typo en `app_description`**.
2. **Sin `permission_query_conditions`**: si en el futuro `Appointment User` necesita desk access para reportes, no estará protegido a nivel query.
3. **Sin `before_install` / `after_install`**: los custom fields agregados por `meet_scheduling` (solo el `calendar_resource` en `Service Portal Tool`) se crean vía fixture, no vía install.py. Si el fixture no se sincroniza, no hay fallback.
4. **`auth_hooks` no usado**: la autenticación por token vive en `common_configurations`. `meet_scheduling` solo consume `get_current_user_contact` desde su API. Si quisiera interceptar requests para algún flow específico, podría declararse aquí.
