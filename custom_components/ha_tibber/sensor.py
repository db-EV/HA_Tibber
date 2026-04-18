"""Sensor platform for the HA Tibber integration."""

from __future__ import annotations

import asyncio
import datetime
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfReactivePower,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from homeassistant.util import slugify

from .api.exceptions import (
    SubscriptionEndpointMissingError,
    WebSocketHandshakeError,
)
from .api.tibber_connection import TibberConnection
from .api.tibber_home import TibberHome
from .const import DOMAIN, MANUFACTURER
from .coordinator import TibberDataCoordinator, TibberPriceCoordinator

_LOGGER = logging.getLogger(__name__)


# Real-time sensor descriptions (from Pulse/Watty)
RT_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="power",
        translation_key="current_power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="powerProduction",
        translation_key="current_power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="minPower",
        translation_key="minimum_power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="averagePower",
        translation_key="average_power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="maxPower",
        translation_key="maximum_power_consumption",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="netPower",
        translation_key="current_net_power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="minPowerProduction",
        translation_key="minimum_power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="maxPowerProduction",
        translation_key="maximum_power_production",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="accumulatedConsumption",
        translation_key="daily_accumulated_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="accumulatedProduction",
        translation_key="daily_accumulated_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="accumulatedConsumptionLastHour",
        translation_key="hourly_accumulated_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="accumulatedProductionLastHour",
        translation_key="hourly_accumulated_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="lastMeterConsumption",
        translation_key="meter_reading_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="lastMeterProduction",
        translation_key="meter_reading_production",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    SensorEntityDescription(
        key="voltagePhase1",
        translation_key="voltage_phase_1",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltagePhase2",
        translation_key="voltage_phase_2",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="voltagePhase3",
        translation_key="voltage_phase_3",
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="currentL1",
        translation_key="current_phase_1",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="currentL2",
        translation_key="current_phase_2",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="currentL3",
        translation_key="current_phase_3",
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="signalStrength",
        translation_key="pulse_signal_strength",
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="powerFactor",
        translation_key="power_factor",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.POWER_FACTOR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="powerReactive",
        translation_key="reactive_power_consumption",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="powerProductionReactive",
        translation_key="reactive_power_production",
        native_unit_of_measurement=UnitOfReactivePower.VOLT_AMPERE_REACTIVE,
        device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
)

RT_SENSOR_MAP: dict[str, SensorEntityDescription] = {
    desc.key: desc for desc in RT_SENSORS
}

# Monetary RT sensors (use home currency as unit)
RT_MONETARY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="accumulatedCost",
        translation_key="daily_accumulated_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="accumulatedReward",
        translation_key="daily_accumulated_reward",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
)

RT_MONETARY_MAP: dict[str, SensorEntityDescription] = {
    desc.key: desc for desc in RT_MONETARY_SENSORS
}

# Monthly data sensors
MONTHLY_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="month_cost",
        translation_key="monthly_cost",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="month_cons",
        translation_key="monthly_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="peak_hour",
        translation_key="monthly_peak_hour_consumption",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    SensorEntityDescription(
        key="peak_hour_time",
        translation_key="monthly_peak_hour_time",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


def _get_device_info(home: TibberHome) -> DeviceInfo:
    """Return DeviceInfo for a Tibber home."""
    return DeviceInfo(
        identifiers={(DOMAIN, home.home_id)},
        name=home.name,
        manufacturer=MANUFACTURER,
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Tibber sensors."""
    runtime_data = entry.runtime_data
    client = await runtime_data.async_get_client(hass)

    entities: list[SensorEntity] = []

    for home in client.get_homes(only_active=True):
        # Price sensor
        if runtime_data.price_coordinator:
            entities.append(
                TibberSensorElPrice(
                    home=home,
                    coordinator=runtime_data.price_coordinator,
                )
            )

        # Monthly data sensors
        if runtime_data.data_coordinator:
            for description in MONTHLY_SENSORS:
                entities.append(
                    TibberDataSensor(
                        home=home,
                        coordinator=runtime_data.data_coordinator,
                        description=description,
                    )
                )

        # Real-time sensors (lifecycle-gated subscription)
        if home.has_real_time_consumption:
            rt_coordinator = TibberRtDataCoordinator(
                hass, home, entry, client,
            )
            entity_creator = TibberRtEntityCreator(
                hass=hass,
                home=home,
                coordinator=rt_coordinator,
                async_add_entities=async_add_entities,
            )
            rt_coordinator.set_entity_creator(entity_creator)

            # Only open the WebSocket if the user has at least one RT
            # sensor enabled, or if this is first-time setup (no RT
            # entities registered yet — we need a message to discover
            # which keys the hardware reports).  If every previously-
            # registered RT entity is disabled, stay idle: reloading the
            # entry after a re-enable will bring us back here.
            if _should_start_rt_subscription(hass, entry, home):
                asyncio.create_task(
                    rt_coordinator.async_start_subscription()
                )

    if entities:
        async_add_entities(entities)


def _should_start_rt_subscription(
    hass: HomeAssistant,
    entry: ConfigEntry,
    home: TibberHome,
) -> bool:
    """Return True if the RT subscription should be opened eagerly.

    Opens on first-time setup (no known RT entities yet) or when at
    least one RT entity for this home is user-enabled.  Returns False
    only when every registered RT entity is disabled — the common
    "I only want prices" case.
    """
    registry = er.async_get(hass)
    prefix = f"{home.home_id}_rt_"
    saw_entity = False
    for rt_entry in registry.entities.values():
        if (
            rt_entry.config_entry_id != entry.entry_id
            or not rt_entry.unique_id.startswith(prefix)
        ):
            continue
        saw_entity = True
        if rt_entry.disabled_by is None:
            return True
    return not saw_entity


class TibberSensorElPrice(
    CoordinatorEntity[TibberPriceCoordinator], SensorEntity
):
    """Sensor for the current electricity price."""

    _attr_has_entity_name = True
    _attr_translation_key = "current_electricity_price"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        home: TibberHome,
        coordinator: TibberPriceCoordinator,
    ) -> None:
        """Initialize the price sensor."""
        self._home = home
        self._attr_unique_id = f"{home.home_id}_price"
        self._attr_device_info = _get_device_info(home)
        self._attr_native_unit_of_measurement = home.price_unit
        self.entity_id = (
            f"sensor.ha_tibber_{slugify(home.name)}_current_electricity_price"
        )
        super().__init__(coordinator)

    @property
    def native_value(self) -> float | None:
        """Return the current electricity price."""
        if self.coordinator.data and self._home.home_id in self.coordinator.data:
            price, _, _ = self._home.current_price_data()
            return price
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional price attributes."""
        if self.coordinator.data and self._home.home_id in self.coordinator.data:
            home_data = self.coordinator.data[self._home.home_id]
            attrs = dict(home_data["attributes"])
            if home_data["price_rank"] is not None:
                attrs["price_rank"] = home_data["price_rank"]
            return attrs
        return {}


class TibberDataSensor(
    CoordinatorEntity[TibberDataCoordinator], SensorEntity
):
    """Sensor for monthly consumption data."""

    _attr_has_entity_name = True

    def __init__(
        self,
        home: TibberHome,
        coordinator: TibberDataCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the data sensor."""
        self.entity_description = description
        self._home = home
        self._attr_unique_id = f"{home.home_id}_{description.key}"
        self._attr_device_info = _get_device_info(home)
        self._attr_translation_key = description.translation_key
        self.entity_id = (
            f"sensor.ha_tibber_{slugify(home.name)}"
            f"_{description.translation_key}"
        )

        # Set currency for monetary sensors
        if description.device_class == SensorDeviceClass.MONETARY:
            self._attr_native_unit_of_measurement = home.currency

        super().__init__(coordinator)

    @property
    def native_value(self) -> float | datetime.datetime | None:
        """Return the sensor value."""
        key = self.entity_description.key
        if key == "month_cost":
            return self._home.month_cost or None
        if key == "month_cons":
            return self._home.month_cons or None
        if key == "peak_hour":
            return self._home.peak_hour or None
        if key == "peak_hour_time":
            ts = self._home.peak_hour_time
            if ts:
                try:
                    return datetime.datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    pass
            return None
        return None


class TibberRtDataCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator for real-time data from WebSocket.

    The WebSocket subscription is opened lazily based on the listener
    count: it is started when the first CoordinatorEntity registers and
    stopped when the last one goes away.  This keeps the integration
    idle (no WS traffic, no CPU) when the user has disabled every RT
    sensor.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        home: TibberHome,
        entry: ConfigEntry,
        client: TibberConnection,
    ) -> None:
        """Initialize the RT coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_rt_{home.home_id}",
            config_entry=entry,
        )
        self._home = home
        self._client = client
        self._entity_creator: TibberRtEntityCreator | None = None
        self._ws_active = False

    def set_entity_creator(
        self, creator: TibberRtEntityCreator
    ) -> None:
        """Set the entity creator for lazy entity creation."""
        self._entity_creator = creator

    async def async_start_subscription(self) -> None:
        """Open the WebSocket subscription (idempotent)."""
        if self._ws_active:
            return
        # Mark active up front so overlapping listener additions don't
        # race into a second subscribe() call.
        self._ws_active = True

        def _rt_callback(data: dict[str, Any]) -> None:
            enriched = self._home.add_rt_extra_data(data)
            self._home.rt_subscription_running = True
            self.hass.loop.call_soon_threadsafe(
                self.async_set_updated_data, enriched,
            )

        try:
            await self._client.ws_client.subscribe(
                self._home.home_id, _rt_callback,
            )
        except (
            SubscriptionEndpointMissingError,
            WebSocketHandshakeError,
            aiohttp.ClientError,
            TimeoutError,
        ) as err:
            self._ws_active = False
            _LOGGER.warning(
                "Failed to start RT subscription for %s: %s",
                self._home.name, type(err).__name__,
            )

    async def async_stop_subscription(self) -> None:
        """Close the WebSocket subscription (idempotent)."""
        if not self._ws_active:
            return
        self._ws_active = False
        self._home.rt_subscription_running = False
        try:
            await self._client.ws_client.unsubscribe(self._home.home_id)
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug(
                "Error unsubscribing RT for %s: %s",
                self._home.name, type(err).__name__,
            )

    @callback
    def async_add_listener(
        self,
        update_callback: Callable[[], None],
        context: Any = None,
    ) -> Callable[[], None]:
        """Track listener count and open/close the WS accordingly."""
        remove = super().async_add_listener(update_callback, context)
        if len(self._listeners) == 1 and not self._ws_active:
            self.hass.async_create_task(self.async_start_subscription())

        @callback
        def _remove() -> None:
            remove()
            if not self._listeners and self._ws_active:
                self.hass.async_create_task(self.async_stop_subscription())

        return _remove

    @callback
    def async_set_updated_data(self, data: dict[str, Any]) -> None:
        """Set updated data and notify listeners.

        Merges in place into the existing data dict to avoid allocating
        a fresh copy on every real-time message (Pulse streams at ~1 Hz).
        Null fields in the incoming payload keep the previous value.
        """
        existing = self.data
        if existing is None:
            merged = data
        else:
            for key, value in data.items():
                if value is not None:
                    existing[key] = value
            merged = existing
        super().async_set_updated_data(merged)
        if self._entity_creator:
            self._entity_creator.add_sensors(merged)


class TibberRtEntityCreator:
    """Lazily create RT sensor entities as data keys arrive."""

    def __init__(
        self,
        hass: HomeAssistant,
        home: TibberHome,
        coordinator: TibberRtDataCoordinator,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        """Initialize the entity creator."""
        self._hass = hass
        self._home = home
        self._coordinator = coordinator
        self._async_add_entities = async_add_entities
        self._created_keys: set[str] = set()

    @callback
    def add_sensors(self, data: dict[str, Any]) -> None:
        """Create sensor entities for new data keys."""
        new_entities: list[SensorEntity] = []

        for key, value in data.items():
            if key in self._created_keys or value is None:
                continue

            # Check standard RT sensors
            if key in RT_SENSOR_MAP:
                self._created_keys.add(key)
                new_entities.append(
                    TibberSensorRT(
                        home=self._home,
                        coordinator=self._coordinator,
                        description=RT_SENSOR_MAP[key],
                    )
                )
            # Check monetary RT sensors
            elif key in RT_MONETARY_MAP:
                self._created_keys.add(key)
                new_entities.append(
                    TibberSensorRT(
                        home=self._home,
                        coordinator=self._coordinator,
                        description=RT_MONETARY_MAP[key],
                        currency=self._home.currency,
                    )
                )

        if new_entities:
            self._async_add_entities(new_entities)


class TibberSensorRT(
    CoordinatorEntity[TibberRtDataCoordinator], SensorEntity
):
    """Sensor for real-time measurements from Tibber Pulse/Watty."""

    _attr_has_entity_name = True

    def __init__(
        self,
        home: TibberHome,
        coordinator: TibberRtDataCoordinator,
        description: SensorEntityDescription,
        currency: str | None = None,
    ) -> None:
        """Initialize the RT sensor."""
        self.entity_description = description
        self._home = home
        self._attr_unique_id = f"{home.home_id}_rt_{description.key}"
        self._attr_device_info = _get_device_info(home)
        self._attr_translation_key = description.translation_key
        self.entity_id = (
            f"sensor.ha_tibber_{slugify(home.name)}"
            f"_{description.translation_key}"
        )

        if currency:
            self._attr_native_unit_of_measurement = currency

        super().__init__(coordinator)

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        return (
            super().available
            and self._home.rt_subscription_running
        )

    @property
    def native_value(self) -> float | None:
        """Return the sensor value from the latest RT data."""
        if not self.coordinator.data:
            return None
        value = self.coordinator.data.get(self.entity_description.key)
        if value is None:
            return None

        # Power factor is reported as 0-1, convert to percentage
        if self.entity_description.key == "powerFactor":
            return round(value * 100, 1)

        if isinstance(value, float):
            return round(value, 2)
        return value
