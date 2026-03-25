"""Focused tests for the live ICC signal runner script."""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.strategies.models import StrategyDecision


def _load_run_signal_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_signal.py"
    spec = importlib.util.spec_from_file_location("run_signal_module_for_tests", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_signal.py for tests")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunSignalScriptTests(unittest.TestCase):
    """Validate live signal guard rails and helper behavior."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_run_signal_module()

    def test_is_in_session_utc_boundaries(self) -> None:
        self.assertFalse(self.module._is_in_session(pd.Timestamp("2026-01-01 06:59:00+00:00")))
        self.assertTrue(self.module._is_in_session(pd.Timestamp("2026-01-01 07:00:00+00:00")))
        self.assertTrue(self.module._is_in_session(pd.Timestamp("2026-01-01 11:59:00+00:00")))
        self.assertFalse(self.module._is_in_session(pd.Timestamp("2026-01-01 12:00:00+00:00")))

    def test_is_stale_closed_candle(self) -> None:
        evaluation_time = pd.Timestamp("2026-01-01 11:00:00+00:00")
        fresh_candle = pd.Timestamp("2026-01-01 10:20:00+00:00")
        stale_candle = pd.Timestamp("2026-01-01 09:00:00+00:00")
        self.assertFalse(
            self.module._is_stale_closed_candle(
                candle_time=fresh_candle,
                evaluation_time=evaluation_time,
            )
        )
        self.assertTrue(
            self.module._is_stale_closed_candle(
                candle_time=stale_candle,
                evaluation_time=evaluation_time,
            )
        )

    def test_is_future_candle(self) -> None:
        evaluation_time = pd.Timestamp("2026-01-01 11:00:00+00:00")
        future_candle = pd.Timestamp("2026-01-01 11:15:00+00:00")
        past_candle = pd.Timestamp("2026-01-01 10:45:00+00:00")
        self.assertTrue(
            self.module._is_future_candle(
                candle_time=future_candle,
                evaluation_time=evaluation_time,
            )
        )
        self.assertFalse(
            self.module._is_future_candle(
                candle_time=past_candle,
                evaluation_time=evaluation_time,
            )
        )

    def test_build_ema_bias_h1_no_lookahead_boundary(self) -> None:
        lower = pd.DataFrame(
            {
                "time": pd.to_datetime(
                    [
                        "2026-01-01 00:45:00+00:00",
                        "2026-01-01 01:00:00+00:00",
                        "2026-01-01 02:00:00+00:00",
                    ]
                )
            }
        )
        htf = pd.DataFrame(
            {
                "time": pd.to_datetime(
                    [
                        "2026-01-01 00:00:00+00:00",
                        "2026-01-01 01:00:00+00:00",
                    ]
                ),
                "close": [1.0000, 1.3000],
            }
        )
        bias = self.module._build_ema_bias_by_time(
            lower_timeframe_df=lower,
            htf_df=htf,
            ema_period=200,
            htf_bar_hours=1,
        )
        self.assertEqual(bias[pd.Timestamp("2026-01-01 00:45:00+00:00")], "NEUTRAL")
        self.assertEqual(bias[pd.Timestamp("2026-01-01 01:00:00+00:00")], "NEUTRAL")
        self.assertEqual(bias[pd.Timestamp("2026-01-01 02:00:00+00:00")], "BULLISH")

    def test_duplicate_candle_guard(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "signals.csv"
            pd.DataFrame(
                [{"candle_timestamp_utc": "2026-01-01T10:45:00+00:00", "signal": "SELL"}]
            ).to_csv(log_path, index=False)
            with patch.object(self.module, "SIGNAL_LOG_PATH", log_path):
                self.assertTrue(self.module._is_duplicate_candle("2026-01-01T10:45:00+00:00"))
                self.assertFalse(self.module._is_duplicate_candle("2026-01-01T11:00:00+00:00"))

    def test_evaluate_latest_closed_uses_second_last_bar(self) -> None:
        evaluation_time = pd.Timestamp("2026-01-01 11:15:00+00:00")
        m15 = pd.DataFrame(
            [
                {
                    "time": pd.Timestamp("2026-01-01 10:30:00+00:00"),
                    "open": 1.10,
                    "high": 1.11,
                    "low": 1.09,
                    "close": 1.10,
                    "volume": 100,
                },
                {
                    "time": pd.Timestamp("2026-01-01 10:45:00+00:00"),
                    "open": 1.10,
                    "high": 1.11,
                    "low": 1.09,
                    "close": 1.10,
                    "volume": 110,
                },
                {
                    "time": pd.Timestamp("2026-01-01 11:00:00+00:00"),
                    "open": 1.10,
                    "high": 1.11,
                    "low": 1.09,
                    "close": 1.10,
                    "volume": 120,
                },
            ]
        )
        h1 = pd.DataFrame(
            [
                {"time": pd.Timestamp("2026-01-01 09:00:00+00:00"), "close": 1.2},
                {"time": pd.Timestamp("2026-01-01 10:00:00+00:00"), "close": 1.1},
            ]
        )

        with patch.object(
            self.module,
            "evaluate_icc_v1",
            return_value=StrategyDecision(signal="NONE", reason="no_setup"),
        ):
            result = self.module._evaluate_latest_closed_signal(
                evaluation_time=evaluation_time,
                m15_df=m15,
                h1_df=h1,
                ema_period=200,
                take_profit_rr=1.5,
            )

        self.assertEqual(result["candle_timestamp_utc"], "2026-01-01T10:45:00+00:00")

    def test_evaluate_blocks_future_candle_timestamp(self) -> None:
        evaluation_time = pd.Timestamp("2026-01-01 11:00:00+00:00")
        m15 = pd.DataFrame(
            [
                {
                    "time": pd.Timestamp("2026-01-01 10:45:00+00:00"),
                    "open": 1.10,
                    "high": 1.11,
                    "low": 1.09,
                    "close": 1.10,
                    "volume": 100,
                },
                {
                    "time": pd.Timestamp("2026-01-01 11:15:00+00:00"),
                    "open": 1.10,
                    "high": 1.11,
                    "low": 1.09,
                    "close": 1.10,
                    "volume": 110,
                },
                {
                    "time": pd.Timestamp("2026-01-01 11:30:00+00:00"),
                    "open": 1.10,
                    "high": 1.11,
                    "low": 1.09,
                    "close": 1.10,
                    "volume": 120,
                },
            ]
        )
        h1 = pd.DataFrame(
            [
                {"time": pd.Timestamp("2026-01-01 09:00:00+00:00"), "close": 1.2},
                {"time": pd.Timestamp("2026-01-01 10:00:00+00:00"), "close": 1.1},
            ]
        )
        result = self.module._evaluate_latest_closed_signal(
            evaluation_time=evaluation_time,
            m15_df=m15,
            h1_df=h1,
            ema_period=200,
            take_profit_rr=1.5,
        )
        self.assertEqual(result["signal"], "NONE")
        self.assertEqual(result["reason"], "future_candle_timestamp")


if __name__ == "__main__":
    unittest.main()
