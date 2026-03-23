# Trading Bot (Python + MT5)

## Overview

This project is a rule-based trading system built with:

- Python (research, backtesting, orchestration)
- MetaTrader 5 (data access and live execution)

The goal is to build a **simple, robust, and testable trading system** that:

1. Trades a single market (EURUSD)
2. Uses a rule-based ICC-style strategy
3. Is validated through backtesting and demo trading
4. Runs live with small risk
5. Builds a 6–9 month real-money track record
6. May later be used for copy trading

---

## Current Scope (v1)

- Market: EURUSD  
- Timeframe: M15  
- Strategy: Rule-based ICC (Indication → Correction → Continuation)  
- Execution: MetaTrader 5  
- Focus: Simplicity, correctness, and risk control  

Out of scope for now:
- Machine learning  
- Multi-market live trading  
- Complex UI/dashboard  
- Over-optimization  

---

## Project Goals

- Build a clean, maintainable trading system
- Separate strategy, risk, execution, and data concerns
- Ensure all logic is testable and understandable
- Avoid overfitting and unnecessary complexity
- Prioritize risk management over raw returns
- Create a system that can run reliably for months

---

## System Architecture

The system is divided into six core components:

1. **Research system**  
   Historical data, backtesting, experiments

2. **Strategy system**  
   ICC logic that generates trade signals

3. **Risk system**  
   Position sizing, trade limits, safety checks

4. **Execution system**  
   MT5 integration and order handling

5. **Monitoring system**  
   Logging, health checks, alerts

6. **Reporting system**  
   Performance tracking and trade history

See `ARCHITECTURE.md` for full details.

---

## Project Structure

```text
trading-bot/
  src/
    app/          # entry points and orchestration
    config/       # settings and configuration
    data/         # MT5 client and data loading
    strategies/   # ICC strategy logic
    backtest/     # backtesting engine
    execution/    # trade execution (MT5)
    risk/         # risk management
    utils/        # logging and helpers
  tests/          # unit tests
  scripts/        # manual scripts
```

---

## Velocity Strategy (Research Mode)

The repo supports a momentum-velocity strategy alongside ICC for backtests.

Velocity definition:

- `velocity_t = ln(close_t / close_{t-k}) / ATR_t`
- ATR uses Wilder-style smoothing
- Optional EMA smoothing is applied when `VELOCITY_SMOOTHING_SPAN > 1`
- Entries require threshold persistence on consecutive closed bars
- Exits are momentum-fade based (no fixed TP), with an ATR disaster stop

Example `.env` block:

```env
STRATEGY_NAME=velocity
VELOCITY_LOOKBACK_K=4
VELOCITY_ATR_PERIOD=14
VELOCITY_SMOOTHING_SPAN=1
VELOCITY_ENTRY_THRESHOLD=0.75
VELOCITY_ENTRY_PERSISTENCE_BARS=2
VELOCITY_EXIT_DRAWDOWN_FRACTION=0.35
VELOCITY_ATR_STOP_MULTIPLIER=2.0
VELOCITY_COOLDOWN_BARS=0
VELOCITY_USE_EMA_TREND_FILTER=false
VELOCITY_TREND_EMA_PERIOD=200
```

Run examples:

```powershell
# Use strategy from STRATEGY_NAME
python scripts/run_backtest.py

# Explicit strategy override
python scripts/run_backtest.py --strategy velocity
```

---

## Local Setup (Windows PowerShell)

```powershell
# from repo root
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .
```

If activation is blocked:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Run a basic import check:

```powershell
python -c "import src, src.app.main, src.config.settings; print('import-ok')"
python -m unittest tests/test_smoke_imports.py -v
```