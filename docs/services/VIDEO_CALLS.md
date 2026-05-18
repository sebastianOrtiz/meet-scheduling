# Service: Video Calls (`video_calls/`)

Módulo que implementa el **adapter pattern** para crear/actualizar/eliminar meetings en proveedores externos (Google Meet, Microsoft Teams). Actualmente con implementación **mock** (sin OAuth real).

- **Carpeta**: `meet_scheduling/meet_scheduling/video_calls/`
- **Archivos**:
  - `__init__.py` — docstring del módulo.
  - `base.py` — interfaz abstracta `VideoCallAdapter` y excepción `VideoCallError`.
  - `factory.py` — `get_adapter(provider)`.
  - `google_meet.py` — `GoogleMeetAdapter` (mock).
  - `microsoft_teams.py` — `TeamsAdapter` (mock).

---

## `base.py`

`video_calls/base.py:11-55`.

### Clase `VideoCallAdapter(ABC)`

Interfaz que todos los adapters deben implementar.

```python
class VideoCallAdapter(ABC):
    @abstractmethod
    def create_meeting(self, profile: Any, appointment: Any) -> Dict[str, Any]:
        """Retorna {"meeting_url": str, "meeting_id": str}"""

    @abstractmethod
    def update_meeting(self, profile: Any, appointment: Any) -> bool:
        """Actualiza meeting (opcional)."""

    @abstractmethod
    def delete_meeting(self, profile: Any, appointment: Any) -> bool:
        """Cancela/elimina meeting (opcional)."""

    def validate_profile(self, profile: Any) -> None:
        """Valida configuración del perfil (default: no-op)."""
        pass
```

### Excepción `VideoCallError`

```python
class VideoCallError(Exception):
    """Excepción para errores de videollamadas."""
    pass
```

Lanzada por los adapters cuando hay un problema (cuenta no conectada, fallo de API, etc.). Capturada en `Appointment._create_meeting_via_adapter` para marcar `meeting_status = "failed"`.

---

## `factory.py`

`video_calls/factory.py:10-30`. Factory que retorna el adapter correcto.

```python
def get_adapter(provider: str) -> VideoCallAdapter:
    if provider == "google_meet":
        from .google_meet import GoogleMeetAdapter
        return GoogleMeetAdapter()
    elif provider == "microsoft_teams":
        from .microsoft_teams import TeamsAdapter
        return TeamsAdapter()
    else:
        raise ValueError(f"Unsupported provider: {provider}")
```

Usa `from import` perezoso para no cargar Google/Microsoft SDKs si no se necesitan.

---

## `google_meet.py` (mock)

`video_calls/google_meet.py`. Adapter para Google Meet.

### `create_meeting(profile, appointment)`

Implementación mock — retorna URL fake:

```python
return {
    "meeting_url": f"https://meet.google.com/mock-{appointment.name}",
    "meeting_id": f"mock-{appointment.name}",
}
```

### `validate_profile(profile)`

```python
def validate_profile(self, profile: Any) -> None:
    if profile.link_mode in ["auto_generate", "auto_or_manual"]:
        if not profile.provider_account:
            frappe.throw("Provider Account es requerido para modo automático")
        account = frappe.get_doc("Provider Account", profile.provider_account)
        if account.status != "Connected":
            raise VideoCallError(f"Provider Account no está conectado: {account.status}")
```

Sí valida que la cuenta esté conectada antes de "crear" el meeting.

### `update_meeting` y `delete_meeting`

Mock que siempre retorna `True`.

---

## `microsoft_teams.py` (mock)

`video_calls/microsoft_teams.py`. Idéntico a Google Meet pero con URLs `https://teams.microsoft.com/mock-{name}`.

---

## Flujo desde Appointment

`appointment.py:341-395` (`_handle_meeting_creation` + `_create_meeting_via_adapter`):

```python
def _handle_meeting_creation(self) -> None:
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
    try:
        adapter = get_adapter(profile.provider)
        adapter.validate_profile(profile)
        result = adapter.create_meeting(profile, self)

        self.meeting_url = result.get("meeting_url")
        self.meeting_id = result.get("meeting_id")
        self.meeting_status = "created"

        frappe.msgprint(_(f"Meeting creado: {self.meeting_url}"), ...)

    except VideoCallError as e:
        self.meeting_status = "failed"
        frappe.throw(_(f"Error al crear meeting: {str(e)}"))
    except Exception as e:
        self.meeting_status = "failed"
        frappe.log_error(...)
        frappe.throw(_(f"Error inesperado al crear meeting: {str(e)}"))
```

---

## Re-creación al cambiar horario

`appointment.py:418-470` (`_handle_meeting_update_on_time_change`):

- Solo aplica si la cita está `Confirmed` y tiene `meeting_id` (auto-generado).
- Compara `start_datetime`/`end_datetime` con `get_doc_before_save`.
- Si cambió: llama `adapter.delete_meeting`, luego `_create_meeting_via_adapter` para crear uno nuevo.

---

## Cómo agregar un nuevo proveedor

Para agregar, por ejemplo, Zoom:

1. Crear `meet_scheduling/meet_scheduling/video_calls/zoom.py` con clase `ZoomAdapter(VideoCallAdapter)`.
2. Implementar `create_meeting`, `update_meeting`, `delete_meeting`, `validate_profile`.
3. Agregar al factory:
   ```python
   elif provider == "zoom":
       from .zoom import ZoomAdapter
       return ZoomAdapter()
   ```
4. Agregar `"zoom"` al Select `provider` en `video_call_profile.json` y `provider_account.json`.

---

## Deuda técnica grande

1. **Implementación 100% mock**: ningún meeting real se crea. URLs son `https://meet.google.com/mock-APT-...`. En producción esto debería ser obvio para el usuario; actualmente NO hay indicador visual de que es mock.
2. **OAuth no implementado**: el flujo de autorización, callback y refresh de tokens (documentado en `Provider Account.setup_guide_html`) no existe. El `Provider Account.status` nunca pasa de `Pending` automáticamente.
3. **`meeting_title_template` no se procesa**: el template Jinja del perfil no se aplica en los adapters mock.
4. **`update_meeting` nunca se invoca**: `_handle_meeting_update_on_time_change` borra y recrea, no actualiza. El método existe en la interfaz pero no se usa.
5. **Sin reintentos automáticos**: si `create_meeting` falla, queda `meeting_status = "failed"` y el usuario debe llamar `generate_meeting` manualmente.
