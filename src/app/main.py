"""Application bootstrap placeholder.

Responsible for high-level composition only; must not implement trading loops here yet.
"""

from src.config.settings import load_settings


def main() -> int:
    """Load settings, print minimal startup summary, and exit cleanly."""

    settings = load_settings()
    print(
        "Startup config loaded: "
        f"environment={settings.environment}, "
        f"symbol={settings.trading.symbol}, "
        f"timeframe={settings.trading.timeframe}, "
        f"log_level={settings.logging.log_level}, "
        f"poll_interval={settings.runtime.poll_interval}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
