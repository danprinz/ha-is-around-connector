"""Sensor platform for Is Around Connector."""

from __future__ import annotations

import logging

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTENDANCE_PUSH_INITIATED_COUNT,
    ATTENDANCE_STATS_ARVIT_ONLY,
    ATTENDANCE_STATS_NO,
    ATTENDANCE_STATS_SHAHARIT_ONLY,
    ATTENDANCE_STATS_TOTAL,
    ATTENDANCE_STATS_YES,
    CONF_APP_URL,
    CONF_PRINTER_DEVICE,
    DOMAIN,
    LESSON_PROGRAMS_DATA,
    LESSONS_DATA,
    MEMORIALS_DATA,
    MESSAGES_DATA,
    NEXT_OBSERVANCE_DATE,
    SEATING_DATA,
    SERVICE_TYPES_DATA,
    WEEKLY_SCHEDULE_DATA,
)
from .coordinator import IsAroundDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Is Around Connector sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    sensors = [
        IsAroundAppUrlSensor(hass, entry),
        IsAroundPrinterSensor(entry),
        IsAroundLastInvokedSensor(hass, entry),
        AttendancePushInitiatedCountSensor(hass, entry),
        NextObservanceSensor(hass, entry),
        IsAroundWeeklyScheduleSensor(hass, entry),
        IsAroundLessonsSensor(hass, entry),
        IsAroundMemorialsSensor(hass, entry),
        IsAroundMessagesSensor(hass, entry),
        IsAroundSeatingSensor(hass, entry),
        IsAroundServiceTypesSensor(hass, entry),
    ]
    summary_sensors = [
        AttendanceSummarySensor(coordinator, entry, ATTENDANCE_STATS_TOTAL, "Total"),
        AttendanceSummarySensor(coordinator, entry, ATTENDANCE_STATS_YES, "Yes"),
        AttendanceSummarySensor(
            coordinator, entry, ATTENDANCE_STATS_ARVIT_ONLY, "Arvit Only"
        ),
        AttendanceSummarySensor(
            coordinator, entry, ATTENDANCE_STATS_SHAHARIT_ONLY, "Shaharit Only"
        ),
        AttendanceSummarySensor(coordinator, entry, ATTENDANCE_STATS_NO, "No"),
    ]
    async_add_entities(sensors + summary_sensors)

    # Dynamic lesson-program entities — created on first push, updated on resend
    lesson_program_entities: dict[str, IsAroundLessonProgramSensor] = {}

    @callback
    def _handle_lesson_program(slug: str, state: str, attributes: dict) -> None:
        if slug in lesson_program_entities:
            lesson_program_entities[slug]._update_data(state, attributes)
        else:
            # Migrate entity_id if a previous run registered this unique_id under a
            # name-derived entity_id (e.g. Hebrew transliteration) instead of the
            # expected slug-derived one.
            expected_entity_id = f"sensor.{DOMAIN}_{slug}"
            unique_id = f"{entry.entry_id}_{slug}"
            entity_reg = er.async_get(hass)
            existing_entity_id = entity_reg.async_get_entity_id(
                Platform.SENSOR, DOMAIN, unique_id
            )
            if existing_entity_id and existing_entity_id != expected_entity_id:
                entity_reg.async_update_entity(
                    existing_entity_id, new_entity_id=expected_entity_id
                )
            sensor = IsAroundLessonProgramSensor(hass, entry, slug, state, attributes)
            lesson_program_entities[slug] = sensor
            async_add_entities([sensor])

    @callback
    def _handle_lesson_program_removed(slug: str) -> None:
        lesson_program_entities.pop(slug, None)

    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_update_lesson_program",
            _handle_lesson_program,
        )
    )
    entry.async_on_unload(
        async_dispatcher_connect(
            hass,
            f"{DOMAIN}_{entry.entry_id}_remove_lesson_program",
            _handle_lesson_program_removed,
        )
    )

    # Restore any lesson programs already received before this platform was set up
    for slug, data in (
        hass.data[DOMAIN][entry.entry_id].get(LESSON_PROGRAMS_DATA, {}).items()
    ):
        _handle_lesson_program(slug, data["state"], data["attributes"])


class IsAroundAppUrlSensor(SensorEntity):
    """Sensor showing the configured App URL.

    Also doubles as the connector's diagnostic sensor for the wire-protocol
    version last reported by the is-around server (``entity_key`` /
    ``protocol_version`` on incoming ``is_around/update_state`` messages -
    see ``handle_update_state`` in ``__init__.py``).
    """

    _attr_has_entity_name = True
    _attr_name = "App URL"
    _attr_icon = "mdi:web"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_app_url"
        self._attr_native_value = entry.data.get(CONF_APP_URL)
        self._attr_extra_state_attributes = {"protocol_version": None}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks and restore state."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_protocol_version",
                self._update_protocol_version,
            )
        )
        # Restore the last known value
        stored_version = self.hass.data[DOMAIN][self._entry.entry_id].get(
            "protocol_version"
        )
        if stored_version is not None:
            self._update_protocol_version(stored_version)

    @callback
    def _update_protocol_version(self, protocol_version) -> None:
        """Update the protocol_version attribute."""
        self._attr_extra_state_attributes["protocol_version"] = protocol_version
        self.async_write_ha_state()


class IsAroundPrinterSensor(SensorEntity):
    """Sensor showing the configured Printer."""

    _attr_has_entity_name = True
    _attr_name = "Printer"
    _attr_icon = "mdi:printer"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_printer"

    @property
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        device_id = self._entry.data.get(CONF_PRINTER_DEVICE)
        display_name = device_id

        # Try to resolve device name
        if device_id:
            device_registry = dr.async_get(self.hass)
            device = device_registry.async_get(device_id)
            if device:
                display_name = device.name_by_user or device.name

        return display_name

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    @property
    def extra_state_attributes(self):
        """Return extra attributes."""
        return {"device_id": self._entry.data.get(CONF_PRINTER_DEVICE)}


class IsAroundLastInvokedSensor(SensorEntity):
    """Sensor showing the last invoked timestamp."""

    _attr_has_entity_name = True
    _attr_name = "Last Invoked"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_icon = "mdi:clock-check"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_last_invoked"
        self._attr_native_value = None  # Initial state is unknown until invoked

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        # We need a way to update this sensor from the service call.
        # We can subscribe to a signal or just let the service update the state directly via a helper.
        # Ideally, we put the logic in __init__.py to dispatch a signal.
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_last_invoked",
                self._update_timestamp,
            )
        )

    @callback
    def _update_timestamp(self, timestamp):
        """Update the last invoked timestamp."""
        self._attr_native_value = timestamp
        self.async_write_ha_state()


class AttendancePushInitiatedCountSensor(SensorEntity):
    """Sensor showing the number of users for whom attendance push was initiated."""

    _attr_has_entity_name = True
    _attr_name = "Attendance Push Initiated Count"
    _attr_icon = "mdi:account-multiple-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_attendance_push_initiated_count"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks and restore state."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_{ATTENDANCE_PUSH_INITIATED_COUNT}",
                self._update_count,
            )
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_{NEXT_OBSERVANCE_DATE}",
                self._update_next_observance,
            )
        )
        # Restore the last known value
        if (
            last_value := self.hass.data[DOMAIN].get(
                self._entry.entry_id + "_initiated_count"
            )
        ) is not None:
            self._update_count(last_value)

    @callback
    def _update_count(self, count):
        """Update the initiated count."""
        self._attr_native_value = count
        self.async_write_ha_state()

    @callback
    def _update_next_observance(self, next_observance):
        """Update the next observance attribute."""
        self._attr_extra_state_attributes["next_observance"] = next_observance
        self.async_write_ha_state()


class NextObservanceSensor(SensorEntity):
    """Sensor showing the next observance date."""

    _attr_has_entity_name = True
    _attr_name = "Next Observance Date"
    _attr_icon = "mdi:calendar-star"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_next_observance_date"
        self._attr_native_value = None

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks and restore state."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_{NEXT_OBSERVANCE_DATE}",
                self._update_date,
            )
        )
        # Restore the last known value
        if (
            last_value := self.hass.data[DOMAIN].get(
                self._entry.entry_id + "_" + NEXT_OBSERVANCE_DATE
            )
        ) is not None:
            self._update_date({"date": last_value})

    @callback
    def _update_date(self, next_observance):
        """Update the next observance date."""
        self._attr_native_value = next_observance.get("date")
        self.async_write_ha_state()


class AttendanceSummarySensor(
    CoordinatorEntity[IsAroundDataUpdateCoordinator], SensorEntity
):
    """Representation of an attendance summary sensor."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: IsAroundDataUpdateCoordinator,
        entry: ConfigEntry,
        sensor_type: str,
        sensor_name: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self._entry = entry
        self._sensor_type = sensor_type
        self._attr_name = f"Attendance {sensor_name}"
        self._attr_unique_id = f"{entry.entry_id}_{sensor_type}"

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Coordinator update received in sensor %s", self.entity_id)
        if self.coordinator.data and "summary" in self.coordinator.data:
            new_value = self.coordinator.data["summary"].get(self._sensor_type)
            _LOGGER.debug(
                "Updating sensor %s with new value: %s", self.entity_id, new_value
            )
            self._attr_native_value = new_value
            self.async_write_ha_state()
        else:
            _LOGGER.debug(
                "Coordinator data for sensor %s is empty or missing 'summary'",
                self.entity_id,
            )

    @property
    def native_value(self) -> int | None:
        """Return the state of the sensor."""
        return self._attr_native_value


class IsAroundWeeklyScheduleSensor(SensorEntity):
    """Sensor showing the weekly schedule."""

    _attr_has_entity_name = True
    _attr_name = "Weekly Schedule"
    _attr_icon = "mdi:calendar-week"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_weekly_schedule"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_weekly_schedule",
                self._update_data,
            )
        )
        # Restore from stored data if available
        if stored_data := self.hass.data[DOMAIN][self._entry.entry_id].get(
            WEEKLY_SCHEDULE_DATA
        ):
            self._update_data(stored_data["state"], stored_data["attributes"])

    @callback
    def _update_data(self, state: str, attributes: dict) -> None:
        """Update the sensor with new data."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class IsAroundLessonsSensor(SensorEntity):
    """Sensor showing the lessons."""

    _attr_has_entity_name = True
    _attr_name = "Lessons"
    _attr_icon = "mdi:book-open-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_lessons"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_lessons",
                self._update_data,
            )
        )
        # Restore from stored data if available
        if stored_data := self.hass.data[DOMAIN][self._entry.entry_id].get(
            LESSONS_DATA
        ):
            self._update_data(stored_data["state"], stored_data["attributes"])

    @callback
    def _update_data(self, state: str, attributes: dict) -> None:
        """Update the sensor with new data."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class IsAroundMemorialsSensor(SensorEntity):
    """Sensor showing the memorials."""

    _attr_has_entity_name = True
    _attr_name = "Memorials"
    _attr_icon = "mdi:candelabra"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_memorials"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_memorials",
                self._update_data,
            )
        )
        # Restore from stored data if available
        if stored_data := self.hass.data[DOMAIN][self._entry.entry_id].get(
            MEMORIALS_DATA
        ):
            self._update_data(stored_data["state"], stored_data["attributes"])

    @callback
    def _update_data(self, state: str, attributes: dict) -> None:
        """Update the sensor with new data."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class IsAroundServiceTypesSensor(SensorEntity):
    """Sensor showing the schedule service types with their labels and colors."""

    _attr_has_entity_name = True
    _attr_name = "Service Types"
    _attr_icon = "mdi:shape"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_service_types"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_service_types",
                self._update_data,
            )
        )
        # Restore from stored data if available
        if stored_data := self.hass.data[DOMAIN][self._entry.entry_id].get(
            SERVICE_TYPES_DATA
        ):
            self._update_data(stored_data["state"], stored_data["attributes"])

    @callback
    def _update_data(self, state: str, attributes: dict) -> None:
        """Update the sensor with new data."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class IsAroundSeatingSensor(SensorEntity):
    """Sensor showing all seating maps with their layout and allocations."""

    _attr_has_entity_name = True
    _attr_name = "Seating"
    _attr_icon = "mdi:seat"
    # The maps attribute is ~85 KB, far over the recorder's 16 KB attribute limit.
    _unrecorded_attributes = frozenset({"maps", "default_map"})

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_seating"
        self._attr_native_value = None
        self._attr_extra_state_attributes = {}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_seating",
                self._update_data,
            )
        )
        # Restore from stored data if available
        if stored_data := self.hass.data[DOMAIN][self._entry.entry_id].get(
            SEATING_DATA
        ):
            self._update_data(stored_data["state"], stored_data["attributes"])

    @callback
    def _update_data(self, state: str, attributes: dict) -> None:
        """Update the sensor with new data."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class IsAroundMessagesSensor(SensorEntity):
    """Sensor showing community messages."""

    _attr_has_entity_name = True
    _attr_name = "Messages"
    _attr_icon = "mdi:message-text-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_messages"
        self._attr_native_value = 0
        self._attr_extra_state_attributes = {"messages": []}

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    async def async_added_to_hass(self) -> None:
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_{self._entry.entry_id}_update_messages",
                self._update_data,
            )
        )
        # Restore from stored data if available
        if stored_data := self.hass.data[DOMAIN][self._entry.entry_id].get(
            MESSAGES_DATA
        ):
            self._update_data(stored_data["state"], stored_data["attributes"])

    @callback
    def _update_data(self, state: int, attributes: dict) -> None:
        """Update the sensor with new data."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self.async_write_ha_state()


class IsAroundLessonProgramSensor(SensorEntity):
    """Sensor representing a single lesson program pushed by the is-around server."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:book-clock"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        slug: str,
        state: str,
        attributes: dict,
    ) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._entry = entry
        self._slug = slug
        self.entity_id = f"sensor.{DOMAIN}_{slug}"
        self._attr_unique_id = f"{entry.entry_id}_{slug}"
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self._attr_name = attributes.get("name", slug)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }

    @callback
    def _update_data(self, state: str, attributes: dict) -> None:
        """Apply a fresh push from the server."""
        self._attr_native_value = state
        self._attr_extra_state_attributes = attributes
        self._attr_name = attributes.get("name", self._slug)
        self.async_write_ha_state()
