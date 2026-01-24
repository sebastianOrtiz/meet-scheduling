# Copyright (c) 2026, Sebastian Ortiz Valencia and contributors
# For license information, please see license.txt

"""
Calendar Exception DocType

Override de disponibilidad para fechas específicas:
- Closed: Cierra todo el día o un rango
- Blocked: Bloquea un rango
- Extra Availability: Agrega disponibilidad adicional
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, get_time
from datetime import time, timedelta


class CalendarException(Document):
	"""
	Calendar Exception with validations.

	Validations:
	- calendar_resource required
	- exception_type required
	- date required
	- start_time < end_time (if both present)
	- Extra Availability requires start_time and end_time
	- Warn on duplicate exceptions for same date/resource
	"""

	def validate(self) -> None:
		"""
		Validación antes de guardar.
		"""
		self._validate_required_fields()
		self._validate_times()
		self._validate_extra_availability()
		self._check_duplicate_exceptions()

	def _validate_required_fields(self) -> None:
		"""Valida campos requeridos."""
		if not self.calendar_resource:
			frappe.throw(_("Calendar Resource es requerido"))

		if not self.exception_type:
			frappe.throw(_("Exception Type es requerido"))

		if not self.date:
			frappe.throw(_("Date es requerido"))

	def _validate_times(self) -> None:
		"""Valida que start_time < end_time si ambos están presentes."""
		if self.start_time and self.end_time:
			start = self._to_time(self.start_time)
			end = self._to_time(self.end_time)

			if start >= end:
				frappe.throw(
					_(f"Start Time ({start.strftime('%H:%M')}) debe ser menor que End Time ({end.strftime('%H:%M')})")
				)

	def _validate_extra_availability(self) -> None:
		"""
		Valida que Extra Availability tenga start_time y end_time.
		No tiene sentido agregar disponibilidad extra sin especificar el rango.
		"""
		if self.exception_type == "Extra Availability":
			if not self.start_time:
				frappe.throw(_("Extra Availability requiere Start Time"))
			if not self.end_time:
				frappe.throw(_("Extra Availability requiere End Time"))

	def _check_duplicate_exceptions(self) -> None:
		"""
		Advierte si ya existe una excepción para el mismo día y recurso.
		No bloquea, solo informa, porque pueden haber múltiples bloqueos parciales.
		"""
		if not self.calendar_resource or not self.date:
			return

		filters = {
			"calendar_resource": self.calendar_resource,
			"date": self.date,
			"name": ["!=", self.name] if self.name else ["is", "set"]
		}

		existing = frappe.get_all(
			"Calendar Exception",
			filters=filters,
			fields=["name", "exception_type", "start_time", "end_time"]
		)

		if existing:
			# Si es Closed todo el día y ya hay excepciones, advertir
			if self.exception_type == "Closed" and not self.start_time and not self.end_time:
				frappe.msgprint(
					_(f"Ya existen {len(existing)} excepción(es) para {self.calendar_resource} en {self.date}. "
					  f"Esta excepción 'Closed' sin horario cerrará todo el día."),
					indicator="orange",
					alert=True
				)
			else:
				# Verificar si hay overlap con excepciones existentes
				if self.start_time and self.end_time:
					new_start = self._to_time(self.start_time)
					new_end = self._to_time(self.end_time)

					for exc in existing:
						if exc.start_time and exc.end_time:
							exc_start = self._to_time(exc.start_time)
							exc_end = self._to_time(exc.end_time)

							# Verificar overlap
							if new_start < exc_end and new_end > exc_start:
								frappe.msgprint(
									_(f"Esta excepción ({new_start.strftime('%H:%M')}-{new_end.strftime('%H:%M')}) "
									  f"se solapa con {exc.name} ({exc_start.strftime('%H:%M')}-{exc_end.strftime('%H:%M')})"),
									indicator="orange",
									alert=True
								)

	def _to_time(self, time_value) -> time:
		"""
		Convierte diferentes formatos de tiempo a datetime.time.
		"""
		if isinstance(time_value, time):
			return time_value
		elif isinstance(time_value, timedelta):
			from datetime import datetime
			return (datetime.min + time_value).time()
		elif isinstance(time_value, str):
			return get_time(time_value)
		else:
			return get_time(time_value)
