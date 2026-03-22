"""Unit tests for market-data normalization."""

import unittest

import pandas as pd

from src.data.market_data import STANDARD_COLUMNS, bars_to_dataframe


class MarketDataTests(unittest.TestCase):
    """Validate raw MT5 bars to dataframe conversion."""

    def test_bars_to_dataframe_standardizes_shape(self) -> None:
        raw_bars = [
            {
                "time": 1700000600,
                "open": 1.1,
                "high": 1.2,
                "low": 1.0,
                "close": 1.15,
                "tick_volume": 100,
            },
            {
                "time": 1700000000,
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
                "tick_volume": 90,
            },
        ]

        dataframe = bars_to_dataframe(raw_bars)

        self.assertEqual(list(dataframe.columns), STANDARD_COLUMNS)
        self.assertEqual(len(dataframe), 2)
        self.assertIsInstance(dataframe["time"].dtype, pd.DatetimeTZDtype)
        self.assertLessEqual(dataframe.iloc[0]["time"], dataframe.iloc[1]["time"])

    def test_bars_to_dataframe_returns_empty_with_standard_columns(self) -> None:
        dataframe = bars_to_dataframe([])
        self.assertEqual(list(dataframe.columns), STANDARD_COLUMNS)
        self.assertTrue(dataframe.empty)

    def test_bars_to_dataframe_requires_volume_column(self) -> None:
        raw_bars = [
            {
                "time": 1700000000,
                "open": 1.0,
                "high": 1.1,
                "low": 0.9,
                "close": 1.05,
            }
        ]
        with self.assertRaises(ValueError):
            bars_to_dataframe(raw_bars)


if __name__ == "__main__":
    unittest.main()
