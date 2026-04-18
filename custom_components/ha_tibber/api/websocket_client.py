"""WebSocket client for Tibber real-time data using graphql-transport-ws."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Callable
from typing import Any

import aiohttp

from .exceptions import SubscriptionEndpointMissingError, WebSocketHandshakeError
from .gql_queries import LIVE_SUBSCRIBE

_LOGGER = logging.getLogger(__name__)

# graphql-transport-ws message types
_MSG_CONNECTION_INIT = "connection_init"
_MSG_CONNECTION_ACK = "connection_ack"
_MSG_SUBSCRIBE = "subscribe"
_MSG_NEXT = "next"
_MSG_ERROR = "error"
_MSG_COMPLETE = "complete"
_MSG_PING = "ping"
_MSG_PONG = "pong"

_WATCHDOG_INTERVAL = 5.0
_MAX_BACKOFF = 300.0  # 5 minutes
_INIT_TIMEOUT = 30.0


class TibberWebSocketClient:
    """WebSocket client implementing graphql-transport-ws over aiohttp."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        access_token: str,
        user_agent: str = "HATibber/0.1.0",
    ) -> None:
        """Initialize the WebSocket client."""
        self._websession = websession
        self._access_token = access_token
        self._user_agent = user_agent
        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._ws_url: str | None = None
        self._subscriptions: dict[str, Callable[[dict[str, Any]], None]] = {}
        self._subscription_home_ids: dict[str, str] = {}
        self._receive_task: asyncio.Task[None] | None = None
        self._watchdog_task: asyncio.Task[None] | None = None
        self._connected = False
        self._should_reconnect = True
        self._retry_count = 0
        self._last_message_time: float = 0
        self._connection_lock = asyncio.Lock()

    @property
    def subscription_running(self) -> bool:
        """Return True if any subscription is active."""
        return self._connected and bool(self._subscriptions)

    def set_ws_url(self, url: str) -> None:
        """Set the WebSocket URL."""
        self._ws_url = url

    def set_access_token(self, token: str) -> None:
        """Update the access token (applied on next reconnect)."""
        self._access_token = token

    async def subscribe(
        self,
        home_id: str,
        callback: Callable[[dict[str, Any]], None],
    ) -> None:
        """Subscribe to live measurements for a home."""
        if not self._ws_url:
            raise SubscriptionEndpointMissingError(
                "WebSocket subscription URL not available",
            )

        sub_id = f"sub_{home_id}"
        self._subscriptions[sub_id] = callback
        self._subscription_home_ids[sub_id] = home_id

        if not self._connected:
            await self._connect()

        await self._send_subscribe(sub_id, home_id)

        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(self._watchdog())

    async def unsubscribe(self, home_id: str) -> None:
        """Unsubscribe from live measurements for a home."""
        sub_id = f"sub_{home_id}"
        if sub_id in self._subscriptions:
            if self._connected and self._ws:
                await self._send_json({"type": _MSG_COMPLETE, "id": sub_id})
            del self._subscriptions[sub_id]
            self._subscription_home_ids.pop(sub_id, None)

        if not self._subscriptions:
            await self.disconnect()

    async def disconnect(self) -> None:
        """Disconnect and clean up."""
        self._should_reconnect = False
        self._connected = False

        for task_attr in ("_watchdog_task", "_receive_task"):
            task: asyncio.Task[None] | None = getattr(self, task_attr)
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            setattr(self, task_attr, None)

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

    async def _connect(self) -> None:
        """Establish WebSocket connection and perform handshake."""
        async with self._connection_lock:
            if self._connected:
                return

            if not self._ws_url:
                raise SubscriptionEndpointMissingError(
                    "WebSocket subscription URL not available",
                )

            try:
                self._ws = await self._websession.ws_connect(
                    self._ws_url,
                    protocols=["graphql-transport-ws"],
                    headers={"User-Agent": self._user_agent},
                    heartbeat=30,
                )

                # Send connection_init.  Payload intentionally not logged —
                # it contains the access token.
                await self._send_json({
                    "type": _MSG_CONNECTION_INIT,
                    "payload": {"token": self._access_token},
                })

                ack_received = False
                try:
                    async with asyncio.timeout(_INIT_TIMEOUT):
                        async for msg in self._ws:
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                if (
                                    self._safe_json(msg.data).get("type")
                                    == _MSG_CONNECTION_ACK
                                ):
                                    ack_received = True
                                    break
                            elif msg.type in (
                                aiohttp.WSMsgType.CLOSED,
                                aiohttp.WSMsgType.ERROR,
                            ):
                                break
                except TimeoutError:
                    _LOGGER.debug("Timed out waiting for connection_ack")

                if not ack_received:
                    if self._ws and not self._ws.closed:
                        await self._ws.close()
                    self._ws = None
                    raise WebSocketHandshakeError(
                        "Did not receive connection_ack from Tibber",
                    )

                self._connected = True
                self._retry_count = 0
                self._last_message_time = asyncio.get_running_loop().time()

                if self._receive_task is None or self._receive_task.done():
                    self._receive_task = asyncio.create_task(self._receive_loop())

                _LOGGER.debug("WebSocket connected")

            except (aiohttp.ClientError, TimeoutError) as err:
                _LOGGER.debug(
                    "Failed to establish WebSocket connection: %s",
                    type(err).__name__,
                )
                if self._ws and not self._ws.closed:
                    await self._ws.close()
                self._ws = None
                raise

    @staticmethod
    def _safe_json(data: str) -> dict[str, Any]:
        """Parse JSON, returning ``{}`` on failure."""
        try:
            parsed = json.loads(data)
        except (ValueError, TypeError):
            return {}
        return parsed if isinstance(parsed, dict) else {}

    async def _send_json(self, data: dict[str, Any]) -> None:
        """Send a JSON message over the WebSocket."""
        if self._ws and not self._ws.closed:
            await self._ws.send_json(data)

    async def _send_subscribe(self, sub_id: str, home_id: str) -> None:
        """Send a subscribe message using GraphQL variables."""
        await self._send_json({
            "type": _MSG_SUBSCRIBE,
            "id": sub_id,
            "payload": {
                "query": LIVE_SUBSCRIBE,
                "variables": {"homeId": home_id},
            },
        })

    async def _receive_loop(self) -> None:
        """Main message receive loop."""
        if not self._ws:
            return

        try:
            async for msg in self._ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    self._last_message_time = asyncio.get_running_loop().time()
                    await self._handle_message(self._safe_json(msg.data))
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    _LOGGER.debug("WebSocket received error frame")
                    break
                elif msg.type == aiohttp.WSMsgType.CLOSED:
                    break
        except asyncio.CancelledError:
            return
        except (aiohttp.ClientError, ValueError) as err:
            _LOGGER.debug(
                "Error in WebSocket receive loop: %s", type(err).__name__,
            )
        finally:
            self._connected = False

    async def _handle_message(self, data: dict[str, Any]) -> None:
        """Handle a received WebSocket message."""
        msg_type = data.get("type")

        if msg_type == _MSG_NEXT:
            sub_id = data.get("id")
            measurement = (
                data.get("payload", {}).get("data", {}).get("liveMeasurement")
            )
            callback = self._subscriptions.get(sub_id) if sub_id else None
            if callback and measurement:
                try:
                    callback(measurement)
                except (TypeError, ValueError, KeyError) as err:
                    _LOGGER.debug(
                        "Error in subscription callback: %s",
                        type(err).__name__,
                    )

        elif msg_type == _MSG_ERROR:
            _LOGGER.warning(
                "GraphQL subscription error for %s", data.get("id"),
            )

        elif msg_type == _MSG_COMPLETE:
            _LOGGER.debug("Subscription %s completed by server", data.get("id"))

        elif msg_type == _MSG_PING:
            await self._send_json({"type": _MSG_PONG})

    async def _watchdog(self) -> None:
        """Monitor connection health and reconnect if needed."""
        while self._should_reconnect and self._subscriptions:
            try:
                await asyncio.sleep(_WATCHDOG_INTERVAL)
                if not self._connected or not self._ws or self._ws.closed:
                    _LOGGER.debug("WebSocket disconnected, attempting reconnect")
                    await self._reconnect()
            except asyncio.CancelledError:
                return
            except (
                aiohttp.ClientError,
                TimeoutError,
                WebSocketHandshakeError,
            ) as err:
                _LOGGER.debug("Error in watchdog: %s", type(err).__name__)

    async def _reconnect(self) -> None:
        """Reconnect with exponential backoff and jitter."""
        self._connected = False

        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None

        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
            self._receive_task = None

        self._retry_count += 1
        backoff = min(
            random.uniform(1, 30) + self._retry_count ** 2,  # noqa: S311
            _MAX_BACKOFF,
        )
        _LOGGER.debug(
            "Reconnecting in %.1f seconds (attempt %d)",
            backoff, self._retry_count,
        )
        await asyncio.sleep(backoff)

        try:
            await self._connect()
            for sub_id, home_id in self._subscription_home_ids.items():
                if sub_id in self._subscriptions:
                    await self._send_subscribe(sub_id, home_id)
        except (
            aiohttp.ClientError,
            TimeoutError,
            SubscriptionEndpointMissingError,
            WebSocketHandshakeError,
        ) as err:
            _LOGGER.debug("Reconnection failed: %s", type(err).__name__)
