"""The Is Around Connector integration."""

from __future__ import annotations

import logging
from pathlib import Path
import tempfile

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
import homeassistant.util.dt as dt_util

from .connector import IsAroundConnector
from .const import CONF_APP_URL, CONF_PRINTER_ENTITY, CONF_PRINTER_DEVICE, DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Is Around Connector from a config entry."""
    session = async_get_clientsession(hass)
    connector = IsAroundConnector(session, entry.data[CONF_APP_URL])

    # Authenticate to get the cookie
    if not await connector.authenticate(
        entry.data[CONF_USERNAME], entry.data[CONF_PASSWORD]
    ):
        raise ConfigEntryNotReady("Authentication failed")

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = connector

    # Store connector or coordinator if we had one
    # For now we just need to let sensors access the entry data which they can do via entry passed to sensor

    entry.async_on_unload(entry.add_update_listener(update_listener))

    async def handle_print_next_observance(call: ServiceCall) -> None:
        """Handle the print_next_observance service."""
        _LOGGER.info("Starting print_next_observance service")

        try:
            # 1. Get observances
            observances_data = await connector.get_observances()
            next_observance = observances_data.get("nextObservance")

            if not next_observance:
                _LOGGER.warning("No next observance found")
                return

            date = next_observance.get("date")
            if not date:
                _LOGGER.error("Next observance has no date")
                return

            _LOGGER.info("Next observance date: %s", date)

            # 2. Download PDF
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)

            try:
                await connector.download_pdf(date, str(tmp_path))
                _LOGGER.info("PDF downloaded to %s", tmp_path)

                # 3. Print PDF using IPP Printer Service
                override_printer_entity = call.data.get("printer_entity")
                if override_printer_entity:
                    entity_id = override_printer_entity
                else:
                    device_id = entry.data.get(CONF_PRINTER_DEVICE)

                    if device_id:
                        # Find one entity from the device to use for the printing service
                        device_registry = dr.async_get(hass)
                        device = device_registry.async_get(device_id)
                        if device:
                            entity_registry = er.async_get(hass)
                            # entries = entity_registry.entities.get_entries_for_device(
                            #    entry.entry_id, device_id, include_disabled_entities=False
                            # )
                            # The IPP printer service creates entities for the device.
                            # We need to find an entity that belongs to the IPP integration and is associated with this device.
                            # Wait, we are not the IPP integration, so we can't look up by entry_id of THIS integration.
                            # We need to look up entities for the device_id.
                            all_entities = entity_registry.entities.values()
                            for ent in all_entities:
                                if (
                                    ent.device_id == device_id
                                    and ent.platform == "ipp_printer_service"
                                ):  # Actually platform is integration domain usually? "ipp_printer_service" custom integration
                                    entity_id = ent.entity_id
                                    break

                            # Fallback: if we selected a device that might have entities from other integrations too?
                            # The selector was filtered by integration="ipp_printer_service"
                            # so the device SHOULD have entities from it.

                    if not entity_id:
                        # Fallback to old entity config if present
                        entity_id = entry.data.get(CONF_PRINTER_ENTITY)

                if not entity_id:
                    _LOGGER.error("No printer entity found for printing")
                    return

                await hass.services.async_call(
                    "ipp_printer_service",
                    "print_pdf",
                    {"entity_id": entity_id, "file_path": str(tmp_path)},
                    blocking=True,
                )
                _LOGGER.info("Print service called for entity %s", entity_id)

                # Update last invoked timestamp
                now = dt_util.now()
                async_dispatcher_send(
                    hass, f"{DOMAIN}_{entry.entry_id}_update_last_invoked", now
                )

            finally:
                # Cleanup temp file
                if tmp_path.exists():
                    tmp_path.unlink()
                    _LOGGER.debug("Temporary file removed")

        except Exception:
            _LOGGER.exception("Error in print_next_observance")
            raise

    async def handle_test_connection(call: ServiceCall) -> None:
        _LOGGER.info("Starting test_connection service")

        try:
            app_url = call.data.get("app_url") or entry.data[CONF_APP_URL]
            username = call.data.get("username") or entry.data[CONF_USERNAME]
            password = call.data.get("password") or entry.data[CONF_PASSWORD]

            session = async_get_clientsession(hass)
            connector = IsAroundConnector(session, app_url)

            # Authenticate to get the cookie
            if not await connector.authenticate(username, password):
                raise ConfigEntryNotReady("Authentication failed")

            _LOGGER.info("Test connection successful")

        except Exception:
            _LOGGER.exception("Error in test_connection")
            raise

    hass.services.async_register(
        DOMAIN, "print_next_observance", handle_print_next_observance
    )
    hass.services.async_register(DOMAIN, "test_connection", handle_test_connection)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
