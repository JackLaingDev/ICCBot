"""Thin MT5 connectivity and raw data access wrapper.

This module is limited to connection/account/raw-bar access only.
It must not contain strategy, risk, or execution decision logic.
"""

from __future__ import annotations

from typing import Any


class MT5ClientError(RuntimeError):
    """Raised when MT5 connectivity or raw data access fails."""


class MT5Client:
    """Minimal MetaTrader5 wrapper for connectivity and raw bar retrieval."""

    def __init__(
        self,
        *,
        login: int | None = None,
        password: str = "",
        server: str = "",
        path: str = "",
    ) -> None:
        self._login = login
        self._password = password
        self._server = server
        self._path = path
        self._connected = False

    @staticmethod
    def _import_mt5() -> Any:
        try:
            import MetaTrader5 as mt5
        except Exception as exc:  # pragma: no cover - environment specific
            raise MT5ClientError(
                "MetaTrader5 package is not available. Install dependencies first."
            ) from exc
        return mt5

    @staticmethod
    def _resolve_timeframe(mt5: Any, timeframe: str | int) -> int:
        if isinstance(timeframe, int):
            return timeframe

        tf_map = {
            "M1": mt5.TIMEFRAME_M1,
            "M5": mt5.TIMEFRAME_M5,
            "M15": mt5.TIMEFRAME_M15,
            "M30": mt5.TIMEFRAME_M30,
            "H1": mt5.TIMEFRAME_H1,
            "H4": mt5.TIMEFRAME_H4,
            "D1": mt5.TIMEFRAME_D1,
        }
        key = timeframe.upper().strip()
        if key not in tf_map:
            raise ValueError(f"Unsupported timeframe: {timeframe}")
        return tf_map[key]

    def initialize(self) -> None:
        """Initialize MT5 terminal connection with optional credentials."""

        mt5 = self._import_mt5()
        kwargs: dict[str, Any] = {}
        using_explicit_credentials = self._has_explicit_credentials()

        if self._path:
            kwargs["path"] = self._path

        if using_explicit_credentials:
            self._validate_credentials()
            kwargs["login"] = self._login
            kwargs["password"] = self._password
            kwargs["server"] = self._server

        ok = mt5.initialize(**kwargs)
        if not ok:
            error_code, error_message = mt5.last_error()
            self._raise_initialize_error(
                error_code=error_code,
                error_message=error_message,
                using_explicit_credentials=using_explicit_credentials,
            )
        self._connected = True

    def _has_explicit_credentials(self) -> bool:
        """Return True when any explicit login credential field is set."""

        return self._login is not None or bool(self._password) or bool(self._server)

    def _validate_credentials(self) -> None:
        """Ensure credential-based initialization has all required fields."""

        missing: list[str] = []
        if self._login is None:
            missing.append("login")
        if not self._password:
            missing.append("password")
        if not self._server:
            missing.append("server")

        if missing:
            raise MT5ClientError(
                "Explicit MT5 credential mode requires login, password, and server. "
                f"Missing: {', '.join(missing)}."
            )

    def _raise_initialize_error(
        self, error_code: int, error_message: str, *, using_explicit_credentials: bool
    ) -> None:
        """Raise a clearer initialization error for common MT5 failure modes."""

        message = str(error_message or "").lower()
        mode = (
            "credential-based initialization"
            if using_explicit_credentials
            else "existing logged-in terminal session"
        )

        if "process create failed" in message or "ipc initialize failed" in message:
            path_hint = (
                f" path='{self._path}'" if self._path else " path is empty (using default terminal)"
            )
            raise MT5ClientError(
                "MT5 terminal not found or not launchable."
                f" mode={mode}.{path_hint}. last_error=({error_code}, {error_message!r})"
            )

        if error_code == -6 or "authorization failed" in message:
            raise MT5ClientError(
                "MT5 authorization/login failed. Check MT5_LOGIN, MT5_PASSWORD, and MT5_SERVER."
                f" mode={mode}. last_error=({error_code}, {error_message!r})"
            )

        raise MT5ClientError(
            f"MT5 initialize failed in {mode}. last_error=({error_code}, {error_message!r})"
        )

    def shutdown(self) -> None:
        """Shutdown MT5 connection cleanly."""

        mt5 = self._import_mt5()
        try:
            mt5.shutdown()
        finally:
            self._connected = False

    def is_connected(self) -> bool:
        """Return local connection state."""

        return self._connected

    def get_account_info(self) -> dict[str, Any] | None:
        """Return account info as a dictionary if available."""

        if not self._connected:
            raise MT5ClientError("MT5 is not connected. Call initialize() first.")

        mt5 = self._import_mt5()
        account_info = mt5.account_info()
        if account_info is None:
            return None

        if hasattr(account_info, "_asdict"):
            return dict(account_info._asdict())
        return dict(account_info)

    def get_rates(self, symbol: str, timeframe: str | int, count: int) -> Any:
        """Fetch raw OHLCV bars from MT5 using copy_rates_from_pos."""

        if not self._connected:
            raise MT5ClientError("MT5 is not connected. Call initialize() first.")
        if count <= 0:
            raise ValueError("count must be > 0")

        mt5 = self._import_mt5()
        timeframe_value = self._resolve_timeframe(mt5, timeframe)
        rates = mt5.copy_rates_from_pos(symbol, timeframe_value, 0, count)
        if rates is None:
            raise MT5ClientError(
                f"Failed to fetch rates for {symbol} {timeframe}: {mt5.last_error()}"
            )
        return rates
