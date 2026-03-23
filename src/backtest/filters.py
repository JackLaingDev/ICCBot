"""Shared entry-filter and time-normalization helpers for backtests."""

from __future__ import annotations

import pandas as pd


def validate_allowed_directions(allowed_directions: set[str] | None) -> None:
    """Validate optional direction whitelist."""
    if allowed_directions is None:
        return
    invalid = set(allowed_directions).difference({"BUY", "SELL"})
    if invalid:
        raise ValueError(f"allowed_directions contains invalid values: {sorted(invalid)}")


def validate_session_hours(
    *,
    session_start_hour: int | None,
    session_end_hour: int | None,
) -> None:
    """Validate optional UTC session window."""
    if (session_start_hour is None) != (session_end_hour is None):
        raise ValueError("session_start_hour and session_end_hour must be set together")
    if session_start_hour is None and session_end_hour is None:
        return
    if not (0 <= session_start_hour <= 23):
        raise ValueError("session_start_hour must be between 0 and 23")
    if not (0 <= session_end_hour <= 23):
        raise ValueError("session_end_hour must be between 0 and 23")
    if session_start_hour == session_end_hour:
        raise ValueError(
            "session_start_hour and session_end_hour must differ; "
            "omit both to allow all hours"
        )


def is_entry_hour_allowed(
    *,
    entry_time: object,
    session_start_hour: int | None,
    session_end_hour: int | None,
) -> bool:
    """Return whether entry timestamp is inside configured UTC session."""
    if session_start_hour is None and session_end_hour is None:
        return True
    hour = to_utc_hour(entry_time)
    if session_start_hour < session_end_hour:
        return session_start_hour <= hour < session_end_hour
    return hour >= session_start_hour or hour < session_end_hour


def validate_htf_bias_by_time(htf_bias_by_time: dict[object, str] | None) -> None:
    """Validate optional higher-timeframe bias mapping."""
    if htf_bias_by_time is None:
        return
    valid = {"BULLISH", "BEARISH", "NEUTRAL"}
    for key, value in htf_bias_by_time.items():
        to_utc_timestamp(key)
        if value not in valid:
            raise ValueError(f"htf_bias_by_time contains invalid value: {value!r}")


def is_entry_aligned_with_htf_bias(
    *,
    entry_time: object,
    signal: str,
    htf_bias_by_time: dict[object, str] | None,
) -> bool:
    """Return whether entry direction aligns with HTF bias map."""
    if htf_bias_by_time is None:
        return True
    bias = htf_bias_by_time.get(to_utc_timestamp(entry_time))
    if bias is None:
        return False
    if signal == "BUY":
        return bias == "BULLISH"
    if signal == "SELL":
        return bias == "BEARISH"
    return False


def validate_entry_regime_filter(
    *,
    entry_regime_by_time: dict[object, str] | None,
    required_entry_regime: str | None,
) -> None:
    """Validate optional volatility-regime entry filter."""
    if required_entry_regime is None:
        return
    if required_entry_regime not in {"high_vol", "low_vol"}:
        raise ValueError("required_entry_regime must be one of: high_vol, low_vol")
    if entry_regime_by_time is None:
        raise ValueError("entry_regime_by_time must be provided when required_entry_regime is set")
    valid = {"high_vol", "low_vol"}
    for key, value in entry_regime_by_time.items():
        to_utc_timestamp(key)
        if value not in valid:
            raise ValueError(f"entry_regime_by_time contains invalid value: {value!r}")


def is_entry_allowed_by_regime(
    *,
    entry_time: object,
    entry_regime_by_time: dict[object, str] | None,
    required_entry_regime: str | None,
) -> bool:
    """Return whether entry bar regime matches required filter."""
    if required_entry_regime is None:
        return True
    if entry_regime_by_time is None:
        return False
    regime = entry_regime_by_time.get(to_utc_timestamp(entry_time))
    return regime == required_entry_regime


def to_utc_hour(entry_time: object) -> int:
    """Return hour-of-day in UTC from timestamp-like value."""
    timestamp = pd.Timestamp(entry_time)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return int(timestamp.hour)


def to_utc_timestamp(value: object) -> pd.Timestamp:
    """Normalize value to UTC timestamp, treating naive values as UTC."""
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")
