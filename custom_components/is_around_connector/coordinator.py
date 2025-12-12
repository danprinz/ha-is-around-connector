"""DataUpdateCoordinator for Is Around Connector."""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .connector import IsAroundConnector
from .const import DOMAIN, NEXT_OBSERVANCE_DATE

_LOGGER = logging.getLogger(__name__)


from typing import Any


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

    async def _async_update_data(self):
        """Update data via library."""
        _LOGGER.debug("Coordinator update triggered")
        # Get the next observance date that was stored when the service was called
        next_observance_date = self._hass.data[DOMAIN].get(
            self._entry_id + "_" + NEXT_OBSERVANCE_DATE
        )
        _LOGGER.debug("Next observance date from hass.data: %s", next_observance_date)

        if not next_observance_date:
            # No observance to track, so we don't poll for stats
            _LOGGER.debug("No next observance date to track, skipping poll")
            return None

        try:
            # First, check if the next observance is still the same
            _LOGGER.debug("Fetching current observances to check if still valid")
            observances_data = await self.connector.get_observances()
            if (
                not observances_data
                or not observances_data.get("nextObservance")
                or observances_data["nextObservance"].get("date")
                != next_observance_date
            ):
                # The observance has changed, so we stop polling for stats
                _LOGGER.info("Next observance has changed, stopping polling for stats")
                self._hass.data[DOMAIN].pop(
                    self._entry_id + "_" + NEXT_OBSERVANCE_DATE, None
                )
                return None

            # If the observance is the same, fetch the stats
            _LOGGER.debug(
                "Observance date is still valid, fetching attendance stats for %s",
                next_observance_date,
            )
            stats = await self.connector.get_attendance_stats(next_observance_date)
            _LOGGER.debug("Fetched stats: %s", stats)
            return stats
        except Exception as exception:
            raise UpdateFailed(
                f"Error communicating with API: {exception}"
            ) from exception
