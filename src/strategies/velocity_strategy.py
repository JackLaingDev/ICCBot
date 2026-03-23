"""Entry and in-trade rules for momentum-velocity strategy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from src.strategies.models import StrategyDecision

VelocityDirection = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class VelocityStrategyParams:
    """Parameters for velocity strategy decision logic."""

    entry_threshold: float
    entry_persist: int
    drawdown_frac: float
    stop_atr_mult: float
    cooldown_bars: int
    trend_filter_enabled: bool
    trend_ema_period: int


@dataclass
class VelocityPositionState:
    """Mutable in-trade state tracked by velocity backtest engine."""

    direction: VelocityDirection
    entry_index: int
    entry_time: object
    entry_price: float
    stop_loss: float
    velocity_extreme: float


def evaluate_velocity_entry(
    dataframe: pd.DataFrame,
    *,
    current_index: int,
    params: VelocityStrategyParams,
) -> StrategyDecision:
    """Evaluate closed-bar velocity entry rules at current index."""
    validate_velocity_params(params)
    _validate_entry_dataframe(dataframe)
    if current_index < 0 or current_index >= len(dataframe):
        raise ValueError("current_index out of range")
    if current_index < params.entry_persist - 1:
        return StrategyDecision(signal="NONE", reason="insufficient_bars_for_persistence")

    window = dataframe.iloc[current_index - params.entry_persist + 1 : current_index + 1]
    velocity_values = pd.to_numeric(window["velocity"], errors="coerce")
    if velocity_values.isna().any():
        return StrategyDecision(signal="NONE", reason="velocity_not_ready")

    current = dataframe.iloc[current_index]
    current_close = float(current["close"])
    if pd.isna(current_close) or current_close <= 0:
        return StrategyDecision(signal="NONE", reason="invalid_close")
    current_atr = float(current["atr"]) if pd.notna(current["atr"]) else float("nan")
    if pd.isna(current_atr) or current_atr <= 0:
        return StrategyDecision(signal="NONE", reason="atr_not_ready")

    all_long = bool((velocity_values > params.entry_threshold).all())
    all_short = bool((velocity_values < -params.entry_threshold).all())
    if not all_long and not all_short:
        return StrategyDecision(signal="NONE", reason="threshold_or_persistence_not_met")

    if params.trend_filter_enabled:
        trend_ema = float(current["trend_ema"]) if pd.notna(current["trend_ema"]) else float("nan")
        if pd.isna(trend_ema):
            return StrategyDecision(signal="NONE", reason="trend_ema_not_ready")
        if all_long and current_close <= trend_ema:
            return StrategyDecision(signal="NONE", reason="blocked_by_trend_filter")
        if all_short and current_close >= trend_ema:
            return StrategyDecision(signal="NONE", reason="blocked_by_trend_filter")

    if all_long:
        stop_loss = current_close - (params.stop_atr_mult * current_atr)
        return StrategyDecision(signal="BUY", stop_loss=stop_loss, reason="velocity_long_entry")

    stop_loss = current_close + (params.stop_atr_mult * current_atr)
    return StrategyDecision(signal="SELL", stop_loss=stop_loss, reason="velocity_short_entry")


def should_exit_velocity_position(
    *,
    direction: VelocityDirection,
    current_velocity: float,
    velocity_extreme: float,
    drawdown_frac: float,
) -> tuple[bool, str | None]:
    """Determine if momentum-fade exit is triggered for active trade."""
    if direction == "BUY":
        if current_velocity < 0:
            return True, "velocity_sign_flip"
        if current_velocity <= (1.0 - drawdown_frac) * velocity_extreme:
            return True, "velocity_drawdown_exit"
        return False, None
    if current_velocity > 0:
        return True, "velocity_sign_flip"
    if current_velocity >= (1.0 - drawdown_frac) * velocity_extreme:
        return True, "velocity_drawdown_exit"
    return False, None


def update_velocity_extreme(
    *,
    direction: VelocityDirection,
    current_velocity: float,
    velocity_extreme: float,
) -> float:
    """Update in-trade velocity extreme (max for longs, min for shorts)."""
    if direction == "BUY":
        return max(velocity_extreme, current_velocity)
    return min(velocity_extreme, current_velocity)


def validate_velocity_params(params: VelocityStrategyParams) -> None:
    """Validate velocity strategy parameters once at runtime boundaries."""
    if params.entry_threshold <= 0:
        raise ValueError("entry_threshold must be > 0")
    if params.entry_persist <= 0:
        raise ValueError("entry_persist must be > 0")
    if not (0 < params.drawdown_frac <= 1):
        raise ValueError("drawdown_frac must be in (0, 1]")
    if params.stop_atr_mult <= 0:
        raise ValueError("stop_atr_mult must be > 0")
    if params.cooldown_bars < 0:
        raise ValueError("cooldown_bars must be >= 0")
    if params.trend_ema_period <= 1:
        raise ValueError("trend_ema_period must be > 1")


def _validate_entry_dataframe(dataframe: pd.DataFrame) -> None:
    required = {"time", "close", "atr", "velocity", "trend_ema"}
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"dataframe is missing required columns: {sorted(missing)}")
