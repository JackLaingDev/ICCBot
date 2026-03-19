"""Settings loader and validation for project configuration.

This module provides typed access to environment settings and basic value validation.
It must remain free of MT5 connectivity, strategy logic, and backtesting behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class MT5Settings:
    """MT5 credential and terminal path settings."""

    login: int | None
    password: str
    server: str
    path: str


@dataclass(frozen=True)
class TradingSettings:
    """Core trading scope and risk control settings."""

    symbol: str
    timeframe: str
    risk_per_trade: float
    max_spread: float
    max_open_trades: int
    max_daily_loss: float


@dataclass(frozen=True)
class StrategySettings:
    """Strategy parameter settings (data only, no strategy logic)."""

    ema_period: int
    take_profit_rr: float
    stop_loss_type: str
    atr_multiplier: float


@dataclass(frozen=True)
class DataSettings:
    """Market data retrieval settings."""

    lookback_bars: int


@dataclass(frozen=True)
class LoggingSettings:
    """Logging behavior settings."""

    log_level: str
    log_to_file: bool


@dataclass(frozen=True)
class RuntimeSettings:
    """Runtime cadence settings."""

    poll_interval: int


@dataclass(frozen=True)
class OptionalSettings:
    """Optional integrations and storage settings."""

    telegram_token: str
    telegram_chat_id: str
    database_path: str


@dataclass(frozen=True)
class AppSettings:
    """Top-level application settings container."""

    environment: str
    mt5: MT5Settings
    trading: TradingSettings
    strategy: StrategySettings
    data: DataSettings
    logging: LoggingSettings
    runtime: RuntimeSettings
    optional: OptionalSettings


def load_settings(env_file: str | Path = ".env") -> AppSettings:
    """Load settings from environment variables with optional .env support."""

    load_dotenv(dotenv_path=env_file, override=False)

    environment = _get_str("ENVIRONMENT", "development").lower()

    mt5 = MT5Settings(
        login=_get_optional_int("MT5_LOGIN"),
        password=_get_str("MT5_PASSWORD", ""),
        server=_get_str("MT5_SERVER", ""),
        path=_get_str("MT5_PATH", ""),
    )

    trading = TradingSettings(
        symbol=_get_str("SYMBOL", "EURUSD").upper(),
        timeframe=_get_str("TIMEFRAME", "M15").upper(),
        risk_per_trade=_get_float("RISK_PER_TRADE", 0.5),
        max_spread=_get_float("MAX_SPREAD", 20.0),
        max_open_trades=_get_int("MAX_OPEN_TRADES", 1),
        max_daily_loss=_get_float("MAX_DAILY_LOSS", 2.0),
    )

    strategy = StrategySettings(
        ema_period=_get_int("EMA_PERIOD", 200),
        take_profit_rr=_get_float("TAKE_PROFIT_RR", 1.5),
        stop_loss_type=_get_str("STOP_LOSS_TYPE", "atr").lower(),
        atr_multiplier=_get_float("ATR_MULTIPLIER", 1.5),
    )

    data = DataSettings(lookback_bars=_get_int("LOOKBACK_BARS", 5000))

    logging = LoggingSettings(
        log_level=_get_str("LOG_LEVEL", "INFO").upper(),
        log_to_file=_get_bool("LOG_TO_FILE", True),
    )

    runtime = RuntimeSettings(poll_interval=_get_int("POLL_INTERVAL", 60))

    optional = OptionalSettings(
        telegram_token=_get_str("TELEGRAM_TOKEN", ""),
        telegram_chat_id=_get_str("TELEGRAM_CHAT_ID", ""),
        database_path=_get_str("DATABASE_PATH", "./data/trading.db"),
    )

    settings = AppSettings(
        environment=environment,
        mt5=mt5,
        trading=trading,
        strategy=strategy,
        data=data,
        logging=logging,
        runtime=runtime,
        optional=optional,
    )
    _validate(settings)
    return settings


def _get_str(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer.") from exc


def _get_optional_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer if provided.") from exc


def _get_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number.") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default

    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean (true/false).")


def _validate(settings: AppSettings) -> None:
    errors: list[str] = []

    if settings.environment not in {"development", "demo", "live"}:
        errors.append("ENVIRONMENT must be one of: development, demo, live.")

    if settings.trading.symbol != "EURUSD":
        errors.append("SYMBOL must be EURUSD in v1 scope.")

    if settings.trading.timeframe != "M15":
        errors.append("TIMEFRAME must be M15 in v1 scope.")

    if settings.strategy.stop_loss_type not in {"atr", "structure"}:
        errors.append("STOP_LOSS_TYPE must be one of: atr, structure.")

    if settings.logging.log_level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        errors.append("LOG_LEVEL must be one of: DEBUG, INFO, WARNING, ERROR, CRITICAL.")

    if settings.mt5.login is not None and settings.mt5.login <= 0:
        errors.append("MT5_LOGIN must be a positive integer if provided.")

    if settings.trading.risk_per_trade <= 0:
        errors.append("RISK_PER_TRADE must be > 0.")
    if settings.trading.risk_per_trade > 100:
        errors.append("RISK_PER_TRADE must be <= 100.")

    if settings.trading.max_spread < 0:
        errors.append("MAX_SPREAD must be >= 0.")

    if settings.trading.max_open_trades <= 0:
        errors.append("MAX_OPEN_TRADES must be > 0.")

    if settings.trading.max_daily_loss < 0:
        errors.append("MAX_DAILY_LOSS must be >= 0.")
    if settings.trading.max_daily_loss > 100:
        errors.append("MAX_DAILY_LOSS must be <= 100.")

    if settings.strategy.ema_period <= 0:
        errors.append("EMA_PERIOD must be > 0.")

    if settings.strategy.take_profit_rr <= 0:
        errors.append("TAKE_PROFIT_RR must be > 0.")

    if settings.strategy.atr_multiplier <= 0:
        errors.append("ATR_MULTIPLIER must be > 0.")

    if settings.data.lookback_bars <= 0:
        errors.append("LOOKBACK_BARS must be > 0.")

    if settings.runtime.poll_interval <= 0:
        errors.append("POLL_INTERVAL must be > 0.")

    if errors:
        raise ValueError("Invalid settings:\n- " + "\n- ".join(errors))
