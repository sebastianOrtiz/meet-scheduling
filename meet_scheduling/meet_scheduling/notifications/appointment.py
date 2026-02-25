# Copyright (c) 2026, Sebastian Ortiz Valencia and contributors
# For license information, please see license.txt

"""
Appointment Notification Service

Sends email notifications when an appointment is confirmed.
Supports extensibility via hooks:
  - appointment_email_context: add template variables
  - appointment_email_recipients: add extra recipients
"""

import frappe
from frappe import _
from frappe.utils import format_datetime, get_url


def has_outgoing_email() -> bool:
	"""Return True if at least one outgoing Email Account is configured in Frappe."""
	return bool(frappe.db.count("Email Account", {"enable_outgoing": 1}))


def send_appointment_notification(appointment_name: str) -> None:
	"""
	Build and send the appointment confirmation email.

	Runs as a background job (enqueue_after_commit=True) so that all
	on_submit hooks (including lex_app's Case Log creation) have
	already committed before this function queries the DB.

	Args:
		appointment_name: Name of the confirmed Appointment document
	"""
	try:
		if not has_outgoing_email():
			frappe.logger().warning(
				f"Appointment notification skipped for {appointment_name}: "
				"no outgoing Email Account configured in Frappe. "
				"Go to Email Account and enable an outgoing account."
			)
			return

		appointment = frappe.get_doc("Appointment", appointment_name)
		resource = frappe.get_doc("Calendar Resource", appointment.calendar_resource)

		if not resource.send_email_notification:
			return

		# --- Base recipients from notification_users table ---
		recipients = [
			row.user
			for row in resource.notification_users
			if row.is_active and row.user
		]

		# --- Additional recipients from other apps ---
		for hook_path in frappe.get_hooks("appointment_email_recipients"):
			try:
				extra = frappe.get_attr(hook_path)(appointment)
				if extra:
					recipients.extend(extra)
			except Exception:
				frappe.log_error(
					f"Error in appointment_email_recipients hook: {hook_path}",
					"Appointment Notification"
				)

		# Deduplicate and remove empty
		recipients = list({r for r in recipients if r})

		if not recipients:
			frappe.logger().info(
				f"No notification recipients for appointment {appointment_name}, skipping email."
			)
			return

		# --- Base template context ---
		contact_name = frappe.db.get_value(
			"User Contact", appointment.user_contact, "full_name"
		) or appointment.user_contact

		site_url = get_url()
		appointment_url = f"{site_url}/app/appointment/{appointment.name}"

		context = {
			"appointment_name": appointment.name,
			"appointment_url": appointment_url,
			"contact_name": contact_name,
			"calendar_resource": resource.resource_name,
			"start_datetime": format_datetime(appointment.start_datetime, "EEEE d 'de' MMMM yyyy, HH:mm"),
			"end_datetime": format_datetime(appointment.end_datetime, "HH:mm"),
			"meeting_url": appointment.meeting_url or "",
			"appointment_context": appointment.appointment_context or "",
			# case log fields (populated by lex_app hook if installed)
			"case_log_name": None,
			"case_log_title": None,
			"assigned_lawyer_name": None,
			"case_log_url": None,
		}

		# --- Enriched context from other apps ---
		for hook_path in frappe.get_hooks("appointment_email_context"):
			try:
				extra = frappe.get_attr(hook_path)(appointment)
				if extra:
					context.update(extra)
			except Exception:
				frappe.log_error(
					f"Error in appointment_email_context hook: {hook_path}",
					"Appointment Notification"
				)

		# --- Send email ---
		# Base: "[Cita Confirmada] Juan Pérez | Dr. Gómez – lun. 3 mar. 2026, 10:00"
		# With case log: "... | Caso CL-0042"
		subject = _("[Cita Confirmada] {0} | {1} – {2}").format(
			contact_name,
			resource.resource_name,
			format_datetime(appointment.start_datetime, "EEE d MMM yyyy, HH:mm"),
		)
		if context.get("case_log_name"):
			subject += _(" | Caso {0}").format(context["case_log_name"])
		frappe.sendmail(
			recipients=recipients,
			subject=subject,
			template="appointment_confirmed",
			args=context,
		)

		frappe.logger().info(
			f"Appointment notification sent for {appointment_name} to {recipients}"
		)

	except Exception as e:
		frappe.log_error(
			message=f"Failed to send appointment notification for {appointment_name}: {str(e)}",
			title="Appointment Notification Failed"
		)
