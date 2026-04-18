"""Exceptions for the Tibber API."""

from __future__ import annotations


class HttpExceptionError(Exception):
    """Base exception for Tibber HTTP errors."""

    def __init__(
        self,
        status: int,
        message: str = "",
        extension_code: str = "UNKNOWN",
    ) -> None:
        """Initialize the exception."""
        super().__init__(message)
        self.status = status
        self.message = message
        self.extension_code = extension_code


class FatalHttpExceptionError(HttpExceptionError):
    """Fatal HTTP error that should not be retried."""


class RetryableHttpExceptionError(HttpExceptionError):
    """Retryable HTTP error."""


class RateLimitExceededError(RetryableHttpExceptionError):
    """Rate limit exceeded error."""

    def __init__(
        self,
        status: int,
        message: str = "",
        extension_code: str = "UNKNOWN",
        retry_after: float = 0,
    ) -> None:
        """Initialize the exception."""
        super().__init__(status, message, extension_code)
        self.retry_after = retry_after


class InvalidLoginError(FatalHttpExceptionError):
    """Invalid login credentials."""


class SubscriptionEndpointMissingError(Exception):
    """WebSocket subscription endpoint not available."""


class WebSocketHandshakeError(Exception):
    """WebSocket connection opened but GraphQL handshake did not complete."""
