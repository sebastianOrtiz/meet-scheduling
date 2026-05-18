# Feature: Sistema de notificaciones por email

Cuando un `Appointment` se confirma, la app envía un email a los `notification_users` configurados en el `Calendar Resource`. El sistema es extensible: otras apps pueden registrar hooks para agregar contexto al template y destinatarios extra.

---

## Archivos clave

| Archivo | Responsabilidad |
|---|---|
| `meet_scheduling/meet_scheduling/notifications/appointment.py` | Función `send_appointment_notification` (entry point). |
| `meet_scheduling/templates/emails/appointment_confirmed.html` | Template Jinja del email. |
| `meet_scheduling/meet_scheduling/doctype/appointment/appointment.py` (líneas 73-99) | Encola la notificación con `enqueue_after_commit=True`. |
| `meet_scheduling/hooks.py:44-45` | Declara los hooks extensibles `appointment_email_context` y `appointment_email_recipients`. |

---

## Cuándo se envía

**Trigger**: `Appointment.on_submit` (`appointment.py:54-71`). Específicamente, al final del submit:

```python
self._enqueue_email_notification()
```

Que internamente (`appointment.py:73-99`):

1. Lee `Calendar Resource.send_email_notification`. Si es `0`, retorna sin enviar.
2. Verifica `has_outgoing_email()` (de `common_configurations.api.shared`). Si no hay cuenta de email saliente configurada, muestra un `msgprint` naranja explicando cómo configurarla en `/app/email-account` y retorna.
3. Encola `send_appointment_notification(appointment_name)` con `enqueue_after_commit=True` y `queue="default"`.

> El `enqueue_after_commit=True` es **crítico**: garantiza que todos los `doc_events.on_submit` (incluyendo los de lex_app y logbook) hayan committeado antes de que el job de notificación lea el DB. Sin esto, los hooks `appointment_email_context` podrían no encontrar el `Case Log` o el `Logbook Entry` recién creado.

---

## Otras notificaciones (cancelación, recordatorio)

**No están implementadas** en el código actual. Solo se envía email al confirmar. La función `send_appointment_notification` solo construye el email "Confirmation". No hay `send_appointment_cancellation` ni `send_appointment_reminder`.

Esto es deuda técnica documentada.

---

## Flujo de `send_appointment_notification`

`notifications/appointment.py:19-132`.

```python
def send_appointment_notification(appointment_name: str) -> None:
    if not has_outgoing_email():
        log.warning(...)
        return

    appointment = frappe.get_doc("Appointment", appointment_name)
    resource = frappe.get_doc("Calendar Resource", appointment.calendar_resource)

    if not resource.send_email_notification:
        return

    # 1. Destinatarios base desde notification_users
    recipients = [row.user for row in resource.notification_users if row.is_active and row.user]

    # 2. Destinatarios extra de los hooks
    for hook_path in frappe.get_hooks("appointment_email_recipients"):
        try:
            extra = frappe.get_attr(hook_path)(appointment)
            if extra:
                recipients.extend(extra)
        except Exception:
            frappe.log_error(...)

    # Deduplicar y descartar vacíos
    recipients = list({r for r in recipients if r})

    if not recipients:
        return

    # 3. Contexto base del template
    contact_name = frappe.db.get_value(
        "User Contact", appointment.user_contact, "full_name"
    ) or appointment.user_contact

    context = {
        "appointment_name": appointment.name,
        "appointment_url": f"{get_url()}/app/appointment/{appointment.name}",
        "contact_name": contact_name,
        "calendar_resource": resource.resource_name,
        "start_datetime": format_datetime(appointment.start_datetime, "EEEE d 'de' MMMM yyyy, HH:mm"),
        "end_datetime": format_datetime(appointment.end_datetime, "HH:mm"),
        "meeting_url": appointment.meeting_url or "",
        "appointment_context": appointment.appointment_context or "",
        # placeholders que lex_app puede sobrescribir
        "case_log_name": None,
        "case_log_title": None,
        "assigned_lawyer_name": None,
        "case_log_url": None,
    }

    # 4. Contexto enriquecido por hooks
    for hook_path in frappe.get_hooks("appointment_email_context"):
        try:
            extra = frappe.get_attr(hook_path)(appointment)
            if extra:
                context.update(extra)
        except Exception:
            frappe.log_error(...)

    # 5. Construir asunto y enviar
    subject = _("[Cita Confirmada] {0} | {1} – {2}").format(
        contact_name, resource.resource_name,
        format_datetime(appointment.start_datetime, "EEE d MMM yyyy, HH:mm"),
    )
    if context.get("case_log_name"):
        subject += _(" | Caso {0}").format(context["case_log_name"])

    send_email(
        recipients=recipients,
        subject=subject,
        template="appointment_confirmed",
        args=context,
        reference_doctype="Appointment",
        reference_name=appointment.name,
        log_title="Appointment Notification Failed",
    )
```

> `send_email` se importa de `common_configurations.api.shared`. Usa `frappe.sendmail` con el template buscado en `templates/emails/<template>.html`.

---

## Template Jinja

Ubicación: `meet_scheduling/templates/emails/appointment_confirmed.html` (243 líneas).

Estructura visual (tabla HTML compatible con clientes de email):

1. **Header gradiente azul** con el nombre del `calendar_resource`.
2. **Badge de status** verde ("Cita Confirmada").
3. **Tarjeta de detalles**:
   - Fecha y hora (start_datetime + end_datetime).
   - Contacto (`contact_name`).
   - Recurso (`calendar_resource`).
   - Motivo (`appointment_context`, si existe).
4. **Bloque de videollamada** (si `meeting_url`):
   - Botón "Unirse a la videollamada" (azul).
   - Enlace texto plano del meeting_url.
5. **Bloque "Caso Legal" amarillo** (si `case_log_name` — viene de lex_app):
   - `case_log_name`
   - `case_log_title`
   - `assigned_lawyer_name`
   - Botón "Abrir Caso" → `case_log_url`.
6. **Botón "Ver Cita en el Sistema"** → `appointment_url` (link al desk).
7. **Footer** con referencia `appointment_name`.

### Variables del contexto

| Variable | Origen | Descripción |
|---|---|---|
| `appointment_name` | base | ID del Appointment (ej. APT-2026-00001). |
| `appointment_url` | base | URL al desk para el admin. |
| `contact_name` | base | `User contact.full_name`. |
| `calendar_resource` | base | `resource_name`. |
| `start_datetime` | base | Formateado: `EEEE d 'de' MMMM yyyy, HH:mm`. |
| `end_datetime` | base | Formateado: `HH:mm`. |
| `meeting_url` | base | Si existe, muestra bloque de videollamada. |
| `appointment_context` | base | Motivo capturado en el agendamiento. |
| `case_log_name` | hook lex_app | Si existe, muestra bloque amarillo. |
| `case_log_title` | hook lex_app | Título del caso. |
| `assigned_lawyer_name` | hook lex_app | `full_name` del abogado asignado. |
| `case_log_url` | hook lex_app | URL al desk del Case Log. |

> **lógbook no agrega keys nuevas al template**: actualmente solo retorna `logbook_entry_*` (ver `logbook/logbook/events/appointment.py:88-120`), pero el template HTML no las renderiza. Es deuda: el template solo tiene un bloque para `case_log_*`. Sería razonable agregar un bloque genérico para `logbook_entry_*` también.

---

## Hooks extensibles definidos por meet_scheduling

Declarados en `meet_scheduling/hooks.py:44-45`:

```python
appointment_email_context = []
appointment_email_recipients = []
```

Otras apps registran funciones aquí en sus propios `hooks.py`. Los hooks se ejecutan con `frappe.get_hooks(hook_name)` que retorna la unión de todas las apps.

### Firma esperada

```python
def my_appointment_email_context(appointment_doc) -> dict:
    """Retorna dict que se mergea al contexto del template."""
    return {"my_var": "value"}

def my_appointment_email_recipients(appointment_doc) -> list[str]:
    """Retorna lista de emails que se agregan a recipientes."""
    return ["lawyer@example.com"]
```

Se pasan el `Appointment` doc completo como único argumento.

### Implementaciones existentes

| App | Hook | Función |
|---|---|---|
| lex_app | `appointment_email_context` | `lex_app.lex_app.events.appointment.get_appointment_email_context` |
| lex_app | `appointment_email_recipients` | `lex_app.lex_app.events.appointment.get_appointment_email_recipients` |
| logbook | `appointment_email_context` | `logbook.logbook.events.appointment.get_appointment_email_context` |
| logbook | `appointment_email_recipients` | `logbook.logbook.events.appointment.get_appointment_email_recipients` |

Ver [LEX_APP.md](../integration/LEX_APP.md) y [LOGBOOK.md](../integration/LOGBOOK.md) para el detalle de qué retornan.

---

## Cómo se enganchan lex_app y logbook

### lex_app

`lex_app/hooks.py`:

```python
appointment_email_context = [
    "lex_app.lex_app.events.appointment.get_appointment_email_context"
]
appointment_email_recipients = [
    "lex_app.lex_app.events.appointment.get_appointment_email_recipients"
]
```

Función `get_appointment_email_context` (en `lex_app/lex_app/events/appointment.py`):

- Si `Calendar Resource.create_case_log` y existe `Case Log.source_appointment == appointment.name`:
  - Retorna `{case_log_name, case_log_title, assigned_lawyer_name, case_log_url}`.

Función `get_appointment_email_recipients`:

- Si hay `Case Log` asociado, agrega el `assigned_lawyer` y el supervisor (`lawyer_supervisor` de `Lawyer Availability`).

### logbook

`logbook/hooks.py:170-176`:

```python
appointment_email_context = [
    "logbook.logbook.events.appointment.get_appointment_email_context"
]
```

Función `get_appointment_email_context` (en `logbook/logbook/events/appointment.py:88-120`):

- Si `Calendar Resource.create_logbook_entry` y existe `Logbook Entry.source_appointment == appointment.name`:
  - Retorna `{logbook_entry_name, logbook_entry_title, assigned_to_name, logbook_entry_url}`.

Función `get_appointment_email_recipients` (logbook):

- Si hay `Logbook Entry` asociado, agrega el `assigned_to` (email del User).

> El template `appointment_confirmed.html` NO tiene actualmente un bloque para `logbook_entry_*`, así que esos datos llegan al contexto pero no se renderizan. Es deuda técnica.

---

## Configuración necesaria

Para que se envíen los emails:

1. **Cuenta de email saliente configurada** en Frappe (`/app/email-account` con `Enable Outgoing = 1`). Validado por `has_outgoing_email()`.
2. **`Calendar Resource.send_email_notification = 1`**.
3. **Al menos un `Calendar Resource Notification User`** activo con `user` válido, o algún hook que agregue destinatarios.

Si falla alguna de estas, el sistema:
- Sin email saliente: avisa con `msgprint` naranja y retorna sin encolar.
- Sin `send_email_notification`: retorna silenciosamente.
- Sin destinatarios: log info y retorna sin enviar.

---

## Manejo de errores

- Cada hook ejecutado dentro de un `try/except` que captura cualquier exception y la log_error con título descriptivo. Esto evita que un hook roto rompa el envío del email base.
- La función completa `send_appointment_notification` también está envuelta en `try/except` que `frappe.log_error` con título `Appointment Notification Failed`.
- El job se ejecuta en background queue `"default"` con `enqueue_after_commit=True`. Si falla, queda en `RQ Failed Jobs`.

---

## Deuda técnica

1. **Solo email de confirmación**: faltan `cancellation`, `reminder`, `rescheduled`, `expired_draft`.
2. **Template no muestra `logbook_entry_*`**: el hook de logbook agrega contexto que no se renderiza.
3. **Caso `User Contact` vs `User contact`**: se usa con C mayúscula en `notifications/appointment.py:75` pero el field `options` del DocType usa minúsculas. Inconsistencia potencial.
4. **`appointment_context` puede contener HTML/Jinja injection**: no se escapa explícitamente en el template. Jinja por defecto sí auto-escapa, pero el campo `Long Text` permite caracteres especiales.
5. **No hay forma de testear el render**: faltan tests del template + contexto.
