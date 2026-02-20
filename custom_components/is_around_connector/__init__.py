"""The Is Around Connector integration."""

from __future__ import annotations

import asyncio
import base64
import logging
from pathlib import Path
import tempfile
from typing import Any
import uuid

from homeassistant.components import websocket_api
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store
import homeassistant.util.dt as dt_util
import voluptuous as vol

from .connector import IsAroundConnector
from .const import (
    ATTENDANCE_PUSH_INITIATED_COUNT,
    CONF_APP_URL,
    CONF_PRINTER_DEVICE,
    CONF_PRINTER_ENTITY,
    DOMAIN,
    LESSONS_DATA,
    MEMORIALS_DATA,
    MESSAGES_DATA,
    NEXT_OBSERVANCE_DATE,
    RESPONSE_TIMEOUT,
    SERVICE_REQUEST_RESEND,
    SERVICE_SEND_ATTENDANCE,
    WEEKLY_SCHEDULE_DATA,
    WS_TYPE_OPERATION_RESULT,
    WS_TYPE_PDF_CHUNK,
    WS_TYPE_UPDATE_STATE,
)
from .coordinator import IsAroundDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]

STORAGE_VERSION = 1
STORAGE_KEY_PREFIX = f"{DOMAIN}_"


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_UPDATE_STATE,
        vol.Optional("entity_id"): str,  # Legacy: for old schedule/lessons/memorials
        vol.Optional("state"): str,
        vol.Optional("attributes", default={}): dict,
        vol.Optional("config_entry_id"): str,  # New: for observances data
        vol.Optional("data"): dict,  # New: for observances data
    }
)
@websocket_api.async_response
async def handle_update_state(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle the is_around/update_state WebSocket command."""
    _LOGGER.debug("Received WebSocket update_state: %s", msg)

    # Handle different message formats

    # Format 1: config_entry_id + data with nested entity_id (new server format)
    if "config_entry_id" in msg and "data" in msg and "entity_id" in msg["data"]:
        config_entry_id = msg["config_entry_id"]
        entity_id = msg["data"]["entity_id"]
        state = msg["data"]["state"]
        attributes = msg["data"].get("attributes", {})

        if config_entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][config_entry_id]
            if isinstance(entry_data, dict):
                if "weekly_schedule" in entity_id:
                    entry_data[WEEKLY_SCHEDULE_DATA] = {
                        "state": state,
                        "attributes": attributes,
                    }
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{config_entry_id}_update_weekly_schedule",
                        state,
                        attributes,
                    )
                    _LOGGER.debug(
                        "Updated weekly_schedule for entry %s", config_entry_id
                    )
                elif "lessons" in entity_id:
                    entry_data[LESSONS_DATA] = {
                        "state": state,
                        "attributes": attributes,
                    }
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{config_entry_id}_update_lessons",
                        state,
                        attributes,
                    )
                    _LOGGER.debug("Updated lessons for entry %s", config_entry_id)
                elif "memorials" in entity_id:
                    entry_data[MEMORIALS_DATA] = {
                        "state": state,
                        "attributes": attributes,
                    }
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{config_entry_id}_update_memorials",
                        state,
                        attributes,
                    )
                    _LOGGER.debug("Updated memorials for entry %s", config_entry_id)
                elif "messages" in entity_id:
                    entry_data[MESSAGES_DATA] = {
                        "state": state,
                        "attributes": attributes,
                    }
                    async_dispatcher_send(
                        hass,
                        f"{DOMAIN}_{config_entry_id}_update_messages",
                        state,
                        attributes,
                    )
                    _LOGGER.debug("Updated messages for entry %s", config_entry_id)

    # Format 2: entity_id at top level (legacy format)
    elif "entity_id" in msg:
        entity_id = msg["entity_id"]
        state = msg["state"]
        attributes = msg.get("attributes", {})

        for entry_id, entry_data in hass.data.get(DOMAIN, {}).items():
            if not isinstance(entry_data, dict):
                continue

            if "weekly_schedule" in entity_id:
                entry_data[WEEKLY_SCHEDULE_DATA] = {
                    "state": state,
                    "attributes": attributes,
                }
                async_dispatcher_send(
                    hass,
                    f"{DOMAIN}_{entry_id}_update_weekly_schedule",
                    state,
                    attributes,
                )
            elif "lessons" in entity_id:
                entry_data[LESSONS_DATA] = {"state": state, "attributes": attributes}
                async_dispatcher_send(
                    hass, f"{DOMAIN}_{entry_id}_update_lessons", state, attributes
                )
            elif "memorials" in entity_id:
                entry_data[MEMORIALS_DATA] = {"state": state, "attributes": attributes}
                async_dispatcher_send(
                    hass, f"{DOMAIN}_{entry_id}_update_memorials", state, attributes
                )
            elif "messages" in entity_id:
                entry_data[MESSAGES_DATA] = {"state": state, "attributes": attributes}
                async_dispatcher_send(
                    hass, f"{DOMAIN}_{entry_id}_update_messages", state, attributes
                )

    # Format 3: config_entry_id + data for observances (no entity_id inside data)
    elif "config_entry_id" in msg and "data" in msg:
        config_entry_id = msg["config_entry_id"]
        data = msg["data"]

        if config_entry_id in hass.data.get(DOMAIN, {}):
            entry_data = hass.data[DOMAIN][config_entry_id]
            if isinstance(entry_data, dict):
                # Store observances data
                entry_data["observances_data"] = data
                # Signal any waiting futures
                if (
                    "observances_future" in entry_data
                    and not entry_data["observances_future"].done()
                ):
                    entry_data["observances_future"].set_result(data)
                _LOGGER.debug("Stored observances data for entry %s", config_entry_id)

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_PDF_CHUNK,
        vol.Required("config_entry_id"): str,
        vol.Required("request_id"): str,
        vol.Required("chunk_index"): int,
        vol.Required("total_chunks"): int,
        vol.Required("data"): str,
    }
)
@websocket_api.async_response
async def handle_pdf_chunk(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle PDF chunk reception from server."""
    config_entry_id = msg["config_entry_id"]
    request_id = msg["request_id"]
    chunk_index = msg["chunk_index"]
    total_chunks = msg["total_chunks"]
    chunk_data = msg["data"]

    _LOGGER.debug(
        "Received PDF chunk %d/%d for request %s",
        chunk_index + 1,
        total_chunks,
        request_id,
    )

    if config_entry_id not in hass.data.get(DOMAIN, {}):
        _LOGGER.error("Config entry %s not found", config_entry_id)
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    entry_data = hass.data[DOMAIN][config_entry_id]
    if not isinstance(entry_data, dict):
        connection.send_error(msg["id"], "invalid_entry", "Invalid entry data")
        return

    # Initialize PDF chunks storage if needed
    if "pdf_chunks" not in entry_data:
        entry_data["pdf_chunks"] = {}

    if request_id not in entry_data["pdf_chunks"]:
        entry_data["pdf_chunks"][request_id] = {
            "chunks": {},
            "total_chunks": total_chunks,
        }

    # Store chunk
    entry_data["pdf_chunks"][request_id]["chunks"][chunk_index] = chunk_data

    # Check if all chunks received
    received_chunks = len(entry_data["pdf_chunks"][request_id]["chunks"])
    if received_chunks == total_chunks:
        _LOGGER.info("All PDF chunks received, reassembling")
        # Reassemble PDF
        chunks_dict = entry_data["pdf_chunks"][request_id]["chunks"]
        sorted_chunks = [chunks_dict[i] for i in range(total_chunks)]
        base64_pdf = "".join(sorted_chunks)

        # Signal completion
        if "pdf_future" in entry_data and not entry_data["pdf_future"].done():
            entry_data["pdf_future"].set_result(base64_pdf)

        # Cleanup
        del entry_data["pdf_chunks"][request_id]

    connection.send_result(msg["id"])


@websocket_api.websocket_command(
    {
        vol.Required("type"): WS_TYPE_OPERATION_RESULT,
        vol.Required("config_entry_id"): str,
        vol.Optional("request_id"): str,
        vol.Required("success"): bool,
        vol.Optional("error_message"): str,
        vol.Optional("data"): dict,
    }
)
@websocket_api.async_response
async def handle_operation_result(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
) -> None:
    """Handle operation result from server."""
    config_entry_id = msg["config_entry_id"]
    success = msg["success"]
    error_message = msg.get("error_message")
    data = msg.get("data")

    _LOGGER.debug(
        "Received operation result for entry %s: success=%s",
        config_entry_id,
        success,
    )

    if config_entry_id not in hass.data.get(DOMAIN, {}):
        _LOGGER.error("Config entry %s not found", config_entry_id)
        connection.send_error(msg["id"], "not_found", "Config entry not found")
        return

    entry_data = hass.data[DOMAIN][config_entry_id]
    if not isinstance(entry_data, dict):
        connection.send_error(msg["id"], "invalid_entry", "Invalid entry data")
        return

    # Handle attendance push response
    if data and "initiatedCount" in data:
        initiated_count = data["initiatedCount"]
        next_observance = data.get("nextObservance")

        # Store values
        hass.data[DOMAIN][config_entry_id + "_initiated_count"] = initiated_count
        if next_observance and next_observance.get("date"):
            hass.data[DOMAIN][config_entry_id + "_" + NEXT_OBSERVANCE_DATE] = (
                next_observance["date"]
            )

            # Persist data
            store = entry_data.get("store")
            if store:
                await store.async_save(
                    {
                        ATTENDANCE_PUSH_INITIATED_COUNT: initiated_count,
                        NEXT_OBSERVANCE_DATE: next_observance["date"],
                    }
                )

        # Update sensors
        async_dispatcher_send(
            hass,
            f"{DOMAIN}_{config_entry_id}_update_{ATTENDANCE_PUSH_INITIATED_COUNT}",
            initiated_count,
        )
        if next_observance:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}_{config_entry_id}_update_{NEXT_OBSERVANCE_DATE}",
                next_observance,
            )

    # Handle attendance stats response
    if data and "summary" in data:
        # Update coordinator with stats data
        coordinator = entry_data.get("coordinator")
        if coordinator:
            # Manually update coordinator data
            coordinator.async_set_updated_data(data)

    # Signal any waiting futures
    if "operation_future" in entry_data and not entry_data["operation_future"].done():
        if success:
            entry_data["operation_future"].set_result(data)
        else:
            entry_data["operation_future"].set_exception(
                Exception(error_message or "Operation failed")
            )

    connection.send_result(msg["id"])


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Is Around Connector from a config entry."""
    session = async_get_clientsession(hass)
    connector = IsAroundConnector(
        hass, session, entry.data[CONF_APP_URL], entry.entry_id
    )

    hass.data.setdefault(DOMAIN, {})
    store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}{entry.entry_id}")
    coordinator = IsAroundDataUpdateCoordinator(hass, connector, entry.entry_id)
    hass.data[DOMAIN][entry.entry_id] = {
        "connector": connector,
        "store": store,
        "coordinator": coordinator,
    }

    # Load the persisted data
    if (data := await store.async_load()) is not None:
        hass.data[DOMAIN][entry.entry_id + "_initiated_count"] = data.get(
            ATTENDANCE_PUSH_INITIATED_COUNT
        )
        hass.data[DOMAIN][entry.entry_id + "_" + NEXT_OBSERVANCE_DATE] = data.get(
            NEXT_OBSERVANCE_DATE
        )

    # No need to call coordinator refresh - it will be triggered by incoming events
    entry.async_on_unload(entry.add_update_listener(update_listener))

    async def handle_print_next_observance(call: ServiceCall) -> None:
        """Handle the print_next_observance service."""
        _LOGGER.info("Starting print_next_observance service")

        try:
            # 1. Request observances via event
            observances_data = await connector.async_get_observances()

            if not observances_data:
                _LOGGER.error("Failed to get observances")
                return

            next_observance = observances_data.get("nextObservance")
            if not next_observance:
                _LOGGER.warning("No next observance found")
                return

            date = next_observance.get("date")
            if not date:
                _LOGGER.error("Next observance has no date")
                return

            _LOGGER.info("Next observance date: %s", date)

            # 2. Request PDF via event
            entry_data = hass.data[DOMAIN][entry.entry_id]
            entry_data["pdf_future"] = asyncio.Future()

            connector.request_pdf(date)

            # Wait for PDF response with timeout
            try:
                base64_pdf = await asyncio.wait_for(
                    entry_data["pdf_future"], timeout=RESPONSE_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout waiting for PDF response")
                return
            finally:
                entry_data.pop("pdf_future", None)

            # Decode and save PDF
            pdf_data = base64.b64decode(base64_pdf)
            with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(pdf_data)

            try:
                _LOGGER.info("PDF saved to %s", tmp_path)

                # 3. Print PDF using IPP Printer Service
                override_printer_entity = call.data.get("printer_entity")
                copies = call.data.get("copies", 1)

                entity_id = None
                if override_printer_entity:
                    entity_id = override_printer_entity
                else:
                    device_id = entry.data.get(CONF_PRINTER_DEVICE)

                    if device_id:
                        device_registry = dr.async_get(hass)
                        device = device_registry.async_get(device_id)
                        if device:
                            entity_registry = er.async_get(hass)
                            all_entities = entity_registry.entities.values()
                            for ent in all_entities:
                                if (
                                    ent.device_id == device_id
                                    and ent.platform == "ipp_printer_service"
                                ):
                                    entity_id = ent.entity_id
                                    break

                    if not entity_id:
                        entity_id = entry.data.get(CONF_PRINTER_ENTITY)

                if not entity_id:
                    _LOGGER.error("No printer entity found for printing")
                    return

                await hass.services.async_call(
                    "ipp_printer_service",
                    "print_pdf",
                    {
                        "entity_id": entity_id,
                        "file_path": str(tmp_path),
                        "copies": copies,
                    },
                    blocking=True,
                )
                _LOGGER.info(
                    "Print service called for entity %s with %d copies",
                    entity_id,
                    copies,
                )

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
        """Test connection to the server."""
        _LOGGER.info("Starting test_connection service")

        try:
            app_url = call.data.get("app_url") or entry.data[CONF_APP_URL]
            session = async_get_clientsession(hass)
            test_connector = IsAroundConnector(hass, session, app_url, "test")

            if await test_connector.test_connection():
                _LOGGER.info("Test connection successful")
            else:
                _LOGGER.error("Test connection failed")

        except Exception:
            _LOGGER.exception("Error in test_connection")
            raise

    async def handle_send_attendance(call: ServiceCall) -> None:
        """Handle the send_attendance service."""
        _LOGGER.info("Starting send_attendance service")

        try:
            # First get next observance
            observances_data = await connector.async_get_observances()

            if not observances_data:
                _LOGGER.error("Failed to get observances")
                return

            next_observance = observances_data.get("nextObservance")
            if not next_observance or not next_observance.get("date"):
                _LOGGER.warning("No next observance found, cannot send attendance push")
                return

            # Now request attendance push
            entry_data = hass.data[DOMAIN][entry.entry_id]
            entry_data["operation_future"] = asyncio.Future()
            connector.request_attendance_push()

            try:
                response_data = await asyncio.wait_for(
                    entry_data["operation_future"], timeout=RESPONSE_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.error("Timeout waiting for attendance push response")
                return
            finally:
                entry_data.pop("operation_future", None)

            _LOGGER.info("Attendance push completed successfully")

            # Trigger coordinator refresh
            await coordinator.async_request_refresh()

        except Exception:
            _LOGGER.exception("Error in send_attendance")
            raise

    async def handle_request_resend(call: ServiceCall) -> None:
        """Handle the request_resend service."""
        entity_types = call.data.get("entity_types", ["all"])
        _LOGGER.info("Requesting resend for entity types: %s", entity_types)
        connector.request_resend(entity_types)

    hass.services.async_register(
        DOMAIN, "print_next_observance", handle_print_next_observance
    )
    hass.services.async_register(DOMAIN, "test_connection", handle_test_connection)
    hass.services.async_register(
        DOMAIN, SERVICE_SEND_ATTENDANCE, handle_send_attendance
    )
    hass.services.async_register(DOMAIN, SERVICE_REQUEST_RESEND, handle_request_resend)

    # Register WebSocket commands (only once globally, not per entry)
    websocket_api.async_register_command(hass, handle_update_state)
    websocket_api.async_register_command(hass, handle_pdf_chunk)
    websocket_api.async_register_command(hass, handle_operation_result)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Request initial data from is-around server
    _LOGGER.info("Requesting initial data from is-around server")
    connector.request_resend(["all"])

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
        hass.data[DOMAIN].pop(entry.entry_id + "_initiated_count", None)
        hass.data[DOMAIN].pop(entry.entry_id + "_" + NEXT_OBSERVANCE_DATE, None)

    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
