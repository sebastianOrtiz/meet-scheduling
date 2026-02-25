# Copyright (c) 2026, Sebastian Ortiz Valencia and contributors
# For license information, please see license.txt

"""
Appointment DocType

Manages appointment scheduling with video call integration.
"""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, add_to_date, get_datetime
from typing import Any

# Import scheduling services
from meet_scheduling.meet_scheduling.scheduling.overlap import check_overlap
from meet_scheduling.meet_scheduling.scheduling.availability import get_availability_slots_for_day

# Import video call services
from meet_scheduling.meet_scheduling.video_calls.factory import get_adapter
from meet_scheduling.meet_scheduling.video_calls.base import VideoCallError


class Appointment(Document):
	"""
	Appointment DocType with scheduling validation and video call integration.

	Flujo:
	1. Usuario crea Draft -> se bloquea el slot por X minutos (draft_expires_at)
	2. Si no confirma a tiempo, el Draft expira y se cancela automáticamente
	3. Al confirmar (submit), se valida disponibilidad y se crea meeting si aplica
	"""

	def validate(self) -> None:
		"""
		Validación antes de guardar.

		Ejecuta:
		1. Validar calendar_resource requerido
		2. Validar consistencia de fechas
		3. Resolver video_call_profile si está vacío
		4. Calcular draft_expires_at si es Draft nuevo
		5. Bloquear si capacity excedida (Draft bloquea slot)
		6. Validar slot granularity (warning)
		"""
		self._validate_calendar_resource()
		self._validate_datetime_consistency()
		self._resolve_video_call_profile()
		self._calculate_draft_expiration()
		self._validate_overlaps_and_block_if_exceeded()
		self._validate_slot_granularity()

	def on_submit(self) -> None:
		"""
		Validación fuerte y creación de meeting al confirmar.

		Ejecuta:
		1. Verificar que el Draft no haya expirado
		2. Validación fuerte de disponibilidad
		3. Validación fuerte de overlaps (bloquea si capacity exceeded)
		4. Crear meeting si corresponde
		5. Encolar notificación por email (asíncrono, tras commitear la transacción)
		"""
		self._validate_draft_not_expired()
		self._validate_availability_strict()
		self._validate_overlaps_strict()
		self._handle_meeting_creation()
		self.status = "Confirmed"
		self.db_set("status", "Confirmed", update_modified=False)
		self._enqueue_email_notification()

	def _enqueue_email_notification(self) -> None:
		"""Enqueue email notification and warn if outgoing email is not configured."""
		from meet_scheduling.meet_scheduling.notifications.appointment import has_outgoing_email

		resource = frappe.get_cached_doc("Calendar Resource", self.calendar_resource)
		if not resource.send_email_notification:
			return

		if not has_outgoing_email():
			frappe.msgprint(
				_(
					"La cita fue confirmada, pero <strong>no hay servidor de email saliente configurado</strong> "
					"en Frappe. No se enviará ninguna notificación.<br><br>"
					"Para habilitarlas ve a <a href='/app/email-account'>Email Account</a> "
					"y activa una cuenta con <em>Enable Outgoing</em>."
				),
				title=_("Notificación de email no enviada"),
				indicator="orange",
			)
			return

		frappe.enqueue(
			"meet_scheduling.meet_scheduling.notifications.appointment.send_appointment_notification",
			appointment_name=self.name,
			queue="default",
			enqueue_after_commit=True,
		)

	def on_cancel(self) -> None:
		"""
		Cancelación de appointment.

		Ejecuta:
		1. Opcionalmente eliminar meeting del proveedor
		2. Marcar status como Cancelled
		"""
		self._handle_meeting_deletion()
		self.status = "Cancelled"
		self.db_set("status", "Cancelled", update_modified=False)

	def on_update(self) -> None:
		"""
		Detecta cambios de horario y re-crea meetings automáticos.

		Según Decisión 3:
		- Si es auto: re-crear meeting con nuevo horario
		- Si es manual: mantener meeting_url existente
		"""
		self._handle_meeting_update_on_time_change()

	# ===== VALIDATION METHODS =====

	def _validate_calendar_resource(self) -> None:
		"""Valida que calendar_resource esté presente."""
		if not self.calendar_resource:
			frappe.throw(_("Calendar Resource es requerido"))

	def _validate_datetime_consistency(self) -> None:
		"""Valida que start_datetime < end_datetime."""
		if not self.start_datetime or not self.end_datetime:
			frappe.throw(_("Start DateTime y End DateTime son requeridos"))

		start = get_datetime(self.start_datetime)
		end = get_datetime(self.end_datetime)

		if start >= end:
			frappe.throw(_("Start DateTime debe ser menor que End DateTime"))

	def _resolve_video_call_profile(self) -> None:
		"""
		Resuelve video_call_profile desde Calendar Resource si está vacío.
		Si el perfil tiene default_meeting_url y la cita no tiene meeting_url, lo copia.
		"""
		if not self.video_call_profile and self.calendar_resource:
			resource = frappe.get_doc("Calendar Resource", self.calendar_resource)
			if resource.video_call_profile:
				self.video_call_profile = resource.video_call_profile

		# Copiar default_meeting_url del perfil si la cita no tiene uno
		if self.video_call_profile and not self.meeting_url:
			profile = frappe.get_cached_doc("Video Call Profile", self.video_call_profile)
			if profile.default_meeting_url:
				self.meeting_url = profile.default_meeting_url

	def _calculate_draft_expiration(self) -> None:
		"""
		Calcula draft_expires_at si status = Draft y es nuevo.

		Usa draft_expiration_minutes del Calendar Resource (default: 15 min).
		El Draft bloquea el slot hasta que expire o se confirme.
		"""
		# Solo calcular si es Draft y no tiene fecha de expiración
		if self.status == "Draft" and not self.draft_expires_at:
			resource = frappe.get_doc("Calendar Resource", self.calendar_resource)
			expiration_minutes = resource.draft_expiration_minutes or 15

			self.draft_expires_at = add_to_date(
				now_datetime(),
				minutes=expiration_minutes,
				as_datetime=True
			)

			frappe.msgprint(
				_(f"Este slot está reservado por {expiration_minutes} minutos. Confirme antes de que expire."),
				indicator="blue",
				alert=True
			)

	def _validate_overlaps_and_block_if_exceeded(self) -> None:
		"""
		Valida overlaps y BLOQUEA si la capacidad está excedida.

		Los Drafts activos (no expirados) bloquean slots para otros usuarios.
		Esto evita que dos usuarios reserven el mismo horario simultáneamente.
		"""
		if not self.calendar_resource or not self.start_datetime or not self.end_datetime:
			return

		overlap_result = check_overlap(
			self.calendar_resource,
			get_datetime(self.start_datetime),
			get_datetime(self.end_datetime),
			exclude_appointment=self.name if not self.is_new() else None
		)

		# Si hay overlap pero no excede capacidad, solo informar
		if overlap_result["has_overlap"] and not overlap_result["capacity_exceeded"]:
			overlapping = ", ".join(overlap_result["overlapping_appointments"])
			frappe.msgprint(
				_(f"Este horario tiene {overlap_result['capacity_used']} cita(s) existente(s). Capacidad disponible: {overlap_result['capacity_available']}"),
				indicator="blue",
				alert=True
			)

		# Si la capacidad está excedida, BLOQUEAR
		if overlap_result["capacity_exceeded"]:
			overlapping = ", ".join(overlap_result["overlapping_appointments"])
			frappe.throw(
				_(f"No hay capacidad disponible en este horario. Ya hay {overlap_result['capacity_used']} cita(s) que ocupan toda la capacidad.")
			)

	def _validate_slot_granularity(self) -> None:
		"""
		Valida que la duración respete slot_duration_minutes.

		Permite override pero muestra warning.
		"""
		if not self.calendar_resource:
			return

		resource = frappe.get_doc("Calendar Resource", self.calendar_resource)
		slot_duration = resource.slot_duration_minutes or 30

		start = get_datetime(self.start_datetime)
		end = get_datetime(self.end_datetime)
		duration_minutes = (end - start).total_seconds() / 60

		if duration_minutes % slot_duration != 0:
			frappe.msgprint(
				_(f"La duración ({int(duration_minutes)} min) no es múltiplo de la duración del slot ({slot_duration} min)"),
				indicator="yellow",
				alert=True
			)

	def _validate_draft_not_expired(self) -> None:
		"""
		Valida que el Draft no haya expirado antes de confirmar.

		Si el Draft expiró, el usuario debe crear una nueva cita.
		"""
		if self.status != "Draft":
			return

		if not self.draft_expires_at:
			return

		expires_at = get_datetime(self.draft_expires_at)
		current_time = now_datetime()

		if expires_at < current_time:
			# Calcular hace cuánto expiró
			expired_ago = current_time - expires_at
			minutes_ago = int(expired_ago.total_seconds() / 60)

			frappe.throw(
				_(f"Esta reserva expiró hace {minutes_ago} minuto(s). El slot ha sido liberado. Por favor, cree una nueva cita si el horario sigue disponible.")
			)

	def _validate_availability_strict(self) -> None:
		"""
		Validación estricta de disponibilidad en on_submit.

		Bloquea si el horario no está disponible según availability plan.
		"""
		if not self.calendar_resource or not self.start_datetime:
			return

		start = get_datetime(self.start_datetime)
		date_only = start.date()

		# Obtener disponibilidad del día
		availability_slots = get_availability_slots_for_day(
			self.calendar_resource,
			date_only
		)

		if not availability_slots:
			frappe.throw(
				_(f"No hay disponibilidad en {date_only.strftime('%Y-%m-%d')} para este Calendar Resource")
			)

		# Verificar que el appointment cae dentro de algún slot disponible
		start = get_datetime(self.start_datetime)
		end = get_datetime(self.end_datetime)

		# Obtener timezone del Calendar Resource para comparación
		resource = frappe.get_cached_doc("Calendar Resource", self.calendar_resource)
		tz_name = resource.timezone or "UTC"
		if tz_name == "system timezone":
			tz_name = frappe.utils.get_system_timezone()

		try:
			import pytz
			tz = pytz.timezone(tz_name)
			# Convertir start y end al timezone del resource para comparar
			if start.tzinfo is None:
				start = tz.localize(start)
			if end.tzinfo is None:
				end = tz.localize(end)
		except Exception:
			# Si falla, continuar con comparación sin timezone
			pass

		is_within_availability = False
		for slot in availability_slots:
			if slot["start"] <= start and slot["end"] >= end:
				is_within_availability = True
				break

		if not is_within_availability:
			frappe.throw(
				_(f"El horario {start.strftime('%H:%M')}-{end.strftime('%H:%M')} no está disponible")
			)

	def _validate_overlaps_strict(self) -> None:
		"""
		Validación estricta de overlaps en on_submit.

		Bloquea si capacity está excedida.
		"""
		if not self.calendar_resource or not self.start_datetime or not self.end_datetime:
			return

		overlap_result = check_overlap(
			self.calendar_resource,
			get_datetime(self.start_datetime),
			get_datetime(self.end_datetime),
			exclude_appointment=self.name if not self.is_new() else None
		)

		if overlap_result["capacity_exceeded"]:
			overlapping = ", ".join(overlap_result["overlapping_appointments"])
			frappe.throw(
				_(f"Capacidad excedida. Ya hay {overlap_result['capacity_used']} cita(s) en este horario.")
			)

	# ===== VIDEO CALL METHODS =====

	def _handle_meeting_creation(self) -> None:
		"""
		Crea meeting según configuración del profile.

		Modos:
		- auto_generate: crea automáticamente vía API
		- manual_only: el usuario debe pegar meeting_url antes de confirmar
		- auto_or_manual: si meeting_url ya tiene valor lo usa, si no crea automáticamente
		"""
		if not self.video_call_profile:
			return

		profile = frappe.get_doc("Video Call Profile", self.video_call_profile)
		link_mode = profile.link_mode or "manual_only"

		if link_mode == "manual_only":
			if not self.meeting_url:
				frappe.throw(_("Meeting URL es requerido para este perfil"))

		elif link_mode == "auto_generate":
			self._create_meeting_via_adapter(profile)

		elif link_mode == "auto_or_manual":
			if not self.meeting_url:
				self._create_meeting_via_adapter(profile)

	def _create_meeting_via_adapter(self, profile: Any) -> None:
		"""Crea meeting usando el adapter del proveedor."""
		try:
			adapter = get_adapter(profile.provider)

			# Validar perfil antes de crear
			adapter.validate_profile(profile)

			# Crear meeting
			result = adapter.create_meeting(profile, self)

			# Guardar datos del meeting
			self.meeting_url = result.get("meeting_url")
			self.meeting_id = result.get("meeting_id")
			self.meeting_status = "created"

			frappe.msgprint(
				_(f"Meeting creado: {self.meeting_url}"),
				indicator="green",
				alert=True
			)

		except VideoCallError as e:
			self.meeting_status = "failed"
			frappe.throw(_(f"Error al crear meeting: {str(e)}"))
		except Exception as e:
			self.meeting_status = "failed"
			frappe.log_error(f"Error creating meeting: {str(e)}", "Appointment Meeting Creation")
			frappe.throw(_(f"Error inesperado al crear meeting: {str(e)}"))

	def _handle_meeting_deletion(self) -> None:
		"""Elimina meeting del proveedor al cancelar (opcional)."""
		if not self.meeting_id or not self.video_call_profile:
			return

		try:
			profile = frappe.get_doc("Video Call Profile", self.video_call_profile)
			adapter = get_adapter(profile.provider)

			adapter.delete_meeting(profile, self)

			frappe.msgprint(
				_("Meeting cancelado en el proveedor"),
				indicator="orange",
				alert=True
			)

		except Exception as e:
			frappe.log_error(f"Error deleting meeting: {str(e)}", "Appointment Meeting Deletion")
			# No bloquear cancelación si falla

	def _handle_meeting_update_on_time_change(self) -> None:
		"""
		Re-crea meeting automático si cambió el horario.

		Solo aplica a appointments Confirmed con meetings auto-generados.
		"""
		# Solo si ya está guardado (not is_new)
		if self.is_new():
			return

		# Solo si está Confirmed
		if self.status != "Confirmed":
			return

		# Solo si tiene meeting_id (auto-generado)
		if not self.meeting_id:
			return

		# Detectar cambio de horario
		doc_before_save = self.get_doc_before_save()
		if not doc_before_save:
			return

		old_start = get_datetime(doc_before_save.start_datetime)
		old_end = get_datetime(doc_before_save.end_datetime)
		new_start = get_datetime(self.start_datetime)
		new_end = get_datetime(self.end_datetime)

		if old_start != new_start or old_end != new_end:
			# Horario cambió, re-crear meeting
			profile = frappe.get_doc("Video Call Profile", self.video_call_profile)

			try:
				# Eliminar meeting anterior
				adapter = get_adapter(profile.provider)
				adapter.delete_meeting(profile, self)

				# Crear nuevo meeting
				self._create_meeting_via_adapter(profile)

				frappe.msgprint(
					_("Meeting re-creado con nuevo horario"),
					indicator="blue",
					alert=True
				)

			except Exception as e:
				frappe.log_error(f"Error updating meeting: {str(e)}", "Appointment Meeting Update")
				frappe.msgprint(
					_(f"Error al actualizar meeting: {str(e)}"),
					indicator="orange",
					alert=True
				)

