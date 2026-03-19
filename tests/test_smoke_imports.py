"""Smoke tests that verify core modules import cleanly.

These tests must not execute runtime loops or external integrations.
"""

import importlib
import unittest


MODULES = [
    "src.app.main",
    "src.config.settings",
    "src.data.mt5_client",
    "src.data.market_data",
    "src.strategies.icc_strategy",
    "src.strategies.models",
    "src.backtest.engine",
    "src.backtest.metrics",
    "src.risk.manager",
    "src.risk.sizing",
    "src.execution.mt5_executor",
    "src.execution.models",
    "src.utils.logging",
    "src.utils.time",
]


class SmokeImportTests(unittest.TestCase):
    """Ensure foundational modules are import-safe."""

    def test_core_modules_import_without_side_effects(self) -> None:
        for module_name in MODULES:
            with self.subTest(module=module_name):
                imported = importlib.import_module(module_name)
                self.assertIsNotNone(imported)


if __name__ == "__main__":
    unittest.main()
