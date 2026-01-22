"""
Video Call Adapter Factory

Factory pattern to get the correct adapter based on provider.
"""

from .base import VideoCallAdapter


def get_adapter(provider: str) -> VideoCallAdapter:
	"""
	Factory para obtener el adapter correcto según proveedor.

	Args:
		provider: "google_meet" o "microsoft_teams"

	Returns:
		VideoCallAdapter: instancia del adapter

	Raises:
		ValueError: si provider no es soportado
	"""
	if provider == "google_meet":
		from .google_meet import GoogleMeetAdapter
		return GoogleMeetAdapter()
	elif provider == "microsoft_teams":
		from .microsoft_teams import TeamsAdapter
		return TeamsAdapter()
	else:
		raise ValueError(f"Unsupported provider: {provider}")
