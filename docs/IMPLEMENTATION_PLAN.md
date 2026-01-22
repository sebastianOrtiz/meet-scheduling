# Plan de Implementación - Meet Scheduling

**Fecha**: 2026-01-21
**Estado Actual**: DocTypes creados (solo estructura JSON), lógica pendiente

---

## Visión General

Este plan está diseñado para implementar la aplicación Meet Scheduling de manera incremental, probando cada componente antes de avanzar al siguiente. Se divide en 5 fases principales.

---

## Decisiones de Diseño Confirmadas ✅

### 1. Validación de Overlaps ✅
**Decisión**: Validar desde Draft con advertencias, bloquear fuerte al Submit

**Comportamiento**:
- En Draft: Mostrar advertencia (msgprint) si hay overlap
- En Submit: Bloquear (frappe.throw) si hay overlap

### 2. Estados que Bloquean Horarios ✅
**Decisión**: Draft y Confirmed bloquean, PERO Drafts expiran temporalmente

**Comportamiento**:
- Draft y Confirmed bloquean horarios según capacity
- Drafts tienen expiración configurable (default 15 minutos)
- Drafts expirados NO bloquean (se liberan automáticamente)
- Scheduled task limpia Drafts expirados cada 15 minutos

**Campos adicionales requeridos**:
- `Calendar Resource.draft_expiration_minutes` (Int, default 15)
- `Appointment.draft_expires_at` (Datetime, read-only, hidden)

### 3. Cambio de Hora con Meeting Creado ✅
**Decisión**: Depende del tipo de meeting

**Comportamiento**:
- **Meeting automático** (`meeting_status = "created"`): Cancelar viejo + crear nuevo
- **Meeting manual** (`manual_meeting_url`): Mantener enlace, solo advertir

**Lógica**:
- Detectar cambio en `start_datetime` o `end_datetime`
- Si es automático: llamar `_recreate_meeting()`
- Si es manual: solo msgprint informativo

### 4. Validación de Slot Duration ✅
**Decisión**: Validar con advertencia, permitir override

**Comportamiento**:
- Validar que duración sea múltiplo de `slot_duration_minutes`
- En Draft: Advertencia (msgprint)
- En Submit: Advertencia (permitir continuar por defecto)
- (Opcional) Agregar campo `enforce_slot_duration` para bloquear si se prefiere

---

## Fase 0: Preparación del Entorno

### Tarea 0.1: Agregar Campos Adicionales a DocTypes

Basado en las decisiones de diseño, agregar estos campos a los DocTypes.

#### 0.1.1 Actualizar Calendar Resource

**Vía Frappe UI**: Customize Form → Calendar Resource → Add Field

**Campo a agregar**:
```json
{
    "fieldname": "draft_expiration_minutes",
    "fieldtype": "Int",
    "label": "Draft Expiration (Minutes)",
    "description": "Tiempo en minutos antes de que un Draft expire y libere el horario. Default: 15 minutos",
    "default": "15",
    "insert_after": "capacity"
}
```

**Checklist**:
- [ ] Agregar campo `draft_expiration_minutes` a Calendar Resource
- [ ] Verificar default value = 15
- [ ] Migrar: `bench --site [site] migrate`

---

#### 0.1.2 Actualizar Appointment

**Vía Frappe UI**: Customize Form → Appointment → Add Field

**Campo a agregar**:
```json
{
    "fieldname": "draft_expires_at",
    "fieldtype": "Datetime",
    "label": "Draft Expires At",
    "description": "Momento en que este Draft expira y libera el horario",
    "read_only": 1,
    "hidden": 1,
    "insert_after": "status"
}
```

**Checklist**:
- [ ] Agregar campo `draft_expires_at` a Appointment
- [ ] Marcar como read_only y hidden
- [ ] Migrar: `bench --site [site] migrate`

---

### Tarea 0.2: Crear Estructura de Módulos
**Archivos a crear**:

```
meet_scheduling/meet_scheduling/
├── scheduling/
│   ├── __init__.py
│   ├── availability.py
│   ├── overlap.py
│   ├── slots.py
│   └── tasks.py          # ← NUEVO: para scheduled tasks
├── video_calls/
│   ├── __init__.py
│   ├── base.py
│   ├── factory.py
│   ├── google_meet.py
│   └── microsoft_teams.py
└── api/
    ├── __init__.py
    └── appointment_api.py
```

**Checklist**:
- [ ] Crear directorio `scheduling/` con `__init__.py`
- [ ] Crear directorio `video_calls/` con `__init__.py`
- [ ] Crear directorio `api/` con `__init__.py`
- [ ] Crear archivos vacíos con docstrings básicos
- [ ] Crear `scheduling/tasks.py` para scheduled tasks

---

### Tarea 0.3: Configurar Scheduled Task en hooks.py

**Archivo**: `meet_scheduling/meet_scheduling/hooks.py`

**Agregar**:
```python
# Scheduled Tasks
# ---------------

scheduler_events = {
    "cron": {
        "*/15 * * * *": [  # Cada 15 minutos
            "meet_scheduling.meet_scheduling.scheduling.tasks.cleanup_expired_drafts"
        ]
    }
}
```

**Checklist**:
- [ ] Descomentar sección `scheduler_events` en hooks.py
- [ ] Agregar cron job para `cleanup_expired_drafts`
- [ ] Verificar sintaxis

---

## Fase 1: Servicios de Scheduling (Core Business Logic)

**Objetivo**: Implementar la lógica de disponibilidad y solapamiento SIN tocar DocTypes todavía.

### Tarea 1.1: Implementar `scheduling/availability.py`

**Archivo**: `meet_scheduling/meet_scheduling/scheduling/availability.py`

**Funciones a implementar**:

#### 1.1.1 `get_availability_slots_for_day(calendar_resource, date)`
```python
def get_availability_slots_for_day(calendar_resource, date):
    """
    Obtiene slots de disponibilidad para un día específico.

    Args:
        calendar_resource: nombre del Calendar Resource o doc
        date: fecha (date object o string YYYY-MM-DD)

    Returns:
        list[dict]: [
            {"start": datetime, "end": datetime},
            ...
        ]

    Algoritmo:
        1. Obtener availability_plan del calendar_resource
        2. Obtener weekday del date (Monday, Tuesday, etc.)
        3. Obtener Availability Slots para ese weekday
        4. Convertir time slots a datetime con timezone del calendar_resource
        5. Aplicar excepciones (Closed, Blocked, Extra Availability)
        6. Merge intervalos adyacentes/overlapping
        7. Retornar lista ordenada
    """
```

**Dependencias**:
- Frappe ORM para consultar DocTypes
- Python `datetime`, `pytz` para manejo de timezones

**Tests a crear**:
- [ ] Test: día con slots normales (sin excepciones)
- [ ] Test: día con excepción Closed (todo el día)
- [ ] Test: día con excepción Blocked (parcial)
- [ ] Test: día con Extra Availability
- [ ] Test: día sin plan asignado
- [ ] Test: múltiples slots en el mismo día

---

#### 1.1.2 `get_effective_availability(calendar_resource, start_date, end_date)`
```python
def get_effective_availability(calendar_resource, start_date, end_date):
    """
    Obtiene disponibilidad efectiva para un rango de fechas.

    Args:
        calendar_resource: nombre del Calendar Resource
        start_date: fecha inicial
        end_date: fecha final

    Returns:
        dict: {
            "2026-01-15": [{"start": datetime, "end": datetime}, ...],
            "2026-01-16": [...],
            ...
        }
    """
```

**Dependencias**: `get_availability_slots_for_day()`

**Tests**:
- [ ] Test: rango de 7 días con diferentes configuraciones
- [ ] Test: rango cruzando fin de mes

---

#### 1.1.3 Funciones auxiliares

```python
def _apply_exceptions(intervals, calendar_resource, date):
    """Aplica excepciones (Closed/Blocked/Extra) a intervalos base."""

def _merge_intervals(intervals):
    """Une intervalos adyacentes o overlapping."""

def _interval_subtract(interval, block):
    """Resta un bloqueo de un intervalo."""
```

**Checklist**:
- [ ] Implementar `get_availability_slots_for_day()`
- [ ] Implementar `get_effective_availability()`
- [ ] Implementar funciones auxiliares
- [ ] Escribir unit tests
- [ ] Documentar con docstrings completos

---

### Tarea 1.2: Implementar `scheduling/overlap.py`

**Archivo**: `meet_scheduling/meet_scheduling/scheduling/overlap.py`

**Funciones a implementar**:

#### 1.2.1 `check_overlap(calendar_resource, start_datetime, end_datetime, exclude_appointment=None)`
```python
def check_overlap(calendar_resource, start_datetime, end_datetime, exclude_appointment=None):
    """
    Detecta overlaps con appointments existentes.

    Args:
        calendar_resource: nombre del Calendar Resource
        start_datetime: inicio del rango a validar
        end_datetime: fin del rango a validar
        exclude_appointment: nombre del Appointment a excluir (para ediciones)

    Returns:
        dict: {
            "has_overlap": bool,
            "overlapping_appointments": [list of appointment names],
            "capacity_exceeded": bool,
            "capacity_used": int,
            "capacity_available": int
        }

    Algoritmo:
        1. Obtener capacity del calendar_resource
        2. Consultar appointments con:
            - calendar_resource = X
            - status in ("Confirmed")  # según decisión
            - (start < end_datetime AND end > start_datetime)
            - name != exclude_appointment
        3. Contar overlaps
        4. Comparar con capacity
        5. Retornar resultado
    """
```

**Consulta SQL recomendada**:
```python
frappe.db.sql("""
    SELECT name, start_datetime, end_datetime, status
    FROM `tabAppointment`
    WHERE calendar_resource = %(resource)s
        AND status IN ('Confirmed')
        AND start_datetime < %(end)s
        AND end_datetime > %(start)s
        AND name != %(exclude)s
""", {
    "resource": calendar_resource,
    "start": start_datetime,
    "end": end_datetime,
    "exclude": exclude_appointment or ""
}, as_dict=True)
```

**Tests**:
- [ ] Test: capacity=1, sin overlap → OK
- [ ] Test: capacity=1, con overlap → FAIL
- [ ] Test: capacity=2, 1 overlap → OK
- [ ] Test: capacity=2, 2 overlaps → FAIL
- [ ] Test: exclude_appointment funciona correctamente
- [ ] Test: Draft appointments no bloquean (según decisión)

**Checklist**:
- [ ] Implementar `check_overlap()`
- [ ] Escribir tests unitarios
- [ ] Documentar edge cases

---

### Tarea 1.3: Implementar `scheduling/slots.py`

**Archivo**: `meet_scheduling/meet_scheduling/scheduling/slots.py`

**Funciones a implementar**:

#### 1.3.1 `generate_available_slots(calendar_resource, start_date, end_date)`
```python
def generate_available_slots(calendar_resource, start_date, end_date):
    """
    Genera slots discretos disponibles para UI.

    Args:
        calendar_resource: nombre del Calendar Resource
        start_date: fecha inicial
        end_date: fecha final

    Returns:
        list[dict]: [
            {
                "start": "2026-01-15 09:00:00",
                "end": "2026-01-15 09:30:00",
                "capacity_remaining": 1,
                "is_available": True
            },
            ...
        ]

    Algoritmo:
        1. Obtener effective_availability para rango
        2. Obtener slot_duration_minutes del calendar_resource
        3. Para cada intervalo disponible:
            a. Generar slots discretos cada slot_duration_minutes
            b. Para cada slot, verificar overlaps y capacity
            c. Marcar capacity_remaining
        4. Retornar lista ordenada
    """
```

**Dependencias**:
- `availability.get_effective_availability()`
- `overlap.check_overlap()`

**Tests**:
- [ ] Test: día completo sin appointments
- [ ] Test: día con algunos appointments → capacity_remaining correcta
- [ ] Test: slot_duration_minutes = 30
- [ ] Test: slot_duration_minutes = 60

**Checklist**:
- [ ] Implementar `generate_available_slots()`
- [ ] Integrar con availability y overlap
- [ ] Escribir tests de integración
- [ ] Optimizar performance (evitar N+1 queries)

---

### Tarea 1.4: Implementar `scheduling/tasks.py` (Scheduled Tasks)

**Archivo**: `meet_scheduling/meet_scheduling/scheduling/tasks.py`

**Función a implementar**:

#### 1.4.1 `cleanup_expired_drafts()`
```python
import frappe
from frappe.utils import now

def cleanup_expired_drafts():
    """
    Marca Drafts expirados como Cancelled automáticamente.
    Se ejecuta cada 15 minutos vía cron (configurado en hooks.py).

    Algoritmo:
        1. Buscar Appointments con:
            - status = "Draft"
            - docstatus = 0
            - draft_expires_at < now()
        2. Para cada Draft expirado:
            - Cambiar status a "Cancelled"
            - Agregar comment automático
            - Guardar
        3. Log cantidad de drafts expirados
    """
    expired_drafts = frappe.db.sql("""
        SELECT name, calendar_resource, start_datetime, end_datetime
        FROM `tabAppointment`
        WHERE status = 'Draft'
            AND docstatus = 0
            AND draft_expires_at IS NOT NULL
            AND draft_expires_at < %(now)s
    """, {"now": now()}, as_dict=True)

    count = 0
    for draft in expired_drafts:
        try:
            doc = frappe.get_doc("Appointment", draft.name)

            # Agregar comentario
            doc.add_comment(
                "Comment",
                text="⏱️ Draft expirado automáticamente por inactividad"
            )

            # Cambiar status
            doc.status = "Cancelled"
            doc.save(ignore_permissions=True)

            frappe.db.commit()
            count += 1

        except Exception as e:
            frappe.log_error(
                f"Error al expirar Draft {draft.name}: {str(e)}",
                "Cleanup Expired Drafts"
            )
            frappe.db.rollback()

    if count > 0:
        frappe.logger().info(f"✅ Se expiraron {count} draft(s) automáticamente")

    return count
```

**Tests**:
- [ ] Test: crear Draft con `draft_expires_at` pasado → debe cancelarse
- [ ] Test: crear Draft con `draft_expires_at` futuro → NO debe cancelarse
- [ ] Test: Draft sin `draft_expires_at` → ignorar
- [ ] Test: Confirmed appointment → ignorar

**Checklist**:
- [ ] Implementar `cleanup_expired_drafts()`
- [ ] Escribir tests
- [ ] Probar manualmente (ejecutar función directamente)
- [ ] Verificar que cron esté configurado en hooks.py
- [ ] Verificar logs en Frappe

---

## Fase 2: Servicios de Videollamadas (Adapter Pattern)

**Objetivo**: Implementar infraestructura de videollamadas sin integración real de APIs (mocks primero).

### Tarea 2.1: Implementar `video_calls/base.py`

**Archivo**: `meet_scheduling/meet_scheduling/video_calls/base.py`

```python
from abc import ABC, abstractmethod

class VideoCallAdapter(ABC):
    """
    Interfaz base para adaptadores de videollamadas.

    Todos los adaptadores deben implementar estos métodos.
    """

    @abstractmethod
    def create_meeting(self, profile, appointment):
        """
        Crea una reunión en el proveedor.

        Args:
            profile: Video Call Profile doc
            appointment: Appointment doc

        Returns:
            dict: {
                "meeting_url": str,
                "meeting_id": str,
                "provider_payload": dict (respuesta completa del API)
            }

        Raises:
            VideoCallError: si falla la creación
        """
        pass

    @abstractmethod
    def update_meeting(self, profile, appointment):
        """Actualiza una reunión existente (opcional)."""
        pass

    @abstractmethod
    def delete_meeting(self, profile, appointment):
        """Cancela/elimina una reunión (opcional)."""
        pass

    def validate_profile(self, profile):
        """Valida que el perfil tenga configuración correcta."""
        pass


class VideoCallError(Exception):
    """Excepción para errores de videollamadas."""
    pass
```

**Checklist**:
- [ ] Crear clase abstracta `VideoCallAdapter`
- [ ] Crear excepción `VideoCallError`
- [ ] Documentar contrato de interfaz

---

### Tarea 2.2: Implementar `video_calls/factory.py`

**Archivo**: `meet_scheduling/meet_scheduling/video_calls/factory.py`

```python
def get_adapter(provider):
    """
    Factory para obtener el adapter correcto según proveedor.

    Args:
        provider: "google_meet" o "microsoft_teams"

    Returns:
        VideoCallAdapter: instancia del adapter

    Raises:
        ValueError: si provider no es soportado
    """
    if provider == "google_meet":
        from .google_meet import GoogleMeetAdapter
        return GoogleMeetAdapter()
    elif provider == "microsoft_teams":
        from .microsoft_teams import TeamsAdapter
        return TeamsAdapter()
    else:
        raise ValueError(f"Unsupported provider: {provider}")
```

**Checklist**:
- [ ] Implementar factory function
- [ ] Agregar import lazy para evitar circular imports
- [ ] Escribir test unitario

---

### Tarea 2.3: Implementar `video_calls/google_meet.py` (Mock inicial)

**Archivo**: `meet_scheduling/meet_scheduling/video_calls/google_meet.py`

```python
import frappe
from .base import VideoCallAdapter, VideoCallError

class GoogleMeetAdapter(VideoCallAdapter):
    """Adapter para Google Meet."""

    def create_meeting(self, profile, appointment):
        """
        Crea una reunión en Google Meet.

        FASE 1: Mock implementation
        FASE 2+: Implementar OAuth + Google Calendar API
        """
        # Mock por ahora
        return {
            "meeting_url": f"https://meet.google.com/mock-{appointment.name}",
            "meeting_id": f"mock-{appointment.name}",
            "provider_payload": {"mock": True}
        }

    def validate_profile(self, profile):
        """Valida configuración del perfil."""
        if profile.link_mode in ["auto_generate", "auto_or_manual"]:
            if not profile.provider_account:
                frappe.throw("Provider Account es requerido para modo automático")

            account = frappe.get_doc("Provider Account", profile.provider_account)
            if account.status != "Connected":
                raise VideoCallError(f"Provider Account no está conectado: {account.status}")

    def update_meeting(self, profile, appointment):
        # Mock
        return True

    def delete_meeting(self, profile, appointment):
        # Mock
        return True
```

**Checklist**:
- [ ] Implementar mock de `create_meeting()`
- [ ] Implementar `validate_profile()`
- [ ] Implementar mocks de update/delete
- [ ] Documentar TODOs para implementación real

---

### Tarea 2.4: Implementar `video_calls/microsoft_teams.py` (Mock inicial)

**Archivo**: `meet_scheduling/meet_scheduling/video_calls/microsoft_teams.py`

Similar a Google Meet pero para Teams.

```python
class TeamsAdapter(VideoCallAdapter):
    """Adapter para Microsoft Teams."""

    def create_meeting(self, profile, appointment):
        # Mock similar a Google Meet
        return {
            "meeting_url": f"https://teams.microsoft.com/mock-{appointment.name}",
            "meeting_id": f"teams-mock-{appointment.name}",
            "provider_payload": {"mock": True}
        }

    # ... resto similar
```

**Checklist**:
- [ ] Implementar mock básico
- [ ] Mantener misma interfaz que GoogleMeetAdapter

---

## Fase 3: Lógica de DocTypes

**Objetivo**: Implementar hooks y validaciones en los DocTypes.

### Tarea 3.1: Implementar validaciones en DocTypes simples

#### 3.1.1 `Availability Plan`

**Archivo**: `meet_scheduling/meet_scheduling/doctype/availability_plan/availability_plan.py`

```python
import frappe
from frappe.model.document import Document

class AvailabilityPlan(Document):
    def validate(self):
        """Validaciones básicas."""
        self.validate_date_range()
        self.validate_slots()

    def validate_date_range(self):
        """Valida que valid_from < valid_to si ambos existen."""
        if self.valid_from and self.valid_to:
            if self.valid_from > self.valid_to:
                frappe.throw("Valid From debe ser anterior a Valid To")

    def validate_slots(self):
        """Valida que los slots sean coherentes."""
        for slot in self.get("slots", []):  # Child table
            if not slot.start_time or not slot.end_time:
                frappe.throw(f"Slot {slot.idx}: debe tener start_time y end_time")
            if slot.start_time >= slot.end_time:
                frappe.throw(f"Slot {slot.idx}: start_time debe ser menor que end_time")
```

**Checklist**:
- [ ] Implementar `validate()`
- [ ] Implementar `validate_date_range()`
- [ ] Implementar `validate_slots()`
- [ ] Escribir tests

---

#### 3.1.2 `Calendar Exception`

**Archivo**: `meet_scheduling/meet_scheduling/doctype/calendar_exception/calendar_exception.py`

```python
class CalendarException(Document):
    def validate(self):
        """Validaciones básicas."""
        self.validate_time_range()
        self.validate_required_fields()

    def validate_time_range(self):
        """Si hay start_time y end_time, validar que start < end."""
        if self.start_time and self.end_time:
            if self.start_time >= self.end_time:
                frappe.throw("Start Time debe ser menor que End Time")

    def validate_required_fields(self):
        """Valida campos según exception_type."""
        if not self.calendar_resource:
            frappe.throw("Calendar Resource es requerido")
        if not self.date:
            frappe.throw("Date es requerido")
```

**Checklist**:
- [ ] Implementar validaciones
- [ ] Escribir tests

---

#### 3.1.3 `Calendar Resource`

**Archivo**: `meet_scheduling/meet_scheduling/doctype/calendar_resource/calendar_resource.py`

```python
class CalendarResource(Document):
    def validate(self):
        """Validaciones básicas."""
        if self.capacity and self.capacity < 1:
            frappe.throw("Capacity debe ser al menos 1")

        if self.slot_duration_minutes and self.slot_duration_minutes < 1:
            frappe.throw("Slot Duration debe ser al menos 1 minuto")

        if not self.timezone:
            self.timezone = frappe.utils.get_system_timezone()
```

**Checklist**:
- [ ] Implementar validaciones
- [ ] Escribir tests

---

### Tarea 3.2: Implementar `Appointment` (DocType principal)

**Archivo**: `meet_scheduling/meet_scheduling/doctype/appointment/appointment.py`

Este es el DocType más complejo. Se divide en sub-tareas:

#### 3.2.1 Método `validate()`

```python
import frappe
from frappe.model.document import Document
from frappe.utils import get_datetime

class Appointment(Document):
    def validate(self):
        """Validaciones básicas (NO valida disponibilidad todavía)."""
        self.validate_times()
        self.validate_required_fields()
        self.resolve_video_call_profile()
        self.resolve_effective_call_mode()
        self.validate_slot_granularity()

    def validate_times(self):
        """Valida que start < end."""
        if not self.start_datetime or not self.end_datetime:
            frappe.throw("Start Datetime y End Datetime son requeridos")

        start = get_datetime(self.start_datetime)
        end = get_datetime(self.end_datetime)

        if start >= end:
            frappe.throw("Start Datetime debe ser anterior a End Datetime")

    def validate_required_fields(self):
        """Valida campos requeridos."""
        if not self.calendar_resource:
            frappe.throw("Calendar Resource es requerido")

    def resolve_video_call_profile(self):
        """
        Si video_call_profile está vacío, tomar del Calendar Resource.
        Esto es un "snapshot" del perfil en el momento de crear la cita.
        """
        if not self.video_call_profile and self.calendar_resource:
            resource = frappe.get_doc("Calendar Resource", self.calendar_resource)
            if resource.video_call_profile:
                self.video_call_profile = resource.video_call_profile

    def resolve_effective_call_mode(self):
        """
        Resuelve el modo efectivo de enlace:
        - Si call_link_mode = "inherit" → usar profile.link_mode
        - Si call_link_mode = "manual" o "auto" → usar ese
        """
        if self.call_link_mode == "inherit" and self.video_call_profile:
            profile = frappe.get_doc("Video Call Profile", self.video_call_profile)
            self._effective_mode = profile.link_mode
            self.video_provider = profile.provider
        else:
            self._effective_mode = self.call_link_mode

    def validate_slot_granularity(self):
        """
        Valida que start/end respeten slot_duration_minutes (opcional).
        """
        if not self.calendar_resource:
            return

        resource = frappe.get_doc("Calendar Resource", self.calendar_resource)
        if not resource.slot_duration_minutes:
            return

        # Validar que duración sea múltiplo de slot_duration
        duration_minutes = (get_datetime(self.end_datetime) - get_datetime(self.start_datetime)).total_seconds() / 60
        if duration_minutes % resource.slot_duration_minutes != 0:
            frappe.throw(f"La duración debe ser múltiplo de {resource.slot_duration_minutes} minutos")
```

**Checklist**:
- [ ] Implementar `validate()`
- [ ] Implementar `validate_times()`
- [ ] Implementar `resolve_video_call_profile()`
- [ ] Implementar `resolve_effective_call_mode()`
- [ ] Implementar `validate_slot_granularity()`
- [ ] Escribir tests unitarios

---

#### 3.2.2 Método `on_submit()` - Validación Fuerte

```python
def on_submit(self):
    """
    Validación fuerte + generación de videollamada.
    """
    self.validate_availability()
    self.validate_no_overlaps()
    self.handle_video_call_creation()
    self.set_status_confirmed()

def validate_availability(self):
    """
    Valida que el rango [start, end) caiga en disponibilidad efectiva.
    """
    from meet_scheduling.scheduling.availability import get_availability_slots_for_day

    start = get_datetime(self.start_datetime)
    date = start.date()

    slots = get_availability_slots_for_day(self.calendar_resource, date)

    # Verificar que [start, end) caiga completamente en algún slot
    is_available = False
    for slot in slots:
        if slot["start"] <= start and slot["end"] >= get_datetime(self.end_datetime):
            is_available = True
            break

    if not is_available:
        frappe.throw(f"No hay disponibilidad para el horario seleccionado: {self.start_datetime} - {self.end_datetime}")

def validate_no_overlaps(self):
    """
    Valida que no haya overlaps según capacidad.
    """
    from meet_scheduling.scheduling.overlap import check_overlap

    result = check_overlap(
        self.calendar_resource,
        self.start_datetime,
        self.end_datetime,
        exclude_appointment=self.name
    )

    if result["capacity_exceeded"]:
        frappe.throw(
            f"Capacidad excedida. Hay {result['capacity_used']} citas en este horario, "
            f"capacidad máxima: {result['capacity_available']}"
        )

def handle_video_call_creation(self):
    """
    Maneja la creación del enlace de videollamada.
    """
    effective_mode = getattr(self, "_effective_mode", self.call_link_mode)

    if effective_mode == "manual_only" or effective_mode == "manual":
        self._handle_manual_link()
    elif effective_mode in ["auto_generate", "auto"]:
        self._handle_auto_link()
    elif effective_mode == "auto_or_manual":
        self._handle_auto_with_fallback()

def _handle_manual_link(self):
    """Modo manual: copiar manual_meeting_url a meeting_url."""
    if not self.manual_meeting_url:
        frappe.throw("Manual Meeting URL es requerido para este perfil")

    self.meeting_url = self.manual_meeting_url
    self.meeting_status = "not_created"  # No se creó por API

def _handle_auto_link(self):
    """Modo auto: crear meeting vía adapter."""
    try:
        self._create_meeting_via_adapter()
    except Exception as e:
        frappe.throw(f"Error al crear videollamada: {str(e)}")

def _handle_auto_with_fallback(self):
    """Modo auto con fallback: intentar auto, si falla permitir manual."""
    profile = frappe.get_doc("Video Call Profile", self.video_call_profile)

    try:
        self._create_meeting_via_adapter()
    except Exception as e:
        # Si falla y require_manual_if_auto_fails está activado, permitir manual
        if profile.require_manual_if_auto_fails:
            self.meeting_status = "failed"
            self.meeting_error = str(e)
            if not self.manual_meeting_url:
                frappe.throw(f"La creación automática falló: {str(e)}. Por favor ingresa un enlace manual.")
            else:
                self.meeting_url = self.manual_meeting_url
        else:
            frappe.throw(f"Error al crear videollamada: {str(e)}")

def _create_meeting_via_adapter(self):
    """Crea meeting usando el adapter del proveedor."""
    from meet_scheduling.video_calls.factory import get_adapter

    # Verificar idempotencia
    if self.meeting_id and self.meeting_status == "created":
        return  # Ya fue creado

    profile = frappe.get_doc("Video Call Profile", self.video_call_profile)

    # Obtener adapter
    adapter = get_adapter(profile.provider)

    # Validar perfil
    adapter.validate_profile(profile)

    # Crear meeting
    result = adapter.create_meeting(profile, self)

    # Guardar resultados
    self.meeting_url = result["meeting_url"]
    self.meeting_id = result["meeting_id"]
    self.provider_payload = result["provider_payload"]
    self.meeting_status = "created"
    self.meeting_created_at = frappe.utils.now()
    self.video_provider = profile.provider

def set_status_confirmed(self):
    """Marca el appointment como Confirmed."""
    self.status = "Confirmed"
```

**Checklist**:
- [ ] Implementar `on_submit()`
- [ ] Implementar `validate_availability()`
- [ ] Implementar `validate_no_overlaps()`
- [ ] Implementar `handle_video_call_creation()`
- [ ] Implementar métodos `_handle_*_link()`
- [ ] Implementar `_create_meeting_via_adapter()`
- [ ] Escribir tests de integración

---

#### 3.2.3 Método `on_cancel()`

```python
def on_cancel(self):
    """
    Maneja la cancelación del appointment.
    """
    self.status = "Cancelled"

    # Si se creó meeting por API, intentar cancelarlo
    if self.meeting_id and self.meeting_status == "created":
        self._cancel_meeting_if_possible()

def _cancel_meeting_if_possible(self):
    """Intenta cancelar el meeting en el proveedor."""
    try:
        from meet_scheduling.video_calls.factory import get_adapter

        profile = frappe.get_doc("Video Call Profile", self.video_call_profile)
        adapter = get_adapter(profile.provider)
        adapter.delete_meeting(profile, self)

        self.meeting_status = "cancelled"
    except Exception as e:
        frappe.log_error(f"Error al cancelar meeting: {str(e)}", "Appointment Cancel")
        # No lanzar error, solo log (la cita se cancela igual)
```

**Checklist**:
- [ ] Implementar `on_cancel()`
- [ ] Implementar `_cancel_meeting_if_possible()`
- [ ] Escribir tests

---

### Tarea 3.3: Implementar `Provider Account`

**Archivo**: `meet_scheduling/meet_scheduling/doctype/provider_account/provider_account.py`

```python
import frappe
from frappe.model.document import Document

class ProviderAccount(Document):
    def validate(self):
        """Validaciones básicas."""
        if not self.owner_user:
            frappe.throw("Owner User es requerido")

        if not self.provider:
            frappe.throw("Provider es requerido")

    def is_connected(self):
        """Verifica si la cuenta está conectada y tokens válidos."""
        if self.status != "Connected":
            return False

        # TODO: Verificar si token está expirado
        # if self.token_expires_at and self.token_expires_at < frappe.utils.now():
        #     return False

        return True

    def refresh_token_if_needed(self):
        """
        Refresca el access_token si está expirado.
        TODO: Implementar en Fase 4 con OAuth real.
        """
        pass
```

**Checklist**:
- [ ] Implementar validaciones básicas
- [ ] Implementar `is_connected()`
- [ ] Preparar estructura para OAuth (Fase 4)

---

## Fase 4: API Endpoints Whitelisted

**Objetivo**: Crear endpoints públicos para frontend/integración.

### Tarea 4.1: Crear archivo API

**Archivo**: `meet_scheduling/meet_scheduling/api/appointment_api.py`

```python
import frappe
from frappe import _

@frappe.whitelist()
def get_available_slots(calendar_resource, from_date, to_date):
    """
    Obtiene slots disponibles para un rango de fechas.

    Args:
        calendar_resource: nombre del Calendar Resource
        from_date: fecha inicial (YYYY-MM-DD)
        to_date: fecha final (YYYY-MM-DD)

    Returns:
        list[dict]: slots disponibles
    """
    from meet_scheduling.scheduling.slots import generate_available_slots

    # Validar permisos
    if not frappe.has_permission("Appointment", "read"):
        frappe.throw(_("No permission"), frappe.PermissionError)

    # Validar parámetros
    if not calendar_resource or not from_date or not to_date:
        frappe.throw(_("Faltan parámetros requeridos"))

    # Generar slots
    slots = generate_available_slots(calendar_resource, from_date, to_date)

    return slots

@frappe.whitelist()
def validate_appointment(calendar_resource, start_datetime, end_datetime, appointment_name=None):
    """
    Valida si un appointment es válido ANTES de guardarlo.
    Útil para UI/frontend.

    Returns:
        dict: {
            "valid": bool,
            "errors": list[str],
            "warnings": list[str]
        }
    """
    from meet_scheduling.scheduling.availability import get_availability_slots_for_day
    from meet_scheduling.scheduling.overlap import check_overlap
    from frappe.utils import get_datetime

    errors = []
    warnings = []

    # Validar tiempos
    start = get_datetime(start_datetime)
    end = get_datetime(end_datetime)

    if start >= end:
        errors.append("Start datetime debe ser anterior a end datetime")
        return {"valid": False, "errors": errors, "warnings": warnings}

    # Validar disponibilidad
    try:
        date = start.date()
        slots = get_availability_slots_for_day(calendar_resource, date)

        is_available = any(
            slot["start"] <= start and slot["end"] >= end
            for slot in slots
        )

        if not is_available:
            errors.append("No hay disponibilidad en el horario seleccionado")
    except Exception as e:
        errors.append(f"Error al validar disponibilidad: {str(e)}")

    # Validar overlaps
    try:
        overlap_result = check_overlap(
            calendar_resource,
            start_datetime,
            end_datetime,
            exclude_appointment=appointment_name
        )

        if overlap_result["capacity_exceeded"]:
            errors.append(
                f"Capacidad excedida. {overlap_result['capacity_used']} citas en este horario, "
                f"máximo {overlap_result['capacity_available']}"
            )
        elif overlap_result["has_overlap"]:
            warnings.append(f"Hay {len(overlap_result['overlapping_appointments'])} cita(s) en este horario")
    except Exception as e:
        errors.append(f"Error al validar overlaps: {str(e)}")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }

@frappe.whitelist()
def generate_meeting(appointment_name):
    """
    Genera meeting manualmente (cuando create_on = manual).

    Args:
        appointment_name: nombre del Appointment

    Returns:
        dict: {meeting_url, meeting_id, status}
    """
    # Validar permisos
    if not frappe.has_permission("Appointment", "write"):
        frappe.throw(_("No permission"), frappe.PermissionError)

    appointment = frappe.get_doc("Appointment", appointment_name)

    # Verificar que no exista ya
    if appointment.meeting_id and appointment.meeting_status == "created":
        frappe.throw(_("El meeting ya fue creado"))

    # Crear meeting
    try:
        appointment._create_meeting_via_adapter()
        appointment.save(ignore_permissions=True)

        return {
            "meeting_url": appointment.meeting_url,
            "meeting_id": appointment.meeting_id,
            "status": appointment.meeting_status
        }
    except Exception as e:
        frappe.throw(f"Error al crear meeting: {str(e)}")
```

**Checklist**:
- [ ] Implementar `get_available_slots()`
- [ ] Implementar `validate_appointment()`
- [ ] Implementar `generate_meeting()`
- [ ] Agregar validación de permisos
- [ ] Escribir tests de API
- [ ] Documentar endpoints

---

## Fase 5: Tests Comprehensivos

**Objetivo**: Asegurar que todo funciona correctamente con tests automatizados.

### Tarea 5.1: Tests Unitarios de Scheduling

**Archivo**: `meet_scheduling/meet_scheduling/tests/test_availability.py`

```python
import unittest
import frappe
from frappe.utils import add_days, today
from meet_scheduling.scheduling.availability import get_availability_slots_for_day

class TestAvailability(unittest.TestCase):
    def setUp(self):
        """Crear datos de prueba."""
        # Crear Availability Plan
        # Crear Calendar Resource
        # etc.
        pass

    def test_normal_day_with_slots(self):
        """Test: día normal con slots sin excepciones."""
        pass

    def test_day_with_closed_exception(self):
        """Test: día con excepción Closed."""
        pass

    def test_day_with_blocked_exception(self):
        """Test: día con excepción Blocked parcial."""
        pass

    def test_day_with_extra_availability(self):
        """Test: día con Extra Availability."""
        pass
```

**Checklist**:
- [ ] Crear `test_availability.py`
- [ ] Crear `test_overlap.py`
- [ ] Crear `test_slots.py`
- [ ] Todos los tests deben pasar

---

### Tarea 5.2: Tests de Integración de Appointment

**Archivo**: `meet_scheduling/meet_scheduling/doctype/appointment/test_appointment.py`

```python
class TestAppointment(unittest.TestCase):
    def test_create_valid_appointment(self):
        """Test: crear appointment válido y hacer submit."""
        pass

    def test_appointment_no_availability(self):
        """Test: falla si no hay disponibilidad."""
        pass

    def test_appointment_overlap_capacity_1(self):
        """Test: falla si hay overlap con capacity=1."""
        pass

    def test_appointment_overlap_capacity_2(self):
        """Test: permite overlap con capacity=2."""
        pass

    def test_manual_video_call(self):
        """Test: modo manual copia manual_meeting_url."""
        pass

    def test_auto_video_call(self):
        """Test: modo auto crea meeting (mock)."""
        pass

    def test_cancel_appointment(self):
        """Test: cancelar appointment."""
        pass
```

**Checklist**:
- [ ] Escribir todos los tests de appointment
- [ ] Tests deben usar fixtures/test data
- [ ] Todos los tests deben pasar

---

## Fase 6: Permisos y Roles

**Objetivo**: Configurar permisos correctos para los roles.

### Tarea 6.1: Crear Roles Customizados

**Via Frappe UI**:
1. Ir a Role List
2. Crear roles:
   - `Scheduling Admin`
   - `Scheduler / Staff`
   - `Appointment Viewer`

**Checklist**:
- [ ] Crear roles en Frappe

---

### Tarea 6.2: Configurar Permisos en DocTypes

**Para cada DocType**, configurar permisos vía Frappe UI o fixtures:

#### Appointment
- `Scheduling Admin`: Full access
- `Scheduler / Staff`: Create, Read, Write, Submit, Cancel (sin Delete)
- `Appointment Viewer`: Read only

#### Calendar Resource
- `Scheduling Admin`: Full access
- `Scheduler / Staff`: Read only
- `Appointment Viewer`: Read only

#### Availability Plan
- `Scheduling Admin`: Full access
- Otros: Read only

#### Provider Account
- `Scheduling Admin`: Full access
- **Otros**: NO ACCESS (seguridad)

**Checklist**:
- [ ] Configurar permisos para todos los DocTypes
- [ ] Probar con usuarios de diferentes roles
- [ ] Documentar matriz de permisos

---

## Fase 7: OAuth y APIs Reales (Google Meet / Teams)

**Nota**: Esta fase es avanzada y requiere configuración externa.

### Tarea 7.1: Implementar OAuth Flow para Google Meet

**Pasos**:
1. Crear proyecto en Google Cloud Console
2. Habilitar Google Calendar API
3. Crear OAuth 2.0 credentials
4. Implementar OAuth flow en Provider Account:
   - Endpoint de autorización
   - Callback handler
   - Refresh token logic

**Archivo**: `meet_scheduling/meet_scheduling/oauth/google.py`

**Checklist**:
- [ ] Configurar Google Cloud project
- [ ] Implementar OAuth authorization URL
- [ ] Implementar callback handler
- [ ] Implementar refresh token
- [ ] Actualizar `GoogleMeetAdapter` para usar Google Calendar API real
- [ ] Documentar configuración

---

### Tarea 7.2: Implementar OAuth Flow para Microsoft Teams

Similar a Google Meet pero con Microsoft Graph API.

**Checklist**:
- [ ] Configurar Azure AD application
- [ ] Implementar OAuth flow
- [ ] Actualizar `TeamsAdapter` para usar Microsoft Graph API
- [ ] Documentar configuración

---

## Fase 8: Frontend y UX (Opcional)

### Tarea 8.1: Custom Scripts para DocTypes

**Archivos**:
- `appointment.js`: UI enhancements
- `calendar_resource.js`: UI enhancements

**Funcionalidades**:
- Vista de calendario para appointments
- Selector de slots disponibles
- Preview de video call settings

**Checklist**:
- [ ] Crear custom scripts
- [ ] Mejorar UX de selección de horarios
- [ ] Agregar validaciones en frontend

---

## Cronograma Sugerido

| Fase | Duración Estimada | Dependencias |
|------|-------------------|--------------|
| Fase 0 | 1 hora | Ninguna |
| Fase 1 | 8-12 horas | Fase 0 |
| Fase 2 | 4-6 horas | Fase 0 |
| Fase 3 | 12-16 horas | Fase 1, Fase 2 |
| Fase 4 | 4-6 horas | Fase 3 |
| Fase 5 | 8-12 horas | Todas las anteriores |
| Fase 6 | 2-4 horas | Ninguna (paralela) |
| Fase 7 | 16-24 horas | Fase 2, Fase 3 |
| Fase 8 | 8-12 horas | Fase 3, Fase 4 |

**Total**: 63-93 horas de desarrollo

---

## Priorización

### MVP (Minimum Viable Product) - Debe hacerse:
- ✅ Fase 0, 1, 2, 3, 4, 5, 6

### Features Avanzadas - Puede posponerse:
- ⏳ Fase 7 (OAuth real - usar mocks por ahora)
- ⏳ Fase 8 (Frontend - usar UI estándar de Frappe)

---

## Checklist General de Implementación

### Antes de Empezar
- [ ] Confirmar decisiones de diseño (Sección inicial)
- [ ] Leer documentación técnica completa
- [ ] Configurar entorno de desarrollo

### Durante Implementación
- [ ] Seguir orden de fases
- [ ] Escribir tests para cada módulo
- [ ] Documentar código con docstrings
- [ ] Hacer commits frecuentes
- [ ] Ejecutar pre-commit hooks

### Al Finalizar Cada Fase
- [ ] Todos los tests pasan
- [ ] Código revisado
- [ ] Documentación actualizada
- [ ] Demo funcional

### Al Finalizar MVP
- [ ] Crear datos de prueba (fixtures)
- [ ] Documentar casos de uso
- [ ] Crear guía de deployment
- [ ] Presentar demo al equipo

---

## Comandos Útiles

```bash
# Ejecutar tests
bench --site [site-name] run-tests --app meet_scheduling

# Ejecutar tests específicos
bench --site [site-name] run-tests --app meet_scheduling --module meet_scheduling.scheduling.tests.test_availability

# Migrar después de cambios en DocTypes
bench --site [site-name] migrate

# Limpiar caché
bench --site [site-name] clear-cache

# Ejecutar pre-commit
cd apps/meet_scheduling
pre-commit run --all-files

# Instalar app en otro site
bench --site [new-site] install-app meet_scheduling
```

---

## Recursos y Referencias

- [Frappe Framework Documentation](https://frappeframework.com/docs)
- [Frappe DocType Guide](https://frappeframework.com/docs/user/en/guides/basics/doctypes)
- [Frappe Server Scripts](https://frappeframework.com/docs/user/en/python-api)
- [Google Calendar API](https://developers.google.com/calendar/api/guides/overview)
- [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/api/overview)

---

## Contacto y Soporte

**Desarrollador**: Sebastian Ortiz Valencia
**Email**: sebastianortiz989@gmail.com

---

**Última actualización**: 2026-01-21
