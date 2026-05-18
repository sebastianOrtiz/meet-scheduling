# DocType: Availability Plan

Plantilla semanal reutilizable de disponibilidad. Define qué franjas horarias están abiertas por día de la semana. Un mismo plan puede asignarse a múltiples `Calendar Resource`.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/availability_plan/availability_plan.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/availability_plan/availability_plan.py`
- **Naming rule**: `By fieldname` → `plan_name`.

---

## Propósito y casos de uso

- Definir un horario semanal reutilizable (ej. "Horario Consultorio 2026", "Atención lunes a viernes 9-17").
- Una organización puede crear un único plan y reusarlo en varios `Calendar Resource`.
- Las `Calendar Exception` overridean este plan en fechas específicas.

---

## Campos

Orden según `field_order` (`availability_plan.json:8-15`).

| Fieldname | Tipo | Default | Unique | Descripción |
|---|---|---|---|---|
| `plan_name` | Data | — | yes | Nombre del plan. Es el `name` del documento. |
| `is_active` | Check | `1` | — | Si está desactivado, `get_availability_slots_for_day` retorna lista vacía (`availability.py:91-92`). |
| `valid_from` | Date | — | — | Inicio de vigencia (inclusive). Si está seteado y la fecha consultada < `valid_from`, retorna vacío (`availability.py:95-96`). |
| `valid_to` | Date | — | — | Fin de vigencia (inclusive). Si está seteado y la fecha consultada > `valid_to`, retorna vacío (`availability.py:97-98`). |
| `notes` | Small Text | — | — | Notas internas. |
| `availability_slots` | Table → `Availability Slot` | — | — | Child table con las franjas por día de la semana. |

---

## Permisos por rol

Definidos en `availability_plan.json:65-96`.

| Rol | Read | Write | Create | Delete |
|---|---|---|---|---|
| `System Manager` | yes | yes | yes | yes |
| `Meet Scheduling Manager` | yes | yes | yes | yes |
| `Appointment User` | yes (export, report) | no | no | no |

---

## Validaciones del controller (`availability_plan.py`)

### `validate(self) -> None`

Ejecuta:

1. `_validate_plan_name` — `plan_name` requerido (`availability_plan.py:41-44`).
2. `_validate_validity_dates` — `valid_from <= valid_to` si ambos están seteados (`availability_plan.py:46-53`).
3. `_validate_slots_exist` — debe haber al menos un slot (`availability_plan.py:55-58`).
4. `_validate_slots_times` — por cada slot:
   - `weekday` requerido.
   - `start_time` requerido.
   - `end_time` requerido.
   - `start_time < end_time` (error con mensaje "Fila N (Weekday): Start Time HH:MM debe ser menor que End Time HH:MM").
   - Si `capacity` está seteado, debe ser > 0.
5. `_validate_no_overlapping_slots` — no permite slots solapados en el mismo día. Ordena por `start_time` y compara pares consecutivos. Error con detalle de las dos filas en conflicto.

### Helper `_to_time(time_value)`

Convierte `time`, `timedelta` (común desde MariaDB) o `str` a `datetime.time`. Implementación en `availability_plan.py:137-157`.

---

## Algoritmo: cómo el plan se traduce en slots concretos

Ver [features/AVAILABILITY_LOGIC.md](../features/AVAILABILITY_LOGIC.md) y [services/AVAILABILITY.md](../services/AVAILABILITY.md). Resumen:

1. Dado un `Calendar Resource` y una fecha objetivo.
2. Obtener `weekday` de la fecha en inglés (`"%A"` → `Monday`, `Tuesday`, etc.).
3. Filtrar `availability_slots` por `weekday == weekday_name`.
4. Para cada slot match, combinar `start_time` y `end_time` con la fecha objetivo y la zona horaria del recurso.
5. Aplicar `Calendar Exception` (Closed / Blocked / Extra Availability).
6. Merge intervals adyacentes/superpuestos.
7. Retornar lista ordenada.

---

## Bugs / deuda técnica

1. **`plan_name` no tiene `reqd: 1` en JSON** (solo `unique: 1`), pero el controller lo valida en `_validate_plan_name`. Inconsistencia menor.
2. **`weekday` en `Availability Slot` no se valida contra Select**: si alguien inserta vía Script Report un valor distinto, no se filtra (depende del `strftime("%A")` en inglés).
3. **`capacity` y `location` por slot existen** pero el servicio `availability.py` no los usa (`get_availability_slots_for_day` solo lee `start_time`/`end_time`). La capacidad final se toma del `Calendar Resource.capacity`. Posible deuda: implementar capacidad por slot.
