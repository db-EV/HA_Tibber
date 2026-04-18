"""Service handlers for the HA Tibber integration."""

from __future__ import annotations

import datetime
import logging
from typing import Any

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall, SupportsResponse
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api.exceptions import FatalHttpExceptionError, InvalidLoginError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_PRICES = "get_prices"

SERVICE_SCHEMA_GET_PRICES = vol.Schema({
    vol.Optional("start"): cv.datetime,
    vol.Optional("end"): cv.datetime,
})


async def async_register_services(hass: HomeAssistant) -> None:
    """Register integration services."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_PRICES):
        return

    async def handle_get_prices(call: ServiceCall) -> dict[str, Any]:
        """Handle the get_prices service call (cache-backed, no API hit)."""
        start: datetime.datetime | None = call.data.get("start")
        end: datetime.datetime | None = call.data.get("end")

        result: dict[str, Any] = {}

        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="no_config_entry",
            )

        for entry in entries:
            runtime_data = entry.runtime_data
            try:
                client = await runtime_data.async_get_client(hass)

                for home in client.get_homes(only_active=True):
                    prices: list[dict[str, Any]] = []
                    for starts_at, total in home.price_total.items():
                        try:
                            dt = datetime.datetime.fromisoformat(starts_at)
                        except (ValueError, TypeError):
                            continue
                        if start and dt < start:
                            continue
                        if end and dt > end:
                            continue
                        prices.append({
                            "start_time": starts_at,
                            "price": total,
                            "level": home.price_level.get(starts_at),
                        })
                    prices.sort(key=lambda x: x["start_time"])
                    result[home.home_id] = {
                        "name": home.name,
                        "currency": home.currency,
                        "prices": prices,
                    }

            except InvalidLoginError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="auth_error",
                ) from err
            except FatalHttpExceptionError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="api_error",
                ) from err
            except TimeoutError as err:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="timeout_error",
                ) from err

        return result

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_PRICES,
        handle_get_prices,
        schema=SERVICE_SCHEMA_GET_PRICES,
        supports_response=SupportsResponse.ONLY,
    )
