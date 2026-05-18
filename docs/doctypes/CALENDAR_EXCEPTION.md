# DocType: Calendar Exception

Override de disponibilidad para fechas específicas. Permite cerrar, bloquear o agregar disponibilidad fuera del `Availability Plan` semanal.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/calendar_exception/calendar_exception.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/calendar_exception/calendar_exception.py`
- **Naming rule**: `Expression` → `format:{calendar_resource}-EXCEPTION-{#}` (ej. `Dr. Juan Pérez-EXCEPTION-1`).

---

## Propósito y casos de uso

- **Cerrar un día festivo**: tipo `Closed`, sin `start_time`/`end_time`.
- **Bloquear un rango horario puntual** (ej. junta interna 10:00-11:00): tipo `Blocked` con `start_time`/`end_time`.
- **Agregar disponibilidad extraordinaria** (ej. sábado puntual): tipo `Extra Availability` con `start_time`/`end_time` (ambos requeridos).

---

## Campos

Orden según `field_order` (`calendar_exception.json:8-15`).

| Fieldname | Tipo | Default | Descripción |
|---|---|---|---|
| `calendar_resource` | Link → `Calendar Resource` | — | Recurso al que aplica la excepción. Requerido (validado por controller). |
| `exception_type` | Select | `Blocked` | Opciones: `Closed`, `Blocked`, `Extra Availability`. |
| `date` | Date | — | Fecha afectada. Requerida. |
| `start_time` | Time | — | Inicio del bloqueo/extra. Opcional para `Closed` (sin esto, cierra todo el día). |
| `end_time` | Time | — | Fin del bloqueo/extra. Validado `> start_time` si ambos están seteados. |
| `reason` | Small Text | — | Motivo (ej. "Junta médica", "Festivo nacional"). Informativo. |

---

## Tipos de excepción

### `Closed`

- Si **no** tiene `start_time`/`end_time`: cierra todo el día. `availability.py:264` setea `intervals = []`.
- Si tiene `start_time`/`end_time`: cierra parcialmente ese rango (similar a `Blocked` pero semánticamente "cerrado"). `availability.py:247-261` resta ese rango de los intervalos base.

### `Blocked`

- Requiere `start_time` y `end_time` para tener efecto.
- Resta el rango bloqueado de los intervalos base usando `_interval_subtract` (`availability.py:266-280`).
- Diferencia con `Closed` parcial: solo se aplica si ambos tiempos están seteados; sin ellos, no tiene efecto.

### `Extra Availability`

- **Obligatoriamente** requiere `start_time` y `end_time` (validado por `_validate_extra_availability`).
- Agrega un nuevo intervalo a la lista (`availability.py:282-292`).
- Útil para abrir un sábado o un horario fuera del plan habitual.

---

## Permisos por rol

Definidos en `calendar_exception.json:66-97`.

| Rol | Read | Write | Create | Delete |
|---|---|---|---|---|
| `System Manager` | yes | yes | yes | yes |
| `Meet Scheduling Manager` | yes | yes | yes | yes |
| `Appointment User` | yes (export, report) | no | no | no |

---

## Validaciones del controller (`calendar_exception.py`)

### `validate(self) -> None`

Ejecuta:

1. `_validate_required_fields` — `calendar_resource`, `exception_type`, `date` son requeridos (`calendar_exception.py:42-51`).
2. `_validate_times` — si ambos `start_time` y `end_time` están seteados, valida `start_time < end_time`.
3. `_validate_extra_availability` — si `exception_type == "Extra Availability"`, exige `start_time` y `end_time` (sin ellos no tiene sentido agregar disponibilidad).
4. `_check_duplicate_exceptions` — busca excepciones existentes para el mismo `calendar_resource` y `date`. Solo advierte (`msgprint indicator=orange`), no bloquea. Detalle:
   - Si es `Closed` sin horario y ya hay excepciones, avisa que cerrará todo el día sobre las existentes.
   - Si tiene `start_time`/`end_time`, verifica si solapa con alguna existente y advierte mostrando el rango.

### Helper `_to_time(time_value)`

Igual que en `AvailabilityPlan` — convierte `time`, `timedelta`, `str` a `datetime.time` (`calendar_exception.py:124-136`).

---

## Cómo se aplica al cálculo de disponibilidad

Ver `availability.py:210-294` (`_apply_exceptions`):

```python
exceptions = frappe.get_all(
    "Calendar Exception",
    filters={
        "calendar_resource": calendar_resource,
        "date": target_date
    },
    fields=["name", "exception_type", "start_time", "end_time", "reason"]
)
```

Por cada excepción:
- `Closed` → si tiene tiempos, resta del rango; sin tiempos, anula todo el día.
- `Blocked` → resta del rango (solo si tiene tiempos).
- `Extra Availability` → suma un nuevo intervalo.

Después se hace `_merge_intervals` para unir adyacencias/superposiciones (`availability.py:297-327`).

---

## Bugs / deuda técnica

1. **`Blocked` sin tiempos no hace nada**: si alguien crea un `Blocked` sin horario, simplemente se ignora. Podría lanzarse error de validación.
2. **Naming colision**: si se crea más de una excepción para el mismo recurso, el formato `{calendar_resource}-EXCEPTION-{#}` puede ser confuso (el `#` es contador global, no por recurso).
3. **No hay validación de overlap entre `Closed` y `Extra Availability`** del mismo día. Solo se advierte, no se bloquea.
4. **`date` no se valida como futura**: se puede crear una excepción para una fecha pasada (sin efecto, pero ruido en queries).
