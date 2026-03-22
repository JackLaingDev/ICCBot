"""Run a minimal end-to-end backtest for EURUSD M15."""

from __future__ import annotations

import argparse

from src.backtest.engine import run_backtest
from src.backtest.metrics import calculate_metrics
from src.config.settings import load_settings
from src.data.market_data import fetch_market_data
from src.data.mt5_client import MT5Client


def main() -> int:
    """Initialize MT5, fetch data, run backtest, print summary, and exit."""

    args = _parse_args()
    mode = args.mode
    settings = load_settings()
    client = MT5Client()
    symbol = settings.trading.symbol
    timeframe = settings.trading.timeframe
    allowed_directions = None if mode == "normal" else {"SELL"}

    try:
        client.initialize()
        dataframe = fetch_market_data(
            client=client,
            symbol=symbol,
            timeframe=timeframe,
            count=settings.data.lookback_bars,
        )

        trades = run_backtest(
            dataframe,
            ema_period=settings.strategy.ema_period,
            pullback_lookback=5,
            take_profit_rr=settings.strategy.take_profit_rr,
            allowed_directions=allowed_directions,
        )
        metrics = calculate_metrics(trades)

        print(f"Mode: {mode}")
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

        return 0
    finally:
        if client.is_connected():
            client.shutdown()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ICC backtest.")
    parser.add_argument(
        "--mode",
        choices=("normal", "short-only"),
        default="normal",
        help="Backtest mode: normal (BUY+SELL) or short-only (SELL only).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
