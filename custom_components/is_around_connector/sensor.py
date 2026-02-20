"""Sensor platform for Is Around Connector."""

from __future__ import annotations

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    ATTENDANCE_PUSH_INITIATED_COUNT,
    ATTENDANCE_STATS_ARVIT_ONLY,
    ATTENDANCE_STATS_ATTENDING,
    ATTENDANCE_STATS_NO,
    ATTENDANCE_STATS_SHAHARIT_ONLY,
    ATTENDANCE_STATS_TOTAL,
    ATTENDANCE_STATS_YES,
    CONF_APP_URL,
    CONF_PRINTER_DEVICE,
    DOMAIN,
    LESSONS_DATA,
    MEMORIALS_DATA,
    MESSAGES_DATA,
    NEXT_OBSERVANCE_DATE,
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
        IsAroundAppUrlSensor(entry),
        IsAroundPrinterSensor(entry),
        IsAroundLastInvokedSensor(hass, entry),
        AttendancePushInitiatedCountSensor(hass, entry),
        NextObservanceSensor(hass, entry),
        IsAroundWeeklyScheduleSensor(hass, entry),
        IsAroundLessonsSensor(hass, entry),
        IsAroundMemorialsSensor(hass, entry),
        IsAroundMessagesSensor(hass, entry),
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


class IsAroundAppUrlSensor(SensorEntity):
    """Sensor showing the configured App URL."""

    _attr_has_entity_name = True
    _attr_name = "App URL"
    _attr_icon = "mdi:web"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the sensor."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_app_url"
        self._attr_native_value = entry.data.get(CONF_APP_URL)

    @property
    def device_info(self):
        """Return device info."""
        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": "Is Around Connector",
            "entry_type": dr.DeviceEntryType.SERVICE,
        }


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
