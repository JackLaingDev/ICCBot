"""Unit tests for the minimal ICC v1 strategy module."""

import unittest

import pandas as pd

from src.strategies.icc_strategy import evaluate_icc_v1


def _base_rows(total: int = 120) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for i in range(total):
        close = 100.0 + (i * 0.1)
        rows.append(
            {
                "time": 1_700_000_000 + (i * 900),
                "open": close - 0.05,
                "high": close + 0.20,
                "low": close - 0.20,
                "close": close,
                "volume": 1000 + i,
            }
        )
    return rows


class ICCStrategyTests(unittest.TestCase):
    """Validate BUY/SELL/NONE outcomes for ICC v1 rules."""

    def test_returns_buy_when_bullish_pullback_and_breakout(self) -> None:
        rows = _base_rows()
        # Keep latest candles bullish, then force a wick pullback and breakout.
        for idx in range(-30, 0):
            base = 120.0 + (idx + 30) * 0.3
            rows[idx]["open"] = base - 0.05
            rows[idx]["high"] = base + 0.20
            rows[idx]["low"] = base - 0.20
            rows[idx]["close"] = base

        rows[-6]["low"] = rows[-6]["close"] - 5.0  # pullback wick
        rows[-2]["high"] = rows[-2]["close"] + 0.10
        rows[-1]["close"] = rows[-2]["high"] + 0.20  # continuation breakout
        rows[-1]["high"] = rows[-1]["close"] + 0.10
        rows[-1]["low"] = rows[-1]["close"] - 0.10
        dataframe = pd.DataFrame(rows)

        decision = evaluate_icc_v1(dataframe, ema_period=20, pullback_lookback=5)

        self.assertEqual(decision.signal, "BUY")
        self.assertIsNotNone(decision.stop_loss)
        self.assertIsNotNone(decision.take_profit)
        self.assertEqual(decision.reason, "buy_setup")

    def test_returns_sell_when_bearish_pullback_and_breakdown(self) -> None:
        rows = _base_rows()
        # Force downtrend in recent bars, then pullback wick and breakdown.
        for idx in range(-30, 0):
            base = 90.0 + ((idx + 30) * -0.2)
            rows[idx]["open"] = base + 0.05
            rows[idx]["high"] = base + 0.20
            rows[idx]["low"] = base - 0.20
            rows[idx]["close"] = base

        rows[-6]["high"] = rows[-6]["close"] + 5.0  # pullback against bearish trend
        rows[-2]["low"] = rows[-2]["close"] - 0.10
        rows[-1]["close"] = rows[-2]["low"] - 0.20  # continuation breakdown
        rows[-1]["high"] = rows[-1]["close"] + 0.10
        rows[-1]["low"] = rows[-1]["close"] - 0.10
        dataframe = pd.DataFrame(rows)

        decision = evaluate_icc_v1(dataframe, ema_period=20, pullback_lookback=5)

        self.assertEqual(decision.signal, "SELL")
        self.assertIsNotNone(decision.stop_loss)
        self.assertIsNotNone(decision.take_profit)
        self.assertEqual(decision.reason, "sell_setup")

    def test_returns_none_when_no_pullback(self) -> None:
        rows = _base_rows()
        for idx in range(-30, 0):
            base = 130.0 + (idx + 30) * 0.2
            rows[idx]["open"] = base - 0.05
            rows[idx]["high"] = base + 0.20
            rows[idx]["low"] = base + 0.05  # keep lows above EMA to avoid pullback
            rows[idx]["close"] = base
        dataframe = pd.DataFrame(rows)

        decision = evaluate_icc_v1(dataframe, ema_period=20, pullback_lookback=5)

        self.assertEqual(decision.signal, "NONE")
        self.assertIsNone(decision.stop_loss)
        self.assertIsNone(decision.take_profit)

    def test_raises_for_insufficient_data(self) -> None:
        dataframe = pd.DataFrame(_base_rows(total=10))
        with self.assertRaises(ValueError):
            evaluate_icc_v1(dataframe, ema_period=20, pullback_lookback=5)

    def test_unsorted_input_still_produces_expected_signal(self) -> None:
        rows = _base_rows()
        for idx in range(-30, 0):
            base = 120.0 + (idx + 30) * 0.3
            rows[idx]["open"] = base - 0.05
            rows[idx]["high"] = base + 0.20
            rows[idx]["low"] = base - 0.20
            rows[idx]["close"] = base

        rows[-6]["low"] = rows[-6]["close"] - 5.0
        rows[-2]["high"] = rows[-2]["close"] + 0.10
        rows[-1]["close"] = rows[-2]["high"] + 0.20
        rows[-1]["high"] = rows[-1]["close"] + 0.10
        rows[-1]["low"] = rows[-1]["close"] - 0.10

        dataframe = pd.DataFrame(rows).sample(frac=1.0, random_state=42).reset_index(drop=True)
        decision = evaluate_icc_v1(dataframe, ema_period=20, pullback_lookback=5)

        self.assertEqual(decision.signal, "BUY")


if __name__ == "__main__":
    unittest.main()
