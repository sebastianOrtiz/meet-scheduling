# Documentación de Meet Scheduling

Documentación técnica exhaustiva de la app `meet_scheduling`. Esta app gestiona el agendamiento de citas (Appointments) con recursos de calendario (Calendar Resource), validación de disponibilidad, generación de enlaces de videollamada (Google Meet / Microsoft Teams) y notificaciones por email.

Es consumida por:
- **`lex_app`** que crea `Case Log` automáticos al confirmar citas y enriquece el email de confirmación con datos del caso legal.
- **`logbook`** que crea `Logbook Entry` automáticos al confirmar citas.
- **`common_configurations`** para autenticación por token de `User contact` y el sistema de Service Portal Tools.

> Autor: Sebastian Ortiz Valencia (sebastianortiz989@gmail.com)
> Licencia: MIT
> Framework: Frappe Framework (Python + Angular)

---

## Índice general

### DocTypes
- [Appointment](doctypes/APPOINTMENT.md) — Cita transaccional, submittable.
- [Calendar Resource](doctypes/CALENDAR_RESOURCE.md) — Recurso de calendario (persona, sala, servicio).
- [Calendar Resource Notification User](doctypes/CALENDAR_RESOURCE_NOTIFICATION_USER.md) — Child table de usuarios a notificar.
- [Calendar Resource Schedule (Availability Plan + Availability Slot)](doctypes/CALENDAR_RESOURCE_SCHEDULE.md) — Plan semanal y child table de horarios.
- [Availability Plan](doctypes/AVAILABILITY_PLAN.md) — Plan de disponibilidad semanal reutilizable.
- [Calendar Exception](doctypes/CALENDAR_EXCEPTION.md) — Excepciones por fecha (Closed / Blocked / Extra Availability).
- [Video Call Profile](doctypes/VIDEO_CALL_PROFILE.md) — Perfil para enlaces de videollamada (manual o automático).
- [Provider Account](doctypes/PROVIDER_ACCOUNT.md) — Credenciales OAuth para crear meetings vía API.
- [Meet Scheduling Settings](doctypes/MEET_SCHEDULING_SETTINGS.md) — Estado actual (no implementado).

### APIs
- [API de Appointments](api/APPOINTMENTS.md) — `get_my_appointments`, `create_and_confirm_appointment`, `cancel_my_appointment`, `validate_appointment`, etc.
- [API de Calendar Resources](api/CALENDAR_RESOURCES.md) — `get_active_calendar_resources`, `get_available_slots`, validación de slots.

### Features
- [Tool del portal `meet_scheduling`](features/MEET_SCHEDULING_TOOL.md) — Tool del Service Portal para agendar citas.
- [Tool del portal `my_appointments`](features/MY_APPOINTMENTS_TOOL.md) — Tool para ver/cancelar las propias citas.
- [Lógica de disponibilidad](features/AVAILABILITY_LOGIC.md) — Cálculo de slots, excepciones, conflictos.
- [Sistema de notificaciones por email](features/EMAIL_NOTIFICATIONS.md) — Template Jinja `appointment_confirmed`, hooks extensibles.

### Integration (cómo otras apps se enganchan)
- [Integración con lex_app](integration/LEX_APP.md) — `on_appointment_submit`, custom field `create_case_log`, hooks de email.
- [Integración con logbook](integration/LOGBOOK.md) — `on_appointment_submit`, `create_logbook_entry`, `logbook_availability`.
- [Dependencias con common_configurations](integration/COMMON_CONFIGURATIONS.md) — Tool types, `User contact`, autenticación por token.

### Hooks y Email
- [hooks.py completo](hooks.md) — Fixtures, scheduler events, hooks extensibles que define la app.

### Services
- [Servicio de Availability](services/AVAILABILITY.md) — `scheduling/availability.py`.
- [Servicio de Slots](services/SLOTS.md) — `scheduling/slots.py`.
- [Servicio de Overlap](services/OVERLAP.md) — `scheduling/overlap.py`.
- [Servicio de Email](services/EMAIL.md) — `notifications/appointment.py`.
- [Servicio de Tasks](services/TASKS.md) — `scheduling/tasks.py`.
- [Servicio de Video Calls](services/VIDEO_CALLS.md) — `video_calls/` (adapter pattern).

### Instalación
- [Proceso de instalación](INSTALL.md) — Roles, custom fields, tool types y migraciones.

---

## Resumen de archivos clave del repositorio

| Componente | Archivo | Descripción |
|---|---|---|
| Hooks | `meet_scheduling/hooks.py` | Fixtures, scheduler_events, declaraciones de hooks extensibles. |
| Appointment DocType | `meet_scheduling/meet_scheduling/doctype/appointment/appointment.py` | Controller principal con `validate`, `on_submit`, `on_cancel`, `on_update`. |
| Calendar Resource | `meet_scheduling/meet_scheduling/doctype/calendar_resource/calendar_resource.py` | Controller del recurso (clase vacía, lógica delegada). |
| Availability Plan | `meet_scheduling/meet_scheduling/doctype/availability_plan/availability_plan.py` | Validaciones de plan y slots. |
| Calendar Exception | `meet_scheduling/meet_scheduling/doctype/calendar_exception/calendar_exception.py` | Validaciones de excepciones. |
| Availability Service | `meet_scheduling/meet_scheduling/scheduling/availability.py` | `get_availability_slots_for_day`, `get_effective_availability`. |
| Overlap Service | `meet_scheduling/meet_scheduling/scheduling/overlap.py` | `check_overlap`. |
| Slots Service | `meet_scheduling/meet_scheduling/scheduling/slots.py` | `generate_available_slots`. |
| Tasks Service | `meet_scheduling/meet_scheduling/scheduling/tasks.py` | `cleanup_expired_drafts` (cron cada 15 min). |
| Notifications | `meet_scheduling/meet_scheduling/notifications/appointment.py` | `send_appointment_notification` con hooks extensibles. |
| Email Template | `meet_scheduling/templates/emails/appointment_confirmed.html` | Template Jinja del email de confirmación. |
| Video Calls | `meet_scheduling/meet_scheduling/video_calls/` | Adapter pattern (base, factory, google_meet, microsoft_teams). |
| API Appointments | `meet_scheduling/api/appointments/endpoints.py` | Endpoints whitelisted para citas. |
| Fixtures | `meet_scheduling/fixtures/` | `role.json`, `tool_type.json`, `custom_field.json`. |

---

## Estado de la app

- DocTypes definidos e implementados con validaciones.
- Servicios de scheduling implementados (availability, overlap, slots, tasks).
- API REST modular implementada con autenticación por token y rate limiting.
- Notificaciones por email implementadas con hooks extensibles (`appointment_email_context`, `appointment_email_recipients`).
- Adaptadores de Google Meet y Microsoft Teams: **implementación mock** (devuelven URLs fake tipo `https://meet.google.com/mock-APT-...`). La integración real con OAuth y APIs reales está pendiente (fase 7 según roadmap interno).
- Componentes Angular (`meet-scheduling-tool`, `my-appointments-tool`) implementados en `common_configurations/front_apps/service-portal/`.
- No existe un DocType `Meet Scheduling Settings`; la configuración por recurso se hace directamente en `Calendar Resource`.
