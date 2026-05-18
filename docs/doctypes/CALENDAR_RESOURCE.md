# DocType: Calendar Resource

Representa el "recurso" que se agenda: una persona (abogado, médico), una sala, un servicio o cualquier entidad con disponibilidad. Es el punto central de la app: cada `Appointment` apunta a un `Calendar Resource`, que a su vez referencia un `Availability Plan`, un `Video Call Profile` y una tabla de usuarios a notificar.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/calendar_resource/calendar_resource.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/calendar_resource/calendar_resource.py` (clase `CalendarResource(Document)` con `pass`, lógica delegada a servicios).
- **Naming rule**: `By fieldname` → autoname desde `resource_name`.
- **Permite rename**: sí.

---

## Propósito y casos de uso

- Identificar la entidad agendable (sala, persona, recurso compartido) con su zona horaria y reglas básicas.
- Vincular un plan semanal de disponibilidad (`Availability Plan`) y opcionalmente un perfil de videollamada (`Video Call Profile`).
- Configurar:
  - `slot_duration_minutes`: granularidad de los slots.
  - `capacity`: cuántas citas simultáneas se permiten.
  - `draft_expiration_minutes`: tiempo que un Draft bloquea el slot.
  - `send_email_notification` + tabla `notification_users`: a quién avisar cuando se confirma una cita.
- Servir como punto de extensión por otras apps mediante custom fields (`create_case_log` de lex_app, `create_logbook_entry` y `logbook_availability` de logbook).

---

## Campos (uno por uno)

Orden según `field_order` (`calendar_resource.json:8-21`).

### Datos generales

| Fieldname | Tipo | Default | Reqd | Unique | Descripción |
|---|---|---|---|---|---|
| `resource_name` | Data | — | yes | yes | Nombre visible del calendario. Sirve como `name` del documento (autoname `By fieldname`). Ej: "Dr. Carlos Gómez", "Sala de Juntas". |
| `timezone` | Data | `America/Bogota` | no | — | Zona horaria del recurso. Se usa al convertir tiempos para calcular disponibilidad (ver `availability.py:103-115`). Soporta el valor especial `system timezone` que se traduce a la zona del sitio. |
| `is_active` | Check | `1` | — | — | Si está desmarcado, `get_availability_slots_for_day` retorna lista vacía (`availability.py:78-79`). |

### Sección "Scheduling Configuration" (`scheduling_section`)

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `slot_duration_minutes` | Int | `60` | Duración de cada bloque de cita en minutos. Usado por `slots.py:52` y por `_validate_slot_granularity` en Appointment. |
| `capacity` | Int | `1` | Citas simultáneas permitidas. Usado por `check_overlap` (`overlap.py:55`). `1` = sin solapamiento permitido. |
| `draft_expiration_minutes` | Int | `15` | Minutos que un Draft reserva el slot antes de expirar. Usado por `_calculate_draft_expiration` (`appointment.py:167`). |
| `availability_plan` | Link → `Availability Plan` | — | Plan semanal asociado. Sin él, no hay disponibilidad calculable (`availability.py:82-87`). |
| `video_call_profile` | Link → `Video Call Profile` | — | Perfil heredado a las citas creadas en este recurso (`appointment.py:146-149`). |

### Sección "Notifications" (`notifications_section`)

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `send_email_notification` | Check | `0` | Si está marcado, al confirmar una cita se envía email a los `notification_users` activos. Verificado en `appointment.py:78` y `notifications/appointment.py:42`. |
| `notification_users` | Table → `Calendar Resource Notification User` | — | Tabla hija con usuarios a notificar. **`depends_on`**: `eval:doc.send_email_notification == 1`. Ver [CALENDAR_RESOURCE_NOTIFICATION_USER.md](CALENDAR_RESOURCE_NOTIFICATION_USER.md). |

---

## Permisos por rol

Definidos en `calendar_resource.json:115-146`.

| Rol | Read | Write | Create | Delete |
|---|---|---|---|---|
| `System Manager` | yes | yes | yes | yes |
| `Meet Scheduling Manager` | yes | yes | yes | yes |
| `Appointment User` | yes (export, report only) | no | no | no |

Notas:
- `Appointment User` solo puede leer/reportar; no puede modificar recursos.
- No hay restricciones por `if_owner` (a diferencia de `Appointment`).

---

## Custom fields agregados por otras apps

Estos campos NO están en el JSON nativo de `meet_scheduling`. Son creados por las apps consumidoras vía fixtures + `install.py`.

### Por `lex_app`

| Fieldname | Tipo | Origen | Descripción |
|---|---|---|---|
| `create_case_log` | Check | `lex_app/fixtures/custom_field.json` + `lex_app/install.py` | Si está marcado, al confirmar una cita se crea automáticamente un `Case Log`. Validado en `lex_app/lex_app/events/appointment.py:on_appointment_submit`. |

### Por `logbook`

| Fieldname | Tipo | Origen | Descripción |
|---|---|---|---|
| `create_logbook_entry` | Check | `logbook/install.py:13-26` | Si está marcado, al confirmar una cita se crea un `Logbook Entry`. Validado en `logbook/logbook/events/appointment.py:on_appointment_submit`. |
| `logbook_availability` | Link → `Logbook Availability` | `logbook/install.py:28-43` | Disponibilidad de logbook para asignación equitativa. **`depends_on`**: `eval:doc.create_logbook_entry`. **Mandatory** cuando `create_logbook_entry=1`. |

---

## Tabla de horarios (Calendar Resource Schedule)

El "schedule" del recurso no vive en el `Calendar Resource` directamente, sino en su `Availability Plan` vinculado, que a su vez tiene una child table `Availability Slot`. Ver [CALENDAR_RESOURCE_SCHEDULE.md](CALENDAR_RESOURCE_SCHEDULE.md) para el detalle del modelo y de la child table.

Flujo simplificado:

```
Calendar Resource
 └── availability_plan (Link)
      └── Availability Plan
           └── availability_slots (Table)
                └── Availability Slot (child)
                     ├── weekday
                     ├── start_time
                     ├── end_time
                     ├── capacity
                     └── location
```

Adicionalmente, las `Calendar Exception` overridean el plan por fecha específica (ver [CALENDAR_EXCEPTION.md](CALENDAR_EXCEPTION.md)).

---

## Lógica del controller

El controller `CalendarResource(Document)` está vacío (`pass`). Toda la lógica está en los servicios:

| Servicio | Función | Uso |
|---|---|---|
| `scheduling/availability.py` | `get_availability_slots_for_day` | Obtiene slots de un día respetando plan + excepciones + timezone. |
| `scheduling/slots.py` | `generate_available_slots` | Genera slots discretos para UI (cada `slot_duration_minutes`). |
| `scheduling/overlap.py` | `check_overlap` | Detecta overlaps respetando `capacity`. |

---

## Bugs y deuda técnica detectados

1. **`timezone` es Data y no Select**: no hay autocomplete ni validación contra `pytz.all_timezones`. Un valor inválido cae a UTC (`availability.py:108-115`).
2. **No hay validación de tipos en `slot_duration_minutes`, `capacity`, `draft_expiration_minutes`**: se acepta cualquier int (incluso negativo o 0). Solo se aplican defaults vía `or 30`, `or 1`, `or 15`.
3. **`Appointment User` no tiene permisos de read en custom fields sensibles** explícitamente, pero por defecto los hereda.
