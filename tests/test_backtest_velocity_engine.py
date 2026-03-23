"""Unit tests for velocity backtest engine behavior."""

import unittest
from unittest.mock import patch

import pandas as pd

from src.backtest.engine import run_backtest
from src.backtest.velocity_engine import run_velocity_backtest
from src.strategies.models import StrategyDecision
from src.strategies.velocity_strategy import VelocityStrategyParams


def _bars(count: int = 40) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    base = pd.Timestamp("2024-01-01 00:00:00+00:00")
    for index in range(count):
        close = 1.1000 + (index * 0.0004)
        rows.append(
            {
                "time": base + pd.Timedelta(minutes=15 * index),
                "open": close - 0.0002,
                "high": close + 0.0006,
                "low": close - 0.0006,
                "close": close,
                "volume": 1000 + index,
            }
        )
    return pd.DataFrame(rows)


class VelocityBacktestEngineTests(unittest.TestCase):
    """Validate stateful velocity backtest controls."""

    def test_cooldown_blocks_immediate_reentry(self) -> None:
        dataframe = _bars(30)
        params = VelocityStrategyParams(
            entry_threshold=0.1,
            entry_persist=1,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=2,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )

        with patch(
            "src.backtest.velocity_engine.evaluate_velocity_entry",
            return_value=StrategyDecision(signal="BUY", stop_loss=1.0, reason="forced_entry"),
        ):
            with patch(
                "src.backtest.velocity_engine.should_exit_velocity_position",
                return_value=(True, "velocity_drawdown_exit"),
            ):
                trades = run_velocity_backtest(
                    dataframe,
                    lookback_k=1,
                    atr_period=2,
                    smoothing_span=1,
                    params=params,
                )

        self.assertGreaterEqual(len(trades), 2)
        for idx in range(1, len(trades)):
            self.assertGreaterEqual(trades[idx].entry_index - trades[idx - 1].entry_index, 3)

    def test_zero_cooldown_allows_next_bar_reentry(self) -> None:
        dataframe = _bars(20)
        params = VelocityStrategyParams(
            entry_threshold=0.1,
            entry_persist=1,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=0,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )
        with patch(
            "src.backtest.velocity_engine.evaluate_velocity_entry",
            return_value=StrategyDecision(signal="BUY", stop_loss=1.0, reason="forced_entry"),
        ):
            with patch(
                "src.backtest.velocity_engine.should_exit_velocity_position",
                return_value=(True, "velocity_drawdown_exit"),
            ):
                trades = run_velocity_backtest(
                    dataframe,
                    lookback_k=1,
                    atr_period=2,
                    smoothing_span=1,
                    params=params,
                )
        self.assertGreaterEqual(len(trades), 2)
        for idx in range(1, len(trades)):
            self.assertGreaterEqual(trades[idx].entry_index - trades[idx - 1].entry_index, 1)

    def test_velocity_backtest_runs_end_to_end_without_crashing(self) -> None:
        dataframe = _bars(120)
        params = VelocityStrategyParams(
            entry_threshold=0.05,
            entry_persist=2,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=1,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )

        trades = run_velocity_backtest(
            dataframe,
            lookback_k=2,
            atr_period=14,
            smoothing_span=2,
            params=params,
        )

        self.assertIsInstance(trades, list)

    def test_very_short_dataset_returns_no_trades(self) -> None:
        dataframe = _bars(2)
        params = VelocityStrategyParams(
            entry_threshold=0.1,
            entry_persist=2,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=0,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )
        trades = run_velocity_backtest(
            dataframe,
            lookback_k=5,
            atr_period=14,
            smoothing_span=1,
            params=params,
        )
        self.assertEqual(trades, [])

    def test_constant_price_series_generates_no_entries(self) -> None:
        dataframe = _bars(50)
        dataframe["open"] = 1.1000
        dataframe["high"] = 1.1000
        dataframe["low"] = 1.1000
        dataframe["close"] = 1.1000
        params = VelocityStrategyParams(
            entry_threshold=0.1,
            entry_persist=2,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=0,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )
        trades = run_velocity_backtest(
            dataframe,
            lookback_k=2,
            atr_period=14,
            smoothing_span=1,
            params=params,
        )
        self.assertEqual(trades, [])

    def test_nan_inputs_are_skipped_without_crash(self) -> None:
        dataframe = _bars(60)
        dataframe.loc[10:15, "close"] = float("nan")
        params = VelocityStrategyParams(
            entry_threshold=0.05,
            entry_persist=2,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=1,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )
        trades = run_velocity_backtest(
            dataframe,
            lookback_k=2,
            atr_period=14,
            smoothing_span=1,
            params=params,
        )
        self.assertIsInstance(trades, list)

    def test_same_bar_stop_is_not_checked_on_entry_bar(self) -> None:
        dataframe = _bars(20)
        params = VelocityStrategyParams(
            entry_threshold=0.1,
            entry_persist=1,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=0,
            trend_filter_enabled=False,
            trend_ema_period=50,
        )

        # Create a deep wick only on planned entry bar.
        dataframe.loc[5, "low"] = 1.0900

        def entry_side_effect(_: pd.DataFrame, *, current_index: int, **__: object) -> StrategyDecision:
            if current_index == 5:
                return StrategyDecision(signal="BUY", stop_loss=1.0990, reason="forced_entry")
            return StrategyDecision(signal="NONE", reason="none")

        with patch("src.backtest.velocity_engine.evaluate_velocity_entry", side_effect=entry_side_effect):
            with patch(
                "src.backtest.velocity_engine.should_exit_velocity_position",
                return_value=(False, None),
            ):
                trades = run_velocity_backtest(
                    dataframe,
                    lookback_k=1,
                    atr_period=2,
                    smoothing_span=1,
                    params=params,
                )

        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0].entry_index, 5)
        self.assertEqual(trades[0].exit_reason, "end_of_data")

    def test_regression_icc_engine_still_operates(self) -> None:
        dataframe = _bars(8)
        with patch(
            "src.backtest.engine.evaluate_icc_v1",
            return_value=StrategyDecision(signal="NONE", reason="no_setup"),
        ):
            trades = run_backtest(dataframe)
        self.assertEqual(trades, [])


if __name__ == "__main__":
    unittest.main()
