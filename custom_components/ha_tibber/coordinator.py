"""Data update coordinators for the HA Tibber integration."""

from __future__ import annotations

import asyncio
import datetime
import logging

from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.models import (
    StatisticData,
    StatisticMeanType,
    StatisticMetaData,
)
from homeassistant.components.recorder.statistics import (
    async_add_external_statistics,
    get_last_statistics,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfEnergy
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api.exceptions import (
    FatalHttpExceptionError,
    InvalidLoginError,
    RateLimitExceededError,
    RetryableHttpExceptionError,
)
from .api.models import HourlyData, TibberHomeData
from .api.tibber_connection import TibberConnection
from .api.tibber_home import TibberHome, filter_by_date
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_PRICE_UPDATE_INTERVAL = datetime.timedelta(minutes=15)
_DATA_UPDATE_INTERVAL = datetime.timedelta(hours=1)


class TibberPriceCoordinator(
    DataUpdateCoordinator[dict[str, TibberHomeData]]
):
    """Coordinator for Tibber price data.

    Prices are published a day in advance, so the coordinator only hits
    the API when the cache is actually stale (no prices for today, or
    after 13:00 when tomorrow's prices should be available).  Between
    those points the 15-minute cycle just re-evaluates the current
    price from cached data, which still triggers sensor state updates
    without any request.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TibberConnection,
    ) -> None:
        """Initialize the price coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_price",
            update_interval=_PRICE_UPDATE_INTERVAL,
            config_entry=entry,
        )
        self._client = client
        self._unsub_refresh = None  # declared by parent; referenced below

    def _needs_price_fetch(self, home: TibberHome) -> bool:
        """Return True if cached prices are stale for this home."""
        if not home.price_total:
            return True

        now = datetime.datetime.now(home.time_zone)
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        if not filter_by_date(home.price_total, today, home.time_zone):
            return True

        # After 13:00 tomorrow's prices should be available.
        if now.hour >= 13 and not filter_by_date(
            home.price_total, tomorrow, home.time_zone,
        ):
            return True

        return False

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule next refresh aligned to the next :00/:15/:30/:45."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        now = dt_util.utcnow()
        secs_into_quarter = (
            (now.minute % 15) * 60 + now.second + now.microsecond / 1_000_000
        )
        delay = 15 * 60 - secs_into_quarter
        if delay <= 0:
            delay += 15 * 60

        @callback
        def _do_refresh(_now: datetime.datetime) -> None:
            self.hass.async_create_task(self.async_refresh())

        self._unsub_refresh = async_call_later(self.hass, delay, _do_refresh)

    async def async_shutdown(self) -> None:
        """Cancel any pending refresh before HA tears the coordinator down."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None
        await super().async_shutdown()

    async def _async_update_data(self) -> dict[str, TibberHomeData]:
        """Fetch or re-evaluate price data for all active homes."""
        # Preserve previous data so transient errors don't cause gaps.
        result: dict[str, TibberHomeData] = dict(self.data) if self.data else {}

        total_homes = 0
        failed_homes = 0
        last_home_error: Exception | None = None

        try:
            runtime_data = self.config_entry.runtime_data
            client = await runtime_data.async_get_client(self.hass)

            for home in client.get_homes(only_active=True):
                total_homes += 1
                try:
                    if home.needs_static_refresh():
                        await home.update_static_info()
                    if self._needs_price_fetch(home):
                        await home.update_price_info()

                    _, _, rank = home.current_price_data()
                    attributes = home.current_attributes()

                    result[home.home_id] = TibberHomeData(
                        prices=home.price_total,
                        price_rank=rank,
                        attributes=attributes,
                        home_name=home.name,
                        currency=home.currency,
                    )
                except (
                    RetryableHttpExceptionError,
                    RateLimitExceededError,
                ) as err:
                    failed_homes += 1
                    last_home_error = err
                    _LOGGER.warning(
                        "Retryable error fetching prices for %s: %s",
                        home.name, type(err).__name__,
                    )

        except InvalidLoginError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except (
            TimeoutError,
            RetryableHttpExceptionError,
            RateLimitExceededError,
        ) as err:
            raise UpdateFailed(f"Error fetching price data: {err}") from err
        except FatalHttpExceptionError as err:
            raise UpdateFailed(
                f"Fatal error fetching price data: {err}",
            ) from err

        # If every home failed this cycle, surface the failure so entities
        # become unavailable rather than showing stale data forever.
        if total_homes and failed_homes == total_homes:
            raise UpdateFailed(
                f"All {total_homes} homes failed price update: "
                f"{type(last_home_error).__name__ if last_home_error else 'unknown'}",
            )

        return result


class TibberDataCoordinator(DataUpdateCoordinator[None]):
    """Coordinator for Tibber consumption/production data.

    The upstream API only reports hourly-aggregated values, so there's
    nothing to gain from sub-hourly polling.  This coordinator runs once
    per hour, aligned to the top of the hour.  ``TibberHome._fetch_data``
    only fetches new hours since the last successful fetch (delta), and
    recorder statistics are computed from that already-fetched data
    instead of issuing a second request.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: TibberConnection,
    ) -> None:
        """Initialize the data coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_data",
            update_interval=_DATA_UPDATE_INTERVAL,
            config_entry=entry,
        )
        self._client = client
        self._unsub_refresh = None

    @callback
    def _schedule_refresh(self) -> None:
        """Schedule next refresh aligned to the top of the next hour."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None

        now = dt_util.utcnow()
        secs_into_hour = (
            now.minute * 60 + now.second + now.microsecond / 1_000_000
        )
        delay = 3600 - secs_into_hour
        if delay <= 0:
            delay += 3600

        @callback
        def _do_refresh(_now: datetime.datetime) -> None:
            self.hass.async_create_task(self.async_refresh())

        self._unsub_refresh = async_call_later(self.hass, delay, _do_refresh)

    async def async_shutdown(self) -> None:
        """Cancel any pending refresh before HA tears the coordinator down."""
        if self._unsub_refresh:
            self._unsub_refresh()
            self._unsub_refresh = None
        await super().async_shutdown()

    async def _async_update_data(self) -> None:
        """Fetch consumption/production data and insert statistics."""
        try:
            runtime_data = self.config_entry.runtime_data
            client = await runtime_data.async_get_client(self.hass)

            await client.fetch_consumption_data_active_homes()
            await client.fetch_production_data_active_homes()

            await self._insert_statistics(client)

        except InvalidLoginError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except (
            TimeoutError,
            RetryableHttpExceptionError,
            RateLimitExceededError,
        ) as err:
            raise UpdateFailed(f"Error fetching data: {err}") from err
        except FatalHttpExceptionError as err:
            raise UpdateFailed(f"Fatal error fetching data: {err}") from err

    async def _insert_statistics(self, client: TibberConnection) -> None:
        """Insert external statistics for consumption and production."""
        for home in client.get_homes(only_active=True):
            home_id_clean = home.home_id.replace("-", "")

            await self._insert_stats_for_direction(
                home=home,
                home_id_clean=home_id_clean,
                hourly=home.hourly_consumption_data,
                money_name="totalcost",
            )

            if home.has_production:
                await self._insert_stats_for_direction(
                    home=home,
                    home_id_clean=home_id_clean,
                    hourly=home.hourly_production_data,
                    money_name="profit",
                )

    async def _insert_stats_for_direction(
        self,
        home: TibberHome,
        home_id_clean: str,
        hourly: HourlyData,
        money_name: str,
    ) -> None:
        """Insert statistics for a direction, reusing already-fetched data."""
        direction = hourly.direction
        if not hourly.data:
            return

        energy_stat_id = f"{DOMAIN}:energy_{direction}_{home_id_clean}"
        money_stat_id = f"{DOMAIN}:energy_{money_name}_{home_id_clean}"

        recorder = get_instance(self.hass)
        last_energy, last_money = await asyncio.gather(
            recorder.async_add_executor_job(
                get_last_statistics, self.hass, 1, energy_stat_id, True, {"sum"},
            ),
            recorder.async_add_executor_job(
                get_last_statistics, self.hass, 1, money_stat_id, True, {"sum"},
            ),
        )

        energy_sum = 0.0
        money_sum = 0.0
        if bucket := last_energy.get(energy_stat_id):
            energy_sum = bucket[0].get("sum") or 0
        if bucket := last_money.get(money_stat_id):
            money_sum = bucket[0].get("sum") or 0

        energy_stats: list[StatisticData] = []
        money_stats: list[StatisticData] = []

        for entry in hourly.data:
            from_time = entry.get("from")
            if not from_time:
                continue
            try:
                dt = datetime.datetime.fromisoformat(from_time)
            except (ValueError, TypeError):
                continue

            energy_value = entry.get(direction) or 0
            cost_value = entry.get("cost") or 0

            if energy_value:
                energy_sum += energy_value
                energy_stats.append(StatisticData(
                    start=dt, state=energy_value, sum=energy_sum,
                ))
            if cost_value:
                money_sum += cost_value
                money_stats.append(StatisticData(
                    start=dt, state=cost_value, sum=money_sum,
                ))

        if energy_stats:
            async_add_external_statistics(
                self.hass,
                StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    mean_type=StatisticMeanType.NONE,
                    name=f"{home.name} {direction}",
                    source=DOMAIN,
                    statistic_id=energy_stat_id,
                    unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
                    unit_class="energy",
                ),
                energy_stats,
            )

        if money_stats:
            async_add_external_statistics(
                self.hass,
                StatisticMetaData(
                    has_mean=False,
                    has_sum=True,
                    mean_type=StatisticMeanType.NONE,
                    name=f"{home.name} {money_name}",
                    source=DOMAIN,
                    statistic_id=money_stat_id,
                    unit_of_measurement=home.currency,
                    unit_class=None,
                ),
                money_stats,
            )
