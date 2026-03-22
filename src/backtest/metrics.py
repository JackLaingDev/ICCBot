"""Core backtest performance metrics.

Responsible for transparent, deterministic metric calculations only.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.backtest.engine import BacktestTrade


@dataclass(frozen=True)
class BacktestMetrics:
    """Core summary metrics for a backtest run."""

    total_trades: int
    win_rate: float
    total_profit: float
    max_drawdown: float
    average_rr: float
    buy_trades: int
    sell_trades: int
    buy_profit: float
    sell_profit: float
    exit_reason_counts: dict[str, int] = field(default_factory=dict)
    entry_hour_counts: dict[str, int] = field(default_factory=dict)
    average_trade_duration_bars: float = 0.0


def calculate_metrics(trades: list[BacktestTrade]) -> BacktestMetrics:
    """Calculate core metrics from simulated trades."""

    total_trades = len(trades)
    if total_trades == 0:
        return BacktestMetrics(
            total_trades=0,
            win_rate=0.0,
            total_profit=0.0,
            max_drawdown=0.0,
            average_rr=0.0,
            buy_trades=0,
            sell_trades=0,
            buy_profit=0.0,
            sell_profit=0.0,
            exit_reason_counts={"take_profit": 0, "stop_loss": 0, "end_of_data": 0},
            entry_hour_counts={},
            average_trade_duration_bars=0.0,
        )

    profits = [trade.profit for trade in trades]
    total_profit = float(sum(profits))
    wins = sum(1 for profit in profits if profit > 0)
    win_rate = (wins / total_trades) * 100.0

    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for profit in profits:
        cumulative += profit
        if cumulative > peak:
            peak = cumulative
        drawdown = peak - cumulative
        if drawdown > max_drawdown:
            max_drawdown = drawdown

    rr_values = [trade.rr for trade in trades if trade.rr is not None]
    average_rr = float(sum(rr_values) / len(rr_values)) if rr_values else 0.0

    buy_trades = sum(1 for trade in trades if trade.direction == "BUY")
    sell_trades = sum(1 for trade in trades if trade.direction == "SELL")
    buy_profit = float(sum(trade.profit for trade in trades if trade.direction == "BUY"))
    sell_profit = float(sum(trade.profit for trade in trades if trade.direction == "SELL"))

    exit_reason_counts = {"take_profit": 0, "stop_loss": 0, "end_of_data": 0}
    for trade in trades:
        exit_reason_counts[trade.exit_reason] = exit_reason_counts.get(trade.exit_reason, 0) + 1

    entry_hour_counts: dict[str, int] = {}
    for trade in trades:
        hour_key = _entry_hour_key(trade.entry_time)
        entry_hour_counts[hour_key] = entry_hour_counts.get(hour_key, 0) + 1

    durations = [trade.exit_index - trade.entry_index for trade in trades]
    average_trade_duration_bars = float(sum(durations) / len(durations)) if durations else 0.0

    return BacktestMetrics(
        total_trades=total_trades,
        win_rate=win_rate,
        total_profit=total_profit,
        max_drawdown=float(max_drawdown),
        average_rr=average_rr,
        buy_trades=buy_trades,
        sell_trades=sell_trades,
        buy_profit=buy_profit,
        sell_profit=sell_profit,
        exit_reason_counts=exit_reason_counts,
        entry_hour_counts=entry_hour_counts,
        average_trade_duration_bars=average_trade_duration_bars,
    )


def _entry_hour_key(entry_time: object) -> str:
    hour_value = getattr(entry_time, "hour", None)
    if isinstance(hour_value, int) and 0 <= hour_value <= 23:
        return f"{hour_value:02d}"
    return "unknown"
