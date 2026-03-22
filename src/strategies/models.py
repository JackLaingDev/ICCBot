"""Strategy input/output contracts for rule-based signal decisions.

These models are intentionally minimal and side-effect free.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SignalDirection = Literal["BUY", "SELL", "NONE"]


@dataclass(frozen=True)
class StrategyDecision:
    """Decision payload returned by strategy evaluation."""

    signal: SignalDirection
    stop_loss: float | None = None
    take_profit: float | None = None
    reason: str | None = None
