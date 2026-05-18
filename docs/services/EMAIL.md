# Service: Email (`notifications/appointment.py`)

Servicio que envía el email de confirmación de una cita usando el template Jinja `appointment_confirmed`. Soporta extensibilidad vía hooks `appointment_email_context` y `appointment_email_recipients`.

- **Archivo**: `meet_scheduling/meet_scheduling/notifications/appointment.py`
- **Template**: `meet_scheduling/templates/emails/appointment_confirmed.html`

> Para el flujo completo (cuándo se envía, qué template renderiza, qué hooks consume), ver [features/EMAIL_NOTIFICATIONS.md](../features/EMAIL_NOTIFICATIONS.md).

---

## Función pública

### `send_appointment_notification(appointment_name: str) -> None`

`notifications/appointment.py:19-132`.

**Args**:
- `appointment_name` — name del `Appointment` confirmado.

**Comportamiento**:

1. Verifica `has_outgoing_email()` (de `common_configurations.api.shared`). Si no hay cuenta de email saliente, log warning y retorna.
2. Carga `Appointment` y `Calendar Resource`.
3. Si `Calendar Resource.send_email_notification = 0` → retorna.
4. Construye lista base de destinatarios desde `resource.notification_users` (filas activas con `user`).
5. Itera hooks `appointment_email_recipients` (de `frappe.get_hooks(...)`). Cada hook retorna `list[str]` que se agrega. Errores son log_error pero no interrumpen.
6. Deduplica con `set()` y descarta vacíos.
7. Si no hay destinatarios, log info y retorna.
8. Construye `context` base:
   - `appointment_name`, `appointment_url` (al desk).
   - `contact_name` (de `User Contact.full_name`).
   - `calendar_resource` (resource_name).
   - `start_datetime` y `end_datetime` formateados con `format_datetime`.
   - `meeting_url`, `appointment_context`.
   - Placeholders `case_log_name`, `case_log_title`, `assigned_lawyer_name`, `case_log_url` (en `None`).
9. Itera hooks `appointment_email_context`. Cada hook retorna `dict` que se mergea (`context.update(extra)`).
10. Construye subject: `"[Cita Confirmada] {contact} | {resource} – {fecha}"`. Si hay `case_log_name`, agrega `" | Caso {case_log_name}"`.
11. Llama `send_email(...)` con template `"appointment_confirmed"`.

---

## Entry point: `_enqueue_email_notification` (en Appointment)

`appointment.py:73-99`. Se llama al final de `on_submit`:

```python
def _enqueue_email_notification(self) -> None:
    from meet_scheduling.meet_scheduling.notifications.appointment import has_outgoing_email

    resource = frappe.get_cached_doc("Calendar Resource", self.calendar_resource)
    if not resource.send_email_notification:
        return

    if not has_outgoing_email():
        frappe.msgprint(
            _("La cita fue confirmada, pero <strong>no hay servidor de email saliente configurado</strong> ..."),
            title=_("Notificación de email no enviada"),
            indicator="orange",
        )
        return

    frappe.enqueue(
        "meet_scheduling.meet_scheduling.notifications.appointment.send_appointment_notification",
        appointment_name=self.name,
        queue="default",
        enqueue_after_commit=True,
    )
```

**Puntos clave**:
- `enqueue_after_commit=True`: garantiza que los `doc_events.on_submit` (lex_app crea Case Log, logbook crea Logbook Entry) hayan committeado antes de que el job consulte el DB para enriquecer el contexto.
- Sin email saliente: muestra `msgprint` naranja al usuario explicando dónde configurarlo. **Nota**: el `import` de `has_outgoing_email` está marcado como `from meet_scheduling.meet_scheduling.notifications.appointment import has_outgoing_email`, pero esa función realmente viene de `common_configurations.api.shared`. Es deuda: el módulo `notifications/appointment.py` re-importa `has_outgoing_email` de `common_configurations` en su línea 16, por lo que el `from ... import has_outgoing_email` desde `appointment.py:75` funciona pero es indirecto.

---

## Hooks consumidos

| Hook | Tipo | Resultado merged |
|---|---|---|
| `appointment_email_context` | `Callable[[Appointment], dict]` | Mergea al `context` del template. |
| `appointment_email_recipients` | `Callable[[Appointment], list[str]]` | Extiende la lista de destinatarios. |

`meet_scheduling/hooks.py:44-45` declara ambas listas vacías. Otras apps (`lex_app`, `logbook`) las extienden en sus propios `hooks.py`.

---

## Manejo de errores

- Cada hook ejecutado en try/except → `frappe.log_error` con mensaje descriptivo si falla.
- La función completa en try/except → `frappe.log_error` con título `"Appointment Notification Failed"`.
- El job en background queue `default`. Reintentos no configurados; los fallos quedan en `RQ Failed Jobs`.

---

## Variables del template

Ver el archivo `templates/emails/appointment_confirmed.html`. Variables esperadas (en el orden en que aparecen):

| Variable | Origen |
|---|---|
| `calendar_resource` | base (resource_name) |
| `contact_name` | base |
| `start_datetime` (formateado largo) | base |
| `end_datetime` (formateado HH:mm) | base |
| `appointment_context` | base (opcional) |
| `meeting_url` | base (opcional) |
| `case_log_name`, `case_log_title`, `assigned_lawyer_name`, `case_log_url` | hook lex_app (opcional) |
| `appointment_url` | base (link al desk) |
| `appointment_name` | base (footer) |

> Variables `logbook_entry_*` (del hook de logbook) llegan al contexto pero el template NO las renderiza. Deuda técnica.

---

## Funciones auxiliares utilizadas

| Función | Origen | Uso |
|---|---|---|
| `has_outgoing_email()` | `common_configurations.api.shared` | Verifica si hay Email Account con `enable_outgoing = 1`. |
| `send_email(...)` | `common_configurations.api.shared` | Wrapper sobre `frappe.sendmail` que busca templates en `templates/emails/<name>.html`. |
| `format_datetime(dt, fmt)` | `frappe.utils` | Formato Babel (`EEEE d 'de' MMMM yyyy, HH:mm` produce "Martes 20 de enero 2026, 10:00"). |
| `get_url()` | `frappe.utils` | URL base del sitio. |

---

## Deuda técnica

1. **Solo email de confirmación**: faltan cancellation, reminder, rescheduled.
2. **Template no renderiza `logbook_entry_*`**.
3. **Inconsistencia de DocType**: `User Contact` (C) vs `User contact` (minúsculas) — ver `notifications/appointment.py:75`.
4. **Sin rate limit del envío**: si se confirman muchas citas en simultáneo, se encolan muchos jobs sin throttling.
5. **No hay reintentos automáticos**: si el SMTP está caído cuando corre el job, el email se pierde a menos que el RQ Worker reintente.
