"""
Appointment API Endpoints

Whitelisted functions for frontend/external use.
All public endpoints allow guest access with security protections:
- Rate limiting by IP address
- Honeypot validation for bot detection
- Input sanitization
"""

import frappe
from frappe import _
from frappe.utils import get_datetime, getdate, now_datetime
from typing import Dict, List, Any, Optional
import pytz

# Import scheduling services
from meet_scheduling.meet_scheduling.scheduling.slots import generate_available_slots
from meet_scheduling.meet_scheduling.scheduling.overlap import check_overlap
from meet_scheduling.meet_scheduling.scheduling.availability import get_availability_slots_for_day

# Import video call services
from meet_scheduling.meet_scheduling.video_calls.factory import get_adapter
from meet_scheduling.meet_scheduling.video_calls.base import VideoCallError

# Import security utilities
from meet_scheduling.api.security import (
    check_rate_limit,
    check_honeypot,
    validate_date_string,
    validate_datetime_string,
    validate_docname,
    sanitize_string,
    get_client_ip
)


@frappe.whitelist(allow_guest=True, methods=['GET'])
def get_active_calendar_resources() -> List[Dict[str, Any]]:
	"""
	Obtiene todos los Calendar Resources activos disponibles para agendar citas.

	Rate limited: 30 requests per minute per IP.

	Returns:
		List[Dict]: Lista de Calendar Resources activos con sus detalles

	Example Response:
		```json
		[
			{
				"name": "CR-00001",
				"resource_name": "Dr. Juan Pérez",
				"resource_type": "Person",
				"timezone": "America/Bogota",
				"slot_duration_minutes": 30,
				"capacity": 1,
				"video_call_profile": "VCP-00001"
			}
		]
		```
	"""
	# Rate limit check
	check_rate_limit("get_calendar_resources", limit=30, seconds=60)

	try:
		# Obtener Calendar Resources activos
		resources = frappe.get_all(
			"Calendar Resource",
			filters={"is_active": 1},
			fields=[
				"name",
				"resource_name",
				"resource_type",
				"timezone",
				"slot_duration_minutes",
				"capacity",
				"draft_expiration_minutes",
				"availability_plan",
				"video_call_profile"
			],
			order_by="resource_name asc"
		)

		return resources

	except Exception as e:
		frappe.log_error(f"Error getting calendar resources: {str(e)}")
		frappe.throw(_("Error al obtener recursos de calendario"))


@frappe.whitelist(allow_guest=True, methods=['GET'])
def get_available_slots(calendar_resource: str, from_date: str, to_date: str) -> List[Dict[str, Any]]:
	"""
	Obtiene slots disponibles para un rango de fechas.

	Este endpoint es usado por el frontend para mostrar slots disponibles
	en un calendario o lista.

	Rate limited: 30 requests per minute per IP.

	Args:
		calendar_resource: nombre del Calendar Resource
		from_date: fecha inicial (YYYY-MM-DD)
		to_date: fecha final (YYYY-MM-DD)

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

	Example:
		```javascript
		frappe.call({
			method: "meet_scheduling.meet_scheduling.api.appointment_api.get_available_slots",
			args: {
				calendar_resource: "Sebastian Ortiz",
				from_date: "2026-01-20",
				to_date: "2026-01-27"
			},
			callback: function(r) {
				console.log(r.message); // Array of available slots
			}
		});
		```
	"""
	# Rate limit check
	check_rate_limit("get_available_slots", limit=30, seconds=60)

	# Validate inputs
	calendar_resource = validate_docname(calendar_resource, "calendar_resource")
	from_date = validate_date_string(from_date, "from_date")
	to_date = validate_date_string(to_date, "to_date")

	try:
		# Validar que el Calendar Resource existe
		if not frappe.db.exists("Calendar Resource", calendar_resource):
			frappe.throw(_(f"Calendar Resource '{calendar_resource}' no existe"))

		# Validar fechas
		try:
			start_date = getdate(from_date)
			end_date = getdate(to_date)
		except Exception:
			frappe.throw(_("Formato de fecha inválido. Use YYYY-MM-DD"))

		if start_date > end_date:
			frappe.throw(_("from_date debe ser menor o igual que to_date"))

		# Generar slots usando el servicio
		slots = generate_available_slots(
			calendar_resource,
			start_date,
			end_date
		)

		return slots

	except Exception as e:
		frappe.log_error(f"Error in get_available_slots: {str(e)}", "API Error")
		frappe.throw(_(f"Error al obtener slots disponibles: {str(e)}"))


@frappe.whitelist(allow_guest=True, methods=['GET', 'POST'])
def validate_appointment(
	calendar_resource: str,
	start_datetime: str,
	end_datetime: str,
	appointment_name: Optional[str] = None
) -> Dict[str, Any]:
	"""
	Valida si un appointment es válido ANTES de guardarlo.
	Útil para UI/frontend para mostrar errores/warnings antes de submit.

	Rate limited: 20 requests per minute per IP.

	Args:
		calendar_resource: nombre del Calendar Resource
		start_datetime: inicio (YYYY-MM-DD HH:MM:SS)
		end_datetime: fin (YYYY-MM-DD HH:MM:SS)
		appointment_name: nombre del Appointment existente (para ediciones)

	Returns:
		dict: {
			"valid": bool,
			"errors": list[str],
			"warnings": list[str],
			"availability_ok": bool,
			"capacity_ok": bool,
			"overlap_info": dict
		}

	Example:
		```javascript
		frappe.call({
			method: "meet_scheduling.meet_scheduling.api.appointment_api.validate_appointment",
			args: {
				calendar_resource: "Sebastian Ortiz",
				start_datetime: "2026-01-20 10:00:00",
				end_datetime: "2026-01-20 11:00:00"
			},
			callback: function(r) {
				if (!r.message.valid) {
					frappe.msgprint(r.message.errors.join("<br>"));
				}
			}
		});
		```
	"""
	# Rate limit check
	check_rate_limit("validate_appointment", limit=20, seconds=60)

	errors = []
	warnings = []
	availability_ok = True
	capacity_ok = True
	overlap_info = {}

	try:
		# Validar que el Calendar Resource existe
		if not frappe.db.exists("Calendar Resource", calendar_resource):
			errors.append(_(f"Calendar Resource '{calendar_resource}' no existe"))
			return {
				"valid": False,
				"errors": errors,
				"warnings": warnings,
				"availability_ok": False,
				"capacity_ok": False,
				"overlap_info": {}
			}

		# Validar formato de fechas
		try:
			start = get_datetime(start_datetime)
			end = get_datetime(end_datetime)
		except Exception:
			errors.append(_("Formato de fecha inválido. Use YYYY-MM-DD HH:MM:SS"))
			return {
				"valid": False,
				"errors": errors,
				"warnings": warnings,
				"availability_ok": False,
				"capacity_ok": False,
				"overlap_info": {}
			}

		# Obtener timezone del resource para localizar los datetimes
		resource = frappe.get_doc("Calendar Resource", calendar_resource)
		tz_name = resource.timezone or "UTC"
		if tz_name == "system timezone":
			tz_name = frappe.utils.get_system_timezone()

		try:
			tz = pytz.timezone(tz_name)
		except Exception:
			tz = pytz.UTC

		# Localizar los datetimes si son naive (sin timezone)
		if start.tzinfo is None:
			start = tz.localize(start)
		if end.tzinfo is None:
			end = tz.localize(end)

		# Validar consistencia de fechas
		if start >= end:
			errors.append(_("Start DateTime debe ser menor que End DateTime"))

		# Validar disponibilidad
		date_only = start.date()
		availability_slots = get_availability_slots_for_day(
			calendar_resource,
			date_only
		)

		if not availability_slots:
			errors.append(_(f"No hay disponibilidad en {date_only.strftime('%Y-%m-%d')}"))
			availability_ok = False
		else:
			# Verificar que el appointment cae dentro de algún slot
			is_within_availability = False
			for slot in availability_slots:
				if slot["start"] <= start and slot["end"] >= end:
					is_within_availability = True
					break

			if not is_within_availability:
				errors.append(
					_(f"El horario {start.strftime('%H:%M')}-{end.strftime('%H:%M')} no está disponible")
				)
				availability_ok = False

		# Validar overlaps y capacity
		overlap_result = check_overlap(
			calendar_resource,
			start,
			end,
			exclude_appointment=appointment_name
		)

		overlap_info = overlap_result

		if overlap_result["has_overlap"]:
			overlapping = ", ".join(overlap_result["overlapping_appointments"])
			warnings.append(
				_(f"Este horario tiene {overlap_result['capacity_used']} appointments: {overlapping}")
			)

		if overlap_result["capacity_exceeded"]:
			errors.append(
				_(f"Capacidad excedida ({overlap_result['capacity_used']} appointments)")
			)
			capacity_ok = False

		# Validar slot granularity (warning)
		resource = frappe.get_doc("Calendar Resource", calendar_resource)
		slot_duration = resource.slot_duration_minutes or 30
		duration_minutes = (end - start).total_seconds() / 60

		if duration_minutes % slot_duration != 0:
			warnings.append(
				_(f"La duración ({duration_minutes} min) no es múltiplo de slot_duration ({slot_duration} min)")
			)

		# Determinar si es válido
		valid = len(errors) == 0

		return {
			"valid": valid,
			"errors": errors,
			"warnings": warnings,
			"availability_ok": availability_ok,
			"capacity_ok": capacity_ok,
			"overlap_info": overlap_info
		}

	except Exception as e:
		frappe.log_error(f"Error in validate_appointment: {str(e)}", "API Error")
		return {
			"valid": False,
			"errors": [_(f"Error al validar appointment: {str(e)}")],
			"warnings": [],
			"availability_ok": False,
			"capacity_ok": False,
			"overlap_info": {}
		}


@frappe.whitelist(allow_guest=True, methods=['POST'])
def create_and_confirm_appointment(
	calendar_resource: str,
	user_contact: str,
	start_datetime: str,
	end_datetime: str,
	appointment_context: Optional[str] = None,
	honeypot: Optional[str] = None
) -> Dict[str, Any]:
	"""
	Crea y confirma un appointment en una sola operación.

	Este endpoint:
	1. Crea el Appointment en estado Draft
	2. Hace submit (lo confirma)
	3. Retorna el documento confirmado

	Rate limited: 5 requests per minute per IP (write operation).
	Protected by honeypot field.

	Args:
		calendar_resource: nombre del Calendar Resource
		user_contact: nombre del User Contact
		start_datetime: inicio (YYYY-MM-DD HH:MM:SS)
		end_datetime: fin (YYYY-MM-DD HH:MM:SS)
		appointment_context: contexto adicional del appointment (opcional)
		honeypot: campo honeypot para detección de bots (debe estar vacío)

	Returns:
		dict: Appointment confirmado

	Example:
		```javascript
		frappe.call({
			method: "meet_scheduling.api.appointment_api.create_and_confirm_appointment",
			args: {
				calendar_resource: "Sebastian Ortiz",
				user_contact: "UC-00001",
				start_datetime: "2026-01-20 10:00:00",
				end_datetime: "2026-01-20 10:30:00",
				appointment_context: "Consulta sobre tema legal específico"
			},
			callback: function(r) {
				console.log("Appointment confirmado:", r.message);
			}
		});
		```
	"""
	# Security checks
	check_honeypot(honeypot)
	check_rate_limit("create_appointment", limit=5, seconds=60)

	# Validate and sanitize inputs
	calendar_resource = validate_docname(calendar_resource, "calendar_resource")
	user_contact = validate_docname(user_contact, "user_contact")
	start_datetime = validate_datetime_string(start_datetime, "start_datetime")
	end_datetime = validate_datetime_string(end_datetime, "end_datetime")
	if appointment_context:
		appointment_context = sanitize_string(appointment_context, 2000)

	try:
		# Validar que el Calendar Resource existe
		if not frappe.db.exists("Calendar Resource", calendar_resource):
			frappe.throw(_(f"Calendar Resource '{calendar_resource}' no existe"))

		# Validar que el User Contact existe
		if not frappe.db.exists("User contact", user_contact):
			frappe.throw(_(f"User contact '{user_contact}' no existe"))

		# Validar formato de fechas
		try:
			start = get_datetime(start_datetime)
			end = get_datetime(end_datetime)
		except Exception:
			frappe.throw(_("Formato de fecha inválido. Use YYYY-MM-DD HH:MM:SS"))

		# Validar disponibilidad
		validation_result = validate_appointment(
			calendar_resource,
			start_datetime,
			end_datetime
		)

		if not validation_result["valid"]:
			frappe.throw(_("Appointment no válido: ") + ", ".join(validation_result["errors"]))

		# Crear Appointment en Draft
		appointment = frappe.get_doc({
			"doctype": "Appointment",
			"calendar_resource": calendar_resource,
			"user_contact": user_contact,
			"start_datetime": start_datetime,
			"end_datetime": end_datetime,
			"status": "Draft",
			"appointment_context": appointment_context or ""
		})

		# Guardar
		appointment.insert(ignore_permissions=True)

		# Submit (confirmar)
		appointment.submit()

		frappe.db.commit()

		# Retornar el documento completo
		return appointment.as_dict()

	except Exception as e:
		frappe.log_error(f"Error in create_and_confirm_appointment: {str(e)}", "API Error")
		frappe.throw(_(f"Error al crear appointment: {str(e)}"))


@frappe.whitelist()
def cancel_or_delete_appointment(appointment_name: str) -> Dict[str, Any]:
	"""
	Cancela o elimina un appointment según su estado.

	- Si está en Draft (docstatus=0): lo elimina
	- Si está Submitted (docstatus=1): lo cancela (docstatus=2)
	- Si ya está cancelado: retorna error

	Args:
		appointment_name: nombre del Appointment

	Returns:
		dict: {
			"success": bool,
			"action": "deleted" | "cancelled",
			"message": str
		}

	Example:
		```javascript
		frappe.call({
			method: "meet_scheduling.api.appointment_api.cancel_or_delete_appointment",
			args: {
				appointment_name: "APT-00001"
			},
			callback: function(r) {
				console.log(r.message);
			}
		});
		```
	"""
	try:
		# Validar que existe
		if not frappe.db.exists("Appointment", appointment_name):
			frappe.throw(_(f"Appointment '{appointment_name}' no existe"))

		# Obtener el appointment
		appointment = frappe.get_doc("Appointment", appointment_name)

		# Determinar acción según docstatus
		if appointment.docstatus == 0:
			# Draft - eliminar
			frappe.delete_doc("Appointment", appointment_name, ignore_permissions=True)
			frappe.db.commit()
			return {
				"success": True,
				"action": "deleted",
				"message": _("Appointment eliminado exitosamente")
			}
		elif appointment.docstatus == 1:
			# Submitted - cancelar
			appointment.cancel()
			frappe.db.commit()
			return {
				"success": True,
				"action": "cancelled",
				"message": _("Appointment cancelado exitosamente")
			}
		elif appointment.docstatus == 2:
			# Ya está cancelado
			return {
				"success": False,
				"action": "none",
				"message": _("El appointment ya está cancelado")
			}
		else:
			frappe.throw(_("Estado de documento inválido"))

	except Exception as e:
		frappe.log_error(f"Error in cancel_or_delete_appointment: {str(e)}", "API Error")
		frappe.throw(_(f"Error al cancelar/eliminar appointment: {str(e)}"))


@frappe.whitelist()
def generate_meeting(appointment_name: str) -> Dict[str, Any]:
	"""
	Genera meeting manualmente (cuando create_on = manual).

	Este endpoint permite generar meetings bajo demanda, por ejemplo:
	- Cuando el Video Call Profile tiene create_on = "manual"
	- Cuando se quiere re-generar un meeting después de submit

	Args:
		appointment_name: nombre del Appointment

	Returns:
		dict: {
			"success": bool,
			"meeting_url": str,
			"meeting_id": str,
			"status": str,
			"message": str
		}

	Example:
		```javascript
		frappe.call({
			method: "meet_scheduling.meet_scheduling.api.appointment_api.generate_meeting",
			args: {
				appointment_name: "APT-00001"
			},
			callback: function(r) {
				if (r.message.success) {
					frappe.msgprint(`Meeting creado: ${r.message.meeting_url}`);
				}
			}
		});
		```
	"""
	try:
		# Obtener Appointment
		if not frappe.db.exists("Appointment", appointment_name):
			frappe.throw(_(f"Appointment '{appointment_name}' no existe"))

		appointment = frappe.get_doc("Appointment", appointment_name)

		# Validar que está Confirmed
		if appointment.status != "Confirmed":
			frappe.throw(_("Solo se pueden generar meetings para appointments Confirmed"))

		# Validar que tiene video_call_profile
		if not appointment.video_call_profile:
			frappe.throw(_("El appointment no tiene Video Call Profile configurado"))

		# Obtener profile
		profile = frappe.get_doc("Video Call Profile", appointment.video_call_profile)

		# Validar que el profile permite generación manual
		if profile.create_on != "manual":
			frappe.throw(
				_(f"El Video Call Profile tiene create_on = '{profile.create_on}'. Solo se puede usar este endpoint con create_on = 'manual'")
			)

		# Obtener adapter
		adapter = get_adapter(profile.provider)

		# Validar perfil
		adapter.validate_profile(profile)

		# Crear meeting
		result = adapter.create_meeting(profile, appointment)

		# Actualizar appointment
		appointment.meeting_url = result.get("meeting_url")
		appointment.meeting_id = result.get("meeting_id")
		appointment.meeting_status = "created"
		appointment.video_provider = profile.provider
		appointment.meeting_created_at = now_datetime()
		appointment.provider_payload = frappe.as_json(result.get("provider_payload", {}))

		# Guardar sin triggers (para evitar loops)
		appointment.flags.ignore_validate = True
		appointment.save(ignore_permissions=True)

		frappe.db.commit()

		return {
			"success": True,
			"meeting_url": appointment.meeting_url,
			"meeting_id": appointment.meeting_id,
			"status": "Created",
			"message": _("Meeting generado exitosamente")
		}

	except VideoCallError as e:
		frappe.log_error(f"VideoCallError in generate_meeting: {str(e)}", "API Error")
		return {
			"success": False,
			"meeting_url": None,
			"meeting_id": None,
			"status": "Error",
			"message": _(f"Error al crear meeting: {str(e)}")
		}

	except Exception as e:
		frappe.log_error(f"Error in generate_meeting: {str(e)}", "API Error")
		return {
			"success": False,
			"meeting_url": None,
			"meeting_id": None,
			"status": "Error",
			"message": _(f"Error inesperado: {str(e)}")
		}
