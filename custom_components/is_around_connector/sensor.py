"""Sensor platform for Is Around Connector."""

from __future__ import annotations

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_APP_URL, CONF_PRINTER_DEVICE, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Is Around Connector sensors."""
    async_add_entities(
        [
            IsAroundAppUrlSensor(entry),
            IsAroundPrinterSensor(entry),
            IsAroundLastInvokedSensor(hass, entry),
        ]
    )


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
