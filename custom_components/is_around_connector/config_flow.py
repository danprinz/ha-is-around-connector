"""Config flow for Is Around Connector integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .connector import IsAroundConnector
from .const import (
    CONF_APP_URL,
    CONF_PRINTER_ENTITY,
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
        self._username: str | None = None
        self._password: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._app_url = user_input[CONF_APP_URL]
            session = async_get_clientsession(self.hass)
            connector = IsAroundConnector(session, self._app_url)

            # Try to connect
            if await connector.test_connection():
                # If connection is successful (even if 401/403), proceed to auth
                return await self.async_step_auth()
            else:
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

    async def async_step_auth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the authentication step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            self._username = user_input[CONF_USERNAME]
            self._password = user_input[CONF_PASSWORD]

            session = async_get_clientsession(self.hass)
            connector = IsAroundConnector(session, self._app_url)

            if await connector.authenticate(self._username, self._password):
                return await self.async_step_printer()
            else:
                errors["base"] = "invalid_auth"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME): str,
                    vol.Required(CONF_PASSWORD): str,
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
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_PRINTER_DEVICE: user_input[CONF_PRINTER_DEVICE],
                },
            )

        return self.async_show_form(
            step_id="printer",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PRINTER_DEVICE): selector.DeviceSelector(
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
            # Update config entry with new options (or data in this case since we don't have separate options)
            # Since we are reconfiguring essential connection details, we should update data.
            # However, Home Assistant usually keeps data separate from options.
            # But Config Flow Reconfiguration is preferred for connection details.
            # For this request, user asked for "support reconfiguration".
            # The standard way to reconfigure active connection params is via reconfigure flow (HA 2024.4+),
            # but simple OptionsFlow updating the data is a common pattern for custom integrations.

            # Let's update the entry data directly
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
                    vol.Required(
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
