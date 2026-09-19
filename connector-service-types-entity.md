# Handover for the is-around connector (HACS): the service types entity

Schedule event types (שחרית, סליחות, כל נדרי, …) are no longer hardcoded in
is-around. Admins manage them on a new admin page (`/admin?section=service-types`).
Each type has:

- an English **key**, e.g. `KolNidrei`. It's fixed once the type is created, and
  it's the value of `serviceType` in the weekly schedule;
- two Hebrew labels: the **admin label**, used by is-around's schedule editors,
  the PDF and the question bot, and the **dashboard label**, the kiosk's
  wording. Only the dashboard label is published, as `label`. For example,
  `ShaharitShabbat` is "שחרית שבת" in the admin label and "שחרית" on the kiosk;
- an optional **color**, `"#rrggbb"` or `null`;
- a position in the admin's display order.

is-around publishes the whole list as one entity:

**`sensor.is_around_connector_service_types`**

The kiosk dashboard needs this entity to name and color schedule rows, so the
connector must create it. Until it does, the kiosk only knows the types it has
hardcoded.

---

## 1. What is-around sends

The same `is_around/update_state` message, in Format 1, that every other entity
uses:

```json
{
  "type": "is_around/update_state",
  "config_entry_id": "…",
  "data": {
    "entity_id": "sensor.is_around_connector_service_types",
    "state": "27 Types",
    "attributes": {
      "service_types": {
        "Shaharit":  { "key": "Shaharit",  "label": "שחרית",   "color": "#dd6b20", "order": 0 },
        "ShaharitShabbat": { "key": "ShaharitShabbat", "label": "שחרית", "color": "#dd6b20", "order": 9 },
        "KolNidrei": { "key": "KolNidrei", "label": "כל נדרי", "color": null,      "order": 24 },
        "Event":     { "key": "Event",     "label": "אירוע",   "color": "#319795", "order": 26 }
      },
      "friendly_name": "is-around Service Types",
      "icon": "mdi:shape"
    }
  }
}
```

- `service_types` is keyed by type key. `label` is the dashboard label. `order`
  runs from 0 to n-1, in the admin's order.
- `state` is `"<n> Types"`. Nothing should rely on it.
- The attributes are about 2–3 KB, well under the recorder's 16 KB limit, so
  the entity doesn't need a recorder exclusion.

### When it's sent

- On every is-around ⇄ HA (re)connect, as the **first** push of the initial
  sync, before `weekly_schedule`.
- Right after any admin change on the page: add, relabel (either label),
  recolor, reorder or delete.
- When the admin presses **"שלח ל-Home Assistant"** on the page.
- On `request_resend` with `entity_types` containing `"service_types"` or
  `"all"`. is-around already handles both.

---

## 2. Connector changes

The connector routes `is_around/update_state` by substring of `entity_id`
(`weekly_schedule`, `lessons`, `memorials`, `messages`, `lesson_program`, and
`seating` if the seating handover is done). **Anything else is dropped
silently.** `service_types` doesn't contain any of those substrings, so it
needs its own branch. Follow the memorials pattern:

1. **`const.py`:** add `SERVICE_TYPES_DATA = "service_types_data"`.
2. **`__init__.py` → `handle_update_state`, Format 1:** add a branch:
   ```python
   elif "service_types" in entity_id:
       entry_data[SERVICE_TYPES_DATA] = {"state": state, "attributes": attributes}
       async_dispatcher_send(
           hass, f"{DOMAIN}_{config_entry_id}_update_service_types", state, attributes
       )
   ```
   Put it before any branch whose substring could someday match a longer id.
   Today no existing substring overlaps with `service_types`.
3. **`sensor.py`:** add `IsAroundServiceTypesSensor`, a copy of
   `IsAroundMemorialsSensor` with:
   - `_attr_name = "Service Types"`
   - `_attr_icon = "mdi:shape"`
   - unique id `f"{entry.entry_id}_service_types"`
   - the `_update_service_types` signal
   - `SERVICE_TYPES_DATA`

   Add it to `sensors` in `async_setup_entry`. With `has_entity_name` and the
   device name, the entity id comes out as
   `sensor.is_around_connector_service_types`. Check this after installing: the
   dashboard reads that exact id.
4. **`services.yaml` → `request_resend.entity_types`:** add the option
   `"service_types"`.
5. **Restore on startup (if the connector restores other sensors):** restore
   this one the same way. A kiosk that starts before is-around reconnects
   should still have labels.

## 3. Checking it

1. Install the connector update and restart HA.
2. From Developer tools → Actions, call `is_around_connector.request_resend`
   with `entity_types: ["service_types"]`, or press "שלח ל-Home Assistant" on
   the admin page.
3. `sensor.is_around_connector_service_types` should show `27 Types` (or the
   current count), with `service_types` in its attributes.
4. Rename a type on the admin page. The attribute updates within a second.

is-around logs every push as
`[HA] Updating entity sensor.is_around_connector_service_types to state: …`.
