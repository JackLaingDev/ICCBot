"""Unit tests for momentum-velocity strategy decisions."""

import unittest

import pandas as pd

from src.strategies.velocity_strategy import (
    VelocityStrategyParams,
    evaluate_velocity_entry,
    should_exit_velocity_position,
    update_velocity_extreme,
)


def _entry_frame(velocity_values: list[float], *, close: float, trend_ema: float) -> pd.DataFrame:
    base_time = pd.Timestamp("2024-01-01 00:00:00+00:00")
    rows: list[dict[str, object]] = []
    for idx, velocity in enumerate(velocity_values):
        rows.append(
            {
                "time": base_time + pd.Timedelta(minutes=15 * idx),
                "open": close,
                "high": close + 0.0010,
                "low": close - 0.0010,
                "close": close,
                "volume": 1000 + idx,
                "atr": 0.0010,
                "velocity": velocity,
                "trend_ema": trend_ema,
            }
        )
    return pd.DataFrame(rows)


class VelocityStrategyTests(unittest.TestCase):
    """Validate long/short entries and drawdown exits."""

    def setUp(self) -> None:
        self.params = VelocityStrategyParams(
            entry_threshold=0.7,
            entry_persist=2,
            drawdown_frac=0.3,
            stop_atr_mult=2.0,
            cooldown_bars=0,
            trend_filter_enabled=True,
            trend_ema_period=50,
        )

    def test_long_entry_requires_persistent_threshold_breach(self) -> None:
        dataframe = _entry_frame([0.2, 0.6, 0.75, 0.9], close=1.1020, trend_ema=1.1000)

        decision = evaluate_velocity_entry(dataframe, current_index=3, params=self.params)
        self.assertEqual(decision.signal, "BUY")
        self.assertIsNotNone(decision.stop_loss)
        self.assertLess(float(decision.stop_loss), 1.1020)

    def test_short_entry_requires_persistent_threshold_breach(self) -> None:
        dataframe = _entry_frame([0.0, -0.4, -0.8, -1.1], close=1.0980, trend_ema=1.1000)

        decision = evaluate_velocity_entry(dataframe, current_index=3, params=self.params)
        self.assertEqual(decision.signal, "SELL")
        self.assertIsNotNone(decision.stop_loss)
        self.assertGreater(float(decision.stop_loss), 1.0980)

    def test_exit_triggers_on_velocity_drawdown_for_long(self) -> None:
        should_exit, reason = should_exit_velocity_position(
            direction="BUY",
            current_velocity=0.60,
            velocity_extreme=1.00,
            drawdown_frac=0.30,
        )
        self.assertTrue(should_exit)
        self.assertEqual(reason, "velocity_drawdown_exit")

    def test_exit_triggers_on_velocity_drawdown_for_short(self) -> None:
        should_exit, reason = should_exit_velocity_position(
            direction="SELL",
            current_velocity=-0.60,
            velocity_extreme=-1.00,
            drawdown_frac=0.30,
        )
        self.assertTrue(should_exit)
        self.assertEqual(reason, "velocity_drawdown_exit")

    def test_sign_flip_exit_symmetry(self) -> None:
        long_exit, long_reason = should_exit_velocity_position(
            direction="BUY",
            current_velocity=-0.01,
            velocity_extreme=0.80,
            drawdown_frac=0.3,
        )
        short_exit, short_reason = should_exit_velocity_position(
            direction="SELL",
            current_velocity=0.01,
            velocity_extreme=-0.80,
            drawdown_frac=0.3,
        )
        self.assertTrue(long_exit)
        self.assertEqual(long_reason, "velocity_sign_flip")
        self.assertTrue(short_exit)
        self.assertEqual(short_reason, "velocity_sign_flip")

    def test_warmup_returns_none_before_persistence_window(self) -> None:
        dataframe = _entry_frame([0.9], close=1.1020, trend_ema=1.1000)
        decision = evaluate_velocity_entry(dataframe, current_index=0, params=self.params)
        self.assertEqual(decision.signal, "NONE")
        self.assertEqual(decision.reason, "insufficient_bars_for_persistence")

    def test_no_entry_when_threshold_not_met(self) -> None:
        dataframe = _entry_frame([0.1, 0.2, 0.3, 0.4], close=1.1020, trend_ema=1.1000)
        decision = evaluate_velocity_entry(dataframe, current_index=3, params=self.params)
        self.assertEqual(decision.signal, "NONE")
        self.assertEqual(decision.reason, "threshold_or_persistence_not_met")

    def test_no_entry_when_velocity_nan(self) -> None:
        dataframe = _entry_frame([0.8, 0.9, 1.0], close=1.1020, trend_ema=1.1000)
        dataframe.loc[2, "velocity"] = float("nan")
        decision = evaluate_velocity_entry(dataframe, current_index=2, params=self.params)
        self.assertEqual(decision.signal, "NONE")
        self.assertEqual(decision.reason, "velocity_not_ready")

    def test_update_velocity_extreme_tracks_max_for_long_and_min_for_short(self) -> None:
        self.assertEqual(
            update_velocity_extreme(direction="BUY", current_velocity=0.9, velocity_extreme=0.7),
            0.9,
        )
        self.assertEqual(
            update_velocity_extreme(direction="SELL", current_velocity=-0.9, velocity_extreme=-0.7),
            -0.9,
        )


if __name__ == "__main__":
    unittest.main()
