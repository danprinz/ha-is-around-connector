"""Event dispatcher for Is Around integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aiohttp

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

from .const import (
    EVENT_REQUEST_ATTENDANCE_PUSH,
    EVENT_REQUEST_ATTENDANCE_STATS,
    EVENT_REQUEST_OBSERVANCES,
    EVENT_REQUEST_PDF,
    EVENT_REQUEST_RESEND,
)

_LOGGER = logging.getLogger(__name__)


class IsAroundConnector:
    """Connector for Is Around integration using event-based communication."""

    def __init__(
        self,
        hass: HomeAssistant,
        session: aiohttp.ClientSession,
        app_url: str,
        entry_id: str,
    ) -> None:
        """Initialize the connector."""
        self._hass = hass
        self._session = session
        self._app_url = app_url.rstrip("/")
        self._entry_id = entry_id

    async def test_connection(self) -> bool:
        """Test connection to the server (basic connectivity check)."""
        try:
            async with self._session.get(
                self._app_url, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                # Any response (even 404) means server is reachable
                return response.status < 500
        except Exception as err:
            _LOGGER.debug("Connection test failed: %s", err)
            return False

    def request_observances(self) -> None:
        """Request observances data from server via event."""
        _LOGGER.debug("Firing event to request observances")
        self._hass.bus.async_fire(
            EVENT_REQUEST_OBSERVANCES,
            {"config_entry_id": self._entry_id},
        )

    def request_pdf(self, date: str, service: str = "all") -> None:
        """Request PDF generation from server via event."""
        _LOGGER.debug("Firing event to request PDF for date %s", date)
        self._hass.bus.async_fire(
            EVENT_REQUEST_PDF,
            {
                "config_entry_id": self._entry_id,
                "date": date,
                "service": service,
            },
        )

    def request_attendance_push(self) -> None:
        """Request attendance push notification from server via event."""
        _LOGGER.debug("Firing event to request attendance push")
        self._hass.bus.async_fire(
            EVENT_REQUEST_ATTENDANCE_PUSH,
            {"config_entry_id": self._entry_id},
        )

    def request_attendance_stats(self, date: str) -> None:
        """Request attendance statistics from server via event."""
        _LOGGER.debug("Firing event to request attendance stats for date %s", date)
        self._hass.bus.async_fire(
            EVENT_REQUEST_ATTENDANCE_STATS,
            {
                "config_entry_id": self._entry_id,
                "date": date,
            },
        )

    def request_resend(self, entity_types: list[str] | None = None) -> None:
        """Request server to resend state data via event."""
        if entity_types is None:
            entity_types = ["all"]
        _LOGGER.debug(
            "Firing event to request resend for entity types: %s", entity_types
        )
        self._hass.bus.async_fire(
            EVENT_REQUEST_RESEND,
            {
                "config_entry_id": self._entry_id,
                "entity_types": entity_types,
            },
        )
