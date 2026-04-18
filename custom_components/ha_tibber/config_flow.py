"""Config flow for the HA Tibber integration."""

from __future__ import annotations

import logging
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
import voluptuous as vol

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_entry_oauth2_flow

from .api.exceptions import FatalHttpExceptionError, InvalidLoginError
from .api.graphql_client import GraphQLClient
from .api.tibber_connection import TibberConnection
from .const import DEFAULT_SCOPES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class HATibberConfigFlow(  # pylint: disable=abstract-method
    config_entry_oauth2_flow.AbstractOAuth2FlowHandler,
    domain=DOMAIN,
):
    """Handle a config flow for HA Tibber."""

    DOMAIN = DOMAIN
    VERSION = 1

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return _LOGGER

    @property
    def extra_authorize_data(self) -> dict[str, Any]:
        """Extra data that needs to be appended to the authorize url."""
        return {"scope": " ".join(DEFAULT_SCOPES)}

    async def async_oauth_create_entry(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Create an entry for the flow."""
        return await self._async_validate_and_create(data)

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle re-authentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm re-authentication."""
        if user_input is None:
            return self.async_show_form(step_id="reauth_confirm")
        return await self.async_step_user()

    async def async_step_connection_error(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle connection error retry."""
        if user_input is None:
            return self.async_show_form(
                step_id="connection_error",
                data_schema=vol.Schema({}),
            )
        return await self.async_step_user()

    async def _async_validate_and_create(
        self, data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Validate the access token and create the config entry."""
        token = data.get("token", {})
        access_token = token.get("access_token", "")

        try:
            time_zone = ZoneInfo(self.hass.config.time_zone or "UTC")

            timeout = aiohttp.ClientTimeout(total=30)
            async with aiohttp.ClientSession(timeout=timeout) as websession:
                gql_client = GraphQLClient(
                    websession=websession,
                    access_token=access_token,
                )
                connection = TibberConnection(
                    gql_client=gql_client,
                    websession=websession,
                    time_zone=time_zone,
                )
                await connection.update_info()

        except InvalidLoginError:
            return self.async_abort(reason="invalid_access_token")
        except FatalHttpExceptionError:
            return self.async_abort(reason="connection_error")
        except (TimeoutError, aiohttp.ClientError):
            return await self.async_step_connection_error()

        await self.async_set_unique_id(connection.user_id)

        if self.source == "reauth":
            reauth_entry = self._get_reauth_entry()
            if reauth_entry.unique_id != connection.user_id:
                return self.async_abort(reason="wrong_account")
            return self.async_update_reload_and_abort(
                reauth_entry,
                data=data,
            )

        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=connection.name or "Tibber",
            data=data,
        )
