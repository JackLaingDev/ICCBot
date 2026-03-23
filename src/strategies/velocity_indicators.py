"""Indicator helpers for momentum-velocity strategy research."""

from __future__ import annotations

import numpy as np
import pandas as pd

REQUIRED_COLUMNS = {"time", "open", "high", "low", "close", "volume"}


def calculate_wilder_atr(dataframe: pd.DataFrame, *, period: int) -> pd.Series:
    """Calculate Wilder-style ATR from OHLC data."""
    if period <= 1:
        raise ValueError("period must be > 1")
    _validate_ohlc_dataframe(dataframe)

    high = pd.to_numeric(dataframe["high"], errors="coerce")
    low = pd.to_numeric(dataframe["low"], errors="coerce")
    close = pd.to_numeric(dataframe["close"], errors="coerce")
    prev_close = close.shift(1)

    true_range = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = true_range.ewm(alpha=1.0 / period, adjust=False, min_periods=period).mean()
    return atr


def calculate_velocity(
    dataframe: pd.DataFrame,
    *,
    lookback_k: int,
    atr_period: int,
    smoothing_span: int,
) -> pd.DataFrame:
    """Build ATR-normalized log-return velocity features.

    Notes:
    - Uses closed-bar values only.
    - Bars with non-positive close or non-positive ATR yield NaN velocity.
    """
    if lookback_k <= 0:
        raise ValueError("lookback_k must be > 0")
    if smoothing_span <= 0:
        raise ValueError("smoothing_span must be > 0")
    _validate_ohlc_dataframe(dataframe)

    close = pd.to_numeric(dataframe["close"], errors="coerce")
    atr = calculate_wilder_atr(dataframe, period=atr_period)

    safe_close = close.where(close > 0)
    safe_atr = atr.where(atr > 0)
    log_return = np.log(safe_close / safe_close.shift(lookback_k))
    raw_velocity = log_return / safe_atr

    velocity = raw_velocity
    if smoothing_span > 1:
        velocity = raw_velocity.ewm(span=smoothing_span, adjust=False).mean()

    features = pd.DataFrame(index=dataframe.index)
    features["atr"] = atr
    features["raw_velocity"] = raw_velocity
    features["velocity"] = velocity
    return features


def calculate_trend_ema(
    dataframe: pd.DataFrame,
    *,
    period: int,
) -> pd.Series:
    """Calculate trend EMA over close prices."""
    if period <= 1:
        raise ValueError("period must be > 1")
    _validate_ohlc_dataframe(dataframe)
    close = pd.to_numeric(dataframe["close"], errors="coerce")
    return close.ewm(span=period, adjust=False, min_periods=period).mean()


def _validate_ohlc_dataframe(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")
    missing = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing:
        raise ValueError(f"dataframe is missing required columns: {sorted(missing)}")
