"""
Microsoft Teams Adapter

Implementation for Microsoft Teams video calls.
Currently uses mock implementation (Fase 2).
Real OAuth + Microsoft Graph API integration in Fase 7.
"""

import frappe
from typing import Dict, Any
from .base import VideoCallAdapter, VideoCallError


class TeamsAdapter(VideoCallAdapter):
	"""Adapter para Microsoft Teams."""

	def create_meeting(self, profile: Any, appointment: Any) -> Dict[str, Any]:
		"""
		Crea una reunión en Microsoft Teams.

		FASE 2: Mock implementation
		FASE 7: Implementar OAuth + Microsoft Graph API
		"""
		# Mock similar a Google Meet
		return {
			"meeting_url": f"https://teams.microsoft.com/mock-{appointment.name}",
			"meeting_id": f"teams-mock-{appointment.name}",
			"provider_payload": {"mock": True}
		}

	def validate_profile(self, profile: Any) -> None:
		"""Valida configuración del perfil."""
		if profile.link_mode in ["auto_generate", "auto_or_manual"]:
			if not profile.provider_account:
				frappe.throw("Provider Account es requerido para modo automático")

			account = frappe.get_doc("Provider Account", profile.provider_account)
			if account.status != "Connected":
				raise VideoCallError(f"Provider Account no está conectado: {account.status}")

	def update_meeting(self, profile: Any, appointment: Any) -> bool:
		"""Actualiza meeting (mock)."""
		# Mock
		return True

	def delete_meeting(self, profile: Any, appointment: Any) -> bool:
		"""Cancela meeting (mock)."""
		# Mock
		return True
