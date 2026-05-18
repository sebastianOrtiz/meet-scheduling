# API: Appointments

Endpoints whitelisted para gestión de citas. Definidos en `meet_scheduling/api/appointments/endpoints.py` y re-exportados en `meet_scheduling/api/appointments/__init__.py`. La ruta pública sigue el patrón:

```
meet_scheduling.api.appointments.<funcion>
```

Las utilidades de seguridad (rate limit, honeypot, autenticación por token, sanitización) se importan de `common_configurations.api.shared` a través de `meet_scheduling.api.shared` (ver `api/shared/__init__.py`).

---

## Tabla resumen de endpoints

| Endpoint | Método HTTP | Auth | Rate limit | Honeypot |
|---|---|---|---|---|
| `get_active_calendar_resources` | GET | guest | 30/min | no |
| `get_available_slots` | GET | guest | 30/min | no |
| `validate_appointment` | GET/POST | guest | 20/min | no |
| `create_and_confirm_appointment` | POST | **token** (`X-User-Contact-Token`) | 5/min | yes |
| `cancel_or_delete_appointment` | (default whitelist) | Frappe session | — | no |
| `generate_meeting` | (default whitelist) | Frappe session | — | no |
| `get_my_appointments` | GET | **token** | 30/min | no |
| `get_appointment_detail` | GET | **token** | 30/min | no |
| `cancel_my_appointment` | POST | **token** | 5/min | yes |

Notas:
- Los rate limits están implementados por IP en `common_configurations.api.shared.check_rate_limit`.
- Los endpoints con `allow_guest=True` no requieren login de Frappe; los autenticados validan el token enviado en header.

---

## Autenticación con `X-User-Contact-Token`

Los endpoints "my_*" y `create_and_confirm_appointment` exigen que el header HTTP `X-User-Contact-Token` (constante `AUTH_HEADER` en `common_configurations.api.shared`) contenga un token válido emitido a un `User contact`.

Validación interna:

```python
from meet_scheduling.api.shared import get_current_user_contact

user_contact = get_current_user_contact()
if not user_contact:
    frappe.throw(_("Authentication required..."), frappe.AuthenticationError)
```

El token se hashea con SHA-256 y se compara contra `User contact.auth_token_hash`. Expira a 30 días (`TOKEN_EXPIRY_DAYS`).

---

## Endpoint: `get_active_calendar_resources`

**Ubicación**: `endpoints.py:41-90`.

```
GET /api/method/meet_scheduling.api.appointments.get_active_calendar_resources
```

**Auth**: guest. **Rate limit**: 30/min/IP.

**Args**: ninguno.

**Response (200)**:

```json
{
  "message": [
    {
      "name": "Dr. Juan Pérez",
      "resource_name": "Dr. Juan Pérez",
      "timezone": "America/Bogota",
      "slot_duration_minutes": 30,
      "capacity": 1,
      "draft_expiration_minutes": 15,
      "availability_plan": "Horario Consultorio 2026",
      "video_call_profile": "Google Meet - Consultas"
    }
  ]
}
```

Filtra por `is_active = 1`. Ordena por `resource_name asc`.

**Ejemplo curl**:

```bash
curl -sS "https://nexora.com.co/api/method/meet_scheduling.api.appointments.get_active_calendar_resources" \
  -H "Accept: application/json"
```

---

## Endpoint: `get_available_slots`

**Ubicación**: `endpoints.py:93-168`.

```
GET /api/method/meet_scheduling.api.appointments.get_available_slots
```

**Auth**: guest. **Rate limit**: 30/min/IP.

**Args**:
- `calendar_resource` (string, requerido, validado por `validate_docname`).
- `from_date` (string YYYY-MM-DD, validado por `validate_date_string`).
- `to_date` (string YYYY-MM-DD, validado por `validate_date_string`).

Validaciones extra: existencia del Calendar Resource, `from_date <= to_date`.

**Response**: lista de slots:

```json
{
  "message": [
    {
      "start": "2026-01-20 09:00:00",
      "end": "2026-01-20 09:30:00",
      "capacity_remaining": 1,
      "is_available": true
    },
    {
      "start": "2026-01-20 09:30:00",
      "end": "2026-01-20 10:00:00",
      "capacity_remaining": 0,
      "is_available": false
    }
  ]
}
```

Internamente llama a `scheduling.slots.generate_available_slots`. Ver [services/SLOTS.md](../services/SLOTS.md).

**Ejemplo curl**:

```bash
curl -sS "https://nexora.com.co/api/method/meet_scheduling.api.appointments.get_available_slots?calendar_resource=Dr.%20Juan%20P%C3%A9rez&from_date=2026-01-20&to_date=2026-01-27" \
  -H "Accept: application/json"
```

---

## Endpoint: `validate_appointment`

**Ubicación**: `endpoints.py:171-352`.

```
GET|POST /api/method/meet_scheduling.api.appointments.validate_appointment
```

**Auth**: guest. **Rate limit**: 20/min/IP.

**Args**:
- `calendar_resource` (string).
- `start_datetime` (string `YYYY-MM-DD HH:MM:SS`).
- `end_datetime` (string `YYYY-MM-DD HH:MM:SS`).
- `appointment_name` (string opcional, para ediciones; se excluye del check de overlap).

**Response**:

```json
{
  "message": {
    "valid": true,
    "errors": [],
    "warnings": ["La duración (45.0 min) no es múltiplo de slot_duration (30 min)"],
    "availability_ok": true,
    "capacity_ok": true,
    "overlap_info": {
      "has_overlap": false,
      "overlapping_appointments": [],
      "capacity_exceeded": false,
      "capacity_used": 0,
      "capacity_available": 1
    }
  }
}
```

Útil para feedback en tiempo real desde el frontend antes de hacer `create_and_confirm_appointment`. La validación localiza los datetimes a la timezone del recurso si vienen sin tzinfo (`endpoints.py:266-269`).

---

## Endpoint: `create_and_confirm_appointment`

**Ubicación**: `endpoints.py:355-486`.

```
POST /api/method/meet_scheduling.api.appointments.create_and_confirm_appointment
```

**Auth**: token requerido. **Rate limit**: 5/min/IP. **Honeypot**: sí.

**Args**:
- `calendar_resource` (string).
- `user_contact` (string) — debe coincidir con el `User contact` autenticado.
- `start_datetime`, `end_datetime` (strings).
- `appointment_context` (string opcional, max 2000 chars, sanitizado).
- `honeypot` (string opcional; debe estar vacío).

**Flujo interno**:
1. `check_honeypot(honeypot)`.
2. `check_rate_limit("create_appointment", 5, 60)`.
3. `get_current_user_contact()` — debe existir.
4. Verifica que `authenticated_user_contact == user_contact`. Si no, `PermissionError`.
5. Valida existencia de Calendar Resource y User contact.
6. Llama a `validate_appointment(...)` internamente; si no es válido, lanza error con todos los `errors`.
7. Crea el `Appointment` en `Draft`.
8. `appointment.insert(ignore_permissions=True)` y luego `appointment.submit()`.
9. `frappe.db.commit()`.
10. Retorna `appointment.as_dict()`.

**Ejemplo curl**:

```bash
curl -sS -X POST "https://nexora.com.co/api/method/meet_scheduling.api.appointments.create_and_confirm_appointment" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -H "X-User-Contact-Token: 4f7e8c3a9b2d1e8f6a3c0b9d5e7f2a1b8c4d6e9f3a2b5c8d1e4f7a0b3c6d9e2" \
  -d "calendar_resource=Dr.%20Juan%20P%C3%A9rez" \
  -d "user_contact=UC-00001" \
  -d "start_datetime=2026-01-20%2010%3A00%3A00" \
  -d "end_datetime=2026-01-20%2010%3A30%3A00" \
  -d "appointment_context=Consulta%20sobre%20herencia"
```

**Posibles errores**:
- `401 AuthenticationError` — token inválido o ausente.
- `403 PermissionError` — el token autenticado no coincide con el `user_contact` solicitado.
- `400 ValidationError` — slot no disponible / capacidad excedida / formato de fecha incorrecto.

---

## Endpoint: `get_my_appointments`

**Ubicación**: `endpoints.py:677-804`.

```
GET /api/method/meet_scheduling.api.appointments.get_my_appointments
```

**Auth**: token. **Rate limit**: 30/min/IP.

**Args** (opcionales):
- `status` — filtrar por `Confirmed`, `Cancelled`, etc. Sanitizado.
- `from_date` — `YYYY-MM-DD`. Validado.
- `to_date` — `YYYY-MM-DD`. Validado.

**Response**: lista con `name`, `calendar_resource`, `calendar_resource_name`, `start_datetime`, `end_datetime`, `status`, `docstatus`, `appointment_context`, `meeting_url`, `meeting_status`, `creation`, `modified`. Limitada a 100 filas, ordenada por `start_datetime desc`.

**Ejemplo curl**:

```bash
curl -sS "https://nexora.com.co/api/method/meet_scheduling.api.appointments.get_my_appointments?status=Confirmed&from_date=2026-01-01&to_date=2026-12-31" \
  -H "X-User-Contact-Token: <token>"
```

---

## Endpoint: `get_appointment_detail`

**Ubicación**: `endpoints.py:807-888`.

```
GET /api/method/meet_scheduling.api.appointments.get_appointment_detail
```

**Auth**: token. **Rate limit**: 30/min/IP.

**Args**: `appointment_name` (validado por `validate_docname`).

**Validación de ownership**: usa `validate_user_contact_ownership(user_contact, "Appointment", appointment_name)` de `common_configurations`. Lanza `PermissionError` si el `Appointment.user_contact != authenticated_user_contact`.

**Response**: dict con todos los campos relevantes del Appointment (`name`, `calendar_resource`, `calendar_resource_name`, `user_contact`, `start_datetime`, `end_datetime`, `status`, `docstatus`, `appointment_context`, `meeting_url`, `meeting_id`, `meeting_status`, `creation`, `modified`).

---

## Endpoint: `cancel_my_appointment`

**Ubicación**: `endpoints.py:891-987`.

```
POST /api/method/meet_scheduling.api.appointments.cancel_my_appointment
```

**Auth**: token. **Rate limit**: 5/min/IP. **Honeypot**: sí.

**Args**: `appointment_name`, `honeypot` (opcional, debe estar vacío).

**Lógica**:
- Si `docstatus == 0` (Draft) → `frappe.delete_doc(...)` con `ignore_permissions=True`. Retorna `action="deleted"`.
- Si `docstatus == 1` (Submitted) → `appointment.cancel()`. Retorna `action="cancelled"`.
- Si `docstatus == 2` (ya Cancelled) → `success=False`, `action="none"`.

**Ejemplo curl**:

```bash
curl -sS -X POST "https://nexora.com.co/api/method/meet_scheduling.api.appointments.cancel_my_appointment" \
  -H "X-User-Contact-Token: <token>" \
  -d "appointment_name=APT-2026-00001"
```

---

## Endpoint: `cancel_or_delete_appointment`

**Ubicación**: `endpoints.py:489-560`.

```
POST /api/method/meet_scheduling.api.appointments.cancel_or_delete_appointment
```

**Auth**: requiere sesión de Frappe (no usa token). Pensado para uso administrativo o desde el desk. Hace lo mismo que `cancel_my_appointment` pero sin validar ownership por token.

---

## Endpoint: `generate_meeting`

**Ubicación**: `endpoints.py:563-670`.

```
POST /api/method/meet_scheduling.api.appointments.generate_meeting
```

**Auth**: sesión de Frappe. Sin rate limit explícito.

**Args**: `appointment_name`.

**Pre-condiciones**:
- Appointment debe estar `Confirmed`.
- Debe tener `video_call_profile`.
- `Video Call Profile.link_mode != "manual_only"`.

**Flujo**:
1. Obtiene `Appointment` y `Video Call Profile`.
2. Llama `get_adapter(provider).validate_profile(profile)`.
3. Llama `adapter.create_meeting(profile, appointment)`.
4. Actualiza `meeting_url`, `meeting_id`, `meeting_status = "created"`.
5. Guarda con `flags.ignore_validate = True` para no re-ejecutar validaciones.

Útil para re-intentar meetings que fallaron, o forzar generación en `auto_or_manual`.

---

## Errores comunes y códigos

| Excepción | HTTP | Cuándo |
|---|---|---|
| `frappe.AuthenticationError` | 401 | Token faltante o inválido. |
| `frappe.PermissionError` | 403 | Intento de operar sobre otro `User contact`. |
| `frappe.ValidationError` | 417 | Formato inválido, slot no disponible, capacidad excedida. |
| `frappe.DoesNotExistError` | 404 | Appointment o Calendar Resource no existe. |

---

## Validadores específicos

Definidos en `meet_scheduling/api/shared/validators.py`:

- `validate_date_string(date_str)` — regex `^\d{4}-\d{2}-\d{2}$`.
- `validate_datetime_string(datetime_str)` — regex `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$`.
- `validate_docname(name)` — max 140 chars, bloquea patrones de inyección (`<script`, `SELECT`, `UNION`, `--`, `;`, etc.).

---

## Deuda técnica / observaciones

1. **`cancel_or_delete_appointment` y `generate_meeting` no tienen rate limit ni validan ownership**: pensados para admin, pero whitelisted públicamente sin allow_guest, así que requieren sesión de Frappe.
2. **`get_my_appointments` tiene un branch dead-code** en `endpoints.py:737-741` (el `if "start_datetime" in filters: pass`).
3. **No hay endpoint para listar `Calendar Exception`**: el frontend no puede mostrar al usuario los días bloqueados explícitamente; debe inferirlos de `get_available_slots`.
