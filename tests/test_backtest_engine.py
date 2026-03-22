"""Unit tests for the simple backtest engine."""

import unittest
from unittest.mock import patch

import pandas as pd

from src.backtest.engine import run_backtest
from src.strategies.models import StrategyDecision


def _bars() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"time": 1, "open": 1.00, "high": 1.02, "low": 0.99, "close": 1.01, "volume": 100},
            {"time": 2, "open": 1.01, "high": 1.03, "low": 1.00, "close": 1.02, "volume": 101},
            {"time": 3, "open": 1.02, "high": 1.04, "low": 1.01, "close": 1.03, "volume": 102},
            {"time": 4, "open": 1.03, "high": 1.06, "low": 1.02, "close": 1.05, "volume": 103},
            {"time": 5, "open": 1.05, "high": 1.07, "low": 1.04, "close": 1.06, "volume": 104},
        ]
    )


class BacktestEngineTests(unittest.TestCase):
    """Validate deterministic trade simulation behavior."""

    def test_runs_single_buy_trade_to_take_profit(self) -> None:
        data = _bars()

        def decision_for_window(window: pd.DataFrame, **_: object) -> StrategyDecision:
            if len(window) == 3:
                return StrategyDecision(
                    signal="BUY",
                    stop_loss=1.00,
                    take_profit=1.05,
                    reason="buy_setup",
                )
            return StrategyDecision(signal="NONE", reason="none")

        with patch(
            "src.backtest.engine.evaluate_icc_v1",
            side_effect=decision_for_window,
        ):
            trades = run_backtest(data, ema_period=20, pullback_lookback=5, take_profit_rr=1.5)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade.direction, "BUY")
        self.assertEqual(trade.exit_reason, "take_profit")
        self.assertAlmostEqual(trade.exit_price, 1.05, places=8)

    def test_allows_only_one_trade_at_a_time(self) -> None:
        data = _bars()

        def always_buy(_: pd.DataFrame, **__: object) -> StrategyDecision:
            return StrategyDecision(signal="BUY", stop_loss=1.00, take_profit=1.05)

        with patch("src.backtest.engine.evaluate_icc_v1", side_effect=always_buy):
            trades = run_backtest(data, ema_period=20, pullback_lookback=5, take_profit_rr=1.5)

        self.assertGreaterEqual(len(trades), 1)
        for idx in range(1, len(trades)):
            self.assertGreater(trades[idx].entry_index, trades[idx - 1].exit_index)

    def test_runs_single_buy_trade_to_stop_loss(self) -> None:
        data = _bars()

        def decision_for_window(window: pd.DataFrame, **_: object) -> StrategyDecision:
            if len(window) == 3:
                return StrategyDecision(
                    signal="BUY",
                    stop_loss=1.02,
                    take_profit=1.08,
                    reason="buy_setup",
                )
            return StrategyDecision(signal="NONE", reason="none")

        with patch("src.backtest.engine.evaluate_icc_v1", side_effect=decision_for_window):
            trades = run_backtest(data, ema_period=20, pullback_lookback=5, take_profit_rr=1.5)

        self.assertEqual(len(trades), 1)
        trade = trades[0]
        self.assertEqual(trade.exit_reason, "stop_loss")
        self.assertAlmostEqual(trade.exit_price, 1.02, places=8)
        self.assertLess(trade.profit, 0.0)

    def test_returns_no_trades_when_strategy_never_signals(self) -> None:
        data = _bars()

        with patch(
            "src.backtest.engine.evaluate_icc_v1",
            return_value=StrategyDecision(signal="NONE", reason="no_setup"),
        ):
            trades = run_backtest(data, ema_period=20, pullback_lookback=5, take_profit_rr=1.5)

        self.assertEqual(trades, [])


if __name__ == "__main__":
    unittest.main()
