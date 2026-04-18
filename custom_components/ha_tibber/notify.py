"""Notification platform for the HA Tibber integration."""

from __future__ import annotations

import logging

from homeassistant.components.notify import NotifyEntity, NotifyEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Tibber notification entity."""
    async_add_entities([TibberNotificationEntity(entry)])


class TibberNotificationEntity(NotifyEntity):  # pylint: disable=abstract-method
    """Notification entity for Tibber push notifications.

    HA's NotifyEntity declares ``send_message`` as abstract but integrations
    override the async variant ``async_send_message`` instead; pylint cannot
    see this relationship.
    """

    _attr_has_entity_name = True
    _attr_name = "Push notification"
    _attr_icon = "mdi:message-flash"
    _attr_supported_features = NotifyEntityFeature.TITLE

    def __init__(self, entry: ConfigEntry) -> None:
        """Initialize the notification entity."""
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_notify"
        self.entity_id = "notify.ha_tibber_push_notification"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Tibber",
            manufacturer=MANUFACTURER,
        )

    async def async_send_message(
        self, message: str, title: str | None = None
    ) -> None:
        """Send a push notification via Tibber."""
        runtime_data = self._entry.runtime_data

        try:
            client = await runtime_data.async_get_client(self.hass)
            await client.send_notification(
                title=title or "Home Assistant",
                message=message,
            )
        except TimeoutError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="send_notification_timeout",
            ) from err
