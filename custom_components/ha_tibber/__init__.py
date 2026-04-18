"""The HA Tibber integration."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
)

from .api.exceptions import (
    FatalHttpExceptionError,
    InvalidLoginError,
    RetryableHttpExceptionError,
)
from .api.graphql_client import GraphQLClient
from .api.tibber_connection import TibberConnection
from .const import AUTH_IMPLEMENTATION, DOMAIN
from .coordinator import TibberDataCoordinator, TibberPriceCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.NOTIFY]


@dataclass
class TibberRuntimeData:
    """Runtime data for the HA Tibber integration."""

    session: config_entry_oauth2_flow.OAuth2Session
    price_coordinator: TibberPriceCoordinator | None = None
    data_coordinator: TibberDataCoordinator | None = None
    _client: TibberConnection | None = field(default=None, repr=False)

    async def async_get_client(
        self, hass: HomeAssistant
    ) -> TibberConnection:
        """Get the Tibber connection, refreshing token if needed."""
        await self.session.async_ensure_token_valid()
        token = self.session.token
        access_token = token.get("access_token", "")

        if self._client is not None:
            self._client.set_access_token(access_token)
            return self._client

        websession = aiohttp_client.async_get_clientsession(hass)
        gql_client = GraphQLClient(
            websession=websession,
            access_token=access_token,
        )

        from zoneinfo import ZoneInfo

        tz_str = hass.config.time_zone
        time_zone = ZoneInfo(tz_str)

        self._client = TibberConnection(
            gql_client=gql_client,
            websession=websession,
            time_zone=time_zone,
        )
        return self._client


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up HA Tibber from configuration.yaml."""
    return True


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Set up HA Tibber from a config entry."""
    if AUTH_IMPLEMENTATION not in entry.data:
        raise ConfigEntryAuthFailed(
            "No OAuth implementation found. Please re-authenticate."
        )

    try:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )
    except ValueError as err:
        raise ConfigEntryNotReady(
            "OAuth implementation not available"
        ) from err

    session = config_entry_oauth2_flow.OAuth2Session(
        hass, entry, implementation
    )

    # Validate token
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as err:
        if 400 <= err.status < 500:
            raise ConfigEntryAuthFailed(
                f"Token validation failed: {err.status}"
            ) from err
        raise ConfigEntryNotReady(
            f"Token validation error: {err.status}"
        ) from err
    except aiohttp.ClientError as err:
        raise ConfigEntryNotReady(
            f"Connection error: {err}"
        ) from err

    runtime_data = TibberRuntimeData(session=session)
    entry.runtime_data = runtime_data

    # Create and validate the Tibber connection
    try:
        client = await runtime_data.async_get_client(hass)
        await client.update_info()
    except InvalidLoginError as err:
        raise ConfigEntryAuthFailed(
            "Invalid Tibber credentials"
        ) from err
    except (
        TimeoutError,
        aiohttp.ClientError,
        RetryableHttpExceptionError,
    ) as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to Tibber: {err}"
        ) from err
    except FatalHttpExceptionError as err:
        raise ConfigEntryNotReady(
            f"Tibber API error: {err}"
        ) from err

    # Check for active homes
    active_homes = client.get_homes(only_active=True)

    # Set up coordinators
    price_coordinator: TibberPriceCoordinator | None = None
    data_coordinator: TibberDataCoordinator | None = None

    if active_homes:
        price_coordinator = TibberPriceCoordinator(
            hass, entry, client
        )
        await price_coordinator.async_config_entry_first_refresh()

        data_coordinator = TibberDataCoordinator(
            hass, entry, client
        )
        await data_coordinator.async_config_entry_first_refresh()

    runtime_data.price_coordinator = price_coordinator
    runtime_data.data_coordinator = data_coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Register services
    await _async_register_services(hass)

    return True


async def async_unload_entry(
    hass: HomeAssistant, entry: ConfigEntry
) -> bool:
    """Unload a config entry."""
    runtime_data: TibberRuntimeData = entry.runtime_data

    # Disconnect WebSocket
    if runtime_data._client:
        await runtime_data._client.rt_disconnect()

    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    from .services import async_register_services

    await async_register_services(hass)
