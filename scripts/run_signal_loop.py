"""Local automation loop for live ICC signal checks (no order execution).

This helper runs the existing one-shot signal script on a 15-minute cadence and
applies a strict UTC session gate:
- weekdays only (Mon-Fri)
- 07:00 <= time < 12:00 UTC
"""

from __future__ import annotations

import importlib.util
import sys
import time
from pathlib import Path

import pandas as pd


INTERVAL_MINUTES = 15
SESSION_START_HOUR_UTC = 7
SESSION_END_HOUR_UTC = 12
RUN_SIGNAL_PATH = Path(__file__).resolve().parent / "run_signal.py"


def main() -> int:
    """Run signal checks every 15 minutes during the UTC session window."""
    _log("Starting local signal loop (15m cadence, weekdays, 07-12 UTC).")
    run_signal_module = _load_run_signal_module()
    try:
        while True:
            now = pd.Timestamp.now(tz="UTC")
            next_run = _next_run_time(now)
            sleep_seconds = max(0.0, (next_run - now).total_seconds())
            _log(f"Sleeping until next cycle at {next_run.isoformat()} ({sleep_seconds:.0f}s).")
            time.sleep(sleep_seconds)

            cycle_time = pd.Timestamp.now(tz="UTC")
            _log(f"Cycle tick at {cycle_time.isoformat()}.")
            if not _is_weekday_session_time(cycle_time):
                _log("Outside weekday/session window, skipping signal check.")
                continue

            _log("Inside weekday/session window, running signal check once.")
            exit_code = run_signal_module.main()
            _log(f"Signal check finished (exit_code={exit_code}).")
    except KeyboardInterrupt:
        _log("Stop requested (Ctrl+C). Exiting cleanly.")
        return 0


def _is_weekday_session_time(timestamp_utc: pd.Timestamp) -> bool:
    """Return True only for Mon-Fri and 07:00-12:00 UTC."""
    timestamp_utc = _to_utc_timestamp(timestamp_utc)
    is_weekday = timestamp_utc.weekday() < 5
    in_session = SESSION_START_HOUR_UTC <= int(timestamp_utc.hour) < SESSION_END_HOUR_UTC
    return is_weekday and in_session


def _next_run_time(now_utc: pd.Timestamp) -> pd.Timestamp:
    """Return next UTC 15-minute boundary strictly after now."""
    now_utc = _to_utc_timestamp(now_utc)
    floored = now_utc.floor(f"{INTERVAL_MINUTES}min")
    next_run = floored + pd.Timedelta(minutes=INTERVAL_MINUTES)
    return _to_utc_timestamp(next_run)


def _load_run_signal_module():
    spec = importlib.util.spec_from_file_location("run_signal_runtime_module", RUN_SIGNAL_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load run_signal.py")
    module = importlib.util.module_from_spec(spec)
    # Register module before exec to support dataclass/type introspection.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _to_utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        return timestamp.tz_localize("UTC")
    return timestamp.tz_convert("UTC")


def _log(message: str) -> None:
    print(f"[run_signal_loop] {message}", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
