"""
Scheduled Tasks

Background tasks that run periodically:
- cleanup_expired_drafts: Cancels expired Draft appointments
"""

import frappe
from frappe.utils import now_datetime, add_to_date


DRAFT_FALLBACK_MAX_AGE_HOURS = 24


def cleanup_expired_drafts() -> int:
	"""
	Marca Drafts expirados como Cancelled automáticamente.
	Se ejecuta cada 15 minutos vía cron (configurado en hooks.py).

	Reglas de "expirado":
		1. Tiene draft_expires_at y ya pasó.
		2. NO tiene draft_expires_at y su start_datetime ya pasó (cita perdida).
		3. NO tiene draft_expires_at y fue creado hace más de
		   DRAFT_FALLBACK_MAX_AGE_HOURS horas (draft abandonado).

	Returns:
		int: Cantidad de drafts expirados
	"""
	current_time = now_datetime()
	fallback_cutoff = add_to_date(current_time, hours=-DRAFT_FALLBACK_MAX_AGE_HOURS)

	# 1. Buscar Drafts expirados con cualquiera de las 3 condiciones
	expired_drafts = frappe.db.sql("""
		SELECT name, calendar_resource, start_datetime, end_datetime, draft_expires_at, creation
		FROM `tabAppointment`
		WHERE status = 'Draft'
		AND docstatus = 0
		AND (
			(draft_expires_at IS NOT NULL AND draft_expires_at < %(now)s)
			OR (draft_expires_at IS NULL AND start_datetime < %(now)s)
			OR (draft_expires_at IS NULL AND creation < %(fallback_cutoff)s)
		)
	""", {"now": current_time, "fallback_cutoff": fallback_cutoff}, as_dict=True)

	cancelled_count = 0

	# 2. Para cada Draft expirado, cancelar
	for draft_info in expired_drafts:
		try:
			# Obtener documento completo
			appointment = frappe.get_doc("Appointment", draft_info.name)

			# Verificar nuevamente que sigue siendo Draft (por si cambió durante query)
			if appointment.status != "Draft":
				continue

			# Cambiar status a Cancelled
			appointment.status = "Cancelled"

			# Agregar comment automático con la razón
			if appointment.draft_expires_at:
				reason = f"draft_expires_at: {appointment.draft_expires_at}"
			elif appointment.start_datetime and appointment.start_datetime < current_time:
				reason = f"start_datetime ya pasó: {appointment.start_datetime}"
			else:
				reason = f"draft abandonado por más de {DRAFT_FALLBACK_MAX_AGE_HOURS}h (creado: {appointment.creation})"

			appointment.add_comment(
				"Info",
				f"Draft expirado automáticamente ({reason})"
			)

			# Guardar sin validaciones adicionales
			appointment.save(ignore_permissions=True)

			cancelled_count += 1

			frappe.logger().info(
				f"Draft expirado cancelado: {appointment.name} "
				f"(Resource: {appointment.calendar_resource}, "
				f"Expiró: {appointment.draft_expires_at})"
			)

		except Exception as e:
			frappe.logger().error(
				f"Error al cancelar Draft expirado {draft_info.name}: {str(e)}"
			)
			# Continuar con los demás drafts
			continue

	# 3. Log cantidad de drafts expirados
	if cancelled_count > 0:
		frappe.logger().info(
			f"cleanup_expired_drafts: {cancelled_count} Drafts expirados cancelados"
		)

	# Commit de todos los cambios
	frappe.db.commit()

	return cancelled_count


REMINDER_LEAD_HOURS = 24
REMINDER_WINDOW_MINUTES = 60


def send_appointment_reminders() -> int:
	"""
	Envía emails de recordatorio para citas Confirmed que iniciarán
	aproximadamente en REMINDER_LEAD_HOURS horas.

	Se ejecuta cada hora vía cron. Usa una ventana de REMINDER_WINDOW_MINUTES
	para no perder citas si el scheduler falla por algunos minutos.

	Marca la cita con `reminder_sent_at` (campo no requerido — si no existe,
	se evita doble envío comparando contra una ventana corta).

	Returns:
		int: Cantidad de recordatorios enviados
	"""
	current_time = now_datetime()
	lead_start = add_to_date(current_time, hours=REMINDER_LEAD_HOURS)
	lead_end = add_to_date(lead_start, minutes=REMINDER_WINDOW_MINUTES)

	upcoming = frappe.db.sql("""
		SELECT name
		FROM `tabAppointment`
		WHERE status = 'Confirmed'
		AND start_datetime >= %(lead_start)s
		AND start_datetime < %(lead_end)s
	""", {"lead_start": lead_start, "lead_end": lead_end}, as_dict=True)

	sent_count = 0

	for appt_info in upcoming:
		try:
			# Encolar el envío del recordatorio
			frappe.enqueue(
				"meet_scheduling.meet_scheduling.notifications.appointment.send_appointment_notification",
				appointment_name=appt_info.name,
				event_type="reminder",
				queue="default",
			)
			sent_count += 1
		except Exception as e:
			frappe.logger().error(
				f"Error encolando recordatorio para {appt_info.name}: {str(e)}"
			)
			continue

	if sent_count > 0:
		frappe.logger().info(
			f"send_appointment_reminders: {sent_count} recordatorios encolados"
		)

	return sent_count


def auto_complete_past_appointments() -> int:
	"""
	Marca citas Confirmed cuya end_datetime ya pasó como Completed.

	Se ejecuta cada hora vía cron (configurado en hooks.py).

	Returns:
		int: Cantidad de citas marcadas como Completed
	"""
	current_time = now_datetime()

	past_confirmed = frappe.db.sql("""
		SELECT name
		FROM `tabAppointment`
		WHERE status = 'Confirmed'
		AND end_datetime < %s
	""", (current_time,), as_dict=True)

	completed_count = 0

	for appt_info in past_confirmed:
		try:
			appointment = frappe.get_doc("Appointment", appt_info.name)

			if appointment.status != "Confirmed":
				continue

			appointment.status = "Completed"
			appointment.add_comment(
				"Info",
				f"Marcada como Completed automáticamente (end_datetime: {appointment.end_datetime})"
			)
			appointment.save(ignore_permissions=True)

			completed_count += 1

		except Exception as e:
			frappe.logger().error(
				f"Error al auto-completar Appointment {appt_info.name}: {str(e)}"
			)
			continue

	if completed_count > 0:
		frappe.logger().info(
			f"auto_complete_past_appointments: {completed_count} citas marcadas como Completed"
		)

	frappe.db.commit()

	return completed_count
