# Integración: common_configurations

`common_configurations` es la app base sobre la que se construye `meet_scheduling`. Provee:

1. El sistema de **Service Portal Tools** (catálogo + child table en `Service Portal`).
2. El DocType **`User contact`** (usuario público con token).
3. Las utilidades compartidas de **API** (rate limit, honeypot, sanitización, autenticación por token).

`meet_scheduling` declara `required_apps = ["common_configurations"]` en `hooks.py:31`.

---

## 1. Tool Types registrados por meet_scheduling

`meet_scheduling/fixtures/tool_type.json` declara dos `Tool Type` (DocType de `common_configurations`):

| `name` | `tool_label` | `icon` | Descripción |
|---|---|---|---|
| `meet_scheduling` | Agendamiento de Citas | `Calendar` | Permite agendar citas según disponibilidad de Calendar Resources. |
| `my_appointments` | Mis Citas | `ClipboardList` | Visualiza y gestiona tus citas agendadas. |

Estos se sincronizan vía fixtures cuando se hace `bench migrate` (declarado en `meet_scheduling/hooks.py:19-21`):

```python
fixtures = [
    ...
    {
        "doctype": "Tool Type",
        "filters": [["app_name", "=", "meet_scheduling"]]
    },
    ...
]
```

Una vez sincronizado, los `Tool Type` aparecen como opciones cuando el admin agrega una fila a `Service Portal.tools`.

---

## 2. Custom field `calendar_resource` en Service Portal Tool

`meet_scheduling/fixtures/custom_field.json` agrega un campo `calendar_resource` al child DocType `Service Portal Tool` (de `common_configurations`):

```json
{
  "doctype": "Custom Field",
  "name": "Service Portal Tool-calendar_resource",
  "dt": "Service Portal Tool",
  "fieldname": "calendar_resource",
  "fieldtype": "Link",
  "options": "Calendar Resource",
  "label": "Calendar Resource",
  "insert_after": "tool_type",
  "depends_on": "eval:doc.tool_type=='meet_scheduling'",
  "mandatory_depends_on": "eval:doc.tool_type=='meet_scheduling'"
}
```

- **Visible solo** si `tool_type == 'meet_scheduling'`.
- **Obligatorio** si `tool_type == 'meet_scheduling'`.

Esto permite a un admin configurar QUÉ recurso de calendario expone una tool `meet_scheduling` específica del portal.

> Notar que la tool `my_appointments` **no** requiere este campo: muestra todas las citas del `User contact` autenticado, sin filtrar por recurso.

---

## 3. `User contact` y autenticación por token

### El DocType

`User contact` está definido en `common_configurations`. Es un "guest user" con:

- `full_name` (Data)
- `document_type` (Select: Cedula, NIT, ...)
- `document` (Data)
- `phone_number` (Data)
- `email` (Data)
- `auth_token_hash` (Password, `permlevel: 1` — solo System Manager)
- `token_created_at` (Datetime)

### El token

- Se genera con `common_configurations.api.shared.create_user_contact_token(user_contact_name)`.
- Se hashea con SHA-256 y se guarda en `auth_token_hash`.
- El token plano solo se devuelve UNA VEZ al registrar (luego no se puede recuperar).
- Expiración: 30 días (`TOKEN_EXPIRY_DAYS`).
- El frontend lo envía en el header `X-User-Contact-Token` (constante `AUTH_HEADER`).

### Validación del token en meet_scheduling

`meet_scheduling/api/shared/__init__.py` re-exporta utilidades:

```python
from common_configurations.api.shared import (
    check_rate_limit,
    get_client_ip,
    check_honeypot,
    create_user_contact_token,
    get_current_user_contact,
    require_user_contact,
    validate_user_contact_ownership,
    AUTH_HEADER,
    TOKEN_EXPIRY_DAYS,
    sanitize_string,
    validate_document_number,
    validate_email,
    validate_phone,
    validate_name,
)
```

Y los endpoints de `meet_scheduling/api/appointments/endpoints.py` usan:

```python
authenticated_user_contact = get_current_user_contact()
if not authenticated_user_contact:
    frappe.throw(_("Authentication required..."), frappe.AuthenticationError)
```

`get_current_user_contact()` lee el header `X-User-Contact-Token` de `frappe.local.request`, lo hashea con SHA-256 y busca un `User contact` con ese `auth_token_hash` y `token_created_at` dentro de los últimos 30 días.

### Validación de ownership

Para endpoints como `get_appointment_detail` y `cancel_my_appointment`, se usa:

```python
validate_user_contact_ownership(user_contact, "Appointment", appointment_name)
```

Que internamente hace `frappe.db.get_value("Appointment", appointment_name, "user_contact")` y compara con el `user_contact` autenticado. Lanza `PermissionError` si no coincide.

---

## 4. Utilidades compartidas usadas

| Utilidad | Origen | Uso en meet_scheduling |
|---|---|---|
| `check_rate_limit(name, limit, seconds)` | `common_configurations.api.shared.rate_limit` | Todos los endpoints (5-30/min). |
| `get_client_ip()` | `common_configurations.api.shared.rate_limit` | Indirectamente vía `check_rate_limit`. |
| `check_honeypot(value)` | `common_configurations.api.shared.security` | En `create_and_confirm_appointment` y `cancel_my_appointment`. |
| `get_current_user_contact()` | `common_configurations.api.shared.security` | En todos los endpoints autenticados. |
| `validate_user_contact_ownership(...)` | `common_configurations.api.shared.security` | En `get_appointment_detail` y `cancel_my_appointment`. |
| `sanitize_string(s, max_len)` | `common_configurations.api.shared.validators` | Sanitiza `appointment_context` (2000 chars) y `status` (50 chars). |
| `has_outgoing_email()` | `common_configurations.api.shared` | En `Appointment._enqueue_email_notification` y `notifications/appointment.py:31`. |
| `send_email(...)` | `common_configurations.api.shared` | En `notifications/appointment.py:118`. Wrapper sobre `frappe.sendmail` con búsqueda de template en `templates/emails/`. |

---

## 5. SPA Angular (Service Portal)

El frontend de `meet_scheduling` no vive en `meet_scheduling/`. Vive en `common_configurations/front_apps/service-portal/`:

| Componente | Ubicación |
|---|---|
| `meet-scheduling-tool` | `front_apps/service-portal/src/app/features/tools/meet-scheduling/` |
| `my-appointments-tool` | `front_apps/service-portal/src/app/features/tools/my-appointments/` |
| `MeetSchedulingService` | `front_apps/service-portal/src/app/core/services/meet-scheduling.service.ts` |
| Modelo `Appointment` / `AvailableSlot` | `front_apps/service-portal/src/app/core/models/appointment.model.ts` |

El router de tools (`tool-router/tool-router.component.ts`) carga lazy estos componentes según el `tool_type`. Para registrar uno nuevo, ver `common_configurations/CLAUDE.md` (sección "Guía: Cómo Crear una Tool del Service Portal desde otra App").

---

## 6. Diagrama de dependencias

```
meet_scheduling
  ├─ required_apps = ["common_configurations"]
  ├─ usa: DocType "User contact" (de common_configurations)
  ├─ usa: DocType "Service Portal Tool" (de common_configurations)
  ├─ usa: DocType "Tool Type" (de common_configurations)
  ├─ usa: API shared (rate limit, security, validators)
  ├─ exporta DocTypes: Appointment, Calendar Resource, Availability Plan, etc.
  └─ es consumida por:
       ├─ lex_app (crea Case Log)
       └─ logbook (crea Logbook Entry)
```

---

## 7. Versionado y compatibilidad

- `meet_scheduling/pyproject.toml` declara la versión del paquete y dependencias mínimas.
- No hay declaración explícita de versión mínima de `common_configurations`. Si la API de `common_configurations.api.shared` cambia (renombrar funciones, etc.), `meet_scheduling` puede romper.
- Recomendado: pinar la versión de `common_configurations` en `pyproject.toml` cuando se publique a un repo Git.

---

## Deuda técnica

1. **Sin lock de versión de `common_configurations`**: dependencia frágil.
2. **El custom field `calendar_resource` está pegado al `tool_type=='meet_scheduling'`**: si en el futuro hay otra tool que también necesite Calendar Resource, habría que renombrar o crear otro field.
3. **`User contact` no tiene relación reverse documentada con `Appointment`**: hay que consultar `frappe.get_all("Appointment", filters={"user_contact": uc})` cada vez.
