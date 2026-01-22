"""
Base Video Call Adapter

Defines the interface that all video call adapters must implement.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


class VideoCallAdapter(ABC):
	"""
	Interfaz base para adaptadores de videollamadas.

	Todos los adaptadores deben implementar estos métodos.
	"""

	@abstractmethod
	def create_meeting(self, profile: Any, appointment: Any) -> Dict[str, Any]:
		"""
		Crea una reunión en el proveedor.

		Args:
			profile: Video Call Profile doc
			appointment: Appointment doc

		Returns:
			dict: {
				"meeting_url": str,
				"meeting_id": str,
				"provider_payload": dict (respuesta completa del API)
			}

		Raises:
			VideoCallError: si falla la creación
		"""
		pass

	@abstractmethod
	def update_meeting(self, profile: Any, appointment: Any) -> bool:
		"""Actualiza una reunión existente (opcional)."""
		pass

	@abstractmethod
	def delete_meeting(self, profile: Any, appointment: Any) -> bool:
		"""Cancela/elimina una reunión (opcional)."""
		pass

	def validate_profile(self, profile: Any) -> None:
		"""Valida que el perfil tenga configuración correcta."""
		pass


class VideoCallError(Exception):
	"""Excepción para errores de videollamadas."""
	pass
