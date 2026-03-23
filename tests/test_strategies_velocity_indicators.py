"""Unit tests for momentum-velocity indicator helpers."""

import unittest

import pandas as pd

from src.strategies.velocity_indicators import calculate_velocity


def _bars(count: int = 20) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    base = pd.Timestamp("2024-01-01 00:00:00+00:00")
    for index in range(count):
        close = 1.1000 + (index * 0.0005)
        rows.append(
            {
                "time": base + pd.Timedelta(minutes=15 * index),
                "open": close - 0.0002,
                "high": close + 0.0004,
                "low": close - 0.0004,
                "close": close,
                "volume": 1000 + index,
            }
        )
    return pd.DataFrame(rows)


class VelocityIndicatorTests(unittest.TestCase):
    """Validate ATR and velocity feature construction."""

    def test_calculate_velocity_returns_expected_shape_and_columns(self) -> None:
        dataframe = _bars(30)
        features = calculate_velocity(
            dataframe,
            lookback_k=3,
            atr_period=5,
            smoothing_span=1,
        )

        self.assertEqual(len(features), len(dataframe))
        self.assertEqual(list(features.columns), ["atr", "raw_velocity", "velocity"])
        self.assertTrue(features["atr"].iloc[:4].isna().all())
        self.assertTrue(features["atr"].iloc[10:].notna().all())
        self.assertTrue((features["velocity"].iloc[12:] > 0).all())

    def test_constant_price_series_yields_zero_or_nan_velocity(self) -> None:
        dataframe = _bars(30)
        dataframe["open"] = 1.1000
        dataframe["high"] = 1.1000
        dataframe["low"] = 1.1000
        dataframe["close"] = 1.1000
        features = calculate_velocity(
            dataframe,
            lookback_k=3,
            atr_period=5,
            smoothing_span=1,
        )
        valid = features["velocity"].dropna()
        self.assertTrue(((valid == 0.0) | (valid.isna())).all())

    def test_short_dataset_returns_all_nan_velocity_without_errors(self) -> None:
        dataframe = _bars(3)
        features = calculate_velocity(
            dataframe,
            lookback_k=5,
            atr_period=14,
            smoothing_span=1,
        )
        self.assertTrue(features["velocity"].isna().all())


if __name__ == "__main__":
    unittest.main()
