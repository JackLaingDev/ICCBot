"""Focused unit tests for MT5Client behavior without live MT5."""

import unittest
from unittest.mock import patch

from src.data.mt5_client import MT5Client, MT5ClientError


class _DummyMT5:
    TIMEFRAME_M1 = 1
    TIMEFRAME_M5 = 5
    TIMEFRAME_M15 = 15
    TIMEFRAME_M30 = 30
    TIMEFRAME_H1 = 60
    TIMEFRAME_H4 = 240
    TIMEFRAME_D1 = 1440

    def initialize(self, **_: object) -> bool:
        return True

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> list[dict[str, object]]:
        return [{"symbol": symbol, "timeframe": timeframe, "start": start_pos, "count": count}]


class MT5ClientTests(unittest.TestCase):
    """Validate minimal MT5Client guardrails and input handling."""

    def test_get_rates_raises_when_disconnected(self) -> None:
        client = MT5Client()
        with self.assertRaises(MT5ClientError):
            client.get_rates(symbol="EURUSD", timeframe="M15", count=10)

    def test_get_rates_invalid_timeframe_raises(self) -> None:
        client = MT5Client()
        client._connected = True  # keep test focused on timeframe handling

        with patch.object(MT5Client, "_import_mt5", return_value=_DummyMT5()):
            with self.assertRaises(ValueError):
                client.get_rates(symbol="EURUSD", timeframe="M2", count=10)

    def test_initialize_raises_for_partial_credentials(self) -> None:
        client = MT5Client(login=123456, password="", server="")

        with patch.object(MT5Client, "_import_mt5", return_value=_DummyMT5()):
            with self.assertRaises(MT5ClientError):
                client.initialize()


if __name__ == "__main__":
    unittest.main()
