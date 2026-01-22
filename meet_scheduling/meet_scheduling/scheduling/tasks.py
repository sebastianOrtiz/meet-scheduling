"""
Scheduled Tasks

Background tasks that run periodically:
- cleanup_expired_drafts: Cancels expired Draft appointments
"""

import frappe
from frappe.utils import now_datetime


def cleanup_expired_drafts() -> int:
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

	Returns:
		int: Cantidad de drafts expirados
	"""
	current_time = now_datetime()

	# 1. Buscar Drafts expirados
	# Nota: Solo busca drafts con draft_expires_at < current_time AND draft_expires_at IS NOT NULL
	# Los drafts sin draft_expires_at (NULL) no serán procesados
	expired_drafts = frappe.db.sql("""
		SELECT name, calendar_resource, start_datetime, end_datetime
		FROM `tabAppointment`
		WHERE status = 'Draft'
		AND docstatus = 0
		AND draft_expires_at IS NOT NULL
		AND draft_expires_at < %s
	""", (current_time,), as_dict=True)

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

			# Agregar comment automático
			appointment.add_comment(
				"Info",
				f"Draft expirado automáticamente (expiró: {appointment.draft_expires_at})"
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
