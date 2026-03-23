"""Stateful backtest engine for momentum-velocity strategy."""

from __future__ import annotations

from typing import Callable

import pandas as pd

from src.backtest.engine import BacktestTrade
from src.backtest.filters import (
    is_entry_aligned_with_htf_bias,
    is_entry_allowed_by_regime,
    is_entry_hour_allowed,
    validate_allowed_directions,
    validate_entry_regime_filter,
    validate_htf_bias_by_time,
    validate_session_hours,
)
from src.strategies.velocity_indicators import calculate_trend_ema, calculate_velocity
from src.strategies.velocity_strategy import (
    VelocityPositionState,
    VelocityStrategyParams,
    evaluate_velocity_entry,
    should_exit_velocity_position,
    update_velocity_extreme,
    validate_velocity_params,
)


def run_velocity_backtest(
    dataframe: pd.DataFrame,
    *,
    lookback_k: int,
    atr_period: int,
    smoothing_span: int,
    params: VelocityStrategyParams,
    allowed_directions: set[str] | None = None,
    session_start_hour: int | None = None,
    session_end_hour: int | None = None,
    htf_bias_by_time: dict[object, str] | None = None,
    entry_regime_by_time: dict[object, str] | None = None,
    required_entry_regime: str | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> list[BacktestTrade]:
    """Run one-trade-at-a-time velocity backtest with momentum-fade exits.

    Design notes:
    - Uses closed-bar signal evaluation only.
    - Never exits on the same bar as entry to avoid same-candle ambiguity.
    """
    _validate_input(dataframe)
    validate_velocity_params(params)
    validate_allowed_directions(allowed_directions)
    validate_session_hours(
        session_start_hour=session_start_hour,
        session_end_hour=session_end_hour,
    )
    validate_htf_bias_by_time(htf_bias_by_time)
    validate_entry_regime_filter(
        entry_regime_by_time=entry_regime_by_time,
        required_entry_regime=required_entry_regime,
    )

    ordered = dataframe.sort_values("time").reset_index(drop=True).copy()
    velocity_features = calculate_velocity(
        ordered,
        lookback_k=lookback_k,
        atr_period=atr_period,
        smoothing_span=smoothing_span,
    )
    ordered["atr"] = velocity_features["atr"]
    ordered["velocity"] = velocity_features["velocity"]
    ordered["trend_ema"] = calculate_trend_ema(ordered, period=params.trend_ema_period)

    trades: list[BacktestTrade] = []
    position: VelocityPositionState | None = None
    cooldown_remaining = 0
    total_bars = len(ordered)

    if progress_callback is not None:
        progress_callback(0, total_bars)

    for index in range(total_bars):
        row = ordered.iloc[index]
        current_time = row["time"]

        if position is None:
            if cooldown_remaining > 0:
                cooldown_remaining -= 1
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue
            if not is_entry_hour_allowed(
                entry_time=current_time,
                session_start_hour=session_start_hour,
                session_end_hour=session_end_hour,
            ):
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue
            decision = evaluate_velocity_entry(ordered, current_index=index, params=params)
            if decision.signal == "NONE":
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue
            if allowed_directions is not None and decision.signal not in allowed_directions:
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue
            if not is_entry_aligned_with_htf_bias(
                entry_time=current_time,
                signal=decision.signal,
                htf_bias_by_time=htf_bias_by_time,
            ):
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue
            if not is_entry_allowed_by_regime(
                entry_time=current_time,
                entry_regime_by_time=entry_regime_by_time,
                required_entry_regime=required_entry_regime,
            ):
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue
            if decision.stop_loss is None:
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue

            entry_price = float(row["close"])
            current_velocity = float(row["velocity"])
            if pd.isna(current_velocity):
                if progress_callback is not None:
                    progress_callback(index + 1, total_bars)
                continue

            position = VelocityPositionState(
                direction=decision.signal,
                entry_index=index,
                entry_time=current_time,
                entry_price=entry_price,
                stop_loss=float(decision.stop_loss),
                velocity_extreme=current_velocity,
            )
            if progress_callback is not None:
                progress_callback(index + 1, total_bars)
            continue

        # Entry is executed at close of entry bar. Exit checks start on next bar.
        if index <= position.entry_index:
            if progress_callback is not None:
                progress_callback(index + 1, total_bars)
            continue

        stop_hit, stop_price = _check_disaster_stop(position=position, row=row)
        if stop_hit:
            trades.append(
                _build_trade(
                    position=position,
                    exit_index=index,
                    exit_time=current_time,
                    exit_price=stop_price,
                    exit_reason="stop_loss",
                )
            )
            position = None
            cooldown_remaining = params.cooldown_bars
            if progress_callback is not None:
                progress_callback(index + 1, total_bars)
            continue

        current_velocity = float(row["velocity"])
        if pd.isna(current_velocity):
            if progress_callback is not None:
                progress_callback(index + 1, total_bars)
            continue
        position.velocity_extreme = update_velocity_extreme(
            direction=position.direction,
            current_velocity=current_velocity,
            velocity_extreme=position.velocity_extreme,
        )
        should_exit, reason = should_exit_velocity_position(
            direction=position.direction,
            current_velocity=current_velocity,
            velocity_extreme=position.velocity_extreme,
            drawdown_frac=params.drawdown_frac,
        )
        if should_exit:
            trades.append(
                _build_trade(
                    position=position,
                    exit_index=index,
                    exit_time=current_time,
                    exit_price=float(row["close"]),
                    exit_reason=reason or "velocity_exit",
                )
            )
            position = None
            cooldown_remaining = params.cooldown_bars

        if progress_callback is not None:
            progress_callback(index + 1, total_bars)

    if position is not None:
        last = ordered.iloc[-1]
        trades.append(
            _build_trade(
                position=position,
                exit_index=total_bars - 1,
                exit_time=last["time"],
                exit_price=float(last["close"]),
                exit_reason="end_of_data",
            )
        )

    if progress_callback is not None:
        progress_callback(total_bars, total_bars)
    return trades


def _build_trade(
    *,
    position: VelocityPositionState,
    exit_index: int,
    exit_time: object,
    exit_price: float,
    exit_reason: str,
) -> BacktestTrade:
    if position.direction == "BUY":
        profit = exit_price - position.entry_price
        risk = position.entry_price - position.stop_loss
    else:
        profit = position.entry_price - exit_price
        risk = position.stop_loss - position.entry_price
    rr = (profit / risk) if risk > 0 else None
    return BacktestTrade(
        direction=position.direction,
        entry_index=position.entry_index,
        entry_time=position.entry_time,
        entry_price=position.entry_price,
        stop_loss=position.stop_loss,
        # Velocity strategy uses open-ended exits, so TP is informational only.
        take_profit=position.entry_price,
        exit_index=exit_index,
        exit_time=exit_time,
        exit_price=exit_price,
        exit_reason=exit_reason,
        profit=profit,
        rr=rr,
    )


def _check_disaster_stop(
    *,
    position: VelocityPositionState,
    row: pd.Series,
) -> tuple[bool, float]:
    high = float(row["high"])
    low = float(row["low"])
    if position.direction == "BUY":
        if low <= position.stop_loss:
            return True, position.stop_loss
        return False, 0.0
    if high >= position.stop_loss:
        return True, position.stop_loss
    return False, 0.0


def _validate_input(dataframe: pd.DataFrame) -> None:
    if dataframe.empty:
        raise ValueError("dataframe must not be empty")
    required = {"time", "open", "high", "low", "close", "volume"}
    missing = required.difference(dataframe.columns)
    if missing:
        raise ValueError(f"dataframe is missing required columns: {sorted(missing)}")
