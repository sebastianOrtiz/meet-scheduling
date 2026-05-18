# API: Calendar Resources

La app `meet_scheduling` no tiene un módulo `api/calendar_resources/` separado. Los endpoints relacionados con recursos de calendario están dentro del módulo `api/appointments/endpoints.py` por simplicidad. Este documento enumera los endpoints que operan sobre `Calendar Resource`.

> **Ubicación de los endpoints**: `meet_scheduling/api/appointments/endpoints.py`.
> **Re-exports**: `meet_scheduling/api/appointments/__init__.py`.
> **Rutas públicas**: `meet_scheduling.api.appointments.<funcion>`.

---

## Endpoint: `get_active_calendar_resources`

```
GET /api/method/meet_scheduling.api.appointments.get_active_calendar_resources
```

- **Ubicación**: `endpoints.py:41-90`.
- **Auth**: guest (sin login).
- **Rate limit**: 30/min/IP.
- **Args**: ninguno.

**Filtro**: `is_active = 1`. Ordena por `resource_name asc`.

**Campos devueltos por recurso**:
- `name`
- `resource_name`
- `timezone`
- `slot_duration_minutes`
- `capacity`
- `draft_expiration_minutes`
- `availability_plan`
- `video_call_profile`

**No incluye**: custom fields como `create_case_log`, `create_logbook_entry`, `logbook_availability`, `send_email_notification`, `notification_users`. Si una app necesita conocerlos, debe hacer una consulta adicional.

**Ejemplo curl**:

```bash
curl -sS "https://nexora.com.co/api/method/meet_scheduling.api.appointments.get_active_calendar_resources"
```

**Ejemplo respuesta**:

```json
{
  "message": [
    {
      "name": "Dr. Juan Pérez",
      "resource_name": "Dr. Juan Pérez",
      "timezone": "America/Bogota",
      "slot_duration_minutes": 30,
      "capacity": 1,
      "draft_expiration_minutes": 15,
      "availability_plan": "Horario Consultorio 2026",
      "video_call_profile": "Google Meet - Consultas"
    },
    {
      "name": "Sala de Juntas",
      "resource_name": "Sala de Juntas",
      "timezone": "America/Bogota",
      "slot_duration_minutes": 60,
      "capacity": 1,
      "draft_expiration_minutes": 15,
      "availability_plan": "Horario Oficina",
      "video_call_profile": null
    }
  ]
}
```

---

## Endpoint: `get_available_slots`

Documentado en detalle en [APPOINTMENTS.md](APPOINTMENTS.md). Es el endpoint principal para "ver disponibilidad de un recurso" en un rango de fechas.

```
GET /api/method/meet_scheduling.api.appointments.get_available_slots?calendar_resource=...&from_date=...&to_date=...
```

- **Auth**: guest.
- **Rate limit**: 30/min/IP.
- **Internamente** llama a `scheduling.slots.generate_available_slots`, que a su vez usa `get_effective_availability` + `check_overlap`.

Retorna una lista de slots con `start`, `end`, `capacity_remaining`, `is_available`.

---

## ¿Endpoint para resource availability detallada por día?

**No existe**. Si se quiere agrupar los slots por día, se debe hacer del lado del cliente. Ver `meet-scheduling-tool.component.ts:127-150` que agrupa el resultado en un `Map<string, AvailableSlot[]>` para pintar el calendario.

---

## ¿Endpoint para obtener Calendar Exceptions?

**No existe en la API pública**. El frontend deduce los días bloqueados implícitamente mirando qué fechas no aparecen en `get_available_slots`.

Si se necesitara, sería razonable implementar:

```python
@frappe.whitelist(allow_guest=True, methods=['GET'])
def get_calendar_exceptions(calendar_resource: str, from_date: str, to_date: str):
    return frappe.get_all(
        "Calendar Exception",
        filters={
            "calendar_resource": calendar_resource,
            "date": ["between", [from_date, to_date]]
        },
        fields=["name", "exception_type", "date", "start_time", "end_time", "reason"]
    )
```

Es deuda técnica documentada.

---

## ¿Endpoint para crear/actualizar Calendar Resources?

**No vía API pública**. La gestión de `Calendar Resource`, `Availability Plan` y `Calendar Exception` se hace desde el Desk de Frappe (`/app/calendar-resource`, etc.) bajo los permisos del rol `Meet Scheduling Manager`.

---

## Deuda técnica

1. Falta un endpoint para listar `Calendar Exception` por rango.
2. Falta endpoint para listar `Availability Plan` o sus slots (para que el frontend pueda mostrar los horarios "normales" del recurso).
3. `get_active_calendar_resources` no devuelve metadata útil para la UI como horarios típicos, primera fecha disponible, etc. La UI tiene que pedir `get_available_slots` para cada recurso.
