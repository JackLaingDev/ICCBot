"""Signal guard-rail checks for forward-testing safety.

This module provides pure, reusable checks that can block signal emission when
data/session/cadence safety conditions are not met. It contains no broker calls,
no order placement, and no strategy logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd


GateStatus = Literal["passed", "blocked"]


@dataclass(frozen=True)
class SignalGuardInput:
    """Input payload for signal guard-rail evaluation."""

    evaluation_time_utc: pd.Timestamp
    candle_time_utc: pd.Timestamp | None
    has_m15_data: bool
    has_h1_data: bool
    duplicate_candle: bool
    session_start_hour_utc: int
    session_end_hour_utc: int
    candle_minutes: int = 15
    stale_after_minutes: int = 30
    max_signals_per_day: int | None = None
    signals_today: int = 0


@dataclass(frozen=True)
class SignalGuardResult:
    """Guard-rail decision with per-gate statuses and block reason."""

    allowed: bool
    reason: str
    closed_candle: GateStatus
    session: GateStatus
    data_freshness: GateStatus
    duplicate: GateStatus
    max_signals_per_day: GateStatus


def evaluate_signal_guardrails(input_data: SignalGuardInput) -> SignalGuardResult:
    """Evaluate guard rails in a deterministic order."""
    evaluation_time = _to_utc_timestamp(input_data.evaluation_time_utc)

    has_data = bool(input_data.has_m15_data and input_data.has_h1_data)
    if not has_data:
        if not input_data.has_m15_data:
            reason = "missing_m15_data"
        elif not input_data.has_h1_data:
            reason = "missing_h1_data"
        else:
            reason = "missing_required_data"
        return SignalGuardResult(
            allowed=False,
            reason=reason,
            closed_candle="blocked",
            session="blocked",
            data_freshness="blocked",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )

    if input_data.candle_time_utc is None:
        return SignalGuardResult(
            allowed=False,
            reason="missing_closed_candle",
            closed_candle="blocked",
            session="blocked",
            data_freshness="blocked",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )

    candle_time = _to_utc_timestamp(input_data.candle_time_utc)

    close_time = candle_time + pd.Timedelta(minutes=input_data.candle_minutes)
    if candle_time > evaluation_time:
        return SignalGuardResult(
            allowed=False,
            reason="future_candle_timestamp",
            closed_candle="blocked",
            session="blocked",
            data_freshness="blocked",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )
    if close_time > evaluation_time:
        return SignalGuardResult(
            allowed=False,
            reason="current_candle_not_closed",
            closed_candle="blocked",
            session="blocked",
            data_freshness="blocked",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )

    if (evaluation_time - close_time) > pd.Timedelta(minutes=input_data.stale_after_minutes):
        return SignalGuardResult(
            allowed=False,
            reason="stale_closed_candle",
            closed_candle="passed",
            session="blocked",
            data_freshness="blocked",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )

    hour = int(candle_time.hour)
    in_session = _is_hour_in_window(
        hour=hour,
        start_hour=input_data.session_start_hour_utc,
        end_hour=input_data.session_end_hour_utc,
    )
    if not in_session:
        return SignalGuardResult(
            allowed=False,
            reason="blocked_by_session",
            closed_candle="passed",
            session="blocked",
            data_freshness="passed",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )

    if input_data.duplicate_candle:
        return SignalGuardResult(
            allowed=False,
            reason="duplicate_candle_already_logged",
            closed_candle="passed",
            session="passed",
            data_freshness="passed",
            duplicate="blocked",
            max_signals_per_day="blocked",
        )

    if (
        input_data.max_signals_per_day is not None
        and input_data.signals_today >= input_data.max_signals_per_day
    ):
        return SignalGuardResult(
            allowed=False,
            reason="max_signals_per_day_reached",
            closed_candle="passed",
            session="passed",
            data_freshness="passed",
            duplicate="passed",
            max_signals_per_day="blocked",
        )

    return SignalGuardResult(
        allowed=True,
        reason="guardrails_passed",
        closed_candle="passed",
        session="passed",
        data_freshness="passed",
        duplicate="passed",
        max_signals_per_day="passed",
    )


def _to_utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _is_hour_in_window(*, hour: int, start_hour: int, end_hour: int) -> bool:
    if start_hour < end_hour:
        return start_hour <= hour < end_hour
    return hour >= start_hour or hour < end_hour
