# Service: Tasks (`scheduling/tasks.py`)

Servicio con jobs programados (scheduler events). Actualmente solo contiene `cleanup_expired_drafts`.

- **Archivo**: `meet_scheduling/meet_scheduling/scheduling/tasks.py`
- **Tamaño**: 94 líneas.
- **Configurado en**: `hooks.py:185-191` (`scheduler_events.cron["*/15 * * * *"]`).

---

## Función pública

### `cleanup_expired_drafts() -> int`

`tasks.py:12-93`.

**Args**: ninguno.

**Returns**: cantidad de Drafts cancelados.

**Comportamiento**:

1. Lee `current_time = now_datetime()`.
2. Ejecuta SQL directo (no usa ORM):
   ```sql
   SELECT name, calendar_resource, start_datetime, end_datetime
   FROM `tabAppointment`
   WHERE status = 'Draft'
     AND docstatus = 0
     AND draft_expires_at IS NOT NULL
     AND draft_expires_at < %s
   ```
3. Para cada Draft expirado:
   - `frappe.get_doc("Appointment", name)`.
   - Verifica que `status == "Draft"` (por si cambió durante la query).
   - Cambia `status = "Cancelled"`.
   - Agrega comment automático: `f"Draft expirado automáticamente (expiró: {draft_expires_at})"`.
   - `save(ignore_permissions=True)`.
   - Increment counter.
4. Si hubo cancelaciones, log info.
5. `frappe.db.commit()`.
6. Retorna el counter.

**Manejo de errores**:
- Cada Draft está en try/except: si falla uno, se loggea y se continúa con los demás.

---

## Cómo se ejecuta

Registrado en `hooks.py:185-191`:

```python
scheduler_events = {
    "cron": {
        "*/15 * * * *": [  # Cada 15 minutos
            "meet_scheduling.meet_scheduling.scheduling.tasks.cleanup_expired_drafts"
        ]
    }
}
```

El scheduler de Frappe (que requiere `bench enable-scheduler` y un worker activo) ejecuta este job cada 15 minutos.

---

## Por qué existe

Cuando un usuario crea una cita en `Draft` (vía el flow web), el sistema marca `draft_expires_at = now() + draft_expiration_minutes` para bloquear el slot por un tiempo limitado (default 15 min). Si el usuario nunca confirma:

- El Draft sigue en DB.
- `check_overlap` lo ignora vía el filtro `draft_expires_at < now` (ver `overlap.py:80-89`), así que el slot YA está disponible.
- Pero el Draft sigue ocupando espacio y apareciendo en queries.

Este job los marca como `Cancelled` para limpiar el listado y mantener consistencia.

---

## ¿Por qué no usa `frappe.qb` o el ORM?

Usa SQL directo (`frappe.db.sql`) en lugar del ORM por:

1. Eficiencia (evita cargar docs completos solo para filtrar).
2. La query es trivial y no se beneficia del ORM.

Luego, en el loop, sí carga `frappe.get_doc` para usar `add_comment` y `save`. Híbrido.

---

## Drafts sin `draft_expires_at`

**No se procesan**. La query exige `draft_expires_at IS NOT NULL`. Esto significa que si un Draft se crea sin pasar por `_calculate_draft_expiration` (ej. desde el desk del admin), no será limpiado nunca.

> Deuda técnica: o se hace `draft_expires_at` obligatorio en `validate` para todos los Drafts, o el job procesa también los NULL con una política (ej. drafts > 24h).

---

## Diferencia entre "cancelar" y "eliminar"

El job hace `status = "Cancelled"` con `save`, no `submit_cancel` ni `delete_doc`. Esto significa:

- `docstatus` queda en `0` (sigue siendo Draft a nivel Frappe).
- Pero `status` (campo Select) queda en `Cancelled`.
- El Draft sigue existiendo en DB. No se elimina.
- En queries de UI (ej. `get_my_appointments` con `status=Confirmed`), no aparecerá.

Esto es ligeramente inconsistente con el flujo de cancelación de un Confirmed: ahí sí se hace `appointment.cancel()` que pone `docstatus=2`. Pero como el Draft no está submitted, no se puede "cancelar" en el sentido Frappe (solo eliminar).

---

## Performance

- Una sola query por ejecución.
- Loop con `get_doc` + `save` por cada Draft expirado. Si hay muchísimos, podría ser lento, pero típicamente son pocos.

---

## Deuda técnica

1. **Drafts sin `draft_expires_at` no se limpian nunca**.
2. **No hay job adicional** para limpiar Cancelled antiguos (data retention).
3. **No hay job de reminder previo al horario de la cita**: faltaría enviar email "tu cita es en 1 hora".
4. **No hay job de auto-completion**: una cita Confirmed que ya pasó se queda en `Confirmed`; nunca se marca `Completed` automáticamente.
