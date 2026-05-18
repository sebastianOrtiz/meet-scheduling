# Feature: Lógica de disponibilidad

Documenta cómo se calcula la disponibilidad efectiva de un `Calendar Resource` para un día/rango, considerando:

- El `Availability Plan` semanal (`Availability Slot` por día de la semana).
- Las `Calendar Exception` por fecha específica (Closed / Blocked / Extra Availability).
- La zona horaria del recurso.
- Los `Appointment` existentes (Drafts no expirados + Confirmed) que ocupan capacidad.

Servicio principal: `meet_scheduling/meet_scheduling/scheduling/availability.py`.

---

## Visión general

```
+-------------------------+
|   Calendar Resource     |
|   (timezone, capacity)  |
+-----------+-------------+
            |
            v
+-------------------------+         +----------------------+
|   Availability Plan     |  -+-->  |  Availability Slot   |
|   (valid_from/to)       |   |     |  (weekday, start,    |
|                         |   |     |   end)               |
+-------------------------+   |     +----------------------+
            |                 |
            v                 |
+-------------------------+   |     +----------------------+
|  Calendar Exception     |  -+-->  |  Per-date overrides  |
|  (date, type, times)    |         |  Closed/Blocked/Extra|
+-------------------------+         +----------------------+
            |
            v
+----------------------------------------------------------+
| scheduling/availability.py::get_availability_slots_for_day |
| 1. Filtra plan por weekday → intervalos base              |
| 2. Aplica excepciones (resta o suma)                      |
| 3. Merge intervalos adyacentes/superpuestos               |
| 4. Retorna lista ordenada [{start, end}, ...]             |
+----------------------------------------------------------+
            |
            v
+----------------------------------------------------------+
| scheduling/slots.py::generate_available_slots             |
| Para cada intervalo, generar slots cada                  |
| slot_duration_minutes y verificar overlap con            |
| Appointments existentes (check_overlap)                  |
+----------------------------------------------------------+
            |
            v
   [{start, end, capacity_remaining, is_available}, ...]
```

---

## Función pivote: `get_availability_slots_for_day`

Ubicación: `scheduling/availability.py:39-169`.

Firma:

```python
def get_availability_slots_for_day(
    calendar_resource: Union[str, Any],
    target_date: Union[date, str]
) -> List[Dict[str, datetime]]:
```

### Pasos del algoritmo

1. **Resolver el Calendar Resource** (acepta string o doc).
2. **Verificar `is_active`** — si no, retorna `[]`.
3. **Verificar `availability_plan`** — sin él, log_error y retorna `[]`.
4. **Verificar `plan.is_active`** y vigencia (`valid_from <= target_date <= valid_to`).
5. **Resolver timezone** del resource. Si es `"system timezone"`, usa la del sitio. Si es inválida, cae a UTC con log_error.
6. **Obtener weekday en inglés**: `target_date.strftime("%A")` → `Monday`, `Tuesday`, etc.
7. **Filtrar slots del plan** por `weekday == weekday_name`.
8. **Para cada slot match**:
   - Convertir `start_time`/`end_time` a `datetime.time` con helper `_to_time`.
   - Combinar con `target_date` → `datetime` naive.
   - Localizar con `tz.localize(...)` (vuelve aware).
   - Agregar a `base_intervals`.
9. **Aplicar excepciones** vía `_apply_exceptions`.
10. **Merge intervalos** vía `_merge_intervals` (ordena, une adyacentes/superpuestos).
11. **Retornar ordenado por start**.

### Helper `_to_time(time_value)`

`availability.py:18-36`. Convierte:
- `time` → tal cual.
- `timedelta` (común de MariaDB) → `(datetime.min + tdelta).time()`.
- `str` → `frappe.utils.get_time(str)`.

---

## Aplicación de excepciones (`_apply_exceptions`)

Ubicación: `availability.py:210-294`.

Consulta `Calendar Exception` filtrando por `calendar_resource` y `date`. Por cada excepción:

| `exception_type` | Con tiempos | Sin tiempos |
|---|---|---|
| `Closed` | Resta el rango de cada intervalo base | `intervals = []` (cierra todo el día) |
| `Blocked` | Resta el rango | No tiene efecto |
| `Extra Availability` | Agrega como nuevo intervalo | No tiene efecto (validación previa lo bloquea) |

### `_interval_subtract(interval, block)`

`availability.py:330-377`. Casos:
1. Sin overlap → retorna el intervalo original.
2. Block cubre todo → `[]`.
3. Block cubre parte inicial → un intervalo recortado al final.
4. Block cubre parte final → un intervalo recortado al inicio.
5. Block en medio → dos intervalos (split).

### `_merge_intervals(intervals)`

`availability.py:297-327`. Ordena por start, recorre y une si `current.start <= last_merged.end` (adyacentes o superpuestos).

---

## Generación de slots discretos para UI

Servicio: `scheduling/slots.py`. Función pública: `generate_available_slots`.

`slots.py:17-104`:

```python
def generate_available_slots(calendar_resource, start_date, end_date):
    resource = frappe.get_doc("Calendar Resource", calendar_resource)
    slot_duration_minutes = resource.slot_duration_minutes or 30

    availability_intervals = get_effective_availability(
        calendar_resource, start_date, end_date
    )

    slots = []
    for date_intervals in availability_intervals.values():
        for interval in date_intervals:
            current_slot_start = interval["start"]
            while current_slot_start < interval["end"]:
                current_slot_end = current_slot_start + timedelta(minutes=slot_duration_minutes)
                if current_slot_end > interval["end"]:
                    break

                overlap_result = check_overlap(
                    calendar_resource,
                    current_slot_start,
                    current_slot_end,
                    exclude_appointment=None
                )

                slots.append({
                    "start": current_slot_start.strftime("%Y-%m-%d %H:%M:%S"),
                    "end": current_slot_end.strftime("%Y-%m-%d %H:%M:%S"),
                    "capacity_remaining": overlap_result["capacity_available"],
                    "is_available": overlap_result["capacity_available"] > 0,
                })
                current_slot_start = current_slot_end

    return slots
```

Cada slot duración fija (`slot_duration_minutes`). Si el último slot no entra completo, se descarta. El `check_overlap` consulta `Appointment` existentes para calcular `capacity_remaining`.

---

## Detección de conflictos con citas existentes

Servicio: `scheduling/overlap.py`. Función pública: `check_overlap`.

`overlap.py:17-107`.

### Condición de overlap

Dos rangos `[A.start, A.end)` y `[B.start, B.end)` se solapan si:

```
A.start < B.end AND A.end > B.start
```

Aplicado a la query:

```python
filters = {
    "calendar_resource": calendar_resource,
    "status": ["in", ["Draft", "Confirmed"]],
    "start_datetime": ["<", end_datetime],
    "end_datetime": [">", start_datetime]
}
```

### Filtrado de Drafts expirados

`overlap.py:78-91`:

```python
for appt in appointments:
    if appt.status == "Draft":
        if appt.draft_expires_at:
            expires_at = get_datetime(appt.draft_expires_at)
            if expires_at < current_time:
                continue  # ignore expired
    active_appointments.append(appt.name)
```

Los Drafts vencidos no cuentan para el conflicto. Eventualmente son cancelados por el cron `cleanup_expired_drafts` (cada 15 min).

### Resultado

```python
return {
    "has_overlap": bool,
    "overlapping_appointments": [list of names],
    "capacity_exceeded": bool,           # overlap_count >= capacity
    "capacity_used": int,
    "capacity_available": int            # max(0, capacity - overlap_count)
}
```

---

## Filtrado por día de la semana

Ya está integrado en `get_availability_slots_for_day` paso 7: `target_date.strftime("%A")` produce el weekday en inglés (`Monday`...`Sunday`). Los slots del plan tienen el mismo formato en su Select.

Si el target_date cae en un día sin slots configurados, retorna `[]` (no hay disponibilidad).

---

## Manejo de zonas horarias

- `Calendar Resource.timezone` (default `America/Bogota`).
- `pytz.timezone(tz_name)` se usa para localizar.
- Si el `target_date` es naive, `tz.localize` lo convierte en aware.
- En `Appointment._validate_availability_strict` (`appointment.py:294-304`) también se localiza `start_datetime` y `end_datetime` al tz del recurso antes de comparar.

> Caveat: si la cita cruza medianoche o hay cambio de horario (DST), el cálculo puede tener efectos sutiles. No hay tests específicos de DST en el repositorio.

---

## Casos borde a tener en cuenta

| Caso | Comportamiento |
|---|---|
| `is_active = 0` en Resource | Retorna `[]` siempre. |
| Plan inactivo o sin slots ese weekday | Retorna `[]`. |
| Fecha fuera de `valid_from`/`valid_to` del plan | Retorna `[]`. |
| `Closed` todo el día | Borra todos los intervalos. |
| `Closed` parcial | Resta el rango (puede splittear un intervalo en dos). |
| `Blocked` sin tiempos | **No hace nada** (deuda técnica). |
| `Extra Availability` | Agrega un nuevo intervalo (no hace merge automático con base, pero `_merge_intervals` lo unifica si es adyacente). |
| `Draft` activo bloquea capacidad | Sí, hasta `draft_expires_at`. |
| `Draft` expirado | No bloquea (filtrado en `check_overlap`). |
| `capacity > 1` | Permite N overlaps; el slot se vuelve `is_available=false` solo cuando `capacity_used >= capacity`. |
| Slot que no entra completo en el intervalo | Se descarta (no se genera slot parcial). |
| Slot granularity no múltiplo (en validación de Appointment) | Solo warning, no bloquea. |

---

## Deuda técnica

1. **`Blocked` sin tiempos no hace nada**: debería ser un error de validación o equivalente a `Closed` todo el día.
2. **`capacity` por `Availability Slot` no se aplica**: el servicio usa solo `Calendar Resource.capacity`.
3. **No hay caché**: cada llamada a `get_available_slots` recalcula desde DB. Para portales con tráfico alto convendría caché por (resource, date, hash de excepciones).
4. **DST y cambios de hora**: no hay tests.
