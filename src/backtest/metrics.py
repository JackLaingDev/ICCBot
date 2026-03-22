"""Core backtest performance metrics.

Responsible for transparent, deterministic metric calculations only.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.backtest.engine import BacktestTrade


@dataclass(frozen=True)
class BacktestMetrics:
    """Core summary metrics for a backtest run."""

    total_trades: int
    win_rate: float
    total_profit: float
    max_drawdown: float
    average_rr: float


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

    return BacktestMetrics(
        total_trades=total_trades,
        win_rate=win_rate,
        total_profit=total_profit,
        max_drawdown=float(max_drawdown),
        average_rr=average_rr,
    )
