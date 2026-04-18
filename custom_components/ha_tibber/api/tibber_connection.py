"""TibberConnection - top-level API client orchestrator."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from .gql_queries import INFO, PUSH_NOTIFICATION
from .tibber_home import TibberHome
from .websocket_client import TibberWebSocketClient

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    import aiohttp

    from .graphql_client import GraphQLClient

_LOGGER = logging.getLogger(__name__)

_ALLOWED_WS_HOST_SUFFIX = ".tibber.com"


def _is_trusted_ws_url(url: str) -> bool:
    """Return True if ``url`` is a wss:// URL pointing to tibber.com."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "wss" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    return host == "tibber.com" or host.endswith(_ALLOWED_WS_HOST_SUFFIX)


class TibberConnection:
    """Top-level Tibber API client managing all homes and connections."""

    def __init__(
        self,
        gql_client: GraphQLClient,
        websession: aiohttp.ClientSession,
        time_zone: ZoneInfo,
        user_agent: str = "HATibber/0.1.0",
    ) -> None:
        """Initialize TibberConnection."""
        self._gql_client = gql_client
        self._websession = websession
        self._time_zone = time_zone
        self._user_agent = user_agent

        self._ws_client = TibberWebSocketClient(
            websession=websession,
            access_token=gql_client.access_token,
            user_agent=user_agent,
        )

        self._homes: dict[str, TibberHome] = {}
        self._active_home_ids: list[str] = []
        self._all_home_ids: list[str] = []
        self._ws_url: str | None = None

        self.user_id: str = ""
        self.name: str = ""

    @property
    def gql_client(self) -> GraphQLClient:
        """Return the GraphQL client."""
        return self._gql_client

    @property
    def ws_client(self) -> TibberWebSocketClient:
        """Return the WebSocket client."""
        return self._ws_client

    @property
    def home_ids(self) -> list[str]:
        """Return all home IDs."""
        return self._all_home_ids

    def get_homes(self, only_active: bool = True) -> list[TibberHome]:
        """Return TibberHome instances."""
        if only_active:
            return [
                self._homes[hid]
                for hid in self._active_home_ids
                if hid in self._homes
            ]
        return list(self._homes.values())

    def get_home(self, home_id: str) -> TibberHome | None:
        """Return a TibberHome by ID."""
        return self._homes.get(home_id)

    async def update_info(self) -> None:
        """Fetch viewer info and populate homes."""
        data = await self._gql_client.execute(INFO)
        if not data:
            return

        viewer = data.get("viewer", {})
        self.name = viewer.get("name", "")
        self.user_id = viewer.get("userId", "")

        ws_url = viewer.get("websocketSubscriptionUrl")
        if ws_url and _is_trusted_ws_url(ws_url):
            self._ws_url = ws_url
            self._ws_client.set_ws_url(ws_url)
        elif ws_url:
            _LOGGER.warning(
                "Ignoring untrusted WebSocket URL returned by Tibber API",
            )

        homes = viewer.get("homes", [])
        self._all_home_ids = []
        self._active_home_ids = []

        for home_data in homes:
            home_id = home_data.get("id")
            if not home_id:
                continue

            self._all_home_ids.append(home_id)

            subscription = home_data.get("currentSubscription") or {}
            status = subscription.get("status")
            if status == "running":
                self._active_home_ids.append(home_id)

            home = self._homes.get(home_id)
            if home is None:
                home = TibberHome(
                    home_id=home_id,
                    gql_client=self._gql_client,
                    time_zone=self._time_zone,
                )
                self._homes[home_id] = home

            home.app_nickname = home_data.get("appNickname", "")
            home._has_real_time_consumption = (
                home_data.get("features", {}).get(
                    "realTimeConsumptionEnabled", False,
                )
            )
            home._has_active_subscription = status == "running"

    async def send_notification(self, title: str, message: str) -> bool:
        """Send a push notification via Tibber."""
        data = await self._gql_client.execute(
            PUSH_NOTIFICATION,
            variable_values={"title": title, "message": message},
        )
        result = (data or {}).get("sendPushNotification") or {}
        return bool(result.get("successful"))

    async def fetch_consumption_data_active_homes(self) -> None:
        """Fetch consumption data for all active homes."""
        tasks = [
            self._homes[hid].fetch_consumption_data()
            for hid in self._active_home_ids
            if hid in self._homes
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def fetch_production_data_active_homes(self) -> None:
        """Fetch production data for all active homes."""
        tasks = [
            self._homes[hid].fetch_production_data()
            for hid in self._active_home_ids
            if hid in self._homes
        ]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def set_access_token(self, token: str) -> None:
        """Update the access token on all sub-clients."""
        self._gql_client.set_access_token(token)
        self._ws_client.set_access_token(token)

    async def rt_disconnect(self) -> None:
        """Disconnect the real-time WebSocket subscription."""
        await self._ws_client.disconnect()
