"""Minimal ICC v1 strategy evaluation.

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
) -> StrategyDecision:
    """Evaluate a simple ICC-style signal from OHLCV data.

    Rules:
    - Indication: close above/below EMA(200)
    - Correction: recent pullback against trend over a short lookback window
    - Continuation: close breaks previous candle high/low after pullback
    """

    _validate_inputs(
        dataframe=dataframe,
        ema_period=ema_period,
        pullback_lookback=pullback_lookback,
        take_profit_rr=take_profit_rr,
    )

    # Strategy evaluation is order-sensitive; enforce chronological ordering.
    working = dataframe.sort_values("time").reset_index(drop=True).copy()
    for column_name in PRICE_COLUMNS:
        working[column_name] = pd.to_numeric(working[column_name], errors="raise")
    working["ema"] = working["close"].ewm(span=ema_period, adjust=False).mean()

    current = working.iloc[-1]
    previous = working.iloc[-2]
    pullback_window = working.iloc[-(pullback_lookback + 1) : -1]

    if current["close"] > current["ema"]:
        has_pullback = bool((pullback_window["low"] <= pullback_window["ema"]).any())
        if not has_pullback:
            return StrategyDecision(signal="NONE", reason="no_bullish_pullback")

        if current["close"] <= previous["high"]:
            return StrategyDecision(signal="NONE", reason="no_bullish_continuation")

        entry = float(current["close"])
        stop_loss = float(pullback_window["low"].min())
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

    if current["close"] < current["ema"]:
        has_pullback = bool((pullback_window["high"] >= pullback_window["ema"]).any())
        if not has_pullback:
            return StrategyDecision(signal="NONE", reason="no_bearish_pullback")

        if current["close"] >= previous["low"]:
            return StrategyDecision(signal="NONE", reason="no_bearish_continuation")

        entry = float(current["close"])
        stop_loss = float(pullback_window["high"].max())
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

    return StrategyDecision(signal="NONE", reason="neutral_bias")


def _validate_inputs(
    *,
    dataframe: pd.DataFrame,
    ema_period: int,
    pullback_lookback: int,
    take_profit_rr: float,
) -> None:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")

    missing = REQUIRED_COLUMNS.difference(dataframe.columns)
    if missing:
        raise ValueError(f"dataframe is missing required columns: {sorted(missing)}")

    if ema_period <= 1:
        raise ValueError("ema_period must be > 1")
    if pullback_lookback < 2:
        raise ValueError("pullback_lookback must be >= 2")
    if take_profit_rr <= 0:
        raise ValueError("take_profit_rr must be > 0")

    minimum_rows = max(ema_period + 2, pullback_lookback + 2)
    if len(dataframe) < minimum_rows:
        raise ValueError(
            f"dataframe requires at least {minimum_rows} rows for configured parameters"
        )

    for column_name in PRICE_COLUMNS:
        try:
            pd.to_numeric(dataframe[column_name], errors="raise")
        except Exception as exc:
            raise ValueError(f"{column_name} must be numeric.") from exc
