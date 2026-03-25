"""Run one live ICC signal check (no order execution).

This script evaluates the latest fully closed M15 candle only and applies the
frozen filter setup used in research:
- short-only
- session 07-12 UTC
- HTF bias h1-ema200
- high-vol only
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import pandas as pd

from src.config.settings import load_settings
from src.data.market_data import fetch_market_data
from src.data.mt5_client import MT5Client
from src.risk.manager import SignalGuardInput, evaluate_signal_guardrails
from src.strategies.icc_strategy import evaluate_icc_v1
from src.strategies.models import StrategyDecision


SIGNAL_LOG_PATH = Path("logs/live_icc_signals.csv")
SESSION_START_HOUR_UTC = 7
SESSION_END_HOUR_UTC = 12
HTF_EMA_PERIOD = 200
M15_MINUTES = 15
STALE_AFTER_MINUTES = 30
MAX_SIGNALS_PER_DAY: int | None = None


@dataclass(frozen=True)
class FilterStatus:
    """Filter pass/fail states for the evaluated candle."""

    session: Literal["passed", "blocked"]
    direction: Literal["passed", "blocked"]
    htf_bias: Literal["passed", "blocked"]
    volatility: Literal["passed", "blocked"]


def main() -> int:
    """Fetch data, evaluate one closed candle, print and CSV-log result."""
    evaluation_time = pd.Timestamp.now(tz="UTC")
    settings = load_settings()
    client = MT5Client()

    try:
        client.initialize()
        m15_df = fetch_market_data(
            client=client,
            symbol=settings.trading.symbol,
            timeframe=settings.trading.timeframe,
            count=settings.data.lookback_bars,
        )
        h1_df = fetch_market_data(
            client=client,
            symbol=settings.trading.symbol,
            timeframe="H1",
            count=settings.data.lookback_bars,
        )

        row = _evaluate_latest_closed_signal(
            evaluation_time=evaluation_time,
            m15_df=m15_df,
            h1_df=h1_df,
            ema_period=settings.strategy.ema_period,
            take_profit_rr=settings.strategy.take_profit_rr,
        )
        _print_result(row)
        if row["duplicate_guard"] == "blocked":
            return 0
        _append_log_row(row)
        return 0
    finally:
        if client.is_connected():
            client.shutdown()


def _evaluate_latest_closed_signal(
    *,
    evaluation_time: pd.Timestamp,
    m15_df: pd.DataFrame,
    h1_df: pd.DataFrame,
    ema_period: int,
    take_profit_rr: float,
) -> dict[str, str]:
    """Evaluate frozen ICC setup on the latest fully closed M15 candle."""
    base = _base_output(evaluation_time=evaluation_time)

    if m15_df.empty:
        guard_result = evaluate_signal_guardrails(
            SignalGuardInput(
                evaluation_time_utc=evaluation_time,
                candle_time_utc=None,
                has_m15_data=False,
                has_h1_data=not h1_df.empty,
                duplicate_candle=False,
                session_start_hour_utc=SESSION_START_HOUR_UTC,
                session_end_hour_utc=SESSION_END_HOUR_UTC,
                candle_minutes=M15_MINUTES,
                stale_after_minutes=STALE_AFTER_MINUTES,
                max_signals_per_day=MAX_SIGNALS_PER_DAY,
                signals_today=0,
            )
        )
        return _finalize(base, reason=guard_result.reason, duplicate_guard=guard_result.duplicate)
    if h1_df.empty:
        guard_result = evaluate_signal_guardrails(
            SignalGuardInput(
                evaluation_time_utc=evaluation_time,
                candle_time_utc=None,
                has_m15_data=True,
                has_h1_data=False,
                duplicate_candle=False,
                session_start_hour_utc=SESSION_START_HOUR_UTC,
                session_end_hour_utc=SESSION_END_HOUR_UTC,
                candle_minutes=M15_MINUTES,
                stale_after_minutes=STALE_AFTER_MINUTES,
                max_signals_per_day=MAX_SIGNALS_PER_DAY,
                signals_today=0,
            )
        )
        return _finalize(base, reason=guard_result.reason, duplicate_guard=guard_result.duplicate)
    if len(m15_df) < 2:
        return _finalize(base, reason="not_enough_m15_rows")

    ordered = m15_df.sort_values("time").reset_index(drop=True).copy()
    ordered["time"] = pd.to_datetime(ordered["time"], utc=True)

    # MT5 position 0 is the newest bar, which can be in-progress.
    closed_index = len(ordered) - 2
    closed_candle = ordered.iloc[closed_index]
    candle_time = pd.Timestamp(closed_candle["time"])
    base["candle_timestamp_utc"] = candle_time.isoformat()

    duplicate = _is_duplicate_candle(base["candle_timestamp_utc"])
    signals_today = _count_logged_sell_signals_for_day(base["candle_timestamp_utc"])
    guard_result = evaluate_signal_guardrails(
        SignalGuardInput(
            evaluation_time_utc=evaluation_time,
            candle_time_utc=candle_time,
            has_m15_data=not m15_df.empty,
            has_h1_data=not h1_df.empty,
            duplicate_candle=duplicate,
            session_start_hour_utc=SESSION_START_HOUR_UTC,
            session_end_hour_utc=SESSION_END_HOUR_UTC,
            candle_minutes=M15_MINUTES,
            stale_after_minutes=STALE_AFTER_MINUTES,
            max_signals_per_day=MAX_SIGNALS_PER_DAY,
            signals_today=signals_today,
        )
    )
    if not guard_result.allowed:
        return _finalize(
            base,
            reason=guard_result.reason,
            filters=FilterStatus(
                guard_result.session,
                "blocked",
                "blocked",
                "blocked",
            ),
            duplicate_guard=guard_result.duplicate,
        )

    htf_bias_by_time = _build_ema_bias_by_time(
        lower_timeframe_df=ordered,
        htf_df=h1_df,
        ema_period=HTF_EMA_PERIOD,
        htf_bar_hours=1,
    )
    entry_regime_by_time = _build_volatility_regime_by_time(ordered)
    candle_key = _to_utc_timestamp(candle_time)
    htf_ok = htf_bias_by_time.get(candle_key) == "BEARISH"
    regime_ok = entry_regime_by_time.get(candle_key) == "high_vol"

    history_window = ordered.iloc[: closed_index + 1]
    try:
        decision = evaluate_icc_v1(
            history_window,
            ema_period=ema_period,
            pullback_lookback=5,
            take_profit_rr=take_profit_rr,
        )
    except ValueError as exc:
        return _finalize(
            base,
            reason=f"strategy_input_error:{exc}",
            filters=FilterStatus(
                guard_result.session,
                "blocked",
                "passed" if htf_ok else "blocked",
                "passed" if regime_ok else "blocked",
            ),
            duplicate_guard=guard_result.duplicate,
        )

    direction_ok = decision.signal == "SELL"
    if not direction_ok:
        return _finalize(
            base,
            reason=decision.reason or "strategy_none",
            filters=FilterStatus(
                guard_result.session,
                "blocked",
                "passed" if htf_ok else "blocked",
                "passed" if regime_ok else "blocked",
            ),
            duplicate_guard=guard_result.duplicate,
        )
    if not htf_ok:
        return _finalize(
            base,
            reason="blocked_by_htf_bias",
            decision=decision,
            filters=FilterStatus(
                guard_result.session,
                "passed",
                "blocked",
                "passed" if regime_ok else "blocked",
            ),
            duplicate_guard=guard_result.duplicate,
        )
    if not regime_ok:
        return _finalize(
            base,
            reason="blocked_by_volatility_regime",
            decision=decision,
            filters=FilterStatus(guard_result.session, "passed", "passed", "blocked"),
            duplicate_guard=guard_result.duplicate,
        )

    return _finalize(
        base,
        reason=decision.reason or "sell_setup",
        decision=decision,
        filters=FilterStatus(guard_result.session, "passed", "passed", "passed"),
        duplicate_guard=guard_result.duplicate,
    )


def _base_output(*, evaluation_time: pd.Timestamp) -> dict[str, str]:
    return {
        "evaluation_timestamp_utc": _to_utc_timestamp(evaluation_time).isoformat(),
        "candle_timestamp_utc": "",
        "signal": "NONE",
        "reason": "",
        "stop_loss": "",
        "take_profit": "",
        "filter_session": "blocked",
        "filter_direction": "blocked",
        "filter_htf_bias": "blocked",
        "filter_volatility": "blocked",
        "duplicate_guard": "passed",
    }


def _finalize(
    base: dict[str, str],
    *,
    reason: str,
    decision: StrategyDecision | None = None,
    filters: FilterStatus | None = None,
    duplicate_guard: Literal["passed", "blocked"] = "passed",
) -> dict[str, str]:
    row = dict(base)
    row["reason"] = reason
    row["duplicate_guard"] = duplicate_guard
    if filters is not None:
        row["filter_session"] = filters.session
        row["filter_direction"] = filters.direction
        row["filter_htf_bias"] = filters.htf_bias
        row["filter_volatility"] = filters.volatility
    if decision is not None and decision.signal == "SELL":
        row["signal"] = "SELL"
        row["stop_loss"] = "" if decision.stop_loss is None else f"{decision.stop_loss:.5f}"
        row["take_profit"] = "" if decision.take_profit is None else f"{decision.take_profit:.5f}"
    return row


def _to_utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _normalize_utc_datetime_key(values: pd.Series) -> pd.Series:
    normalized = pd.to_datetime(values, utc=True)
    return normalized.astype("datetime64[ns, UTC]")


def _build_ema_bias_by_time(
    *,
    lower_timeframe_df: pd.DataFrame,
    htf_df: pd.DataFrame,
    ema_period: int,
    htf_bar_hours: int,
) -> dict[pd.Timestamp, str]:
    if htf_bar_hours <= 0:
        raise ValueError("htf_bar_hours must be > 0")
    if ema_period <= 0:
        raise ValueError("ema_period must be > 0")
    if lower_timeframe_df.empty:
        return {}

    htf = htf_df[["time", "close"]].sort_values("time").copy()
    htf["time"] = _normalize_utc_datetime_key(htf["time"])
    htf["close"] = pd.to_numeric(htf["close"], errors="coerce")
    htf = htf.dropna(subset=["time", "close"]).sort_values("time")
    if htf.empty:
        lower = lower_timeframe_df[["time"]].sort_values("time").copy()
        lower["time"] = _normalize_utc_datetime_key(lower["time"])
        return {_to_utc_timestamp(ts): "NEUTRAL" for ts in lower["time"]}

    htf["ema"] = htf["close"].ewm(span=ema_period, adjust=False).mean()
    htf["bias"] = "NEUTRAL"
    htf.loc[htf["close"] > htf["ema"], "bias"] = "BULLISH"
    htf.loc[htf["close"] < htf["ema"], "bias"] = "BEARISH"
    htf["available_time"] = htf["time"] + pd.Timedelta(hours=htf_bar_hours)
    htf["available_time"] = _normalize_utc_datetime_key(htf["available_time"])

    lower = lower_timeframe_df[["time"]].sort_values("time").copy()
    lower["time"] = _normalize_utc_datetime_key(lower["time"])
    aligned = pd.merge_asof(
        lower,
        htf[["available_time", "bias"]],
        left_on="time",
        right_on="available_time",
        direction="backward",
    )
    aligned["bias"] = aligned["bias"].fillna("NEUTRAL")
    return {_to_utc_timestamp(ts): str(bias) for ts, bias in zip(aligned["time"], aligned["bias"])}


def _build_volatility_regime_by_time(dataframe: pd.DataFrame) -> dict[pd.Timestamp, str]:
    working = dataframe[["time", "high", "low"]].copy()
    working["time"] = _normalize_utc_datetime_key(working["time"])
    working["high"] = pd.to_numeric(working["high"], errors="coerce")
    working["low"] = pd.to_numeric(working["low"], errors="coerce")
    working = working.dropna(subset=["time", "high", "low"]).sort_values("time")
    if working.empty:
        return {}

    working["range"] = working["high"] - working["low"]
    working["threshold"] = working["range"].expanding(min_periods=1).median().shift(1)
    working["threshold"] = working["threshold"].fillna(working["range"])
    working["regime"] = "low_vol"
    working.loc[working["range"] > working["threshold"], "regime"] = "high_vol"
    return working.set_index("time")["regime"].to_dict()


def _is_duplicate_candle(candle_timestamp: str) -> bool:
    if not candle_timestamp:
        return False
    if not SIGNAL_LOG_PATH.exists():
        return False
    existing = pd.read_csv(SIGNAL_LOG_PATH)
    if existing.empty or "candle_timestamp_utc" not in existing.columns:
        return False
    return bool((existing["candle_timestamp_utc"] == candle_timestamp).any())


def _count_logged_sell_signals_for_day(candle_timestamp: str) -> int:
    if not candle_timestamp:
        return 0
    if not SIGNAL_LOG_PATH.exists():
        return 0
    existing = pd.read_csv(SIGNAL_LOG_PATH)
    if existing.empty:
        return 0
    if "candle_timestamp_utc" not in existing.columns or "signal" not in existing.columns:
        return 0

    candle_day = _to_utc_timestamp(candle_timestamp).strftime("%Y-%m-%d")
    candle_series = pd.to_datetime(existing["candle_timestamp_utc"], utc=True, errors="coerce")
    day_mask = candle_series.dt.strftime("%Y-%m-%d") == candle_day
    sell_mask = existing["signal"] == "SELL"
    return int((day_mask & sell_mask).sum())


def _append_log_row(row: dict[str, str]) -> None:
    SIGNAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    output = pd.DataFrame([row])
    header = not SIGNAL_LOG_PATH.exists()
    output.to_csv(SIGNAL_LOG_PATH, mode="a", index=False, header=header)


def _print_result(row: dict[str, str]) -> None:
    print(f"evaluation_timestamp_utc: {row['evaluation_timestamp_utc']}")
    print(f"candle_timestamp_utc: {row['candle_timestamp_utc']}")
    print(f"signal: {row['signal']}")
    print(f"reason: {row['reason']}")
    print(f"stop_loss: {row['stop_loss'] or 'n/a'}")
    print(f"take_profit: {row['take_profit'] or 'n/a'}")
    print(
        "filters: "
        f"session={row['filter_session']} "
        f"direction={row['filter_direction']} "
        f"htf_bias={row['filter_htf_bias']} "
        f"volatility={row['filter_volatility']}"
    )
    print(f"duplicate_guard: {row['duplicate_guard']}")


if __name__ == "__main__":
    raise SystemExit(main())
