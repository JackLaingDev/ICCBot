"""Minimal ICC v2 structure-based strategy evaluation.

This module is pure strategy logic only:
- consumes normalized OHLCV dataframe input
- returns BUY/SELL/NONE plus proposed SL/TP
- contains no MT5, execution, risk-sizing, or runtime-loop behavior
"""

from __future__ import annotations

import pandas as pd

from src.strategies.models import StrategyDecision


REQUIRED_COLUMNS = {"time", "open", "high", "low", "close", "volume"}
PRICE_COLUMNS = ("high", "low", "close")


def evaluate_icc_v1(
    dataframe: pd.DataFrame,
    *,
    ema_period: int = 200,
    pullback_lookback: int = 5,
    take_profit_rr: float = 1.5,
    swing_window: int = 2,
    validate_inputs: bool = True,
) -> StrategyDecision:
    """Evaluate a minimal structure-based ICC signal.

    Rules:
    - Indication: break of previous swing high/low (BOS)
    - Correction: pullback against BOS direction after the break
    - Continuation: current close breaks previous candle in BOS direction
    """

    minimum_rows = max((swing_window * 2) + 5, pullback_lookback + 3)
    if len(dataframe) < minimum_rows:
        raise ValueError(
            f"dataframe requires at least {minimum_rows} rows for configured parameters"
        )

    if validate_inputs:
        _validate_inputs(
            dataframe=dataframe,
            ema_period=ema_period,
            pullback_lookback=pullback_lookback,
            take_profit_rr=take_profit_rr,
            swing_window=swing_window,
        )
        # Strategy evaluation is order-sensitive; enforce chronological ordering.
        working = dataframe.sort_values("time").reset_index(drop=True).copy()
    else:
        # Fast-path for backtest engine: input is already validated and sorted once.
        working = dataframe

    current_index = len(working) - 1
    current = working.iloc[-1]
    previous = working.iloc[-2]

    swing_high_indexes, swing_low_indexes = _find_swings(working, swing_window=swing_window)
    bos = _find_latest_bos(
        dataframe=working,
        swing_high_indexes=swing_high_indexes,
        swing_low_indexes=swing_low_indexes,
        swing_window=swing_window,
        end_index=current_index - 1,
    )
    if bos is None:
        return StrategyDecision(signal="NONE", reason="no_structure_break")

    if current_index - bos["index"] > pullback_lookback:
        return StrategyDecision(signal="NONE", reason="bos_too_old")

    post_bos = working.iloc[bos["index"] + 1 : current_index]
    if post_bos.empty:
        return StrategyDecision(signal="NONE", reason="no_pullback_window")

    if bos["direction"] == "BUY":
        has_pullback = bool((post_bos["low"] <= bos["level"]).any())
        if not has_pullback:
            return StrategyDecision(signal="NONE", reason="no_bullish_pullback")
        if current["close"] <= previous["high"]:
            return StrategyDecision(signal="NONE", reason="no_bullish_continuation")

        entry = float(current["close"])
        stop_loss = float(post_bos["low"].min())
        risk = entry - stop_loss
        if risk <= 0:
            return StrategyDecision(signal="NONE", reason="invalid_bullish_stop")

        take_profit = entry + (risk * take_profit_rr)
        return StrategyDecision(
            signal="BUY",
            stop_loss=stop_loss,
            take_profit=float(take_profit),
            reason="buy_setup",
        )

    has_pullback = bool((post_bos["high"] >= bos["level"]).any())
    if not has_pullback:
        return StrategyDecision(signal="NONE", reason="no_bearish_pullback")
    if current["close"] >= previous["low"]:
        return StrategyDecision(signal="NONE", reason="no_bearish_continuation")

    entry = float(current["close"])
    stop_loss = float(post_bos["high"].max())
    risk = stop_loss - entry
    if risk <= 0:
        return StrategyDecision(signal="NONE", reason="invalid_bearish_stop")

    take_profit = entry - (risk * take_profit_rr)
    return StrategyDecision(
        signal="SELL",
        stop_loss=stop_loss,
        take_profit=float(take_profit),
        reason="sell_setup",
    )


def _find_swings(
    dataframe: pd.DataFrame, *, swing_window: int
) -> tuple[list[int], list[int]]:
    swing_high_indexes: list[int] = []
    swing_low_indexes: list[int] = []
    highs = dataframe["high"]
    lows = dataframe["low"]

    for idx in range(swing_window, len(dataframe) - swing_window):
        left_highs = highs.iloc[idx - swing_window : idx]
        right_highs = highs.iloc[idx + 1 : idx + 1 + swing_window]
        left_lows = lows.iloc[idx - swing_window : idx]
        right_lows = lows.iloc[idx + 1 : idx + 1 + swing_window]

        if highs.iloc[idx] > left_highs.max() and highs.iloc[idx] > right_highs.max():
            swing_high_indexes.append(idx)
        if lows.iloc[idx] < left_lows.min() and lows.iloc[idx] < right_lows.min():
            swing_low_indexes.append(idx)

    return swing_high_indexes, swing_low_indexes


def _find_latest_bos(
    *,
    dataframe: pd.DataFrame,
    swing_high_indexes: list[int],
    swing_low_indexes: list[int],
    swing_window: int,
    end_index: int,
) -> dict[str, float | int | str] | None:
    latest_bos: dict[str, float | int | str] | None = None
    close_series = dataframe["close"]
    high_series = dataframe["high"]
    low_series = dataframe["low"]
    high_pointer = 0
    low_pointer = 0
    last_confirmed_high_idx: int | None = None
    last_confirmed_low_idx: int | None = None

    for idx in range(1, end_index + 1):
        # BOS must leave at least one candle for pullback before continuation.
        if idx >= end_index:
            continue

        # Only use confirmed swings to avoid lookahead:
        # swing at `s` is confirmed only after `s + swing_window` candles.
        while (
            high_pointer < len(swing_high_indexes)
            and (swing_high_indexes[high_pointer] + swing_window) < idx
        ):
            last_confirmed_high_idx = swing_high_indexes[high_pointer]
            high_pointer += 1
        while (
            low_pointer < len(swing_low_indexes)
            and (swing_low_indexes[low_pointer] + swing_window) < idx
        ):
            last_confirmed_low_idx = swing_low_indexes[low_pointer]
            low_pointer += 1

        if last_confirmed_high_idx is not None:
            swing_high = float(high_series.iloc[last_confirmed_high_idx])
            if float(close_series.iloc[idx]) > swing_high:
                latest_bos = {"direction": "BUY", "index": idx, "level": swing_high}

        if last_confirmed_low_idx is not None:
            swing_low = float(low_series.iloc[last_confirmed_low_idx])
            if float(close_series.iloc[idx]) < swing_low:
                latest_bos = {"direction": "SELL", "index": idx, "level": swing_low}

    return latest_bos


def _validate_inputs(
    *,
    dataframe: pd.DataFrame,
    ema_period: int,
    pullback_lookback: int,
    take_profit_rr: float,
    swing_window: int,
) -> None:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")

    missing = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing:
        raise ValueError(f"dataframe is missing required columns: {sorted(missing)}")

    # Kept for backward compatibility with existing callers.
    if ema_period <= 1:
        raise ValueError("ema_period must be > 1")
    if pullback_lookback < 2:
        raise ValueError("pullback_lookback must be >= 2")
    if take_profit_rr <= 0:
        raise ValueError("take_profit_rr must be > 0")
    if swing_window < 1:
        raise ValueError("swing_window must be >= 1")

    minimum_rows = max((swing_window * 2) + 5, pullback_lookback + 3)
    if len(dataframe) < minimum_rows:
        raise ValueError(
            f"dataframe requires at least {minimum_rows} rows for configured parameters"
        )

    for column_name in PRICE_COLUMNS:
        try:
            pd.to_numeric(dataframe[column_name], errors="raise")
        except Exception as exc:
            raise ValueError(f"{column_name} must be numeric.") from exc

    if dataframe[list(PRICE_COLUMNS)].isna().any().any():
        raise ValueError("high, low, and close must not contain missing values")
