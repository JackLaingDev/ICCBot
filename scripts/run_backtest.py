"""Run a minimal end-to-end backtest for EURUSD M15."""

from __future__ import annotations

import argparse
from time import perf_counter

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.metrics import calculate_metrics
from src.config.settings import load_settings
from src.data.market_data import fetch_market_data
from src.data.mt5_client import MT5Client


def main() -> int:
    """Initialize MT5, fetch data, run backtest, print summary, and exit."""

    started_at = perf_counter()
    args = _parse_args()
    mode = args.mode
    _log(f"Starting backtest run (mode={mode})")

    settings = load_settings()
    _log("Settings loaded")

    client = MT5Client()
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe
    allowed_directions = None if mode == "normal" else {"SELL"}
    session_start_hour = args.session_start_hour
    session_end_hour = args.session_end_hour
    htf_bias_mode = args.htf_bias
    htf_bias_by_time: dict[pd.Timestamp, str] | None = None
    progress_state = {"last_percent": -1}
    _log(
        f"Prepared run config: symbol={symbol}, timeframe={timeframe}, "
        f"lookback_bars={settings.data.lookback_bars}"
    )
    if session_start_hour is None:
        _log("Session filter: none (all UTC hours)")
    else:
        _log(f"Session filter UTC: {session_start_hour:02d}-{session_end_hour:02d}")
    _log(f"HTF bias filter: {htf_bias_mode}")

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
        trades = run_backtest(
            dataframe,
            ema_period=settings.strategy.ema_period,
            pullback_lookback=5,
            take_profit_rr=settings.strategy.take_profit_rr,
            allowed_directions=allowed_directions,
            session_start_hour=session_start_hour,
            session_end_hour=session_end_hour,
            htf_bias_by_time=htf_bias_by_time,
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
        print(
            "Session filter (UTC): "
            + (
                "none"
                if session_start_hour is None
                else f"{session_start_hour:02d}-{session_end_hour:02d}"
            )
        )
        print(f"HTF bias filter: {htf_bias_mode}")
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
        print(f"Average trade duration (bars): {metrics.average_trade_duration_bars:.2f}")
        print("First 5 trades:")

        for index, trade in enumerate(trades[:5], start=1):
            rr_text = f"{trade.rr:.5f}" if trade.rr is not None else "n/a"
            print(
                f"{index}. {trade.direction} "
                f"entry={trade.entry_time} exit={trade.exit_time} "
                f"reason={trade.exit_reason} profit={trade.profit:.5f} rr={rr_text}"
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
    parser = argparse.ArgumentParser(description="Run ICC backtest.")
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
    return parser.parse_args()


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
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _normalize_utc_datetime_key(values: pd.Series) -> pd.Series:
    """Normalize merge keys to datetime64[ns, UTC] for merge_asof."""
    normalized = pd.to_datetime(values, utc=True)
    return normalized.astype("datetime64[ns, UTC]")


if __name__ == "__main__":
    raise SystemExit(main())
