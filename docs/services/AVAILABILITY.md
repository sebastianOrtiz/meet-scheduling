# Service: Availability (`scheduling/availability.py`)

Servicio que calcula la **disponibilidad efectiva** de un `Calendar Resource` para un día o rango, combinando el `Availability Plan` semanal con las `Calendar Exception` por fecha y respetando la zona horaria del recurso.

- **Archivo**: `meet_scheduling/meet_scheduling/scheduling/availability.py`
- **Importaciones**: `frappe`, `pytz`, `datetime`.

---

## Funciones públicas

### `get_availability_slots_for_day(calendar_resource, target_date) -> List[Dict[str, datetime]]`

`availability.py:39-169`. Retorna los intervalos disponibles para un día concreto.

**Args**:
- `calendar_resource` — `str` (name) o el doc.
- `target_date` — `date` o `str` (`YYYY-MM-DD`).

**Returns**:

```python
[
    {"start": datetime(aware), "end": datetime(aware)},
    {"start": datetime(aware), "end": datetime(aware)},
    ...
]
```

Los `datetime` son **aware** (con tzinfo del Calendar Resource).

**Algoritmo**:

1. Resuelve el resource (`str` → `get_doc`).
2. Si `is_active = 0`, retorna `[]`.
3. Si no hay `availability_plan`, log_error y `[]`.
4. Si el plan no está activo o la fecha está fuera de su `valid_from`/`valid_to`, retorna `[]`.
5. Resuelve timezone (default `UTC` si inválida, soporta valor especial `"system timezone"`).
6. Obtiene `weekday_name = target_date.strftime("%A")` (inglés).
7. Itera los slots del plan filtrando por `weekday`. Por cada match:
   - Convierte `start_time`/`end_time` a `datetime.time` con `_to_time`.
   - Combina con `target_date` → `datetime` naive.
   - Localiza con `tz.localize(...)` → aware.
   - Agrega a `base_intervals`.
8. Aplica excepciones con `_apply_exceptions`.
9. Hace merge con `_merge_intervals`.
10. Retorna ordenado por `start`.

### `get_effective_availability(calendar_resource, start_date, end_date) -> Dict[str, List[Dict]]`

`availability.py:172-207`. Llama `get_availability_slots_for_day` para cada día en el rango y retorna un dict por fecha (solo días con disponibilidad).

```python
{
    "2026-01-15": [{"start": dt, "end": dt}, ...],
    "2026-01-16": [...],
}
```

---

## Funciones privadas

### `_to_time(time_value) -> time`

`availability.py:18-36`. Convierte distintos tipos a `datetime.time`:

| Input | Resultado |
|---|---|
| `time` | tal cual |
| `timedelta` (común de MariaDB) | `(datetime.min + tdelta).time()` |
| `str` | `frappe.utils.get_time(str)` |
| otro | `ValueError` |

### `_apply_exceptions(intervals, calendar_resource, target_date, tz) -> List[Dict]`

`availability.py:210-294`. Consulta `Calendar Exception` para el resource y la fecha. Por cada excepción:

- **`Closed` con tiempos** → resta el rango con `_interval_subtract`.
- **`Closed` sin tiempos** → `intervals = []` (cierra todo el día).
- **`Blocked` con tiempos** → resta el rango.
- **`Blocked` sin tiempos** → no hace nada (deuda técnica).
- **`Extra Availability` con tiempos** → agrega un intervalo nuevo.

### `_merge_intervals(intervals) -> List[Dict]`

`availability.py:297-327`. Ordena por `start` y recorre uniendo si `current["start"] <= last["end"]`.

### `_interval_subtract(interval, block) -> List[Dict]`

`availability.py:330-377`. Resta un bloque de un intervalo. Casos:

| Caso | Resultado |
|---|---|
| No overlap | `[interval]` |
| Block cubre todo | `[]` |
| Block cubre parte inicial | `[parte final]` |
| Block cubre parte final | `[parte inicial]` |
| Block en medio (split) | `[parte inicial, parte final]` |

---

## Ejemplo de uso

```python
from datetime import date
from meet_scheduling.meet_scheduling.scheduling.availability import (
    get_availability_slots_for_day,
    get_effective_availability,
)

# Un día
slots = get_availability_slots_for_day("Dr. Juan Pérez", date(2026, 1, 20))
# [
#   {"start": datetime(2026, 1, 20, 8, 0, tzinfo=<Bogota>), "end": datetime(2026, 1, 20, 12, 0, tzinfo=<Bogota>)},
#   {"start": datetime(2026, 1, 20, 14, 0, tzinfo=<Bogota>), "end": datetime(2026, 1, 20, 18, 0, tzinfo=<Bogota>)},
# ]

# Un rango
avail = get_effective_availability("Dr. Juan Pérez", "2026-01-20", "2026-01-27")
# {"2026-01-20": [...], "2026-01-21": [...], ...}
```

---

## Consumidores

- `Appointment._validate_availability_strict` (`appointment.py:261-315`) — valida en `on_submit` que la cita cae dentro de algún slot disponible.
- `scheduling/slots.py:generate_available_slots` — usa `get_effective_availability` para generar slots discretos.
- `api/appointments/endpoints.py:validate_appointment` — usa `get_availability_slots_for_day` para validar antes de submit.

---

## Performance / caché

- **No hay caché**: cada llamada hace queries a `Calendar Resource`, `Availability Plan`, `Availability Slot` (child) y `Calendar Exception`.
- Para rangos amplios (`get_effective_availability` con muchos días), se hace una query de excepciones por día. Posible optimización: una sola query con `date in [...]`.
- `frappe.get_doc` no usa caché por defecto; sería bueno usar `frappe.get_cached_doc` para `Calendar Resource` y `Availability Plan`.

---

## Deuda técnica

1. **`Blocked` sin tiempos no hace nada**: debería ser equivalente a `Closed` todo el día o error de validación.
2. **No usa `frappe.get_cached_doc`** para datos que rara vez cambian.
3. **No hay batch query** para excepciones en un rango.
4. **Tests específicos**: hay `test_appointment.py`, pero no se ven tests dedicados de `availability.py` aislados.
