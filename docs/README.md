Documentación técnica — Módulo de Calendarios, Agendamientos y Videollamadas (Frappe)

1) Objetivo del módulo

Permitir:
	1.	Configurar disponibilidad por calendario (días y horas por día) usando plantillas semanales + excepciones.
	2.	Crear agendamientos (Appointment) con validación robusta (disponibilidad + solapes + capacidad).
	3.	Opcionalmente generar enlace de videollamada (Google Meet / Microsoft Teams) o permitir enlace manual, según el perfil de videollamada configurado.

⸻

2) Entidades y responsabilidades

2.1 Calendar Resource

Qué es: el “recurso” que se agenda (persona, sala, equipo, servicio).
Responsabilidades lógicas:
	•	Define zona horaria, duración de slot, capacidad por defecto.
	•	Selecciona un Availability Plan.
	•	Selecciona un Video Call Profile por defecto.

2.2 Availability Plan + Availability Slot (child)

Qué es: plantilla semanal reutilizable de disponibilidad.
Responsabilidades lógicas:
	•	Define franjas por día de semana (pueden ser múltiples por día).
	•	NO guarda slots concretos por fecha (se calculan al vuelo).

2.3 Calendar Exception

Qué es: override por fecha: cierres/bloqueos/aperturas extra.
Responsabilidades lógicas:
	•	Ajusta la disponibilidad de un día específico sin editar el plan.
	•	Tipos:
	•	Closed: cierra todo el día o un rango
	•	Blocked: bloquea un rango
	•	Extra Availability: agrega disponibilidad adicional

2.4 Appointment

Qué es: el agendamiento real (transaccional).
Responsabilidades lógicas:
	•	Validar:
	•	tiempos (start < end)
	•	encaje en disponibilidad (plan + excepciones)
	•	solapes vs otras citas (según capacidad)
	•	Resolver y persistir:
	•	video_call_profile snapshot
	•	modo de enlace (inherit/manual/auto)
	•	meeting_url final y datos técnicos (id/payload/status)

2.5 Video Call Profile

Qué es: perfil reutilizable para definir cómo se crea (o se pega) el enlace.
Campos: `profile_name` (reqd), `is_active`, `provider` (reqd), `link_mode` (reqd, default: manual_only), `provider_account` (condicional), `meeting_title_template` (condicional).
Responsabilidades lógicas:
	•	Proveedor (google_meet / microsoft_teams)
	•	Modo de enlace:
	•	manual_only (default)
	•	auto_generate
	•	auto_or_manual (con fallback manual)
	•	Sección de auto-configuración solo visible cuando link_mode !== 'manual_only'
	•	Cuenta (Provider Account) si auto

2.6 Provider Account

Qué es: credenciales OAuth para crear meetings por API.
Campos: `account_name`, `provider`, `status` (default: Pending), `client_id`, `client_secret` (Password), `access_token` (read_only), `refresh_token` (read_only), `token_expires_at`, `scopes`.
Secciones: "Credenciales OAuth", "Tokens" (read_only), "Guía de Configuración" (HTML con guías para Google Meet y Microsoft Teams).
Responsabilidades lógicas:
	•	Estado: Pending (default) / Connected / Expired / Revoked
	•	Guardar credenciales OAuth y tokens de forma segura
	•	Facilitar refresh token (si aplica)

⸻

3) Flujos principales (user journeys)

3.1 Crear/editar disponibilidad

Admin:
	1.	Crea Availability Plan y sus Availability Slots.
	2.	Asigna ese plan a uno o varios Calendar Resource.
	3.	Crea excepciones cuando sea necesario (Closed/Blocked/Extra).

Resultado: el sistema puede calcular “slots disponibles” para un rango de fechas.

⸻

3.2 Crear Appointment (con validación)
	1.	Usuario selecciona calendar_resource.
	2.	Define start_datetime y end_datetime (o start + duración).
	3.	Guarda en Draft.
	4.	Al confirmar/submit:
	•	Se valida disponibilidad + solapes
	•	Se resuelve la videollamada (auto o manual)
	•	Se completa meeting_url si aplica

⸻

3.3 Videollamada: manual vs automática

El modo se determina por `link_mode` del Video Call Profile vinculado.

Manual (`manual_only`)
	•	Usuario pega el enlace directamente en meeting_url.
	•	Se requiere antes de confirmar (submit).

Auto (`auto_generate`)
	•	En on_submit: se crea meeting vía adapter (factory pattern).
	•	Se llena meeting_url, meeting_id, meeting_status.

Auto o Manual (`auto_or_manual`)
	•	Si meeting_url ya tiene valor, se usa tal cual.
	•	Si no, se crea automáticamente en on_submit.

⸻

4) Reglas de negocio (normas del sistema)

4.1 Reglas de disponibilidad

Para que un Appointment sea válido, el rango [start_datetime, end_datetime) debe:
	1.	Caer completamente dentro de una franja disponible del día (Availability Slots del weekday).
	2.	No estar bloqueado por excepciones Closed o Blocked en esa fecha/rango.
	3.	Puede ser habilitado extra si existe Extra Availability que lo cubra.

Notas:
	•	Si hay múltiples slots ese día, basta con que el rango quepa en alguno (o en combinación solo si lo soportas; recomendado: debe caber en un solo slot para evitar citas “partidas”).
	•	Manejar timezone consistentemente: ideal almacenar y comparar en timezone del Calendar Resource.

4.2 Reglas de solapamiento (overlap)

Definir “citas activas” como aquellas con status in (Draft, Confirmed) o solo Confirmed según tu política.

Recomendación:
	•	Bloquear solapes para Confirmed.
	•	Para Draft, puedes permitir solapes y validar fuerte al confirmar.

Capacidad
	•	Si capacity = 1: no se permite overlap.
	•	Si capacity > 1: se permite overlap hasta N citas simultáneas.

4.3 Reglas de duración/slots
	•	Si slot_duration_minutes existe, se recomienda que:
	•	start_datetime y end_datetime respeten esa granularidad (por ejemplo, múltiplos de 30min).
	•	Si no quieres restringir, omite esta regla.

⸻

5) Arquitectura de implementación (cómo organizar el código)

5.1 Estructura sugerida

En tu app Frappe (ej. my_app):
my_app/my_app/doctype/appointment/appointment.py
my_app/my_app/doctype/calendar_resource/calendar_resource.py
my_app/my_app/doctype/calendar_exception/calendar_exception.py
my_app/my_app/doctype/video_call_profile/video_call_profile.py
my_app/my_app/doctype/provider_account/provider_account.py

my_app/my_app/scheduling/
  availability.py
  overlap.py
  slots.py

my_app/my_app/video_calls/
  base.py
  google_meet.py
  microsoft_teams.py
  factory.py

  5.2 Servicios (separar lógica del DocType)
	•	availability.py: calcular disponibilidad efectiva
	•	overlap.py: detectar colisiones considerando capacidad
	•	slots.py: generar slots disponibles para UI
	•	video_calls/*: crear/update/cancel meetings

⸻

6) Hooks y eventos Frappe (qué va dónde)

6.1 Appointment (clave)

validate
	•	Validar consistencia básica:
	•	start < end
	•	timezone normalizada
	•	slot granularity (si aplica)
	•	Resolver video_call_profile snapshot si está vacío:
	•	si Appointment.video_call_profile vacío -> tomar de Calendar Resource
before_submit / on_submit (recomendado on_submit)
	•	Validación fuerte final:
	•	disponibilidad efectiva
	•	overlaps según capacidad y status
	•	Crear videollamada según link_mode del Video Call Profile:
	•	manual_only: exigir meeting_url ya llenado
	•	auto_generate: crear vía adapter
	•	auto_or_manual: si meeting_url vacío, crear vía adapter

on_cancel
	•	Si meeting fue creado por API:
	•	opcional: adapter.delete_meeting(...) o marcar cancelado sin borrar en proveedor.
	•	Marcar status Cancelled.

6.2 Calendar Exception / Availability Plan

Normalmente solo CRUD, sin lógica pesada.
Pero puedes:
	•	Validar que start_time < end_time en excepciones parciales.
	•	Validar no solapes absurdos dentro del mismo plan (opcional).

⸻

7) Cálculo de disponibilidad efectiva (algoritmo)

Entrada
	•	calendar_resource
	•	date o rango de fechas

Pasos (por cada día)
	1.	Obtener slots del plan por weekday.
	2.	Convertir slots a intervalos [start_datetime, end_datetime) del día.
	3.	Obtener excepciones del calendario para esa fecha:
	•	Closed → elimina intervalos (o recorta si parcial)
	•	Blocked → elimina/recorta intervalos
	•	Extra Availability → agrega intervalos
	4.	Normalizar y merge intervalos (unificar overlaps/adyacentes).
	5.	Resultado: lista final de intervalos disponibles.

Resultado
	•	Intervalos disponibles del día
	•	De ahí generas slots discretos según slot_duration_minutes

⸻

8) Solapes (overlap) — consulta recomendada

Para detectar overlap de un rango [start, end) con otros appointments:

Condición de overlap estándar
	•	Existe overlap si: other.start < end AND other.end > start

Filtrar por
	•	calendar_resource = X
	•	status in (...)
	•	name != current_doc.name

Capacidad
	•	Si capacity=1: si existe cualquiera → bloquea
	•	Si capacity>1:
	•	cuenta cuántos se solapan y compara con capacity

⸻

9) Videollamadas — diseño “Adapter” (muy recomendado)

9.1 Interfaz base

Crear un contrato único:
	•	create_meeting(profile, appointment) -> {meeting_url, meeting_id, payload}
	•	update_meeting(profile, appointment) -> {…} (opcional)
	•	delete_meeting(profile, appointment) -> bool (opcional)

9.2 Factory

factory.get_adapter(profile.provider) devuelve:
	•	GoogleMeetAdapter
	•	TeamsAdapter

9.3 Reglas para crear link

El modo se lee del `link_mode` del Video Call Profile vinculado al Appointment.

Auto (`auto_generate`)
	•	Requiere provider_account conectada y con tokens válidos
	•	Si provider_account.status != Connected → falla
	•	Si falla → lanzar error y marcar meeting_status=failed

Manual (`manual_only`)
	•	Exigir meeting_url ya llenado antes de submit

Auto o Manual (`auto_or_manual`)
	•	Si meeting_url ya tiene valor, se usa
	•	Si no, se crea automáticamente vía adapter

9.4 Idempotencia (evitar duplicados)
	•	Si meeting_id ya existe y meeting_status=created, no volver a crear.
	•	Para llamadas API, usa appointment.name como “external id” si el proveedor lo permite.

⸻

10) Permisos y roles (mínimo viable)

Define roles sugeridos:
	•	Scheduling Admin
	•	CRUD en Calendar Resource, Availability Plan, Exceptions, Video Call Profiles, Provider Accounts
	•	Scheduler / Staff
	•	CRUD en Appointment (según reglas)
	•	NO acceso a tokens/Provider Account
	•	Read-only / Viewer
	•	ver agendas y citas

Importante: Provider Account debe estar muy restringido (tokens encriptados + permisos).

⸻

11) API endpoints recomendados (whitelisted)

Para frontend/UI o integración:
	1.	get_available_slots(calendar_resource, from_date, to_date)

	•	Devuelve slots discretos: [{start, end, capacity_remaining}]

	2.	validate_appointment(calendar_resource, start, end, appointment_name=None)

	•	Devuelve ok/errores, útil para UI antes de guardar.

	3.	generate_meeting(appointment_name)

	•	Para generación manual o reintentos tras falla.

⸻

12) Estados y obligatoriedad de campos

Recomendación práctica:
	•	Draft
	•	Permitir crear sin meeting_url
	•	No generar meeting todavía
	•	Confirmed/Submitted
	•	Debe estar validado:
	•	disponibilidad
	•	no solapes
	•	Videollamada:
	•	si manual_only → meeting_url requerido
	•	si auto → debe quedar meeting_status=created

⸻

13) Casos borde que deben definirse
	1.	Excepción Closed todo el día vs slots del plan → disponibilidad = 0
	2.	Excepción Blocked parcial recorta slot (08–12 con bloqueo 10–11 => 08–10 y 11–12)
	3.	Extra Availability puede crear franjas fuera del plan
	4.	Timezone: citas cruzando medianoche (ideal: no permitir o manejar con cuidado)
	5.	Cambio de hora en una cita ya creada con meeting:
	•	opción simple: cancelar meeting viejo + crear nuevo
	6.	Capacidad: 2 citas simultáneas, tercera debe fallar
	7.	Draft overlap: decide si bloqueas o no en Draft

⸻

14) Plan de pruebas (mínimo)

Unit tests (lógica pura)
	•	availability: plan + excepciones (closed/blocked/extra)
	•	overlap: capacity=1 y capacity>1
	•	slot generation: respeta slot_duration_minutes

Integration tests (DocType)
	•	Crear Appointment válido -> submit -> meeting auto (mock adapter)
	•	Falla provider -> fallback manual permitido
	•	Cancelación -> meeting delete (mock) o status update

⸻

15) “Definition of Done” para el equipo

Está listo cuando:
	•	Se puede consultar disponibilidad y crear citas sin solapes.
	•	Excepciones funcionan y se reflejan en slots disponibles.
	•	Video call funciona en los tres escenarios:
	•	auto_generate
	•	manual_only
	•	auto_or_manual con fallback
	•	Logs/errores claros: errores se registran vía frappe.log_error.
	•	Tokens protegidos y permisos aplicados.

⸻

16) Bloqueo de Slots con Drafts (Implementación actual)

El sistema implementa bloqueo de slots mediante Drafts con expiración:

16.1 Flujo de bloqueo:
	1.	Usuario crea Draft → se calcula draft_expires_at (default: 15 minutos)
	2.	El Draft bloquea el slot para otros usuarios (cuenta como ocupado en capacity)
	3.	Si intenta crear otro Draft en el mismo horario y no hay capacidad → ERROR
	4.	Si el usuario no confirma a tiempo:
		a.	Al intentar submit: ERROR "Esta reserva expiró hace X minutos"
		b.	Task automático (cada 15 min): marca Drafts expirados como Cancelled

16.2 Validaciones en validate():
	•	calendar_resource requerido
	•	start_datetime < end_datetime
	•	Si capacity excedida → BLOQUEAR (no solo warning)
	•	Calcular draft_expires_at si es Draft nuevo

16.3 Validaciones en on_submit():
	•	Verificar que Draft no haya expirado
	•	Validar disponibilidad según plan
	•	Validar overlaps estricto
	•	Crear meeting si corresponde

16.4 Task de limpieza (cron cada 15 min):
	•	Busca Drafts con draft_expires_at < now()
	•	Los marca como Cancelled automáticamente
	•	Agrega comment explicativo

⸻

17) Integración con Service Portal

17.1 Campos relevantes:
	•	user_contact (Link → User Contact): Usuario que agenda la reunión
	•	calendar_resource: Recurso del portal configurado

17.2 Flujo desde Service Portal:
	1.	Frontend obtiene portal configuration
	2.	Si request_contact_user_data = true → crea User Contact
	3.	Obtiene slots disponibles: GET get_available_slots(calendar_resource, from, to)
	4.	Crea Appointment en Draft con user_contact = User Contact creado
	5.	Usuario confirma → submit Appointment

⸻

18) Recomendación para trabajar con Claude (para tu equipo)

Cuando vayas a pedirle a Claude que escriba código, pásale:
	•	Este documento
	•	Los nombres exactos de tus DocTypes y fieldnames
	•	Tu decisión sobre:
	•	¿validar overlaps en Draft o solo al Confirmar? → IMPLEMENTADO: bloquea en Draft
	•	¿Submit vs Confirmed? → Usa submit, status cambia a Confirmed
	•	¿actualizar meeting si cambia hora o recrear? → Re-crear meeting
