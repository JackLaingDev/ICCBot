"""Unit tests for config/settings parsing and validation."""

from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch

from src.config.settings import load_settings


class SettingsTests(unittest.TestCase):
    """Validate settings loading from environment and .env files."""

    def test_load_settings_uses_safe_defaults(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            settings = load_settings(env_file="__missing__.env")

        self.assertEqual(settings.environment, "development")
        self.assertEqual(settings.trading.symbol, "EURUSD")
        self.assertEqual(settings.trading.timeframe, "M15")
        self.assertEqual(settings.trading.risk_per_trade, 0.5)
        self.assertEqual(settings.strategy.strategy_name, "icc")
        self.assertTrue(settings.logging.log_to_file)
        self.assertIsNone(settings.mt5.login)

    def test_load_settings_from_dotenv_file(self) -> None:
        dotenv_content = "\n".join(
            [
                "ENVIRONMENT=demo",
                "SYMBOL=EURUSD",
                "TIMEFRAME=M15",
                "RISK_PER_TRADE=1.0",
                "LOG_TO_FILE=false",
                "MT5_LOGIN=123456",
            ]
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            env_path = f"{tmp_dir}/test.env"
            with open(env_path, "w", encoding="utf-8") as env_file:
                env_file.write(dotenv_content)

            with patch.dict("os.environ", {}, clear=True):
                settings = load_settings(env_file=env_path)

        self.assertEqual(settings.environment, "demo")
        self.assertEqual(settings.trading.risk_per_trade, 1.0)
        self.assertFalse(settings.logging.log_to_file)
        self.assertEqual(settings.mt5.login, 123456)

    def test_environment_variables_override_defaults(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "ENVIRONMENT": "live",
                "SYMBOL": "EURUSD",
                "TIMEFRAME": "M15",
                "RISK_PER_TRADE": "0.75",
                "MAX_OPEN_TRADES": "2",
                "LOG_TO_FILE": "true",
            },
            clear=True,
        ):
            settings = load_settings(env_file="__missing__.env")

        self.assertEqual(settings.environment, "live")
        self.assertEqual(settings.trading.risk_per_trade, 0.75)
        self.assertEqual(settings.trading.max_open_trades, 2)
        self.assertTrue(settings.logging.log_to_file)

    def test_invalid_environment_raises(self) -> None:
        with patch.dict("os.environ", {"ENVIRONMENT": "prod"}, clear=True):
            with self.assertRaises(ValueError):
                load_settings(env_file="__missing__.env")

    def test_invalid_numeric_raises(self) -> None:
        with patch.dict("os.environ", {"RISK_PER_TRADE": "abc"}, clear=True):
            with self.assertRaises(ValueError):
                load_settings(env_file="__missing__.env")

    def test_invalid_percentage_range_raises(self) -> None:
        with patch.dict("os.environ", {"RISK_PER_TRADE": "150"}, clear=True):
            with self.assertRaises(ValueError):
                load_settings(env_file="__missing__.env")

    def test_invalid_boolean_raises(self) -> None:
        with patch.dict("os.environ", {"LOG_TO_FILE": "sometimes"}, clear=True):
            with self.assertRaises(ValueError):
                load_settings(env_file="__missing__.env")

    def test_invalid_strategy_name_raises(self) -> None:
        with patch.dict("os.environ", {"STRATEGY_NAME": "foo"}, clear=True):
            with self.assertRaises(ValueError):
                load_settings(env_file="__missing__.env")

    def test_velocity_strategy_alias_is_normalized(self) -> None:
        with patch.dict("os.environ", {"STRATEGY_NAME": "momentum-velocity"}, clear=True):
            settings = load_settings(env_file="__missing__.env")
        self.assertEqual(settings.strategy.strategy_name, "velocity")


if __name__ == "__main__":
    unittest.main()
