"""Unit tests for signal guard-rail checks."""

from __future__ import annotations

import unittest

import pandas as pd

from src.risk.manager import SignalGuardInput, evaluate_signal_guardrails


class RiskManagerTests(unittest.TestCase):
    """Validate minimal guard-rail decisions and reasons."""

    def _base_input(self) -> SignalGuardInput:
        return SignalGuardInput(
            evaluation_time_utc=pd.Timestamp("2026-01-05 08:00:00+00:00"),
            candle_time_utc=pd.Timestamp("2026-01-05 07:45:00+00:00"),
            has_m15_data=True,
            has_h1_data=True,
            duplicate_candle=False,
            session_start_hour_utc=7,
            session_end_hour_utc=12,
        )

    def test_missing_required_data_blocks(self) -> None:
        input_data = self._base_input()
        input_data = SignalGuardInput(**{**input_data.__dict__, "has_h1_data": False})
        result = evaluate_signal_guardrails(input_data)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "missing_required_data")

    def test_future_candle_blocks(self) -> None:
        input_data = SignalGuardInput(
            **{
                **self._base_input().__dict__,
                "candle_time_utc": pd.Timestamp("2026-01-05 08:15:00+00:00"),
            }
        )
        result = evaluate_signal_guardrails(input_data)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "future_candle_timestamp")

    def test_unclosed_current_candle_blocks(self) -> None:
        input_data = SignalGuardInput(
            **{
                **self._base_input().__dict__,
                "candle_time_utc": pd.Timestamp("2026-01-05 07:50:00+00:00"),
            }
        )
        result = evaluate_signal_guardrails(input_data)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "current_candle_not_closed")

    def test_session_blocks_outside_window(self) -> None:
        input_data = SignalGuardInput(
            **{
                **self._base_input().__dict__,
                "evaluation_time_utc": pd.Timestamp("2026-01-05 12:30:00+00:00"),
                "candle_time_utc": pd.Timestamp("2026-01-05 12:00:00+00:00"),
            }
        )
        result = evaluate_signal_guardrails(input_data)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "blocked_by_session")

    def test_duplicate_blocks(self) -> None:
        input_data = SignalGuardInput(**{**self._base_input().__dict__, "duplicate_candle": True})
        result = evaluate_signal_guardrails(input_data)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "duplicate_candle_already_logged")

    def test_optional_max_signals_per_day_blocks(self) -> None:
        input_data = SignalGuardInput(
            **{
                **self._base_input().__dict__,
                "max_signals_per_day": 2,
                "signals_today": 2,
            }
        )
        result = evaluate_signal_guardrails(input_data)
        self.assertFalse(result.allowed)
        self.assertEqual(result.reason, "max_signals_per_day_reached")

    def test_passes_when_all_guardrails_pass(self) -> None:
        result = evaluate_signal_guardrails(self._base_input())
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "guardrails_passed")


if __name__ == "__main__":
    unittest.main()
