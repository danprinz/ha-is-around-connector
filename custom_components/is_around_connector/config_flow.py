"""Config flow for Is Around Connector integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .connector import IsAroundConnector
from .const import (
    CONF_APP_URL,
    CONF_PRINTER_DEVICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Is Around Connector."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._app_url: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._app_url = user_input[CONF_APP_URL]
            session = async_get_clientsession(self.hass)
            # Use temporary entry_id for connection test
            connector = IsAroundConnector(self.hass, session, self._app_url, "test")

            # Test basic connectivity
            if await connector.test_connection():
                # Connection successful, proceed to printer selection
                return await self.async_step_printer()

            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_APP_URL): str,
                }
            ),
            errors=errors,
        )

    async def async_step_printer(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the printer selection step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            return self.async_create_entry(
                title="Is Around Connector",
                data={
                    CONF_APP_URL: self._app_url,
                    CONF_PRINTER_DEVICE: user_input.get(CONF_PRINTER_DEVICE),
                },
            )

        return self.async_show_form(
            step_id="printer",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PRINTER_DEVICE): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(
                            integration="ipp_printer_service"
                        ),
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return OptionsFlowHandler()


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Is Around Connector."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            # Update config entry data
            self.hass.config_entries.async_update_entry(
                self.config_entry, data={**self.config_entry.data, **user_input}
            )
            return self.async_create_entry(title="", data={})

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_APP_URL, default=self.config_entry.data.get(CONF_APP_URL)
                    ): str,
                    vol.Optional(
                        CONF_PRINTER_DEVICE,
                        default=self.config_entry.data.get(CONF_PRINTER_DEVICE),
                    ): selector.DeviceSelector(
                        selector.DeviceSelectorConfig(
                            integration="ipp_printer_service"
                        ),
                    ),
                }
            ),
        )
