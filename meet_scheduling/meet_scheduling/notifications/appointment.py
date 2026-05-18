# Copyright (c) 2026, Sebastian Ortiz Valencia and contributors
# For license information, please see license.txt

"""
Appointment Notification Service

Sends email notifications for appointment lifecycle events:
- confirmed: appointment was confirmed
- cancelled: appointment was cancelled
- rescheduled: appointment date/time changed
- reminder: scheduled reminder before the appointment

Supports extensibility via hooks:
  - appointment_email_context: add template variables
  - appointment_email_recipients: add extra recipients
"""

import frappe
from frappe import _
from frappe.utils import format_datetime, get_url
from common_configurations.api.shared import has_outgoing_email, send_email


EVENT_CONFIG = {
	"confirmed": {
		"template": "appointment_confirmed",
		"subject_template": "[Cita Confirmada] {contact_name} | {resource_name} – {when}",
	},
	"cancelled": {
		"template": "appointment_cancelled",
		"subject_template": "[Cita Cancelada] {contact_name} | {resource_name} – {when}",
	},
	"rescheduled": {
		"template": "appointment_rescheduled",
		"subject_template": "[Cita Reagendada] {contact_name} | {resource_name} – {when}",
	},
	"reminder": {
		"template": "appointment_reminder",
		"subject_template": "[Recordatorio] {contact_name} | {resource_name} – {when}",
	},
}


def send_appointment_notification(
	appointment_name: str,
	event_type: str = "confirmed",
	previous_start_datetime: str = None,
	previous_end_datetime: str = None,
) -> None:
	"""
	Build and send an appointment notification email for a lifecycle event.

	Runs as a background job so on_submit/on_cancel hooks have committed
	before this function queries the DB.

	Args:
		appointment_name: Name of the Appointment document
		event_type: One of: confirmed, cancelled, rescheduled, reminder
		previous_start_datetime: Original start (only for rescheduled)
		previous_end_datetime: Original end (only for rescheduled)
	"""
	if event_type not in EVENT_CONFIG:
		frappe.logger().error(f"Unknown event_type for notification: {event_type}")
		return

	try:
		if not has_outgoing_email():
			frappe.logger().warning(
				f"Appointment notification ({event_type}) skipped for {appointment_name}: "
				"no outgoing Email Account configured."
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

		recipients = list({r for r in recipients if r})

		if not recipients:
			frappe.logger().info(
				f"No notification recipients for appointment {appointment_name} ({event_type})"
			)
			return

		# --- Base template context ---
		contact_name = frappe.db.get_value(
			"User contact", appointment.user_contact, "full_name"
		) or appointment.user_contact

		site_url = get_url()
		appointment_url = f"{site_url}/app/appointment/{appointment.name}"

		context = {
			"event_type": event_type,
			"appointment_name": appointment.name,
			"appointment_url": appointment_url,
			"contact_name": contact_name,
			"calendar_resource": resource.resource_name,
			"start_datetime": format_datetime(appointment.start_datetime, "EEEE d 'de' MMMM yyyy, HH:mm"),
			"end_datetime": format_datetime(appointment.end_datetime, "HH:mm"),
			"meeting_url": appointment.meeting_url or "",
			"appointment_context": appointment.appointment_context or "",
			# fields populated by lex_app / logbook hooks if installed
			"case_log_name": None,
			"case_log_title": None,
			"assigned_lawyer_name": None,
			"case_log_url": None,
			"logbook_entry_name": None,
			"logbook_entry_title": None,
			"logbook_entry_assigned_to_name": None,
			"logbook_entry_url": None,
		}

		# For rescheduled, include previous datetime
		if event_type == "rescheduled":
			context["previous_start_datetime"] = (
				format_datetime(previous_start_datetime, "EEEE d 'de' MMMM yyyy, HH:mm")
				if previous_start_datetime else ""
			)
			context["previous_end_datetime"] = (
				format_datetime(previous_end_datetime, "HH:mm")
				if previous_end_datetime else ""
			)

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

		# --- Build subject ---
		event_cfg = EVENT_CONFIG[event_type]
		when_str = format_datetime(appointment.start_datetime, "EEE d MMM yyyy, HH:mm")
		subject = _(event_cfg["subject_template"]).format(
			contact_name=contact_name,
			resource_name=resource.resource_name,
			when=when_str,
		)
		if context.get("case_log_name"):
			subject += _(" | Caso {0}").format(context["case_log_name"])
		elif context.get("logbook_entry_name"):
			subject += _(" | Bitácora {0}").format(context["logbook_entry_name"])

		# --- Send email ---
		send_email(
			recipients=recipients,
			subject=subject,
			template=event_cfg["template"],
			args=context,
			reference_doctype="Appointment",
			reference_name=appointment.name,
			log_title=f"Appointment Notification Failed ({event_type})",
		)

	except Exception as e:
		frappe.log_error(
			message=f"Failed to send appointment notification ({event_type}) for {appointment_name}: {str(e)}",
			title="Appointment Notification Failed"
		)
