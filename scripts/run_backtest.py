"""Run end-to-end backtests for configured strategy on EURUSD M15."""

from __future__ import annotations

import argparse
from time import perf_counter

import pandas as pd

from src.backtest.engine import BacktestTrade, run_backtest
from src.backtest.velocity_engine import run_velocity_backtest
from src.backtest.metrics import calculate_metrics
from src.config.settings import AppSettings, load_settings
from src.data.market_data import fetch_market_data
from src.data.mt5_client import MT5Client
from src.strategies.velocity_strategy import VelocityStrategyParams


def main() -> int:
    """Initialize MT5, fetch data, run backtest, print summary, and exit."""

    started_at = perf_counter()
    args = _parse_args()
    mode = args.mode
    _log(f"Starting backtest run (mode={mode})")

    settings = load_settings()
    _log("Settings loaded")
    selected_strategy = args.strategy or settings.strategy.strategy_name
    if selected_strategy not in {"icc", "velocity"}:
        raise ValueError("strategy must be one of: icc, velocity")

    client = MT5Client()
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe
    allowed_directions = None if mode == "normal" else {"SELL"}
    session_start_hour = args.session_start_hour
    session_end_hour = args.session_end_hour
    htf_bias_mode = args.htf_bias
    date_split_mode = args.date_split
    vol_filter_mode = args.vol_filter
    htf_bias_by_time: dict[pd.Timestamp, str] | None = None
    entry_regime_by_time: dict[pd.Timestamp, str] | None = None
    required_entry_regime: str | None = None
    progress_state = {"last_percent": -1}
    _log(
        f"Prepared run config: symbol={symbol}, timeframe={timeframe}, "
        f"lookback_bars={settings.data.lookback_bars}, strategy={selected_strategy}"
    )
    if session_start_hour is None:
        _log("Session filter: none (all UTC hours)")
    else:
        _log(f"Session filter UTC: {session_start_hour:02d}-{session_end_hour:02d}")
    _log(f"HTF bias filter: {htf_bias_mode}")
    _log(f"Volatility regime filter: {vol_filter_mode}")
    _log(f"Date split mode: {date_split_mode}")

    try:
        _log("Initializing MT5 client...")
        client.initialize()
        _log("MT5 initialized")

        _log("Fetching market data...")
        dataframe = fetch_market_data(
            client=client,
            symbol=symbol,
            timeframe=timeframe,
            count=settings.data.lookback_bars,
        )
        _log(f"Data fetch complete (rows={len(dataframe)})")
        entry_regime_by_time = _build_volatility_regime_by_time(dataframe)
        if vol_filter_mode == "high-only":
            required_entry_regime = "high_vol"

        if htf_bias_mode == "h1-ema200":
            _log("Fetching H1 data for HTF bias...")
            htf_dataframe = fetch_market_data(
                client=client,
                symbol=symbol,
                timeframe="H1",
                count=settings.data.lookback_bars,
            )
            if htf_dataframe.empty:
                raise ValueError("HTF bias requested but no H1 data was fetched.")
            htf_bias_by_time = _build_h1_ema_bias_by_time(
                lower_timeframe_df=dataframe,
                htf_df=htf_dataframe,
                ema_period=200,
            )
            _log(f"HTF bias aligned to M15 bars (mapped={len(htf_bias_by_time)})")

        _log("Running backtest engine...")
        if selected_strategy == "velocity":
            velocity_params = _build_velocity_strategy_params(settings)
            trades = run_velocity_backtest(
                dataframe,
                lookback_k=settings.strategy.velocity_lookback,
                atr_period=settings.strategy.velocity_atr_period,
                smoothing_span=settings.strategy.velocity_smoothing_span,
                params=velocity_params,
                allowed_directions=allowed_directions,
                session_start_hour=session_start_hour,
                session_end_hour=session_end_hour,
                htf_bias_by_time=htf_bias_by_time,
                entry_regime_by_time=entry_regime_by_time,
                required_entry_regime=required_entry_regime,
                progress_callback=lambda done, total: _print_progress(
                    done=done,
                    total=total,
                    state=progress_state,
                ),
            )
        else:
            trades = run_backtest(
                dataframe,
                ema_period=settings.strategy.ema_period,
                pullback_lookback=5,
                take_profit_rr=settings.strategy.take_profit_rr,
                allowed_directions=allowed_directions,
                session_start_hour=session_start_hour,
                session_end_hour=session_end_hour,
                htf_bias_by_time=htf_bias_by_time,
                entry_regime_by_time=entry_regime_by_time,
                required_entry_regime=required_entry_regime,
                progress_callback=lambda done, total: _print_progress(
                    done=done,
                    total=total,
                    state=progress_state,
                ),
            )
        print()
        _log(f"Backtest complete (trades={len(trades)})")

        _log("Calculating metrics...")
        metrics = calculate_metrics(trades)
        _log("Metrics calculation complete")

        print(f"Mode: {mode}")
        print(f"Strategy: {selected_strategy}")
        print(
            "Session filter (UTC): "
            + (
                "none"
                if session_start_hour is None
                else f"{session_start_hour:02d}-{session_end_hour:02d}"
            )
        )
        print(f"HTF bias filter: {htf_bias_mode}")
        print(f"Volatility regime filter: {vol_filter_mode}")
        print(f"Symbol: {symbol}")
        print(f"Timeframe: {timeframe}")
        print(f"Rows fetched: {len(dataframe)}")
        print(f"Total trades: {metrics.total_trades}")
        print(f"Win rate: {metrics.win_rate:.2f}%")
        print(f"Total profit: {metrics.total_profit:.5f}")
        print(f"Max drawdown: {metrics.max_drawdown:.5f}")
        print(f"Average RR: {metrics.average_rr:.5f}")
        print(
            f"BUY vs SELL: buy_trades={metrics.buy_trades} sell_trades={metrics.sell_trades} "
            f"buy_profit={metrics.buy_profit:.5f} sell_profit={metrics.sell_profit:.5f}"
        )
        print(
            "Exit reasons: "
            f"take_profit={metrics.exit_reason_counts.get('take_profit', 0)} "
            f"stop_loss={metrics.exit_reason_counts.get('stop_loss', 0)} "
            f"end_of_data={metrics.exit_reason_counts.get('end_of_data', 0)}"
        )
        print(
            "Entry hour counts: "
            + (
                ", ".join(
                    f"{hour}: {count}"
                    for hour, count in sorted(metrics.entry_hour_counts.items(), key=lambda x: x[0])
                )
                if metrics.entry_hour_counts
                else "none"
            )
        )
        print("Profit by entry hour: " + _format_hour_profit(trades))
        print("Win rate by entry hour: " + _format_hour_win_rate(trades))
        print("Monthly breakdown (UTC entry month):")
        _print_monthly_breakdown(trades)
        print("Regime breakdown (M15 range median split):")
        _print_regime_breakdown(trades, entry_regime_by_time or {})
        print(f"Average trade duration (bars): {metrics.average_trade_duration_bars:.2f}")
        print("Top 5 winning trades:")
        _print_trade_list(_top_winning_trades(trades, limit=5))

        print("Top 5 losing trades:")
        _print_trade_list(_top_losing_trades(trades, limit=5))

        if date_split_mode == "halves":
            print("Date split summary:")
            for split_name, split_df in _split_dataframe_for_walkforward(dataframe):
                if split_df.empty:
                    print(f"{split_name}: no data")
                    continue
                split_range = _split_date_range_text(split_df)

                if selected_strategy == "velocity":
                    split_trades = run_velocity_backtest(
                        split_df,
                        lookback_k=settings.strategy.velocity_lookback,
                        atr_period=settings.strategy.velocity_atr_period,
                        smoothing_span=settings.strategy.velocity_smoothing_span,
                        params=_build_velocity_strategy_params(settings),
                        allowed_directions=allowed_directions,
                        session_start_hour=session_start_hour,
                        session_end_hour=session_end_hour,
                        htf_bias_by_time=htf_bias_by_time,
                        entry_regime_by_time=entry_regime_by_time,
                        required_entry_regime=required_entry_regime,
                        progress_callback=None,
                    )
                else:
                    split_trades = run_backtest(
                        split_df,
                        ema_period=settings.strategy.ema_period,
                        pullback_lookback=5,
                        take_profit_rr=settings.strategy.take_profit_rr,
                        allowed_directions=allowed_directions,
                        session_start_hour=session_start_hour,
                        session_end_hour=session_end_hour,
                        htf_bias_by_time=htf_bias_by_time,
                        entry_regime_by_time=entry_regime_by_time,
                        required_entry_regime=required_entry_regime,
                        progress_callback=None,
                    )
                split_metrics = calculate_metrics(split_trades)
                print(
                    f"{split_name} ({split_range}): trades={split_metrics.total_trades} "
                    f"win_rate={split_metrics.win_rate:.2f}% "
                    f"total_profit={split_metrics.total_profit:.5f} "
                    f"max_drawdown={split_metrics.max_drawdown:.5f}"
                )

        if not trades:
            print("No trades generated.")

        elapsed = perf_counter() - started_at
        _log(f"Run finished in {elapsed:.2f}s")
        return 0
    finally:
        if client.is_connected():
            _log("Shutting down MT5 client...")
            client.shutdown()
            _log("MT5 shutdown complete")


def _log(message: str) -> None:
    print(f"[run_backtest] {message}", flush=True)


def _print_progress(*, done: int, total: int, state: dict[str, int]) -> None:
    if total <= 0:
        return
    percent = int(min(100, max(0, (done * 100) // total)))
    if percent == state["last_percent"]:
        return
    state["last_percent"] = percent
    bar_width = 20
    filled = (percent * bar_width) // 100
    bar = ("#" * filled).ljust(bar_width, "-")
    print(
        f"\r[run_backtest] Backtest progress: [{bar}] {percent:3d}% ({done}/{total})",
        end="",
        flush=True,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run strategy backtest.")
    parser.add_argument(
        "--strategy",
        choices=("icc", "velocity"),
        default=None,
        help="Optional strategy override. Defaults to STRATEGY_NAME from settings.",
    )
    parser.add_argument(
        "--mode",
        choices=("normal", "short-only"),
        default="normal",
        help="Backtest mode: normal (BUY+SELL) or short-only (SELL only).",
    )
    parser.add_argument(
        "--session-start-hour",
        type=int,
        default=None,
        help="Optional UTC hour (0-23) to start entry session window.",
    )
    parser.add_argument(
        "--session-end-hour",
        type=int,
        default=None,
        help="Optional UTC hour (0-23) to end entry session window (exclusive).",
    )
    parser.add_argument(
        "--htf-bias",
        choices=("none", "h1-ema200"),
        default="none",
        help="Optional higher-timeframe bias filter: none or H1 close vs EMA(200).",
    )
    parser.add_argument(
        "--date-split",
        choices=("none", "halves"),
        default="none",
        help="Optional text-only robustness split reporting: none or early/later halves.",
    )
    parser.add_argument(
        "--vol-filter",
        choices=("none", "high-only"),
        default="none",
        help="Optional entry filter by volatility regime: none or high-only.",
    )
    return parser.parse_args()


def _build_velocity_strategy_params(settings: AppSettings) -> VelocityStrategyParams:
    strategy = settings.strategy
    return VelocityStrategyParams(
        entry_threshold=strategy.velocity_entry_threshold,
        entry_persist=strategy.velocity_entry_persist,
        drawdown_frac=strategy.velocity_drawdown_frac,
        stop_atr_mult=strategy.velocity_stop_atr_mult,
        cooldown_bars=strategy.velocity_cooldown_bars,
        trend_filter_enabled=strategy.velocity_trend_filter_enabled,
        trend_ema_period=strategy.velocity_trend_ema_period,
    )


def _build_h1_ema_bias_by_time(
    *,
    lower_timeframe_df: pd.DataFrame,
    htf_df: pd.DataFrame,
    ema_period: int,
) -> dict[pd.Timestamp, str]:
    """Build M15->HTF bias map using only confirmed H1 closes.

    MT5 bar timestamps represent bar open time. To avoid lookahead, an H1 bar's
    bias becomes available only after that H1 bar closes (open_time + 1 hour).
    """
    htf = htf_df[["time", "close"]].sort_values("time").copy()
    htf["time"] = _normalize_utc_datetime_key(htf["time"])
    htf["ema"] = htf["close"].ewm(span=ema_period, adjust=False).mean()
    htf["bias"] = "NEUTRAL"
    htf.loc[htf["close"] > htf["ema"], "bias"] = "BULLISH"
    htf.loc[htf["close"] < htf["ema"], "bias"] = "BEARISH"
    htf["available_time"] = htf["time"] + pd.Timedelta(hours=1)
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
    return {
        _to_utc_timestamp(ts): str(bias)
        for ts, bias in zip(aligned["time"], aligned["bias"])
    }


def _to_utc_timestamp(value: object) -> pd.Timestamp:
    """Normalize value to UTC timestamp.

    Naive datetimes are treated as UTC by convention.
    """
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _normalize_utc_datetime_key(values: pd.Series) -> pd.Series:
    """Normalize merge keys to datetime64[ns, UTC] for merge_asof."""
    normalized = pd.to_datetime(values, utc=True)
    return normalized.astype("datetime64[ns, UTC]")


def _entry_hour(entry_time: object) -> str:
    timestamp = _to_utc_timestamp(entry_time)
    hour = int(timestamp.hour)
    if 0 <= hour <= 23:
        return f"{hour:02d}"
    return "unknown"


def _format_hour_profit(trades: list[BacktestTrade]) -> str:
    if not trades:
        return "none"

    by_hour: dict[str, float] = {}
    for trade in trades:
        hour = _entry_hour(trade.entry_time)
        by_hour[hour] = by_hour.get(hour, 0.0) + float(trade.profit)
    return ", ".join(f"{hour}: {value:.5f}" for hour, value in sorted(by_hour.items()))


def _format_hour_win_rate(trades: list[BacktestTrade]) -> str:
    if not trades:
        return "none"

    total_by_hour: dict[str, int] = {}
    wins_by_hour: dict[str, int] = {}
    for trade in trades:
        hour = _entry_hour(trade.entry_time)
        total_by_hour[hour] = total_by_hour.get(hour, 0) + 1
        if trade.profit > 0:
            wins_by_hour[hour] = wins_by_hour.get(hour, 0) + 1

    parts: list[str] = []
    for hour, total in sorted(total_by_hour.items()):
        wins = wins_by_hour.get(hour, 0)
        rate = (wins / total) * 100.0
        parts.append(f"{hour}: {rate:.2f}% ({wins}/{total})")
    return ", ".join(parts)


def _top_winning_trades(trades: list[BacktestTrade], *, limit: int) -> list[BacktestTrade]:
    return sorted((trade for trade in trades if trade.profit > 0), key=lambda t: t.profit, reverse=True)[
        :limit
    ]


def _top_losing_trades(trades: list[BacktestTrade], *, limit: int) -> list[BacktestTrade]:
    return sorted((trade for trade in trades if trade.profit < 0), key=lambda t: t.profit)[:limit]


def _print_trade_list(trades: list[BacktestTrade]) -> None:
    if not trades:
        print("none")
        return
    for index, trade in enumerate(trades, start=1):
        rr_text = f"{trade.rr:.5f}" if trade.rr is not None else "n/a"
        print(
            f"{index}. {trade.direction} "
            f"entry={trade.entry_time} exit={trade.exit_time} "
            f"reason={trade.exit_reason} profit={trade.profit:.5f} rr={rr_text}"
        )


def _split_dataframe_for_walkforward(dataframe: pd.DataFrame) -> list[tuple[str, pd.DataFrame]]:
    """Split chronologically into early/later contiguous UTC time ranges."""
    ordered = dataframe.copy()
    ordered["time"] = _normalize_utc_datetime_key(ordered["time"])
    ordered = ordered.sort_values("time").reset_index(drop=True)

    if ordered.empty:
        return [("early_period", ordered.copy()), ("later_period", ordered.copy())]

    midpoint = len(ordered) // 2
    split_time = ordered.iloc[midpoint]["time"]
    return [
        ("early_period", ordered[ordered["time"] <= split_time].reset_index(drop=True)),
        ("later_period", ordered[ordered["time"] > split_time].reset_index(drop=True)),
    ]


def _split_date_range_text(split_df: pd.DataFrame) -> str:
    start = _to_utc_timestamp(split_df.iloc[0]["time"]).strftime("%Y-%m-%d")
    end = _to_utc_timestamp(split_df.iloc[-1]["time"]).strftime("%Y-%m-%d")
    return f"{start} to {end} UTC"


def _build_volatility_regime_by_time(dataframe: pd.DataFrame) -> dict[pd.Timestamp, str]:
    """Classify each M15 bar into low/high volatility by median candle range.

    Assumptions:
    - Range is `high - low` in raw price units.
    - Threshold at each bar uses only historical ranges up to prior bar
      (expanding median) to avoid lookahead.
    - Bars with range equal to median are treated as `low_vol`.
    """
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
    regime_series = working.set_index("time")["regime"]
    return regime_series.to_dict()


def _print_regime_breakdown(
    trades: list[BacktestTrade],
    regime_by_time: dict[pd.Timestamp, str],
) -> None:
    """Print trade metrics grouped by regime at trade entry time.

    Assumptions:
    - Regime is assigned from the entry bar timestamp only.
    - If an entry timestamp is missing in `regime_by_time`, bucket as `unknown`.
    """
    if not trades:
        print("none")
        return

    buckets: dict[str, list[BacktestTrade]] = {}
    for trade in trades:
        regime = regime_by_time.get(_to_utc_timestamp(trade.entry_time), "unknown")
        buckets.setdefault(regime, []).append(trade)

    ordered_regimes = [name for name in ("low_vol", "high_vol", "unknown") if name in buckets]
    for regime in ordered_regimes:
        regime_metrics = calculate_metrics(buckets[regime])
        print(
            f"{regime}: trades={regime_metrics.total_trades} "
            f"win_rate={regime_metrics.win_rate:.2f}% "
            f"total_profit={regime_metrics.total_profit:.5f} "
            f"max_drawdown={regime_metrics.max_drawdown:.5f}"
        )


def _print_monthly_breakdown(trades: list[BacktestTrade]) -> None:
    """Print per-month trades/profit/win-rate by UTC entry month."""
    if not trades:
        print("none")
        return

    by_month: dict[str, dict[str, float]] = {}
    for trade in trades:
        month_key = _to_utc_timestamp(trade.entry_time).strftime("%Y-%m")
        if month_key not in by_month:
            by_month[month_key] = {"trades": 0.0, "wins": 0.0, "profit": 0.0}
        by_month[month_key]["trades"] += 1
        if trade.profit > 0:
            by_month[month_key]["wins"] += 1
        by_month[month_key]["profit"] += float(trade.profit)

    for month_key in sorted(by_month.keys()):
        month_data = by_month[month_key]
        total = int(month_data["trades"])
        wins = int(month_data["wins"])
        win_rate = (wins / total) * 100.0 if total > 0 else 0.0
        print(
            f"{month_key}: trades={total} "
            f"profit={month_data['profit']:.5f} "
            f"win_rate={win_rate:.2f}%"
        )


if __name__ == "__main__":
    raise SystemExit(main())
