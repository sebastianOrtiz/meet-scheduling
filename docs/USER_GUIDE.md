Guía de Usuario

Sistema de Agendamiento y Videollamadas

Esta guía explica cómo configurar y usar el sistema completo para agendar citas con disponibilidad, excepciones y enlaces de videollamada (automáticos o manuales).

⸻

Índice
	1.	Conceptos básicos
	2.	Configuración inicial (solo administradores)
	•	2.1 Provider Account (conectar cuentas)
	•	2.2 Video Call Profile (perfiles de llamada)
	•	2.3 Availability Plan y Availability Slots (horarios)
	•	2.4 Calendar Resource (calendarios)
	•	2.5 Calendar Exception (excepciones)
	3.	Uso diario
	•	3.1 Crear una cita (Appointment)
	•	3.2 Elegir modo de videollamada
	•	3.3 Confirmar la cita (Submit)
	•	3.4 Ver y compartir el enlace
	4.	Cambios y cancelaciones
	5.	Preguntas frecuentes (FAQ)
	6.	Solución de problemas comunes

⸻

1. Conceptos básicos
	•	Calendar Resource: Es la agenda que se reserva (persona, sala, equipo o servicio).
	•	Availability Plan: Horario semanal reutilizable (qué días y horas se atiende).
	•	Calendar Exception: Bloqueos o aperturas especiales por fecha.
	•	Appointment: La cita real que se agenda.
	•	Video Call Profile: Define cómo se genera (o se pega) el enlace de videollamada.
	•	Provider Account: Cuenta conectada a Google Meet o Microsoft Teams para generar enlaces automáticos.

⸻

2. Configuración inicial (Administradores)

2.1 Crear y conectar una cuenta de proveedor (Provider Account)

Menú: Provider Account → New

Campos principales:
	•	Account Name: Nombre identificador. Ej: Google - Consultas Dr. Gómez
	•	Provider: google_meet o microsoft_teams
	•	Owner User: Usuario que autoriza la conexión
	•	Auth Mode: oauth_user

Después de guardar, usa el botón de conexión (si está disponible) para autorizar la cuenta.

Resultado: esta cuenta permitirá crear reuniones automáticamente.

⸻

2.2 Crear perfiles de videollamada (Video Call Profile)

Menú: Video Call Profile → New

Campos importantes:
	•	Profile Name: Ej: Meet - Consultas (Auto)
	•	Provider: google_meet
	•	Link Mode:
	•	auto_generate: genera enlace automático
	•	manual_only: el usuario pega el enlace
	•	auto_or_manual: intenta automático, si falla permite manual
	•	Provider Account: (solo si es automático)
	•	Create On: on_submit (recomendado)

Opcional:
	•	Meeting Title Template: Consulta - {{ party_name }}
	•	Meeting Description Template: Tu cita es {{ start_datetime }}

Resultado: perfil listo para asignar a calendarios.

⸻

2.3 Crear horarios semanales (Availability Plan)

Menú: Availability Plan → New

Campos:
	•	Plan Name: Horario Consultorio 2026
	•	Is Active: activado

En la tabla de Availability Slots agrega filas como:
	•	Monday | 08:00 – 12:00
	•	Monday | 14:00 – 18:00
	•	Tuesday | 09:00 – 13:00

Resultado: defines los días y horas en que se puede agendar.

⸻

2.4 Crear calendarios (Calendar Resource)

Menú: Calendar Resource → New

Campos clave:
	•	Resource Name: Dr. Carlos Gómez - Consultas
	•	Resource Type: Person
	•	Timezone: America/Bogota
	•	Slot Duration (Minutes): 30
	•	Capacity: 1
	•	Availability Plan: selecciona el plan creado
	•	Video Call Profile: selecciona un perfil (opcional)
	•	Is Active: activado

Resultado: este calendario ya puede recibir citas.

⸻

2.5 Agregar excepciones (Calendar Exception)

Menú: Calendar Exception → New

Campos:
	•	Calendar Resource: el calendario afectado
	•	Exception Type:
	•	Closed: cierra todo el día
	•	Blocked: bloquea un rango
	•	Extra Availability: abre horas extra
	•	Date: fecha
	•	Start Time / End Time: (opcional)
	•	Reason: Ej: Junta médica

Resultado: el horario se ajusta automáticamente ese día.

⸻

3. Uso diario

3.1 Crear una cita (Appointment)

Menú: Appointment → New

Completa:
	•	Calendar Resource: agenda donde se reserva
	•	Start Datetime: inicio de la cita
	•	End Datetime: fin de la cita
	•	Party Type: Ej: Customer
	•	Party: cliente o paciente
	•	Notes: opcional
	•	Source: Web, Admin o API

Guarda. La cita queda en estado Draft.

⸻

3.2 Elegir modo de videollamada

Campos relevantes:
	•	Video Call Profile: se llena automáticamente desde el calendario
	•	Call Link Mode:
	•	inherit (recomendado)
	•	manual
	•	auto

Si eliges manual:
	•	pega el enlace en Manual Meeting URL

⸻

3.3 Confirmar la cita (Submit)

Cuando todo esté correcto:
	1.	Haz clic en Submit

El sistema:
	•	valida disponibilidad
	•	valida solapes
	•	genera el enlace automático (si aplica)
	•	copia enlace manual (si aplica)

Resultado: la cita queda confirmada y el horario bloqueado.

⸻

3.4 Ver y compartir el enlace

El enlace final siempre está en:
	•	Meeting URL

Este es el link que debes enviar al cliente.

⸻

4. Cambios y cancelaciones

Cancelar una cita
	1.	Abre el Appointment
	2.	Haz clic en Cancel

Resultado:
	•	el horario se libera
	•	opcionalmente se cancela la reunión en el proveedor

⸻

Reprogramar una cita (recomendado)
	1.	Cancela la cita original
	2.	Crea una nueva con la nueva fecha/hora
	3.	Confirma (Submit)

⸻

5. Preguntas frecuentes (FAQ)

¿Por qué no me deja guardar la cita?
	•	La hora no está dentro del horario disponible
	•	Hay una excepción bloqueando esa franja
	•	Hay otra cita ocupando ese horario

⸻

¿Por qué no se generó el enlace automático?

Posibles causas:
	•	La cuenta (Provider Account) está expirada o desconectada
	•	El perfil está en modo manual_only
	•	Falló la API del proveedor

Solución:
	•	Revisa el estado de la cuenta
	•	Cambia a modo manual y pega el enlace

⸻

¿Dónde está el enlace que debo enviar al cliente?

Siempre en el campo:

👉 Meeting URL

⸻

¿Puedo usar mi propio enlace de Meet o Teams?

Sí:
	•	Cambia Call Link Mode a manual
	•	Pega el enlace en Manual Meeting URL

⸻

¿Puedo permitir dos citas al mismo tiempo?

Sí:
	•	En Calendar Resource cambia Capacity a 2 o más

⸻

6. Solución de problemas comunes

Error: “No availability for selected time”
	•	Revisa Availability Plan
	•	Revisa Calendar Exception
	•	Verifica que la hora esté dentro del horario

⸻

Error: “Overlapping appointment”
	•	Ya existe una cita en ese rango
	•	Reduce capacidad o cambia horario

⸻

Error al crear meeting automático
	•	Revisa:
	•	Provider Account en estado Connected
	•	Tokens no expirados
	•	Permisos (scopes)

⸻

7. Buenas prácticas
	•	Usa siempre Submit para confirmar citas
	•	No edites citas confirmadas directamente: cancela y crea una nueva
	•	Mantén actualizadas las excepciones (festivos, vacaciones)
	•	Usa perfiles distintos para manual y automático

⸻

Fin de la guía