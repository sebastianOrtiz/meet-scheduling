"""
Overlap Detection Service

Detects scheduling conflicts (overlaps) between appointments,
considering:
- Calendar Resource capacity
- Appointment status (Draft, Confirmed)
- Draft expiration
"""

import frappe
from frappe.utils import now_datetime, get_datetime
from datetime import datetime
from typing import Dict, List, Optional, Any


def check_overlap(
	calendar_resource: str,
	start_datetime: datetime,
	end_datetime: datetime,
	exclude_appointment: Optional[str] = None
) -> Dict[str, Any]:
	"""
	Detecta overlaps con appointments existentes.

	Args:
		calendar_resource: nombre del Calendar Resource
		start_datetime: inicio del rango a validar
		end_datetime: fin del rango a validar
		exclude_appointment: nombre del Appointment a excluir (para ediciones)

	Returns:
		dict: {
			"has_overlap": bool,
			"overlapping_appointments": [list of appointment names],
			"capacity_exceeded": bool,
			"capacity_used": int,
			"capacity_available": int
		}

	Algoritmo:
		1. Obtener capacity del calendar_resource
		2. Consultar appointments con:
			- calendar_resource = X
			- status in ("Draft", "Confirmed")
			- (start < end_datetime AND end > start_datetime)
			- name != exclude_appointment
		3. Filtrar Drafts expirados
		4. Contar overlaps
		5. Comparar con capacity
		6. Retornar resultado
	"""
	# 1. Obtener capacity del Calendar Resource
	resource = frappe.get_doc("Calendar Resource", calendar_resource)
	capacity = resource.capacity or 1

	# 2. Consultar appointments que se solapan
	# Condición de overlap: start < end_datetime AND end > start_datetime
	filters = {
		"calendar_resource": calendar_resource,
		"status": ["in", ["Draft", "Confirmed"]],
		"start_datetime": ["<", end_datetime],
		"end_datetime": [">", start_datetime]
	}

	# Excluir appointment si se especifica (para ediciones)
	if exclude_appointment:
		filters["name"] = ["!=", exclude_appointment]

	appointments = frappe.get_all(
		"Appointment",
		filters=filters,
		fields=["name", "status", "draft_expires_at", "start_datetime", "end_datetime"]
	)

	# 3. Filtrar Drafts expirados
	current_time = now_datetime()
	active_appointments = []

	for appt in appointments:
		# Si es Draft, verificar si ha expirado
		if appt.status == "Draft":
			if appt.draft_expires_at:
				# Si tiene fecha de expiración y ya pasó, ignorar
				expires_at = get_datetime(appt.draft_expires_at)
				if expires_at < current_time:
					continue
			# Si es Draft sin fecha de expiración, incluir

		# Appointment activo (Confirmed o Draft no expirado)
		active_appointments.append(appt.name)

	# 4. Contar overlaps
	overlap_count = len(active_appointments)
	has_overlap = overlap_count > 0
	capacity_exceeded = overlap_count >= capacity
	capacity_used = overlap_count
	capacity_available = max(0, capacity - overlap_count)

	# 5. Retornar resultado
	return {
		"has_overlap": has_overlap,
		"overlapping_appointments": active_appointments,
		"capacity_exceeded": capacity_exceeded,
		"capacity_used": capacity_used,
		"capacity_available": capacity_available
	}
