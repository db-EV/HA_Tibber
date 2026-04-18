"""TibberHome class for managing a single Tibber home."""

from __future__ import annotations

import datetime
import logging
from collections import deque
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..const import RESOLUTION_HOURLY
from .gql_queries import (
    HISTORIC_PRICE,
    UPDATE_CURRENT_PRICE,
    UPDATE_HOME_INFO,
    UPDATE_PRICE_INFO,
    historic_data_date_query,
    historic_data_query,
)
from .models import HourlyData

if TYPE_CHECKING:
    from zoneinfo import ZoneInfo

    from .graphql_client import GraphQLClient

_LOGGER = logging.getLogger(__name__)

_FIRST_RUN_SEED_HOURS = 24 * 30  # 30 days of hourly data to seed statistics
_DELTA_BATCH_HOURS = 200  # upper bound per delta fetch (≈ 8 days)
_HOURLY_DATA_RETENTION = 24 * 90  # keep ~90 days in memory


def _parse_iso(value: str) -> datetime.datetime | None:
    """Parse an ISO-8601 timestamp, returning None if invalid."""
    try:
        return datetime.datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def filter_by_date(
    prices: dict[str, Any],
    target: datetime.date,
    tz: ZoneInfo,
    predicate: Callable[[datetime.datetime], bool] | None = None,
) -> list[Any]:
    """Return values whose ISO keys fall on ``target`` in ``tz``.

    An optional ``predicate`` (receiving the local datetime) can further
    narrow the selection, e.g. by hour of day.
    """
    out: list[Any] = []
    for starts_at, value in prices.items():
        dt = _parse_iso(starts_at)
        if dt is None:
            continue
        local = dt.astimezone(tz)
        if local.date() != target:
            continue
        if predicate is not None and not predicate(local):
            continue
        out.append(value)
    return out


class TibberHome:
    """Represent a single Tibber home."""

    def __init__(
        self,
        home_id: str,
        gql_client: GraphQLClient,
        time_zone: ZoneInfo,
    ) -> None:
        """Initialize a TibberHome."""
        self._home_id = home_id
        self._gql_client = gql_client
        self._time_zone = time_zone

        self._info: dict[str, Any] = {}
        self._price_info: dict[str, Any] = {}
        self.price_total: dict[str, float] = {}
        self.price_level: dict[str, str] = {}
        self._last_static_fetch: datetime.date | None = None

        self._hourly_consumption_data = HourlyData(direction="consumption")
        self._hourly_production_data = HourlyData(direction="production")

        self._rt_power: deque[tuple[datetime.datetime, float]] = deque()
        self._rt_subscription_running = False
        self._has_active_subscription = False
        self._has_real_time_consumption = False

        # Memoization for current_price_rank; invalidated implicitly when
        # the current interval key or its cached price value changes.
        self._rank_cache_key: tuple[str, float] | None = None
        self._rank_cache_value: float | None = None

        self.name: str = ""
        self.currency: str = ""
        self.app_nickname: str = ""

    # ------------------------------------------------------------------
    # Properties

    @property
    def home_id(self) -> str:
        """Return the home ID."""
        return self._home_id

    @property
    def time_zone(self) -> ZoneInfo:
        """Return the home time zone."""
        return self._time_zone

    @property
    def has_active_subscription(self) -> bool:
        """Return True if the home has an active subscription."""
        return self._has_active_subscription

    @property
    def has_real_time_consumption(self) -> bool:
        """Return True if the home has real-time consumption enabled."""
        return self._has_real_time_consumption

    @property
    def has_production(self) -> bool:
        """Return True if the home has production data."""
        return self._hourly_production_data.has_data

    @property
    def address1(self) -> str:
        """Return address line 1."""
        return self._info.get("address", {}).get("address1", "")

    @property
    def country(self) -> str:
        """Return country."""
        return self._info.get("address", {}).get("country", "")

    @property
    def price_unit(self) -> str:
        """Return the price unit (currency/kWh)."""
        return f"{self.currency}/kWh"

    @property
    def hourly_consumption_data(self) -> HourlyData:
        """Return hourly consumption data."""
        return self._hourly_consumption_data

    @property
    def hourly_production_data(self) -> HourlyData:
        """Return hourly production data."""
        return self._hourly_production_data

    @property
    def month_cons(self) -> float:
        """Return monthly consumption."""
        return self._hourly_consumption_data.month_energy

    @property
    def month_cost(self) -> float:
        """Return monthly cost."""
        return self._hourly_consumption_data.month_money

    @property
    def peak_hour(self) -> float:
        """Return peak hour consumption."""
        return self._hourly_consumption_data.peak_hour

    @property
    def peak_hour_time(self) -> str:
        """Return peak hour time."""
        return self._hourly_consumption_data.peak_hour_time

    @property
    def rt_subscription_running(self) -> bool:
        """Return True if real-time subscription is running."""
        return self._rt_subscription_running

    @rt_subscription_running.setter
    def rt_subscription_running(self, value: bool) -> None:
        """Set real-time subscription running state."""
        self._rt_subscription_running = value

    # ------------------------------------------------------------------
    # Info / price fetches

    def _vars(self, **extra: Any) -> dict[str, Any]:
        """Build a GraphQL variables dict that includes ``$homeId``."""
        return {"homeId": self._home_id, **extra}

    def _home_payload(self, data: dict[str, Any] | None) -> dict[str, Any]:
        """Return ``data.viewer.home`` or an empty dict."""
        if not data:
            return {}
        return data.get("viewer", {}).get("home", {}) or {}

    async def update_static_info(self) -> None:
        """Fetch slow-changing home metadata (address, owner, features).

        Callers should invoke this once per day; use
        :meth:`needs_static_refresh` to check.
        """
        data = await self._gql_client.execute(
            UPDATE_HOME_INFO, variable_values=self._vars(),
        )
        home_data = self._home_payload(data)
        if not home_data:
            return

        self._info = home_data
        self.app_nickname = home_data.get("appNickname", "")
        self.name = self.app_nickname or self.address1 or self._home_id

        subscriptions = home_data.get("subscriptions", [])
        self._has_active_subscription = any(
            sub.get("status") == "running" for sub in subscriptions
        )

        features = home_data.get("features", {})
        self._has_real_time_consumption = features.get(
            "realTimeConsumptionEnabled", False,
        )
        self._last_static_fetch = datetime.datetime.now(self._time_zone).date()

    def needs_static_refresh(self) -> bool:
        """Return True if static info has never been fetched today."""
        if self._last_static_fetch is None:
            return True
        today = datetime.datetime.now(self._time_zone).date()
        return today != self._last_static_fetch

    async def update_price_info(self) -> None:
        """Fetch just the price info (dynamic, hourly/quarter-hourly)."""
        data = await self._gql_client.execute(
            UPDATE_PRICE_INFO, variable_values=self._vars(),
        )
        home_data = self._home_payload(data)
        if not home_data:
            return

        price_info = (
            home_data.get("currentSubscription", {}).get("priceInfo", {}) or {}
        )
        self._price_info = price_info
        self._process_price_info(price_info)

    async def update_info(self) -> None:
        """Fetch static info (if stale) and refresh price info."""
        if self.needs_static_refresh():
            await self.update_static_info()
        await self.update_price_info()

    async def update_current_price(self) -> None:
        """Fetch only the current price."""
        data = await self._gql_client.execute(
            UPDATE_CURRENT_PRICE, variable_values=self._vars(),
        )
        current = (
            self._home_payload(data)
            .get("currentSubscription", {})
            .get("priceInfo", {})
            .get("current", {})
        )
        if current and current.get("startsAt"):
            self.price_total[current["startsAt"]] = current.get("total", 0)

    def _keep_sub_hourly(
        self,
        mapping: dict[str, Any],
        today: datetime.date,
        tomorrow: datetime.date,
    ) -> dict[str, Any]:
        """Return entries for today/tomorrow whose startsAt is not on the hour."""
        kept: dict[str, Any] = {}
        for starts_at, value in mapping.items():
            dt = _parse_iso(starts_at)
            if dt is None:
                continue
            local = dt.astimezone(self._time_zone)
            if local.date() in (today, tomorrow) and local.minute != 0:
                kept[starts_at] = value
        return kept

    def _process_price_info(self, price_info: dict[str, Any]) -> None:
        """Merge hourly price_info into price_total/price_level caches.

        Preserves sub-hourly entries from previous ``current`` fetches so
        that 15-minute price resolution is retained across coordinator
        polls.
        """
        now = datetime.datetime.now(self._time_zone)
        today = now.date()
        tomorrow = today + datetime.timedelta(days=1)

        self.price_total = self._keep_sub_hourly(self.price_total, today, tomorrow)
        self.price_level = self._keep_sub_hourly(self.price_level, today, tomorrow)

        for period in ("today", "tomorrow"):
            for price in price_info.get(period) or []:
                starts_at = price.get("startsAt")
                if not starts_at:
                    continue
                if price.get("total") is not None:
                    self.price_total[starts_at] = price["total"]
                if price.get("currency"):
                    self.currency = price["currency"]
                if price.get("level"):
                    self.price_level[starts_at] = price["level"]

        current = price_info.get("current") or {}
        starts_at = current.get("startsAt")
        if starts_at:
            if current.get("total") is not None:
                self.price_total[starts_at] = current["total"]
            if current.get("currency"):
                self.currency = current["currency"]
            if current.get("level"):
                self.price_level[starts_at] = current["level"]

    # ------------------------------------------------------------------
    # Derived price views

    def _find_current_entry(
        self, data: dict[str, Any],
    ) -> tuple[str | None, Any]:
        """Find the latest (startsAt, value) pair whose startsAt <= now."""
        now = datetime.datetime.now(self._time_zone)
        best_dt: datetime.datetime | None = None
        best_key: str | None = None
        best_value: Any = None

        for starts_at, value in data.items():
            dt = _parse_iso(starts_at)
            if dt is None:
                continue
            local = dt.astimezone(self._time_zone)
            if local <= now and (best_dt is None or local > best_dt):
                best_dt = local
                best_key = starts_at
                best_value = value

        return best_key, best_value

    def current_price_data(
        self,
    ) -> tuple[float | None, str | None, float | None]:
        """Return current price, starts_at, and price rank."""
        starts_at, price = self._find_current_entry(self.price_total)
        if price is None:
            return None, None, None
        return price, starts_at, self.current_price_rank()

    def current_price_rank(self) -> float | None:
        """Return the current price rank (0.0..1.0) among today's prices."""
        starts_at, current_price = self._find_current_entry(self.price_total)
        if current_price is None or starts_at is None:
            return None

        cache_key = (starts_at, current_price)
        if self._rank_cache_key == cache_key:
            return self._rank_cache_value

        today = datetime.datetime.now(self._time_zone).date()
        today_prices = filter_by_date(self.price_total, today, self._time_zone)
        if not today_prices:
            return None

        sorted_prices = sorted(today_prices)
        try:
            rank_index = sorted_prices.index(current_price)
        except ValueError:
            return None
        rank = rank_index / max(len(sorted_prices) - 1, 1)

        self._rank_cache_key = cache_key
        self._rank_cache_value = rank
        return rank

    def current_price_level(self) -> str | None:
        """Return the current price level."""
        _, level = self._find_current_entry(self.price_level)
        return level

    def current_attributes(self) -> dict[str, Any]:
        """Return daily price statistics for use as extra state attributes."""
        today = datetime.datetime.now(self._time_zone).date()
        tomorrow = today + datetime.timedelta(days=1)

        # Single pass over price_total, classifying each entry into the
        # buckets needed for the attribute summary.
        today_prices: list[float] = []
        peak_prices: list[float] = []
        off_peak_prices: list[float] = []
        tomorrow_has_data = False

        for starts_at, value in self.price_total.items():
            dt = _parse_iso(starts_at)
            if dt is None:
                continue
            local = dt.astimezone(self._time_zone)
            local_date = local.date()
            if local_date == today:
                today_prices.append(value)
                if 6 <= local.hour < 22:
                    peak_prices.append(value)
                else:
                    off_peak_prices.append(value)
            elif local_date == tomorrow:
                tomorrow_has_data = True

        attrs: dict[str, Any] = {}
        if not today_prices:
            return attrs

        attrs["max_price"] = max(today_prices)
        attrs["avg_price"] = sum(today_prices) / len(today_prices)
        attrs["min_price"] = min(today_prices)

        if peak_prices:
            attrs["peak_price"] = sum(peak_prices) / len(peak_prices)
        if off_peak_prices:
            attrs["off_peak_1"] = sum(off_peak_prices) / len(off_peak_prices)

        attrs["tomorrow_valid"] = tomorrow_has_data

        level = self.current_price_level()
        if level:
            attrs["price_level"] = level
        return attrs

    # ------------------------------------------------------------------
    # Historic data fetch / aggregation

    async def fetch_consumption_data(self) -> None:
        """Fetch hourly consumption data (delta, then re-aggregate)."""
        await self._fetch_data(self._hourly_consumption_data)

    async def fetch_production_data(self) -> None:
        """Fetch hourly production data (delta, then re-aggregate)."""
        await self._fetch_data(self._hourly_production_data)

    async def _fetch_data(self, hourly_data: HourlyData) -> None:
        """Fetch hourly data.

        On first run (no ``last_data_timestamp``) fetches a seed window
        of ~30 days so recorder statistics have context.  Subsequent
        calls use the cached ``last_data_timestamp`` as a
        ``filterFrom`` cursor and only fetch new hours.
        """
        if hourly_data.last_data_timestamp:
            # Delta fetch from last known timestamp.
            new_entries = await self.get_historic_data_date(
                date_from=hourly_data.last_data_timestamp,
                n_data=_DELTA_BATCH_HOURS,
                production=(hourly_data.direction == "production"),
            )
            if new_entries:
                existing = {e.get("from"): e for e in hourly_data.data}
                for entry in new_entries:
                    if key := entry.get("from"):
                        existing[key] = entry
                # Deterministic chronological order.
                merged = sorted(
                    existing.values(),
                    key=lambda e: e.get("from") or "",
                )
                # Bound in-memory retention.
                hourly_data.data = merged[-_HOURLY_DATA_RETENTION:]
                hourly_data.has_data = True
        else:
            # Seed fetch.
            seed = await self.get_historic_data(
                n_data=_FIRST_RUN_SEED_HOURS,
                resolution=RESOLUTION_HOURLY,
                production=(hourly_data.direction == "production"),
            )
            if not seed:
                return
            hourly_data.data = seed
            hourly_data.has_data = True

        if not hourly_data.data:
            return

        self._recompute_monthly_totals(hourly_data)

    def _recompute_monthly_totals(self, hourly_data: HourlyData) -> None:
        """Recalculate month totals / peak hour from ``hourly_data.data``."""
        now = datetime.datetime.now(self._time_zone)
        month_energy = 0.0
        month_money = 0.0
        peak_hour = 0.0
        peak_hour_time = ""

        for entry in hourly_data.data:
            from_time = entry.get("from")
            dt = _parse_iso(from_time) if from_time else None
            if dt is None:
                continue
            local = dt.astimezone(self._time_zone)
            if local.month != now.month or local.year != now.year:
                continue

            energy = entry.get(hourly_data.direction) or 0
            cost = entry.get("cost") or 0
            month_energy += energy
            month_money += cost
            if energy > peak_hour:
                peak_hour = energy
                peak_hour_time = from_time

        hourly_data.month_energy = round(month_energy, 2)
        hourly_data.month_money = round(month_money, 2)
        hourly_data.peak_hour = round(peak_hour, 2)
        hourly_data.peak_hour_time = peak_hour_time

        last = hourly_data.data[-1].get("from", "") if hourly_data.data else ""
        if last:
            hourly_data.last_data_timestamp = last

    async def get_historic_data(
        self,
        n_data: int = 100,
        resolution: str = RESOLUTION_HOURLY,
        production: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch historical data with cursor-based pagination."""
        direction = "production" if production else "consumption"
        query = historic_data_query(direction, resolution)
        all_data: list[dict[str, Any]] = []
        cursor: str | None = None
        remaining = n_data

        while remaining > 0:
            batch_size = min(remaining, 100)
            data = await self._gql_client.execute(
                query,
                variable_values=self._vars(n=batch_size, before=cursor),
            )
            direction_data = self._home_payload(data).get(direction) or {}
            nodes = direction_data.get("nodes") or []
            page_info = direction_data.get("pageInfo") or {}

            if not nodes:
                break

            all_data = nodes + all_data
            remaining -= len(nodes)

            if not page_info.get("hasPreviousPage"):
                break
            cursor = page_info.get("startCursor")

        return all_data

    async def get_historic_data_date(
        self,
        date_from: str,
        n_data: int = 100,
        resolution: str = RESOLUTION_HOURLY,
        production: bool = False,
    ) -> list[dict[str, Any]]:
        """Fetch historical data from a specific date using ``filterFrom``."""
        direction = "production" if production else "consumption"
        query = historic_data_date_query(direction, resolution)
        data = await self._gql_client.execute(
            query,
            variable_values=self._vars(n=n_data, filterFrom=date_from),
        )
        direction_data = self._home_payload(data).get(direction) or {}
        return direction_data.get("nodes") or []

    async def get_historic_price_data(self) -> list[dict[str, Any]]:
        """Fetch historical price rating data."""
        data = await self._gql_client.execute(
            HISTORIC_PRICE, variable_values=self._vars(),
        )
        return (
            self._home_payload(data)
            .get("currentSubscription", {})
            .get("priceRating", {})
            .get("hourly", {})
            .get("entries", [])
        )

    # ------------------------------------------------------------------
    # Real-time enrichment

    def add_rt_extra_data(
        self, data: dict[str, Any],
    ) -> dict[str, Any]:
        """Enrich real-time measurement data with computed fields."""
        timestamp_str = data.get("timestamp")
        power = data.get("power")

        if timestamp_str and power is not None:
            timestamp = _parse_iso(timestamp_str)
            if timestamp is not None:
                self._rt_power.append((timestamp, power))
                # Evict entries older than one hour in O(k) amortized,
                # where k is the (small) number of expired entries.
                cutoff = timestamp - datetime.timedelta(hours=1)
                buf = self._rt_power
                while buf and buf[0][0] <= cutoff:
                    buf.popleft()
                if len(buf) > 1:
                    avg_power = sum(p for _, p in buf) / len(buf)
                    data["estimatedHourConsumption"] = round(
                        avg_power / 1000, 3,
                    )

        for key in ("power", "powerProduction"):
            if key in data and data[key] is None:
                data[key] = 0.0

        data["netPower"] = round(
            (data.get("power") or 0) - (data.get("powerProduction") or 0), 1,
        )
        return data
