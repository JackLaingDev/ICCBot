"""Unit test for minimal app startup integration."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from src.app.main import main


class AppMainTests(unittest.TestCase):
    """Verify app startup loads settings and exits cleanly."""

    def test_main_loads_settings_and_returns_success(self) -> None:
        fake_settings = SimpleNamespace(
            environment="development",
            trading=SimpleNamespace(symbol="EURUSD", timeframe="M15"),
            logging=SimpleNamespace(log_level="INFO"),
            runtime=SimpleNamespace(poll_interval=60),
            mt5=SimpleNamespace(password="super-secret"),
            optional=SimpleNamespace(telegram_token="token-123"),
        )

        with patch("src.app.main.load_settings", return_value=fake_settings) as mock_load:
            with patch("builtins.print") as mock_print:
                exit_code = main()

        mock_load.assert_called_once_with()
        mock_print.assert_called_once()
        summary = mock_print.call_args.args[0]
        self.assertIn("environment=development", summary)
        self.assertIn("symbol=EURUSD", summary)
        self.assertNotIn("super-secret", summary)
        self.assertNotIn("token-123", summary)
        self.assertEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
