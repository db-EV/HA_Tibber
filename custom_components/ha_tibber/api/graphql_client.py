"""GraphQL client for the Tibber API using aiohttp."""

from __future__ import annotations

import asyncio
import logging
import random
from http import HTTPStatus
from typing import Any

import aiohttp

from ..const import API_ENDPOINT, DEFAULT_TIMEOUT
from .exceptions import (
    FatalHttpExceptionError,
    HttpExceptionError,
    InvalidLoginError,
    RateLimitExceededError,
    RetryableHttpExceptionError,
)

_LOGGER = logging.getLogger(__name__)

_API_ERR_CODE_UNAUTH = "UNAUTHENTICATED"
_RETRY_BACKOFF_SECONDS = (1.0, 3.0, 10.0)
_MAX_RETRY_BACKOFF = 60.0

_HTTP_CODES_RETRIABLE = {
    HTTPStatus.TOO_MANY_REQUESTS,
    HTTPStatus.PRECONDITION_REQUIRED,
    HTTPStatus.BAD_GATEWAY,
    HTTPStatus.SERVICE_UNAVAILABLE,
    HTTPStatus.GATEWAY_TIMEOUT,
}
_HTTP_CODES_FATAL = {HTTPStatus.BAD_REQUEST}


class GraphQLClient:
    """Async GraphQL client for the Tibber API."""

    def __init__(
        self,
        websession: aiohttp.ClientSession,
        access_token: str,
        user_agent: str = "HATibber/0.1.0",
        timeout: int = DEFAULT_TIMEOUT,
    ) -> None:
        """Initialize the GraphQL client."""
        self._websession = websession
        self._access_token = access_token
        self._user_agent = user_agent
        self._timeout = timeout

    def set_access_token(self, token: str) -> None:
        """Update the access token."""
        self._access_token = token

    @property
    def access_token(self) -> str:
        """Return the current access token."""
        return self._access_token

    async def execute(
        self,
        document: str,
        variable_values: dict[str, Any] | None = None,
        timeout: int | None = None,
        retries: int = 3,
    ) -> dict[str, Any] | None:
        """Execute a GraphQL query against the Tibber API."""
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "User-Agent": self._user_agent,
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {"query": document}
        if variable_values:
            payload["variables"] = variable_values

        request_timeout = aiohttp.ClientTimeout(
            total=timeout or self._timeout,
        )

        last_error: Exception | None = None
        for attempt in range(retries):
            try:
                async with self._websession.post(
                    API_ENDPOINT,
                    json=payload,
                    headers=headers,
                    timeout=request_timeout,
                ) as resp:
                    return await self._handle_response(resp)
            except (RetryableHttpExceptionError, RateLimitExceededError) as err:
                last_error = err
                _LOGGER.debug(
                    "Retryable error on attempt %d/%d: %s",
                    attempt + 1, retries, type(err).__name__,
                )
            except (TimeoutError, aiohttp.ClientError) as err:
                last_error = err
                _LOGGER.debug(
                    "Network error on attempt %d/%d: %s",
                    attempt + 1, retries, type(err).__name__,
                )
            if attempt < retries - 1:
                # Prefer the server's Retry-After when present; otherwise use
                # a jittered table value to avoid thundering-herd retries.
                retry_after = (
                    last_error.retry_after
                    if isinstance(last_error, RateLimitExceededError)
                    else 0.0
                )
                if retry_after > 0:
                    backoff = min(retry_after, _MAX_RETRY_BACKOFF)
                else:
                    base = _RETRY_BACKOFF_SECONDS[
                        min(attempt, len(_RETRY_BACKOFF_SECONDS) - 1)
                    ]
                    backoff = base * random.uniform(0.8, 1.2)  # noqa: S311
                await asyncio.sleep(backoff)

        if last_error:
            raise last_error
        return None

    async def _handle_response(
        self,
        resp: aiohttp.ClientResponse,
    ) -> dict[str, Any] | None:
        """Parse a GraphQL response, raising typed exceptions on errors."""
        status = resp.status

        if status == HTTPStatus.OK:
            data = await resp.json()
            if errors := data.get("errors"):
                first = errors[0] if errors else {}
                code = first.get("extensions", {}).get("code", "UNKNOWN")
                message = first.get("message", "Unknown error")
                if code == _API_ERR_CODE_UNAUTH:
                    raise InvalidLoginError(
                        status=401, message=message, extension_code=code,
                    )
                _LOGGER.debug("GraphQL error code: %s", code)
            return data.get("data")

        error_msg = f"HTTP {status}"
        try:
            data = await resp.json()
            if errors := data.get("errors"):
                error_msg = errors[0].get("message", error_msg)
        except (aiohttp.ContentTypeError, ValueError):
            error_msg = await resp.text()

        if status in _HTTP_CODES_RETRIABLE:
            retry_after = float(resp.headers.get("Retry-After", 0))
            if status == HTTPStatus.TOO_MANY_REQUESTS:
                raise RateLimitExceededError(
                    status=status, message=error_msg, retry_after=retry_after,
                )
            raise RetryableHttpExceptionError(status=status, message=error_msg)

        if status in _HTTP_CODES_FATAL:
            raise FatalHttpExceptionError(status=status, message=error_msg)

        if status == HTTPStatus.UNAUTHORIZED:
            raise InvalidLoginError(
                status=status, message=error_msg,
                extension_code=_API_ERR_CODE_UNAUTH,
            )

        raise HttpExceptionError(status=status, message=error_msg)
