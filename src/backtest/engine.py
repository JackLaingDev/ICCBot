"""Simple sequential backtest engine.

This module simulates strategy trades candle-by-candle with one active trade at a time.
It contains no MT5 or live execution behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal

import pandas as pd

from src.strategies.icc_strategy import evaluate_icc_v1
from src.strategies.models import StrategyDecision


@dataclass(frozen=True)
class BacktestTrade:
    """A single simulated trade result."""

    direction: Literal["BUY", "SELL"]
    entry_index: int
    entry_time: object
    entry_price: float
    stop_loss: float
    take_profit: float
    exit_index: int
    exit_time: object
    exit_price: float
    exit_reason: str
    profit: float
    rr: float | None


def run_backtest(
    dataframe: pd.DataFrame,
    *,
    ema_period: int = 200,
    pullback_lookback: int = 5,
    take_profit_rr: float = 1.5,
    allowed_directions: set[str] | None = None,
    session_start_hour: int | None = None,
    session_end_hour: int | None = None,
    htf_bias_by_time: dict[object, str] | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[BacktestTrade]:
    """Run a deterministic one-trade-at-a-time backtest over OHLCV candles.

    Session filtering, when configured, applies to entry generation only.
    """

    _validate_backtest_input(dataframe)
    _validate_allowed_directions(allowed_directions)
    _validate_session_hours(
        session_start_hour=session_start_hour,
        session_end_hour=session_end_hour,
    )
    _validate_htf_bias_by_time(htf_bias_by_time)
    ordered = dataframe.sort_values("time").reset_index(drop=True)
    trades: list[BacktestTrade] = []
    total_bars = len(ordered)

    index = 0
    if progress_callback is not None:
        progress_callback(0, total_bars)
    while index < len(ordered):
        current_index = index
        window = ordered.iloc[: index + 1]
        try:
            decision = evaluate_icc_v1(
                window,
                ema_period=ema_period,
                pullback_lookback=pullback_lookback,
                take_profit_rr=take_profit_rr,
            )
        except ValueError as exc:
            # Warm-up period: strategy may need more rows before evaluation is possible.
            if "requires at least" in str(exc):
                index += 1
                if progress_callback is not None:
                    progress_callback(index, total_bars)
                continue
            raise

        if decision.signal == "NONE":
            index += 1
            if progress_callback is not None:
                progress_callback(index, total_bars)
            continue
        if allowed_directions is not None and decision.signal not in allowed_directions:
            index += 1
            if progress_callback is not None:
                progress_callback(index, total_bars)
            continue
        entry_time = ordered.iloc[index]["time"]
        if not _is_entry_hour_allowed(
            entry_time=entry_time,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
        ):
            index += 1
            if progress_callback is not None:
                progress_callback(index, total_bars)
            continue
        if not _is_entry_aligned_with_htf_bias(
            entry_time=entry_time,
            signal=decision.signal,
            htf_bias_by_time=htf_bias_by_time,
        ):
            index += 1
            if progress_callback is not None:
                progress_callback(index, total_bars)
            continue
        if decision.stop_loss is None or decision.take_profit is None:
            index += 1
            if progress_callback is not None:
                progress_callback(index, total_bars)
            continue

        trade = _simulate_trade(
            dataframe=ordered,
            entry_index=index,
            decision=decision,
        )
        trades.append(trade)
        index = trade.exit_index + 1
        if progress_callback is not None:
            progress_callback(index, total_bars)

        # Guard against no-forward-progress edge cases.
        if index <= current_index:
            index = current_index + 1
            if progress_callback is not None:
                progress_callback(index, total_bars)

    if progress_callback is not None:
        progress_callback(total_bars, total_bars)

    return trades


def _simulate_trade(
    *,
    dataframe: pd.DataFrame,
    entry_index: int,
    decision: StrategyDecision,
) -> BacktestTrade:
    entry_candle = dataframe.iloc[entry_index]
    direction = decision.signal
    if direction not in {"BUY", "SELL"}:
        raise ValueError("decision.signal must be BUY or SELL for trade simulation")
    entry_price = float(entry_candle["close"])
    stop_loss = float(decision.stop_loss)
    take_profit = float(decision.take_profit)

    exit_index = len(dataframe) - 1
    exit_price = float(dataframe.iloc[-1]["close"])
    exit_reason = "end_of_data"

    for idx in range(entry_index + 1, len(dataframe)):
        candle = dataframe.iloc[idx]
        high = float(candle["high"])
        low = float(candle["low"])

        if direction == "BUY":
            # Conservative same-candle handling: assume SL first if both hit.
            if low <= stop_loss:
                exit_index = idx
                exit_price = stop_loss
                exit_reason = "stop_loss"
                break
            if high >= take_profit:
                exit_index = idx
                exit_price = take_profit
                exit_reason = "take_profit"
                break
        else:  # SELL
            if high >= stop_loss:
                exit_index = idx
                exit_price = stop_loss
                exit_reason = "stop_loss"
                break
            if low <= take_profit:
                exit_index = idx
                exit_price = take_profit
                exit_reason = "take_profit"
                break

    if direction == "BUY":
        profit = exit_price - entry_price
        risk = entry_price - stop_loss
    else:
        profit = entry_price - exit_price
        risk = stop_loss - entry_price

    rr = (profit / risk) if risk > 0 else None
    exit_candle = dataframe.iloc[exit_index]

    return BacktestTrade(
        direction=direction,
        entry_index=entry_index,
        entry_time=entry_candle["time"],
        entry_price=entry_price,
        stop_loss=stop_loss,
        take_profit=take_profit,
        exit_index=exit_index,
        exit_time=exit_candle["time"],
        exit_price=exit_price,
        exit_reason=exit_reason,
        profit=profit,
        rr=rr,
    )


def _validate_backtest_input(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")

    required = {"time", "open", "high", "low", "close", "volume"}
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"dataframe is missing required columns: {sorted(missing)}")


def _validate_allowed_directions(allowed_directions: set[str] | None) -> None:
    if allowed_directions is None:
        return
    invalid = set(allowed_directions).difference({"BUY", "SELL"})
    if invalid:
        raise ValueError(f"allowed_directions contains invalid values: {sorted(invalid)}")


def _validate_session_hours(
    *,
    session_start_hour: int | None,
    session_end_hour: int | None,
) -> None:
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


def _is_entry_hour_allowed(
    *,
    entry_time: object,
    session_start_hour: int | None,
    session_end_hour: int | None,
) -> bool:
    if session_start_hour is None and session_end_hour is None:
        return True

    hour = _to_utc_hour(entry_time)
    if session_start_hour < session_end_hour:
        return session_start_hour <= hour < session_end_hour
    return hour >= session_start_hour or hour < session_end_hour


def _is_entry_aligned_with_htf_bias(
    *,
    entry_time: object,
    signal: str,
    htf_bias_by_time: dict[object, str] | None,
) -> bool:
    if htf_bias_by_time is None:
        return True

    bias = htf_bias_by_time.get(_to_utc_timestamp(entry_time))
    if bias is None:
        return False

    if signal == "BUY":
        return bias == "BULLISH"
    if signal == "SELL":
        return bias == "BEARISH"
    return False


def _validate_htf_bias_by_time(htf_bias_by_time: dict[object, str] | None) -> None:
    if htf_bias_by_time is None:
        return
    valid = {"BULLISH", "BEARISH", "NEUTRAL"}
    for key, value in htf_bias_by_time.items():
        _to_utc_timestamp(key)
        if value not in valid:
            raise ValueError(f"htf_bias_by_time contains invalid value: {value!r}")


def _to_utc_hour(entry_time: object) -> int:
    """Return hour-of-day in UTC from entry_time.

    Naive datetimes are treated as UTC by convention.
    """
    timestamp = pd.Timestamp(entry_time)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return int(timestamp.hour)


def _to_utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")
