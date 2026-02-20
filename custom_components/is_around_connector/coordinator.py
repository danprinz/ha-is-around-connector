"""DataUpdateCoordinator for Is Around Connector."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .connector import IsAroundConnector
from .const import DOMAIN, RESPONSE_TIMEOUT

_LOGGER = logging.getLogger(__name__)


class IsAroundDataUpdateCoordinator(DataUpdateCoordinator[dict[str, Any] | None]):
    """Class to manage fetching data from the Is Around API."""

    def __init__(
        self, hass: HomeAssistant, connector: IsAroundConnector, entry_id: str
    ) -> None:
        """Initialize."""
        self.connector = connector
        self._entry_id = entry_id
        self._hass = hass

        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=30),
        )

    async def _async_update_data(self) -> dict[str, Any] | None:
        """Update data via event-based requests.

        Fetches the next observance and its attendance statistics.
        This coordinator is self-sufficient and doesn't rely on external state.
        """
        _LOGGER.debug("Coordinator update triggered")

        try:
            # Always fetch current observances
            _LOGGER.debug("Fetching current observances data")
            observances_data = await self.connector.async_get_observances()

            if not observances_data:
                _LOGGER.debug("No observances data received, skipping stats poll")
                return None

            next_observance = observances_data.get("nextObservance")
            if not next_observance:
                _LOGGER.debug("No next observance found, skipping stats poll")
                return None

            next_observance_date = next_observance.get("date")
            if not next_observance_date:
                _LOGGER.debug("Next observance has no date, skipping stats poll")
                return None

            # Fetch attendance stats for the current next observance
            _LOGGER.debug(
                "Fetching attendance stats for observance: %s", next_observance_date
            )

            entry_data = self._hass.data[DOMAIN][self._entry_id]
            entry_data["operation_future"] = asyncio.Future()
            self.connector.request_attendance_stats(next_observance_date)

            try:
                stats = await asyncio.wait_for(
                    entry_data["operation_future"], timeout=RESPONSE_TIMEOUT
                )
            except asyncio.TimeoutError:
                _LOGGER.warning("Timeout waiting for attendance stats response")
                return None
            finally:
                entry_data.pop("operation_future", None)

            _LOGGER.debug("Fetched stats: %s", stats)
            return stats

        except Exception as exception:
            raise UpdateFailed(
                f"Error communicating with server: {exception}"
            ) from exception
