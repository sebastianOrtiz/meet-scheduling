# Service: Overlap (`scheduling/overlap.py`)

Servicio que detecta solapamientos (overlap) entre un rango horario candidato y los `Appointment` existentes en un `Calendar Resource`, respetando la `capacity` configurada.

- **Archivo**: `meet_scheduling/meet_scheduling/scheduling/overlap.py`
- **Tamaño**: 108 líneas.

---

## Función pública

### `check_overlap(calendar_resource, start_datetime, end_datetime, exclude_appointment=None) -> Dict`

`overlap.py:17-107`.

**Args**:
- `calendar_resource` — `str` (name).
- `start_datetime` — `datetime` (puede ser aware o naive).
- `end_datetime` — `datetime`.
- `exclude_appointment` — `str | None`. Si se especifica, ese Appointment se excluye del cómputo (útil para validar edición de una cita existente).

**Returns**:

```python
{
    "has_overlap": bool,
    "overlapping_appointments": List[str],   # names de citas en conflicto
    "capacity_exceeded": bool,                # overlap_count >= capacity
    "capacity_used": int,
    "capacity_available": int                 # max(0, capacity - overlap_count)
}
```

---

## Algoritmo

`overlap.py:53-107`.

1. **Obtener capacity**:
   ```python
   resource = frappe.get_doc("Calendar Resource", calendar_resource)
   capacity = resource.capacity or 1
   ```
2. **Query de Appointments candidatos** con condición de overlap:
   ```python
   filters = {
       "calendar_resource": calendar_resource,
       "status": ["in", ["Draft", "Confirmed"]],
       "start_datetime": ["<", end_datetime],
       "end_datetime": [">", start_datetime]
   }
   ```
   La condición `start < B.end AND end > B.start` es la fórmula estándar para detectar overlaps entre dos rangos `[start, end)`.

   Si `exclude_appointment` se especifica, se agrega `name != exclude_appointment`.

3. **Filtrar Drafts expirados**:
   ```python
   for appt in appointments:
       if appt.status == "Draft":
           if appt.draft_expires_at:
               if get_datetime(appt.draft_expires_at) < now_datetime():
                   continue  # ignorar draft vencido
       active_appointments.append(appt.name)
   ```
4. **Calcular métricas**:
   ```python
   overlap_count = len(active_appointments)
   has_overlap = overlap_count > 0
   capacity_exceeded = overlap_count >= capacity
   capacity_used = overlap_count
   capacity_available = max(0, capacity - overlap_count)
   ```
5. Retornar dict.

---

## Reglas de negocio implementadas

- **Drafts activos cuentan**: un usuario que está en proceso de agendar (Draft no expirado) bloquea el slot para otros usuarios.
- **Drafts expirados NO cuentan**: se ignoran del cómputo aunque sigan en DB hasta que `cleanup_expired_drafts` los cancele.
- **Confirmed siempre cuentan**: una cita confirmada bloquea el slot mientras esté Submitted.
- **Cancelled y otros estados NO cuentan**: solo `Draft` y `Confirmed` participan del status filter.
- **Capacity > 1**: permite N overlaps. `is_available` solo deviene `false` cuando `capacity_used >= capacity`.

---

## Consumidores

| Consumidor | Llamada |
|---|---|
| `Appointment._validate_overlaps_and_block_if_exceeded` | En `validate` — informa o bloquea según capacidad. |
| `Appointment._validate_overlaps_strict` | En `on_submit` — bloquea estrictamente. |
| `scheduling/slots.py:generate_available_slots` | Para cada slot, calcula `capacity_remaining`. |
| `api/appointments/endpoints.py:validate_appointment` | Endpoint de validación previa. |

---

## Ejemplo de uso

```python
from datetime import datetime
from meet_scheduling.meet_scheduling.scheduling.overlap import check_overlap

result = check_overlap(
    "Dr. Juan Pérez",
    datetime(2026, 1, 20, 10, 0),
    datetime(2026, 1, 20, 10, 30),
    exclude_appointment=None
)

if result["capacity_exceeded"]:
    print("No hay capacidad:", result["overlapping_appointments"])
else:
    print(f"Capacidad disponible: {result['capacity_available']}/{result['capacity_used'] + result['capacity_available']}")
```

---

## Performance

- Una sola query por llamada.
- Si `slots.py` lo llama N veces por mes, hay N queries totales (N+1 problem).

---

## Deuda técnica

1. **No considera capacity por `Availability Slot`**: solo usa `Calendar Resource.capacity` global. Si un slot del plan tuviera capacity diferente, no se aplicaría.
2. **No bloquea slot exact-match-overflow**: si capacity=2 y ya hay 2 citas, una tercera lanza error correcto. Si capacity=2 y hay 1 cita y se intenta crear otra, OK. Pero no hay lógica de "capacidad por minuto" (ej. en un café puede haber 50 personas concurrentes por minuto, lo cual nunca se modela aquí).
3. **`draft_expires_at` puede ser NULL**: un Draft sin `draft_expires_at` se trata como "no expirado" (siempre activo). Es decir, si un draft viejo sin fecha se queda en DB, sigue bloqueando indefinidamente. El cron `cleanup_expired_drafts` solo cancela los que tienen `draft_expires_at < now()`, así que los NULL no se limpian.
