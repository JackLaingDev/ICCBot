"""Market-data loading and normalization utilities.

This module converts raw MT5 rates into a clean OHLCV dataframe.
It must not contain strategy, risk, execution, or backtest logic.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from src.data.mt5_client import MT5Client


STANDARD_COLUMNS = ["time", "open", "high", "low", "close", "volume"]


def bars_to_dataframe(raw_bars: Any) -> pd.DataFrame:
    """Convert raw MT5 bars into a standardized OHLCV dataframe."""

    dataframe = pd.DataFrame(raw_bars)
    if dataframe.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    volume_source = None
    if "tick_volume" in dataframe.columns:
        volume_source = "tick_volume"
    elif "real_volume" in dataframe.columns:
        volume_source = "real_volume"
    elif "volume" in dataframe.columns:
        volume_source = "volume"

    if volume_source is None:
        raise ValueError("Raw bars must include one of: tick_volume, real_volume, volume.")

    dataframe = dataframe.rename(columns={volume_source: "volume"})

    missing = [col for col in STANDARD_COLUMNS if col not in dataframe.columns]
    if missing:
        raise ValueError(f"Raw bars missing required columns: {missing}")

    dataframe = dataframe[STANDARD_COLUMNS].copy()
    dataframe["time"] = pd.to_datetime(dataframe["time"], unit="s", utc=True, errors="coerce")

    for column_name in ["open", "high", "low", "close", "volume"]:
        dataframe[column_name] = pd.to_numeric(dataframe[column_name], errors="coerce")

    dataframe = dataframe.dropna(subset=STANDARD_COLUMNS)
    dataframe = dataframe.sort_values("time")
    dataframe = dataframe.drop_duplicates(subset=["time"], keep="last")
    dataframe = dataframe.reset_index(drop=True)
    return dataframe


def fetch_market_data(
    client: MT5Client, symbol: str, timeframe: str | int, count: int
) -> pd.DataFrame:
    """Fetch raw rates through client and return normalized OHLCV data."""

    raw_bars = client.get_rates(symbol=symbol, timeframe=timeframe, count=count)
    return bars_to_dataframe(raw_bars)
