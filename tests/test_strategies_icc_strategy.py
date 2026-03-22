"""Unit tests for the minimal ICC v2 strategy module."""

import unittest

import pandas as pd

from src.strategies.icc_strategy import evaluate_icc_v1


def _to_rows(closes: list[float], highs: list[float], lows: list[float]) -> list[dict[str, float | int]]:
    rows: list[dict[str, float | int]] = []
    for idx, close in enumerate(closes):
        rows.append(
            {
                "time": 1_700_000_000 + (idx * 900),
                "open": close,
                "high": highs[idx],
                "low": lows[idx],
                "close": close,
                "volume": 1_000 + idx,
            }
        )
    return rows


def _bullish_structure_rows() -> list[dict[str, float | int]]:
    closes = [100.0, 101.0, 102.0, 101.2, 103.0, 102.0, 101.0, 104.5, 103.8, 104.2, 104.6]
    highs = [100.5, 101.5, 102.5, 101.4, 104.0, 102.5, 101.5, 105.0, 104.0, 104.3, 104.8]
    lows = [99.5, 100.5, 101.5, 100.8, 102.0, 101.0, 100.5, 104.0, 103.5, 103.9, 104.1]
    return _to_rows(closes, highs, lows)


def _bearish_structure_rows() -> list[dict[str, float | int]]:
    closes = [110.0, 109.0, 108.0, 108.8, 107.0, 108.0, 109.0, 105.5, 106.2, 105.9, 105.4]
    highs = [110.5, 109.5, 108.5, 109.0, 107.5, 108.5, 109.5, 106.0, 106.8, 106.1, 105.8]
    lows = [109.5, 108.5, 107.5, 108.2, 106.0, 107.5, 108.5, 105.0, 105.8, 105.6, 105.2]
    return _to_rows(closes, highs, lows)


def _no_signal_rows() -> list[dict[str, float | int]]:
    closes = [100.0, 100.2, 100.4, 100.3, 100.5, 100.4, 100.6, 100.5, 100.7, 100.6, 100.8]
    highs = [100.3, 100.5, 100.7, 100.6, 100.8, 100.7, 100.9, 100.8, 101.0, 100.9, 101.1]
    lows = [99.7, 99.9, 100.1, 100.0, 100.2, 100.1, 100.3, 100.2, 100.4, 100.3, 100.5]
    return _to_rows(closes, highs, lows)


class ICCStrategyTests(unittest.TestCase):
    """Validate BUY/SELL/NONE outcomes for ICC v2 rules."""

    def test_returns_buy_for_bullish_structure_setup(self) -> None:
        dataframe = pd.DataFrame(_bullish_structure_rows())
        decision = evaluate_icc_v1(dataframe, pullback_lookback=6, swing_window=2)

        self.assertEqual(decision.signal, "BUY")
        self.assertIsNotNone(decision.stop_loss)
        self.assertIsNotNone(decision.take_profit)
        self.assertEqual(decision.reason, "buy_setup")

    def test_returns_sell_for_bearish_structure_setup(self) -> None:
        dataframe = pd.DataFrame(_bearish_structure_rows())
        decision = evaluate_icc_v1(dataframe, pullback_lookback=6, swing_window=2)

        self.assertEqual(decision.signal, "SELL")
        self.assertIsNotNone(decision.stop_loss)
        self.assertIsNotNone(decision.take_profit)
        self.assertEqual(decision.reason, "sell_setup")

    def test_returns_none_when_no_structure_setup(self) -> None:
        dataframe = pd.DataFrame(_no_signal_rows())
        decision = evaluate_icc_v1(dataframe, pullback_lookback=6, swing_window=2)

        self.assertEqual(decision.signal, "NONE")
        self.assertIsNone(decision.stop_loss)
        self.assertIsNone(decision.take_profit)

    def test_raises_for_insufficient_data(self) -> None:
        dataframe = pd.DataFrame(_no_signal_rows()[:4])
        with self.assertRaises(ValueError):
            evaluate_icc_v1(dataframe, pullback_lookback=5, swing_window=2)

    def test_unsorted_input_still_produces_expected_signal(self) -> None:
        dataframe = (
            pd.DataFrame(_bullish_structure_rows())
            .sample(frac=1.0, random_state=42)
            .reset_index(drop=True)
        )
        decision = evaluate_icc_v1(dataframe, pullback_lookback=6, swing_window=2)

        self.assertEqual(decision.signal, "BUY")

    def test_does_not_use_unconfirmed_swing_for_bos(self) -> None:
        # Index 8 can look like a swing low only if future candles are used.
        # With confirmed-swing-only BOS, this should remain NONE.
        closes = [110.0, 109.0, 108.0, 108.8, 107.0, 108.0, 109.0, 107.5, 106.0, 107.5, 105.0]
        highs = [110.5, 109.5, 108.5, 109.0, 107.5, 108.5, 109.5, 108.0, 106.5, 108.0, 105.5]
        lows = [109.5, 108.5, 107.5, 108.2, 106.0, 107.5, 108.5, 107.0, 105.5, 107.0, 104.5]
        dataframe = pd.DataFrame(_to_rows(closes, highs, lows))

        decision = evaluate_icc_v1(dataframe, pullback_lookback=6, swing_window=2)
        self.assertEqual(decision.signal, "NONE")


if __name__ == "__main__":
    unittest.main()
