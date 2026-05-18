# Esquema de horarios: Availability Plan + Availability Slot

> Aclaración terminológica: en el repositorio NO existe un DocType llamado `Calendar Resource Schedule`. La "tabla de horarios" del recurso se modela combinando dos DocTypes:
>
> - **`Availability Plan`** — el plan semanal (parent).
> - **`Availability Slot`** — la franja horaria por día (child table dentro del plan).
>
> Este documento describe el child DocType `Availability Slot` y cómo encaja con `Availability Plan`. Si se busca el plan completo, ver [AVAILABILITY_PLAN.md](AVAILABILITY_PLAN.md).

---

## DocType (child): `Availability Slot`

Child table que vive dentro de `Availability Plan.availability_slots`. Cada fila representa una franja horaria abierta en un día específico de la semana.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/availability_slot/availability_slot.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/availability_slot/availability_slot.py` (clase `AvailabilitySlot(Document)` con `pass`).
- **Es child table**: `istable: 1`.
- **Editable grid**: `editable_grid: 1`.

---

## Campos

Orden según `field_order` (`availability_slot.json:8-14`).

| Fieldname | Tipo | Default | Options / Opciones | in_list_view | Descripción |
|---|---|---|---|---|---|
| `weekday` | Select | `Monday` | `Monday`, `Tuesday`, `Wednesday`, `Thursday`, `Friday`, `Saturday`, `Sunday` | yes | Día de la semana en inglés (debe coincidir con `target_date.strftime("%A")`). |
| `start_time` | Time | — | — | yes | Hora inicial disponible (ej. `08:00:00`). |
| `end_time` | Time | — | — | yes | Hora final disponible (ej. `12:00:00`). Validado `> start_time` por `AvailabilityPlan._validate_slots_times`. |
| `capacity` | Int | — | — | yes | Cupos simultáneos para esta franja. **Nota**: el servicio `availability.py` actualmente NO usa este campo; la capacidad efectiva la toma de `Calendar Resource.capacity`. Deuda técnica. |
| `location` | Data | — | — | yes | Ubicación/sede de la franja (ej. "Consultorio Palermo"). No usado por el servicio de disponibilidad; solo informativo. |

---

## Permisos

No declara permisos propios (campo `permissions: []`). Hereda del padre `Availability Plan`.

---

## Validaciones (heredadas del padre)

Las validaciones del child se ejecutan dentro del `validate` de `Availability Plan`:

1. `weekday`, `start_time`, `end_time` requeridos.
2. `start_time < end_time`.
3. `capacity > 0` si está seteado.
4. No solapes entre slots del mismo `weekday`.

Ver `availability_plan.py:60-135`.

---

## Ejemplo de uso

```python
plan = frappe.get_doc({
    "doctype": "Availability Plan",
    "plan_name": "Horario Consultorio 2026",
    "is_active": 1,
    "valid_from": "2026-01-01",
    "valid_to": "2026-12-31",
    "availability_slots": [
        {"weekday": "Monday",    "start_time": "08:00:00", "end_time": "12:00:00"},
        {"weekday": "Monday",    "start_time": "14:00:00", "end_time": "18:00:00"},
        {"weekday": "Tuesday",   "start_time": "08:00:00", "end_time": "12:00:00"},
        {"weekday": "Wednesday", "start_time": "08:00:00", "end_time": "12:00:00"},
        {"weekday": "Thursday",  "start_time": "08:00:00", "end_time": "12:00:00"},
        {"weekday": "Friday",    "start_time": "08:00:00", "end_time": "16:00:00"},
    ],
})
plan.insert()
```

Luego en un `Calendar Resource`:

```python
resource = frappe.get_doc({
    "doctype": "Calendar Resource",
    "resource_name": "Dr. Juan Pérez",
    "timezone": "America/Bogota",
    "is_active": 1,
    "slot_duration_minutes": 30,
    "capacity": 1,
    "draft_expiration_minutes": 15,
    "availability_plan": "Horario Consultorio 2026",
})
resource.insert()
```

---

## Lectura del slot desde el servicio

El servicio `availability.py:121-154` itera la child table del plan:

```python
if hasattr(plan, 'availability_slots'):
    slots = plan.availability_slots
elif hasattr(plan, 'slots'):
    slots = plan.slots
else:
    slots = frappe.get_all(
        "Availability Slot",
        filters={"parent": plan.name, "parenttype": "Availability Plan"},
        fields=["weekday", "start_time", "end_time"]
    )
```

Esto provee tres rutas: leer la child directa, leer un atributo legacy `slots`, o consultar directamente la tabla. Solo se leen `weekday`, `start_time`, `end_time` (NO se lee `capacity` ni `location`).

---

## Bugs / deuda técnica

1. **`capacity` por slot existe pero no se usa**: el servicio de disponibilidad ignora este campo. La capacidad efectiva siempre viene de `Calendar Resource.capacity`. O se elimina el campo o se implementa.
2. **`location` por slot no se propaga al `Appointment`**: si una franja matutina es en una sede y la vespertina en otra, esa información se pierde.
