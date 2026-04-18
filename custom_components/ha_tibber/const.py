"""Constants for the HA Tibber integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

    from . import TibberRuntimeData

DOMAIN = "ha_tibber"
MANUFACTURER = "Tibber"

AUTH_IMPLEMENTATION = "auth_implementation"

API_ENDPOINT = "https://api.tibber.com/v1-beta/gql"
USERINFO_ENDPOINT = "https://thewall.tibber.com/connect/userinfo"
DEFAULT_TIMEOUT = 10

RESOLUTION_QUARTER_HOURLY = "QUARTER_HOURLY"
RESOLUTION_HOURLY = "HOURLY"
RESOLUTION_DAILY = "DAILY"
RESOLUTION_WEEKLY = "WEEKLY"
RESOLUTION_MONTHLY = "MONTHLY"
RESOLUTION_ANNUAL = "ANNUAL"

DEFAULT_SCOPES = [
    "openid",
    "profile",
    "email",
    "offline_access",
    "data-api-user-read",
    "data-api-homes-read",
]

if TYPE_CHECKING:
    TibberConfigEntry = ConfigEntry[TibberRuntimeData]
