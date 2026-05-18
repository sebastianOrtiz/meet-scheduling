# Integración: lex_app

`lex_app` consume `meet_scheduling` para crear casos legales (`Case Log`) automáticamente cuando se confirma una cita. Adicionalmente enriquece el email de confirmación con datos del caso.

> Esta sección documenta cómo se ven los hooks DESDE el lado de `meet_scheduling`. Para detalle interno de `lex_app`, ver `apps/lex_app/docs/integration/MEET_SCHEDULING.md`.

---

## Resumen de integración

| Punto de integración | Mecanismo | Lado lex_app | Lado meet_scheduling |
|---|---|---|---|
| Crear Case Log al confirmar cita | `doc_events.Appointment.on_submit` | `lex_app.events.appointment.on_appointment_submit` | DocType `Appointment` con `on_submit` que dispara los doc_events de Frappe. |
| Custom field `create_case_log` en Calendar Resource | Fixture + install.py | `lex_app/fixtures/custom_field.json` y `lex_app/install.py` | El DocType `Calendar Resource` no declara este campo; lex_app lo agrega. |
| Hook de contexto del email | `appointment_email_context` | `lex_app.events.appointment.get_appointment_email_context` | Declarado en `meet_scheduling/hooks.py:44` (lista vacía). |
| Hook de destinatarios del email | `appointment_email_recipients` | `lex_app.events.appointment.get_appointment_email_recipients` | Declarado en `meet_scheduling/hooks.py:45`. |
| Lawyer Availability filtrada por Calendar Resource | Tabla en `Lawyer Availability` | DocType de lex_app | meet_scheduling solo expone `Calendar Resource` como target del Link. |

---

## 1. `on_appointment_submit` — Crear Case Log

Registrado en `lex_app/hooks.py`:

```python
doc_events = {
    "Appointment": {
        "on_submit": "lex_app.lex_app.events.appointment.on_appointment_submit"
    }
}
```

Cuando `meet_scheduling/.../appointment.py:on_submit` se ejecuta, Frappe dispara este hook después.

### Flujo del handler (`lex_app/lex_app/events/appointment.py:on_appointment_submit`)

1. Si la cita no tiene `calendar_resource` → return.
2. Carga `Calendar Resource`.
3. Si `calendar_resource.create_case_log` no existe o es falsy → return.
4. Si la cita no tiene `user_contact` → log warning y return.
5. Crea `Case Log` con:
   - `user_contact = appointment.user_contact`
   - `case_title = "Case from appointment: {appointment.name}"`
   - `case_type = "Consultation"`
   - `legal_area = "Other"`
   - `status = "New"`
   - `priority = "Medium"`
   - `start_date = today()`
   - `source_appointment = appointment.name` (Link back).
   - `assigned_lawyer = _get_assigned_lawyer(...)` (usa `Lawyer Availability` para asignación equitativa con filtrado por horario).
   - `user_context = appointment.appointment_context` (si existe).
6. Agrega un `important_dates` con el horario de la cita y `meeting_url` como location.
7. `case_log.insert(ignore_permissions=True)`.
8. Si falla → log_error y **`frappe.throw`** (aborta el submit del Appointment).

> **Importante**: si la creación del `Case Log` falla, **la cita NO se confirma**. Esto se debe a que `frappe.throw` propaga la excepción y Frappe rollbackea la transacción.

---

## 2. Custom field `Calendar Resource.create_case_log`

Agregado por `lex_app/install.py` (crea el field si no existe) y declarado en `lex_app/fixtures/custom_field.json`.

| Atributo | Valor |
|---|---|
| `dt` | `Calendar Resource` |
| `fieldname` | `create_case_log` |
| `fieldtype` | `Check` |
| `label` | `Create Case Log on Appointment` |
| `module` | `Lex App` |

Cuando está marcado en un `Calendar Resource`:
- Todas las citas confirmadas para ese recurso generan automáticamente un `Case Log`.
- El email de confirmación se enriquece con datos del caso (ver hooks abajo).
- Si el recurso aparece en una fila de `Lawyer Availability.resources`, no debería tener este flag desactivado (`lex_app/lawyer_availability.py:173` emite warning).

> Desde `meet_scheduling`, este campo se consulta vía `getattr(calendar_resource, "create_case_log", False)` para no fallar si lex_app no está instalado.

---

## 3. Hook `appointment_email_context` (enriquece el email)

Implementación en `lex_app/lex_app/events/appointment.py:get_appointment_email_context`:

```python
def get_appointment_email_context(appointment_doc) -> dict:
    calendar_resource = frappe.get_doc("Calendar Resource", appointment_doc.calendar_resource)
    if not getattr(calendar_resource, "create_case_log", False):
        return {}

    case_log_name = frappe.db.get_value(
        "Case Log", {"source_appointment": appointment_doc.name}, "name"
    )
    if not case_log_name:
        return {}

    case_log = frappe.get_doc("Case Log", case_log_name)
    assigned_lawyer_name = None
    if case_log.assigned_lawyer:
        assigned_lawyer_name = frappe.db.get_value(
            "User", case_log.assigned_lawyer, "full_name"
        ) or case_log.assigned_lawyer

    return {
        "case_log_name": case_log.name,
        "case_log_title": case_log.case_title,
        "assigned_lawyer_name": assigned_lawyer_name,
        "case_log_url": f"{get_url()}/app/case-log/{case_log.name}",
    }
```

El dict retornado se mergea al `context` del template Jinja en `notifications/appointment.py:98-107`. El template `appointment_confirmed.html` ya tiene un bloque amarillo (`{% if case_log_name %}` en línea 151) que renderiza estos campos.

---

## 4. Hook `appointment_email_recipients`

Agrega:
- El `assigned_lawyer` del `Case Log`.
- El `lawyer_supervisor` del `Lawyer Availability` correspondiente.

Estos emails se agregan a la lista base de destinatarios (que viene de `Calendar Resource.notification_users`).

---

## 5. Lawyer Availability y conflictos

`lex_app` tiene un DocType `Lawyer Availability` que mapea abogados → calendar resources → horarios. Cuando un `Case Log` se crea, se asigna un abogado usando esta tabla.

- **Filtrado por horario**: `Lawyer Availability` define en qué slots cada abogado está disponible.
- **Conflictos con Appointment Confirmed**: `LawyerAvailability._has_conflicting_appointment` (en `lex_app`) hace un JOIN entre `Case Log` y `Appointment` para detectar conflictos del mismo abogado en otra cita confirmada.

> Desde `meet_scheduling` esto es transparente: el flujo `on_submit` simplemente crea el `Case Log` y lex_app maneja la asignación.

---

## Diagrama de secuencia simplificado

```
Usuario web              meet_scheduling.api        Appointment.on_submit       lex_app
   │                          │                            │                       │
   ├─ POST create_and_confirm ►                            │                       │
   │                          │                            │                       │
   │                          ├─ appointment.insert()      │                       │
   │                          ├─ appointment.submit() ───► │                       │
   │                          │                            ├─ valid + create meet  │
   │                          │                            │  meeting (mock)       │
   │                          │                            ├─ doc_events.on_submit ►
   │                          │                            │                       ├─ Case Log creado
   │                          │                            │                       │  assigned_lawyer
   │                          │                            ◄────────────────────── ┤
   │                          │                            ├─ enqueue_email (after commit)
   │                          ◄────────────────────────────┤                       │
   ◄────────────────────────  ┤                            │                       │
                                                          [commit]
                                                              ▼
                                                    send_appointment_notification (job)
                                                              │
                                                              ├─ get_hooks(appointment_email_context)
                                                              │   → lex_app.get_appointment_email_context()
                                                              │     retorna case_log_*
                                                              ├─ get_hooks(appointment_email_recipients)
                                                              │   → agrega lawyer + supervisor
                                                              └─ send_email("appointment_confirmed", ctx)
```

---

## Cómo testear

1. Instalar `meet_scheduling` y `lex_app` en el bench.
2. Asegurar `lex_app/install.py` corrió (crea custom field `create_case_log`).
3. Crear un `Calendar Resource` con `create_case_log = 1`.
4. Crear un `User contact` y un token.
5. POST a `create_and_confirm_appointment` con el token.
6. Verificar:
   - Se creó el `Appointment` en `Confirmed`.
   - Se creó un `Case Log` con `source_appointment = APT-...`.
   - El `Case Log.assigned_lawyer` está poblado (vía `Lawyer Availability` o fallback).
7. Si `send_email_notification = 1`, esperar el job de cola y verificar que llegó el email con el bloque "Caso Legal Creado Automáticamente".

---

## Bugs / deuda técnica observados

1. **Inconsistencia DocType `User Contact` / `User contact`**: lex_app usa indistintamente. Frappe lo tolera pero podría romper en consultas case-sensitive.
2. **`frappe.throw` en handler aborta submit**: si el `Case Log` falla por cualquier motivo, el usuario no puede agendar. Esto podría suavizarse (log_error + msgprint, sin throw).
3. **Dependencia circular potencial**: `lex_app` depende de `meet_scheduling` para el DocType `Appointment`; pero `meet_scheduling` no debería conocer `lex_app`. Los hooks extensibles resuelven esto, pero hay que asegurar que `meet_scheduling/hooks.py` nunca importe nada de lex_app.
