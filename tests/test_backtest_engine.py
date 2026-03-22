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


def _bars_with_hours(hours: list[int]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for index, hour in enumerate(hours, start=1):
        rows.append(
            {
                "time": pd.Timestamp(2024, 1, 1, hour, 0, tz="UTC"),
                "open": 1.00 + (index * 0.01),
                "high": 1.02 + (index * 0.01),
                "low": 0.99 + (index * 0.01),
                "close": 1.01 + (index * 0.01),
                "volume": 100 + index,
            }
        )
    return pd.DataFrame(rows)


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

    def test_short_only_mode_ignores_buy_signals(self) -> None:
        data = _bars()

        def decision_for_window(window: pd.DataFrame, **_: object) -> StrategyDecision:
            if len(window) == 3:
                return StrategyDecision(signal="BUY", stop_loss=1.00, take_profit=1.05)
            if len(window) == 4:
                return StrategyDecision(signal="SELL", stop_loss=1.07, take_profit=1.03)
            return StrategyDecision(signal="NONE", reason="none")

        with patch("src.backtest.engine.evaluate_icc_v1", side_effect=decision_for_window):
            trades = run_backtest(
                data,
                ema_period=20,
                pullback_lookback=5,
                take_profit_rr=1.5,
                allowed_directions={"SELL"},
            )

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].direction, "SELL")

    def test_session_filter_allows_entries_inside_window(self) -> None:
        data = _bars_with_hours([6, 7, 8, 9, 10])

        def always_sell(_: pd.DataFrame, **__: object) -> StrategyDecision:
            return StrategyDecision(signal="SELL", stop_loss=1.20, take_profit=0.80)

        with patch("src.backtest.engine.evaluate_icc_v1", side_effect=always_sell):
            trades = run_backtest(
                data,
                session_start_hour=7,
                session_end_hour=12,
            )

        self.assertGreaterEqual(len(trades), 1)
        self.assertEqual(trades[0].direction, "SELL")

    def test_session_filter_blocks_entries_outside_window(self) -> None:
        data = _bars_with_hours([0, 1, 2, 3, 4])

        def always_sell(_: pd.DataFrame, **__: object) -> StrategyDecision:
            return StrategyDecision(signal="SELL", stop_loss=1.20, take_profit=0.80)

        with patch("src.backtest.engine.evaluate_icc_v1", side_effect=always_sell):
            trades = run_backtest(
                data,
                session_start_hour=7,
                session_end_hour=12,
            )

        self.assertEqual(trades, [])

    def test_session_filter_supports_overnight_window(self) -> None:
        data = _bars_with_hours([22, 23, 0, 1, 2])

        def always_sell(_: pd.DataFrame, **__: object) -> StrategyDecision:
            return StrategyDecision(signal="SELL", stop_loss=1.20, take_profit=0.80)

        with patch("src.backtest.engine.evaluate_icc_v1", side_effect=always_sell):
            trades = run_backtest(
                data,
                session_start_hour=22,
                session_end_hour=2,
            )

        self.assertGreaterEqual(len(trades), 1)

    def test_session_filter_rejects_equal_start_and_end(self) -> None:
        data = _bars_with_hours([7, 8, 9, 10, 11])

        with self.assertRaises(ValueError):
            run_backtest(
                data,
                session_start_hour=7,
                session_end_hour=7,
            )


if __name__ == "__main__":
    unittest.main()
