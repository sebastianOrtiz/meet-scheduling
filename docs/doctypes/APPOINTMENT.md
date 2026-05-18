# DocType: Appointment

DocType principal de la app `meet_scheduling`. Representa una cita transaccional contra un `Calendar Resource`. Es **submittable** (`is_submittable: 1`), por lo que tiene los estados estándar de Frappe (Draft/Submitted/Cancelled) **además** del campo `status` propio.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/appointment/appointment.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/appointment/appointment.py`
- **Frontend JS**: `meet_scheduling/meet_scheduling/doctype/appointment/appointment.js` (vacío, comentado)
- **Naming rule**: `Expression` → `format:APT-{YYYY}-{#####}` (ej. `APT-2026-00001`)
- **Permite rename**: sí (`allow_rename: 1`)

---

## Propósito y casos de uso

- Bloquear un slot horario de un `Calendar Resource` para un `User contact` (ciudadano público).
- Resolver el `Video Call Profile` aplicable y, si corresponde, generar el `meeting_url` automáticamente al confirmar.
- Disparar `doc_events.on_submit` que otras apps (lex_app, logbook) usan para crear documentos asociados (`Case Log`, `Logbook Entry`).
- Disparar la notificación por email al confirmarse (`Appointment.on_submit` → `_enqueue_email_notification`).

---

## Campos (uno por uno)

Orden de campos según `field_order` del JSON (ver `appointment.json:8-28`):

### Sección "Basic Information" (`datos_base_section`)

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `user_contact` | Link → `User contact` | — | Usuario público que agenda la reunión. Consumido por la API autenticada. |
| `appointment_context` | Long Text | — | Contexto inicial del por qué se agenda la cita. Se sanitiza a 2000 caracteres en la API. Se copia a `Case Log.user_context` por lex_app y a `Logbook Entry.user_context` por logbook. |
| `calendar_resource` | Link → `Calendar Resource` | — | Agenda donde se reserva. **Requerido** (validado por `_validate_calendar_resource`). |
| `start_datetime` | Datetime | — | Hora de inicio. Validado `< end_datetime` por `_validate_datetime_consistency`. |
| `end_datetime` | Datetime | — | Hora de fin. |
| `status` | Select | `Draft` | Estado de la cita. Opciones: `Draft`, `Confirmed`, `Cancelled`, `No-show`, `Completed`. Se sincroniza con `docstatus` vía `db_set` en `on_submit` y `on_cancel`. |
| `draft_expires_at` | Datetime (hidden, read_only) | — | Momento en que un Draft expira y libera el slot. Calculado por `_calculate_draft_expiration` usando `Calendar Resource.draft_expiration_minutes` (default 15 min). |
| `party_type` | Link → DocType | — | Tipo de entidad atendida (ej. `Customer`). No usado por las apps consumidoras (lex_app/logbook), pero soportado por el modelo. |
| `party` | Dynamic Link (target = `party_type`) | — | Cliente específico. |
| `service` | Data | — | Servicio agendado (ej. "Consulta General"). |
| `notes` | Text | — | Observaciones adicionales. |
| `source` | Select | `Web` | Canal de creación. Opciones: `Web`, `Admin`, `API`. |

### Sección "Video Call" (`video_call_section`)

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `video_call_profile` | Link → `Video Call Profile` | — | Perfil aplicado. Si está vacío, se hereda del `Calendar Resource` en `_resolve_video_call_profile`. |
| `meeting_url` | Small Text | — | Enlace de la reunión (manual o auto-generado). Si el perfil es `manual_only` y el perfil tiene `default_meeting_url`, se copia automáticamente. |
| `meeting_id` | Data (read_only) | — | ID externo del proveedor (Google/Teams) para editar/cancelar. |
| `meeting_status` | Select (read_only) | `not_created` | Opciones: `not_created`, `created`, `failed`. |

### Otros

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `amended_from` | Link → `Appointment` (read_only, search_index) | — | Estándar de Frappe para documentos submittable amendados. |

---

## Estados (`status`) y su relación con `docstatus`

| `status` | `docstatus` típico | Significado |
|---|---|---|
| `Draft` | 0 | Reserva temporal. Bloquea el slot hasta `draft_expires_at`. |
| `Confirmed` | 1 | Cita confirmada. Se asigna en `on_submit` (`appointment.py:69-70`). |
| `Cancelled` | 2 | Cancelada por el usuario o por el job `cleanup_expired_drafts`. Se asigna en `on_cancel` (`appointment.py:110-111`). |
| `No-show` | 1 | El cliente no se presentó (uso administrativo). |
| `Completed` | 1 | La cita terminó (uso administrativo). |

> Nota: los estados `No-show` y `Completed` se definen en el Select pero ninguno de los servicios del repositorio los asigna automáticamente. Son flags de uso manual por el admin.

---

## Permisos por rol

Definidos en `appointment.json:172-211`.

| Rol | Read | Write | Create | Submit | Cancel | Delete | If owner |
|---|---|---|---|---|---|---|---|
| `System Manager` | yes | yes | yes | yes | yes | yes | no |
| `Meet Scheduling Manager` | yes | yes | yes | yes | yes | yes | no |
| `Appointment User` | yes (if_owner) | yes (if_owner) | yes | yes | no | no | **yes** |

Notas:
- `Appointment User` solo ve y modifica sus propias citas (`if_owner: 1`).
- No tiene permiso `cancel` ni `delete` en Frappe permissions; sin embargo, la API `cancel_my_appointment` permite cancelar usando `ignore_permissions=True` y validando ownership por token (`endpoints.py:891-987`).

---

## Métodos del Python doc (`appointment.py`)

### `validate(self) -> None` (`appointment.py:35-52`)

Se ejecuta antes de cada guardado. Llama a:

1. `_validate_calendar_resource()` — verifica que `calendar_resource` esté seteado.
2. `_validate_datetime_consistency()` — `start_datetime < end_datetime`.
3. `_resolve_video_call_profile()` — si no hay perfil, lo hereda del `Calendar Resource`; si el perfil tiene `default_meeting_url` y la cita no tiene `meeting_url`, lo copia.
4. `_calculate_draft_expiration()` — solo para Drafts nuevos: setea `draft_expires_at = now() + draft_expiration_minutes` (default 15 min). Muestra `msgprint` indicador `blue` informando al usuario.
5. `_validate_overlaps_and_block_if_exceeded()` — llama a `check_overlap` del servicio overlap. Si hay overlap pero hay capacidad, solo informa. Si la capacidad está excedida, **lanza** `frappe.throw`.
6. `_validate_slot_granularity()` — verifica que `(end - start) % slot_duration_minutes == 0`. Si no, muestra warning (no bloquea).

### `on_submit(self) -> None` (`appointment.py:54-71`)

Ejecuta validaciones fuertes y crea el meeting:

1. `_validate_draft_not_expired()` — si `draft_expires_at < now()`, lanza error indicando cuántos minutos hace que expiró.
2. `_validate_availability_strict()` — usa `get_availability_slots_for_day` y verifica que `[start, end]` cae dentro de algún slot disponible considerando timezone.
3. `_validate_overlaps_strict()` — llama a `check_overlap`. Bloquea si capacity excedida.
4. `_handle_meeting_creation()` — según `Video Call Profile.link_mode`:
   - `manual_only` → requiere `meeting_url` (lanza error si está vacío).
   - `auto_generate` → llama `_create_meeting_via_adapter`.
   - `auto_or_manual` → si no hay `meeting_url`, llama al adapter.
5. Asigna `status = "Confirmed"` y persiste con `db_set` para evitar disparar `validate` de nuevo.
6. `_enqueue_email_notification()` — encola `send_appointment_notification` con `enqueue_after_commit=True` para que se ejecute después de que todos los `doc_events.on_submit` (incluyendo los de lex_app y logbook) hayan commiteado.

### `on_cancel(self) -> None` (`appointment.py:101-111`)

1. `_handle_meeting_deletion()` — si tiene `meeting_id`, intenta `adapter.delete_meeting`. No bloquea la cancelación si falla (solo log_error).
2. Asigna `status = "Cancelled"` con `db_set`.

### `on_update(self) -> None` (`appointment.py:113-121`)

Llama a `_handle_meeting_update_on_time_change`:
- Solo aplica a citas `Confirmed` con `meeting_id` (auto-generadas).
- Detecta cambio de horario comparando con `get_doc_before_save`.
- Si cambió: elimina el meeting anterior y crea uno nuevo con el nuevo horario.

### Métodos auxiliares importantes

| Método | Ubicación | Función |
|---|---|---|
| `_create_meeting_via_adapter(profile)` | `appointment.py:367-395` | Llama a `get_adapter(profile.provider)`, valida perfil, crea meeting, guarda `meeting_url`/`meeting_id`/`meeting_status`. Si `VideoCallError`, marca `meeting_status = "failed"` y `throw`. |
| `_handle_meeting_deletion` | `appointment.py:397-416` | Elimina meeting del proveedor; no bloquea si falla. |
| `_enqueue_email_notification` | `appointment.py:73-99` | Comprueba `Calendar Resource.send_email_notification` y `has_outgoing_email()`. Si no hay email server, muestra `msgprint` naranja explicando cómo configurarlo. Si todo OK, encola la notificación. |

---

## `doc_events` asociados (definidos por otras apps)

Esta app **NO** define `doc_events` propios sobre Appointment; pero registra hooks extensibles (`appointment_email_context`, `appointment_email_recipients`). Otras apps sí registran `doc_events`:

| App | Hook | Handler |
|---|---|---|
| `lex_app` | `Appointment.on_submit` | `lex_app.lex_app.events.appointment.on_appointment_submit` (crea `Case Log` si `Calendar Resource.create_case_log = 1`). |
| `logbook` | `Appointment.on_submit` | `logbook.logbook.events.appointment.on_appointment_submit` (crea `Logbook Entry` si `Calendar Resource.create_logbook_entry = 1`). |

Ver [LEX_APP.md](../integration/LEX_APP.md) y [LOGBOOK.md](../integration/LOGBOOK.md) para detalles.

---

## Hooks extensibles que dispara

| Hook (definido en `meet_scheduling/hooks.py`) | Cuándo se dispara | Quién lo escucha |
|---|---|---|
| `appointment_email_context` | Al construir contexto del email (`notifications/appointment.py:98-107`) | `lex_app` (agrega `case_log_*`), `logbook` (agrega `logbook_entry_*`). |
| `appointment_email_recipients` | Al armar la lista de destinatarios (`notifications/appointment.py:53-65`) | `lex_app` (agrega lawyer asignado + supervisor), `logbook` (agrega `assigned_to`). |

---

## Bugs y deuda técnica detectados

1. **Inconsistencia de DocType `User Contact` vs `User contact`**: el JSON del Appointment usa `"options": "User contact"` (minúsculas), mientras que el código de notificaciones usa `frappe.db.get_value("User Contact", ...)` (con C mayúscula) en `notifications/appointment.py:75`. Frappe trata los nombres de DocType case-insensitive en MariaDB en muchos casos, pero esto es una inconsistencia que podría romper en otros backends.
2. **`status` puede desincronizarse con `docstatus`**: el campo `status` se persiste con `db_set` evitando `validate`. Si alguien cancela el documento desde la UI sin pasar por `on_cancel`, podría quedar inconsistente.
3. **`No-show` y `Completed` no tienen lógica**: están en el Select pero ningún servicio los asigna.
4. **Adaptadores mock**: `GoogleMeetAdapter` y `TeamsAdapter` devuelven URLs falsas (`https://meet.google.com/mock-{name}`). En producción aún no se crean meetings reales.
5. **`amended_from`**: el doctype es submittable pero no hay lógica de `amend` documentada.
