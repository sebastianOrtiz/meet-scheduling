# DocType: Meet Scheduling Settings

> **Estado actual**: este DocType **NO existe** en el repositorio `meet_scheduling`. La configuración global de la app no está centralizada en un Single DocType.

---

## Por qué no existe

Al revisar `meet_scheduling/meet_scheduling/doctype/`, los únicos DocTypes definidos son:

- `Appointment`
- `Calendar Resource`
- `Calendar Resource Notification User` (child)
- `Availability Plan`
- `Availability Slot` (child)
- `Calendar Exception`
- `Video Call Profile`
- `Provider Account`

No hay `meet_scheduling_settings/` ni `meet_scheduling_setting/`.

---

## Dónde vive la configuración actualmente

| Configuración | Ubicación |
|---|---|
| Duración del slot | `Calendar Resource.slot_duration_minutes` (por recurso). |
| Capacidad | `Calendar Resource.capacity` (por recurso). |
| Expiración de Drafts | `Calendar Resource.draft_expiration_minutes` (por recurso). |
| Zona horaria | `Calendar Resource.timezone` (por recurso). |
| Si enviar emails | `Calendar Resource.send_email_notification` + `notification_users` (por recurso). |
| Plan semanal | `Availability Plan` (compartido entre recursos). |
| Excepciones | `Calendar Exception` (por recurso + fecha). |
| Perfil de videollamada | `Video Call Profile` (compartido). |
| Credenciales OAuth | `Provider Account` (por proveedor). |
| Cron de cleanup | `meet_scheduling/hooks.py:185-191` (`scheduler_events.cron["*/15 * * * *"]`). |

La filosofía es: **configurar por recurso**, no globalmente. Esto da flexibilidad pero no permite, por ejemplo, "default `slot_duration` para nuevos recursos".

---

## Posible deuda técnica

Sería razonable crear un `Meet Scheduling Settings` Single DocType con:

- `default_slot_duration_minutes`
- `default_capacity`
- `default_draft_expiration_minutes`
- `default_timezone`
- `default_send_email_notification`
- `enable_video_call_auto_generation` (global kill-switch)
- `email_template_override` (Link → `Email Template`)

Mientras tanto, los defaults están hardcoded en el JSON de `Calendar Resource` y en los fallbacks de `availability.py:104` (`tz_name = resource.timezone or "UTC"`).
