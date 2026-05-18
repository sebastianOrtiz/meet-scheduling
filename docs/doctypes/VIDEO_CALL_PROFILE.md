# DocType: Video Call Profile

Perfil reutilizable que define cómo se obtiene el enlace de videollamada (`meeting_url`) para una cita. Puede configurarse como manual (link fijo), automático (creación vía API del proveedor) o híbrido.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/video_call_profile/video_call_profile.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/video_call_profile/video_call_profile.py` (clase `VideoCallProfile(Document)` con `pass`).
- **Naming rule**: `By fieldname` → `profile_name`.

---

## Propósito y casos de uso

- "Google Meet - Consultas" (link manual fijo) → todas las citas usan el mismo enlace.
- "Google Meet - Auto" → genera un link distinto para cada cita vía Google Calendar API (cuando se implemente OAuth real).
- "Teams - Reuniones internas" → similar para Microsoft Teams.

---

## Campos

Orden según `field_order` (`video_call_profile.json:8-18`).

### Datos generales

| Fieldname | Tipo | Default | Reqd | Unique | Descripción |
|---|---|---|---|---|---|
| `profile_name` | Data | — | yes | yes | Nombre descriptivo. Es el `name` del documento. |
| `is_active` | Check | `1` | — | — | Si está desmarcado, lógicamente no debería usarse. **No se valida automáticamente** en `Appointment.validate`. |
| `provider` | Select | `google_meet` | yes | — | Opciones: `google_meet`, `microsoft_teams`. Determina el adapter usado por `factory.get_adapter`. |
| `link_mode` | Select | `manual_only` | yes | — | Opciones: `manual_only`, `auto_generate`, `auto_or_manual`. Ver detalle abajo. |

### Sección "Video Call Link" (`manual_config_section`)

**`depends_on`**: `eval:doc.link_mode === 'manual_only'`.

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `default_meeting_url` | Small Text | — | Enlace fijo que se copia a cada cita creada con este perfil. Aplicado en `appointment.py:152-155`. |

### Sección "Automatic Configuration" (`auto_config_section`)

**`depends_on`**: `eval:doc.link_mode !== 'manual_only'`.

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `provider_account` | Link → `Provider Account` | — | Cuenta OAuth para crear meetings. **Mandatory** cuando `link_mode == 'auto_generate'` (`mandatory_depends_on`). |
| `meeting_title_template` | Data | — | Plantilla Jinja para el título del meeting. Soporta `{{ appointment.name }}`, `{{ appointment.calendar_resource }}`. **Nota**: actualmente los adaptadores son mock y no la usan. |

---

## Modos de enlace (`link_mode`)

### `manual_only` (default)

- El usuario configura `default_meeting_url` en el perfil.
- Al crear una cita, si `meeting_url` está vacío, se copia el `default_meeting_url` (`appointment.py:152-155`).
- En `on_submit`, si `meeting_url` sigue vacío, **lanza error** (`appointment.py:356-358`).
- No se llama al adapter, no se contacta a Google/Microsoft.

### `auto_generate`

- En `on_submit`, **siempre** llama al adapter (`appointment.py:360-361`).
- Si el adapter falla, marca `meeting_status = "failed"` y lanza error (`appointment.py:389-395`).
- Requiere `provider_account` válido y conectado.

### `auto_or_manual`

- Si `meeting_url` ya tiene valor, se respeta tal cual.
- Si `meeting_url` está vacío en `on_submit`, llama al adapter (`appointment.py:363-365`).
- Útil para tener un fallback manual.

---

## Permisos por rol

Definidos en `video_call_profile.json:98-127`.

| Rol | Read | Write | Create | Delete |
|---|---|---|---|---|
| `System Manager` | yes | yes | yes | yes |
| `Meet Scheduling Manager` | yes | yes | yes | yes |
| `Appointment User` | yes | no | no | no |

---

## Flujo de creación de meeting

Ver `appointment.py:341-395` (`_handle_meeting_creation` + `_create_meeting_via_adapter`):

1. Si `Appointment.video_call_profile` está vacío, intenta heredarlo del `Calendar Resource`.
2. Si el perfil tiene `default_meeting_url` y la cita no tiene `meeting_url`, lo copia.
3. En `on_submit`:
   - `manual_only` → exige `meeting_url`.
   - `auto_generate` → llama `factory.get_adapter(profile.provider)` y crea.
   - `auto_or_manual` → si `meeting_url` vacío, crea.

---

## Validación del adapter

`google_meet.py:30-38` y `microsoft_teams.py:30-38` validan:

- Si `link_mode in ("auto_generate", "auto_or_manual")` y no hay `provider_account` → error.
- Si la `Provider Account.status != "Connected"` → `VideoCallError`.

---

## Bugs / deuda técnica

1. **Implementación mock**: ambos adaptadores devuelven URLs falsas (`https://meet.google.com/mock-{name}` y `https://teams.microsoft.com/mock-{name}`). En producción NO se crean meetings reales aún.
2. **`is_active` no se valida** al usar el perfil. Un perfil desactivado podría usarse igualmente.
3. **`meeting_title_template` no se aplica**: los adaptadores mock no procesan Jinja.
4. **`Appointment.video_call_profile` no es read_only**: si el usuario cambia el perfil tras `on_submit`, no se re-crea el meeting; solo se re-crea si cambia el horario (`_handle_meeting_update_on_time_change`).
