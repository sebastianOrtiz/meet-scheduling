# DocType: Provider Account

Credenciales OAuth para conectar con un proveedor externo de videollamadas (Google Workspace, Microsoft 365). Necesario para crear meetings automáticamente vía API.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/provider_account/provider_account.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/provider_account/provider_account.py` (clase vacía).
- **Naming rule**: `By fieldname` → `account_name`.

> **Seguridad**: este DocType almacena `client_secret`, `access_token` y `refresh_token` (tipo `Password`, encriptados por Frappe). Acceso solo para `System Manager` y `Meet Scheduling Manager`. No accesible para `Appointment User`.

---

## Campos

Orden según `field_order` (`provider_account.json:8-22`).

### Datos generales

| Fieldname | Tipo | Default | Reqd | Unique | Descripción |
|---|---|---|---|---|---|
| `account_name` | Data | — | yes | yes | Nombre descriptivo (ej. "Google Meet - Consultas"). Es el `name`. `in_list_view: 1`. |
| `provider` | Select | `google_meet` | yes | — | Opciones: `google_meet`, `microsoft_teams`. `in_list_view: 1`. |
| `status` | Select (read_only) | `Pending` | — | — | Opciones: `Pending`, `Connected`, `Expired`, `Revoked`. Validado por adaptadores: si `status != "Connected"` se lanza `VideoCallError` (`google_meet.py:37-38`, `microsoft_teams.py:37-38`). `in_list_view: 1`. |

### Sección "OAuth Credentials" (`oauth_credentials_section`)

| Fieldname | Tipo | Descripción |
|---|---|---|
| `client_id` | Data | Client ID de la aplicación OAuth. Descripción larga en el JSON guía cómo obtenerlo en Google Cloud Console y Azure Portal. |
| `client_secret` | Password | Client Secret de la aplicación OAuth. Encriptado por Frappe. |

### Sección "Tokens" (`tokens_section`)

| Fieldname | Tipo | Default | Read-only | Descripción |
|---|---|---|---|---|
| `access_token` | Password | — | yes | Token de acceso a la API. Encriptado. Se obtiene automáticamente vía OAuth (pendiente de implementación). |
| `refresh_token` | Password | — | yes | Token para renovar el acceso. Encriptado. |
| `token_expires_at` | Datetime | — | yes | Cuándo expira el access_token. El sistema debe usar el refresh_token para renovar. |
| `scopes` | Small Text | — | yes | Permisos OAuth otorgados. Ej: `https://www.googleapis.com/auth/calendar.events` para Google Meet. |

### Sección "Configuration Guide" (`setup_guide_section`)

| Fieldname | Tipo | Descripción |
|---|---|---|
| `setup_guide_html` | HTML | Bloque HTML estático con instrucciones paso a paso para registrar la app OAuth en Google Cloud y Azure Portal. Incluye scopes y redirect URIs. |

---

## Permisos por rol

Definidos en `provider_account.json:124-149`.

| Rol | Read | Write | Create | Delete |
|---|---|---|---|---|
| `System Manager` | yes | yes | yes | yes |
| `Meet Scheduling Manager` | yes | yes | yes | yes |
| `Appointment User` | — | — | — | — |

> `Appointment User` no tiene NINGÚN permiso (ni siquiera read), por la sensibilidad de tokens.

---

## Estados (`status`)

| Status | Significado |
|---|---|
| `Pending` | Recién creado; aún no completó OAuth. |
| `Connected` | OAuth completado, tokens válidos. **Único estado en el que se permite crear meetings**. |
| `Expired` | `token_expires_at` pasó y no se pudo refrescar. |
| `Revoked` | El usuario revocó el acceso desde Google/Microsoft. |

---

## Flujo OAuth (pendiente)

El campo `setup_guide_html` documenta los redirect URIs esperados:

- Google Meet: `https://tu-sitio.com/api/method/meet_scheduling.integrations.google_callback`
- Microsoft Teams: `https://tu-sitio.com/api/method/meet_scheduling.integrations.microsoft_callback`

> **Estos endpoints NO existen en el código actual**. El módulo `meet_scheduling.integrations` no está implementado. Es deuda técnica documentada.

---

## Uso desde los adaptadores

`google_meet.py:30-38`:

```python
def validate_profile(self, profile: Any) -> None:
    if profile.link_mode in ["auto_generate", "auto_or_manual"]:
        if not profile.provider_account:
            frappe.throw("Provider Account es requerido para modo automático")
        account = frappe.get_doc("Provider Account", profile.provider_account)
        if account.status != "Connected":
            raise VideoCallError(f"Provider Account no está conectado: {account.status}")
```

`microsoft_teams.py:30-38` hace lo mismo. Es decir: ambos adaptadores **validan** que la cuenta esté `Connected` antes de intentar crear el meeting, pero como el `create_meeting` actual es mock, no usan los tokens.

---

## Bugs / deuda técnica

1. **OAuth no implementado**: el flujo real de autorización, callback y refresh de tokens no existe en el código. El `status` siempre se queda en `Pending`.
2. **Endpoints `meet_scheduling.integrations.*_callback` documentados pero no implementados**.
3. **No hay job de renovación de tokens**: ningún `scheduler_event` valida `token_expires_at`.
4. **`setup_guide_html` con HTML inline**: difícil de mantener. Sería mejor un template Jinja en `templates/`.
5. **`scopes` es manual**: no se pobla automáticamente desde el OAuth flow (porque no existe).
