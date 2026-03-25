"""Unit tests for the local signal automation loop helpers."""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

import pandas as pd


def _load_run_signal_loop_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "run_signal_loop.py"
    spec = importlib.util.spec_from_file_location("run_signal_loop_module_for_tests", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_signal_loop.py for tests")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class RunSignalLoopTests(unittest.TestCase):
    """Validate schedule helper behavior for UTC session automation."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.module = _load_run_signal_loop_module()

    def test_is_weekday_session_time(self) -> None:
        self.assertTrue(self.module._is_weekday_session_time(pd.Timestamp("2026-03-23 07:00:00+00:00")))
        self.assertTrue(self.module._is_weekday_session_time(pd.Timestamp("2026-03-23 11:59:00+00:00")))
        self.assertFalse(self.module._is_weekday_session_time(pd.Timestamp("2026-03-23 12:00:00+00:00")))
        self.assertFalse(self.module._is_weekday_session_time(pd.Timestamp("2026-03-22 08:00:00+00:00")))

    def test_next_run_time_uses_next_15m_boundary(self) -> None:
        now = pd.Timestamp("2026-03-23 07:01:05+00:00")
        expected = pd.Timestamp("2026-03-23 07:15:00+00:00")
        self.assertEqual(self.module._next_run_time(now), expected)

        now_on_boundary = pd.Timestamp("2026-03-23 07:15:00+00:00")
        expected_next = pd.Timestamp("2026-03-23 07:30:00+00:00")
        self.assertEqual(self.module._next_run_time(now_on_boundary), expected_next)


if __name__ == "__main__":
    unittest.main()
