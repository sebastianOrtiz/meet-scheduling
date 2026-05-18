# Integración: logbook

`logbook` consume `meet_scheduling` para crear entradas de bitácora (`Logbook Entry`) automáticamente al confirmar una cita, y para enriquecer el email con datos de la entrada.

> Esta sección documenta cómo se ven los hooks DESDE el lado de `meet_scheduling`. El detalle interno de `logbook` está en `apps/logbook/logbook/logbook/events/appointment.py`.

---

## Resumen de integración

| Punto de integración | Mecanismo | Lado logbook | Lado meet_scheduling |
|---|---|---|---|
| Crear Logbook Entry al confirmar cita | `doc_events.Appointment.on_submit` | `logbook.events.appointment.on_appointment_submit` | `Appointment.on_submit` dispara doc_events. |
| Custom field `create_logbook_entry` | install.py + fixture | `logbook/install.py:13-26` y `logbook/fixtures/...` | Custom field agregado al `Calendar Resource`. |
| Custom field `logbook_availability` | install.py | `logbook/install.py:28-43` | Custom field agregado al `Calendar Resource`. |
| Custom field en Service Portal Tool | install.py | `logbook/install.py:45-55` | Custom field `logbook_availability` agregado al `Service Portal Tool` para el tool type `create_logbook` (de logbook, no de meet_scheduling). |
| Hook contexto del email | `appointment_email_context` | `logbook.events.appointment.get_appointment_email_context` | `meet_scheduling/hooks.py:44` declara la lista. |
| Hook destinatarios del email | `appointment_email_recipients` | `logbook.events.appointment.get_appointment_email_recipients` | `meet_scheduling/hooks.py:45` declara la lista. |

---

## 1. Custom fields agregados al Calendar Resource

### `create_logbook_entry` (Check)

Definido en `logbook/install.py:13-26`:

```python
if not frappe.db.exists("Custom Field", "Calendar Resource-create_logbook_entry"):
    frappe.get_doc(
        {
            "doctype": "Custom Field",
            "dt": "Calendar Resource",
            "fieldname": "create_logbook_entry",
            "fieldtype": "Check",
            "label": "Create Logbook Entry on Appointment",
            ...
        }
    ).insert(ignore_permissions=True)
```

Cuando está marcado en un `Calendar Resource`, todas las citas confirmadas para ese recurso generan automáticamente un `Logbook Entry`.

### `logbook_availability` (Link → Logbook Availability)

Definido en `logbook/install.py:28-43`. Atributos:

- `fieldtype`: `Link`
- `options`: `Logbook Availability`
- `insert_after`: `create_logbook_entry`
- `depends_on`: `eval:doc.create_logbook_entry`
- `mandatory_depends_on`: `eval:doc.create_logbook_entry`

Es decir, este campo solo aparece y es obligatorio cuando `create_logbook_entry = 1`. Apunta a una `Logbook Availability` que define qué usuarios pueden recibir las entries (asignación equitativa similar a `Lawyer Availability` de lex_app).

---

## 2. `on_appointment_submit` — Crear Logbook Entry

Registrado en `logbook/hooks.py:165-168`:

```python
doc_events = {
    "Appointment": {
        "on_submit": "logbook.logbook.events.appointment.on_appointment_submit"
    }
}
```

### Flujo del handler

Ubicación: `logbook/logbook/events/appointment.py:16-85`.

1. Si la cita no tiene `calendar_resource` → return.
2. Carga `Calendar Resource`.
3. Si `calendar_resource.create_logbook_entry` es falsy → return.
4. Si la cita no tiene `user_contact` → log warning y return.
5. Crea `Logbook Entry` con:
   - `user_contact = appointment.user_contact`
   - `title = "Entry from appointment: {appointment.name}"`
   - `status = "New"`
   - `priority = "Medium"`
   - `start_date = today()`
   - `source_appointment = appointment.name`
   - `assigned_to = get_user_for_assignment(appointment.calendar_resource) or session.user`
   - `user_context = appointment.appointment_context` (si existe).
   - Agrega un `important_dates` con el horario y `meeting_url` como location.
6. Si falla → log_error (sin throw — la cita SÍ se confirma).

> **Diferencia importante con lex_app**: si la creación del `Logbook Entry` falla, **la cita SÍ se confirma**. Solo se loggea el error. lex_app, en cambio, hace `throw` y aborta el submit.

---

## 3. Servicio de asignación equitativa

`logbook` usa `get_user_for_assignment(calendar_resource)` (`logbook/logbook/services/assignment.py`). Flujo:

1. Lee `Calendar Resource.logbook_availability`.
2. Si no hay, retorna `None`.
3. Si `Logbook Availability` no está activa → log_error y `None`.
4. Si no hay usuarios disponibles en la availability → log_error y `None`.
5. Si hay usuarios, retorna uno (lógica de asignación equitativa — round-robin por carga).

Si `get_user_for_assignment` retorna `None`, el handler usa `frappe.session.user` como fallback.

---

## 4. Hook `appointment_email_context`

Implementación en `logbook/logbook/events/appointment.py:88-120`:

```python
def get_appointment_email_context(appointment_doc):
    calendar_resource = frappe.get_doc("Calendar Resource", appointment_doc.calendar_resource)
    if not getattr(calendar_resource, "create_logbook_entry", False):
        return {}

    logbook_name = frappe.db.get_value(
        "Logbook Entry", {"source_appointment": appointment_doc.name}, "name"
    )
    if not logbook_name:
        return {}

    logbook_entry = frappe.get_doc("Logbook Entry", logbook_name)
    assigned_to_name = None
    if logbook_entry.assigned_to:
        assigned_to_name = (
            frappe.db.get_value("User", logbook_entry.assigned_to, "full_name")
            or logbook_entry.assigned_to
        )

    return {
        "logbook_entry_name": logbook_entry.name,
        "logbook_entry_title": logbook_entry.title,
        "assigned_to_name": assigned_to_name,
        "logbook_entry_url": f"{get_url()}/app/logbook-entry/{logbook_name}",
    }
```

> **Importante**: el template `appointment_confirmed.html` no renderiza estas variables. Es decir, el contexto se enriquece pero no se muestra. Es deuda técnica: o se agrega un bloque al template, o se hace un template alternativo.

---

## 5. Hook `appointment_email_recipients`

Implementación en `logbook/logbook/events/appointment.py:123-149`:

- Si `create_logbook_entry` y hay `Logbook Entry` con `source_appointment`:
  - Lee `assigned_to` del entry.
  - Obtiene el email del User asignado.
  - Lo agrega a la lista de recipientes.

---

## 6. Convivencia con lex_app

Es válido marcar **ambos** flags en un `Calendar Resource`:

- `create_case_log = 1` (lex_app) → crea `Case Log`.
- `create_logbook_entry = 1` (logbook) → crea `Logbook Entry`.

Ambos handlers se ejecutan en `on_submit` (orden no garantizado por Frappe — depende del orden de carga de apps). El email final contendrá variables de ambos hooks (`case_log_*` y `logbook_entry_*`) en el contexto, aunque el template actual solo renderiza `case_log_*`.

---

## Diagrama simplificado

```
Appointment.on_submit
  ├─ validate + create meeting (mock)
  ├─ doc_events.on_submit:
  │    ├─ lex_app.on_appointment_submit
  │    │    └─ Case Log (si create_case_log=1)
  │    └─ logbook.on_appointment_submit
  │         └─ Logbook Entry (si create_logbook_entry=1)
  ├─ status = "Confirmed"
  └─ _enqueue_email_notification (after commit)
       └─ send_appointment_notification(job)
            ├─ context += lex_app hook (case_log_*)
            ├─ context += logbook hook (logbook_entry_*)  ← NO se renderiza
            ├─ recipients += lex_app hook (lawyer + supervisor)
            ├─ recipients += logbook hook (assigned_to)
            └─ send_email("appointment_confirmed", ctx)
```

---

## Deuda técnica

1. **Template no muestra `logbook_entry_*`**: el contexto se enriquece pero el HTML solo tiene bloque para Case Log.
2. **Sin `frappe.throw` en logbook**: si la entry falla, solo se loggea. Diferente comportamiento al de lex_app, podría confundir.
3. **`logbook_availability` puede no existir**: si logbook no está instalado, el `getattr(calendar_resource, "create_logbook_entry", False)` retorna False y todo funciona; si está parcialmente instalado (custom field sin install.py), podría comportarse raro.
