# DocType (child): Calendar Resource Notification User

Tabla hija que vive dentro de `Calendar Resource.notification_users`. Lista los `User` del sistema que recibirán email cuando una cita se confirme en ese recurso.

- **Archivo JSON**: `meet_scheduling/meet_scheduling/doctype/calendar_resource_notification_user/calendar_resource_notification_user.json`
- **Controller Python**: `meet_scheduling/meet_scheduling/doctype/calendar_resource_notification_user/calendar_resource_notification_user.py` (clase vacía).
- **Es child table**: `istable: 1`.
- **Naming rule**: `autoincrement`.
- **Padre**: `Calendar Resource.notification_users` (visible solo si `send_email_notification == 1`).

---

## Campos

Orden según `field_order` (`calendar_resource_notification_user.json:8-12`).

| Fieldname | Tipo | Default | Reqd | in_list_view | Descripción |
|---|---|---|---|---|---|
| `user` | Link → `User` | — | yes | yes | Usuario del sistema que recibirá la notificación. Se usa el `name` (= email del User) para enviar el email. |
| `full_name` | Data (read_only) | — | — | yes | `fetch_from`: `user.full_name`. Auto-poblado desde el `User` enlazado. |
| `is_active` | Check | `1` | — | yes | Si está desmarcado, la fila se ignora al armar destinatarios (`notifications/appointment.py:48`). |

---

## Cómo se usa

En `notifications/appointment.py:46-50`:

```python
recipients = [
    row.user
    for row in resource.notification_users
    if row.is_active and row.user
]
```

Es decir, se construye la lista de destinatarios filtrando filas activas y con `user` no vacío. Luego se agregan recipientes extra de los hooks `appointment_email_recipients` registrados por lex_app y logbook, se deduplica y se envía el email con `template="appointment_confirmed"`.

---

## Permisos

No declara permisos propios (campo `permissions: []` en el JSON). Hereda permisos del padre `Calendar Resource`.

---

## Bugs / deuda técnica

1. **No hay validación de email**: si el `User` no tiene email configurado, el envío silenciosamente falla en `send_email`. El campo `user` es el `name` del User (que generalmente es el email), pero podría no serlo.
2. **No hay control de duplicados**: se puede agregar el mismo `User` varias veces. La deduplicación ocurre por casualidad en `notifications/appointment.py:65` (`list({r for r in recipients if r})`).
