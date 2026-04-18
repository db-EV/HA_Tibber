"""Data models for the Tibber API."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, TypedDict


class TibberHomeData(TypedDict):
    """Coordinator data for a Tibber home."""

    prices: dict[str, float]
    price_rank: float | None
    attributes: dict[str, Any]
    home_name: str
    currency: str


@dataclass
class HourlyData:
    """Track hourly consumption or production data."""

    direction: str  # "consumption" or "production"
    month_energy: float = 0.0
    month_money: float = 0.0
    peak_hour: float = 0.0
    peak_hour_time: str = ""
    last_data_timestamp: str = ""
    data: list[dict[str, Any]] = field(default_factory=list)
    has_data: bool = False
