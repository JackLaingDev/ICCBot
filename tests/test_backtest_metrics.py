"""Unit tests for backtest metrics calculations."""

import unittest

import pandas as pd

from src.backtest.engine import BacktestTrade
from src.backtest.metrics import calculate_metrics


class BacktestMetricsTests(unittest.TestCase):
    """Validate core metrics from deterministic trade inputs."""

    def test_calculate_metrics_from_trades(self) -> None:
        trades = [
            BacktestTrade(
                direction="BUY",
                entry_index=0,
                entry_time=pd.Timestamp("2024-01-01 10:00:00+00:00"),
                entry_price=1.0,
                stop_loss=0.9,
                take_profit=1.15,
                exit_index=1,
                exit_time=pd.Timestamp("2024-01-01 11:00:00+00:00"),
                exit_price=1.15,
                exit_reason="take_profit",
                profit=0.15,
                rr=1.5,
            ),
            BacktestTrade(
                direction="SELL",
                entry_index=2,
                entry_time=pd.Timestamp("2024-01-01 11:00:00+00:00"),
                entry_price=1.2,
                stop_loss=1.3,
                take_profit=1.05,
                exit_index=3,
                exit_time=pd.Timestamp("2024-01-01 12:00:00+00:00"),
                exit_price=1.3,
                exit_reason="stop_loss",
                profit=-0.1,
                rr=-1.0,
            ),
        ]

        metrics = calculate_metrics(trades)

        self.assertEqual(metrics.total_trades, 2)
        self.assertAlmostEqual(metrics.win_rate, 50.0, places=8)
        self.assertAlmostEqual(metrics.total_profit, 0.05, places=8)
        self.assertAlmostEqual(metrics.max_drawdown, 0.1, places=8)
        self.assertAlmostEqual(metrics.average_rr, 0.25, places=8)
        self.assertEqual(metrics.buy_trades, 1)
        self.assertEqual(metrics.sell_trades, 1)
        self.assertAlmostEqual(metrics.buy_profit, 0.15, places=8)
        self.assertAlmostEqual(metrics.sell_profit, -0.1, places=8)
        self.assertEqual(metrics.exit_reason_counts["take_profit"], 1)
        self.assertEqual(metrics.exit_reason_counts["stop_loss"], 1)
        self.assertEqual(metrics.exit_reason_counts["end_of_data"], 0)
        self.assertEqual(metrics.entry_hour_counts["10"], 1)
        self.assertEqual(metrics.entry_hour_counts["11"], 1)
        self.assertAlmostEqual(metrics.average_trade_duration_bars, 1.0, places=8)

    def test_calculate_metrics_empty_input(self) -> None:
        metrics = calculate_metrics([])
        self.assertEqual(metrics.total_trades, 0)
        self.assertEqual(metrics.win_rate, 0.0)
        self.assertEqual(metrics.total_profit, 0.0)
        self.assertEqual(metrics.max_drawdown, 0.0)
        self.assertEqual(metrics.average_rr, 0.0)
        self.assertEqual(metrics.buy_trades, 0)
        self.assertEqual(metrics.sell_trades, 0)
        self.assertEqual(metrics.buy_profit, 0.0)
        self.assertEqual(metrics.sell_profit, 0.0)
        self.assertEqual(metrics.exit_reason_counts["take_profit"], 0)
        self.assertEqual(metrics.exit_reason_counts["stop_loss"], 0)
        self.assertEqual(metrics.exit_reason_counts["end_of_data"], 0)
        self.assertEqual(metrics.entry_hour_counts, {})
        self.assertEqual(metrics.average_trade_duration_bars, 0.0)


if __name__ == "__main__":
    unittest.main()
