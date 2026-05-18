# Service: Slots (`scheduling/slots.py`)

Servicio que genera **slots discretos** para mostrar en la UI, basándose en la disponibilidad efectiva y verificando overlap con citas existentes.

- **Archivo**: `meet_scheduling/meet_scheduling/scheduling/slots.py`
- **Tamaño**: 105 líneas.

---

## Función pública

### `generate_available_slots(calendar_resource, start_date, end_date) -> List[Dict]`

`slots.py:17-104`.

**Args**:
- `calendar_resource` — `str` (name).
- `start_date` — `date` o `str`.
- `end_date` — `date` o `str`.

**Returns**:

```python
[
    {
        "start": "2026-01-20 09:00:00",
        "end": "2026-01-20 09:30:00",
        "capacity_remaining": 1,
        "is_available": True
    },
    {
        "start": "2026-01-20 09:30:00",
        "end": "2026-01-20 10:00:00",
        "capacity_remaining": 0,
        "is_available": False
    },
    ...
]
```

**Algoritmo**:

1. Carga el `Calendar Resource`. Toma `slot_duration_minutes` (default 30) y `capacity` (default 1).
2. Llama `get_effective_availability(calendar_resource, start_date, end_date)` → dict por fecha.
3. Itera cada intervalo disponible:
   - `current_slot_start = interval.start`.
   - Mientras `current_slot_start < interval.end`:
     - `current_slot_end = current_slot_start + slot_duration`.
     - Si `current_slot_end > interval.end` → break (descarta el slot parcial).
     - Llama `check_overlap(resource, current_slot_start, current_slot_end)`.
     - Agrega slot con `capacity_remaining = overlap_result["capacity_available"]` y `is_available = capacity_remaining > 0`.
     - Avanza `current_slot_start = current_slot_end`.
4. Retorna la lista.

> Cada slot se persiste como string `"%Y-%m-%d %H:%M:%S"` (sin tzinfo en el string), pero el cálculo interno usa datetimes aware.

---

## Consumidores

- `api/appointments/endpoints.py:get_available_slots` — endpoint público.
- Componentes Angular `meet-scheduling-tool.component.ts` que pintan el calendario.

---

## Ejemplo de uso

```python
from datetime import date
from meet_scheduling.meet_scheduling.scheduling.slots import generate_available_slots

slots = generate_available_slots(
    "Dr. Juan Pérez",
    date(2026, 1, 20),
    date(2026, 1, 27)
)

for s in slots:
    print(s["start"], "→", s["end"], "(cap:", s["capacity_remaining"], ")")
```

---

## Performance

- **Llama a `check_overlap` por CADA slot**: una query a `Appointment` por slot. Para un mes con muchos slots puede ser costoso.
- **Posibles optimizaciones**:
  - Cargar TODOS los Appointments del rango en una sola query y hacer overlap en memoria.
  - Caché por `(calendar_resource, fecha)` invalidado al cambiar Appointments.

---

## Deuda técnica

1. **N+1 queries**: como se mencionó, una query de overlap por cada slot.
2. **Slots parciales descartados silenciosamente**: si el último slot del intervalo no entra completo, se pierde. Podría ser intencional pero falta documentar.
3. **Devuelve string en lugar de datetime aware**: el cliente debe re-parsear y asumir la timezone del Calendar Resource implícitamente.
