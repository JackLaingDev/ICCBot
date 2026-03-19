# Rules

## Purpose

This file defines strict rules for how this project is built.

These rules exist to:
- prevent overengineering
- avoid bad trading practices
- maintain clean architecture
- ensure the system is testable and reliable
- keep development focused and disciplined

These rules apply to all code generated in this project.

---

## Core Development Rules

- keep everything simple
- do one task at a time
- do not build multiple features at once
- always explain the plan before implementing code
- do not introduce unnecessary abstractions
- avoid premature optimization
- prioritize readability over cleverness
- keep modules small and focused
- use clear naming
- add docstrings to all modules and key functions
- ensure code is easy to understand for a solo developer

---

## Architecture Rules

- strictly follow ARCHITECTURE.md
- keep separation between:
  - data
  - strategy
  - risk
  - execution
  - backtest
- never mix strategy logic with execution logic
- never place broker code inside strategy modules
- keep execution layer thin and explicit
- avoid hidden dependencies between modules
- avoid global state where possible

---

## Trading Scope Rules

- only trade one market initially: EURUSD
- only use one timeframe initially: M15
- do not add multiple markets in v1
- do not add multiple strategies in v1
- do not introduce complexity beyond the initial scope

---

## Strategy Rules

- strategy must be rule-based (ICC style)
- no vague concepts (e.g. "smart money") without explicit logic
- all rules must be clearly defined and testable
- strategy module should only:
  - generate signals (BUY / SELL / NONE)
  - define stop loss and take profit
- strategy must NOT:
  - calculate position size
  - interact with MT5
  - manage trades

---

## Risk Management Rules

- risk management is mandatory
- all trades must pass risk checks before execution
- enforce:
  - fixed % risk per trade
  - max number of open trades
  - spread threshold
  - max daily loss
- do not allow:
  - martingale
  - grid trading
  - doubling down after losses

---

## Backtesting Rules

- backtester must be simple and transparent
- simulate trades step-by-step (no black box)
- include:
  - stop loss
  - take profit
  - basic cost assumptions
- output:
  - profit
  - win rate
  - drawdown
  - trade count
- do not overfit
- do not optimize endlessly

---

## Validation Rules

- require sufficient trade count (target 300+ trades)
- test across multiple time periods
- strategy must be consistent, not just profitable in one period
- reject unstable or overfit strategies

---

## Execution Rules

- execution must go through MT5 only
- execution layer must:
  - place trades
  - set stop loss and take profit
  - return clear results
- do not embed strategy logic in execution
- prevent duplicate trades
- ensure only allowed number of open positions

---

## Live Trading Rules

- no live trading without:
  - working backtest
  - demo validation
- start with very small position sizes
- prioritize stability over profit
- do not change strategy logic frequently once live
- only fix bugs during live phase

---

## Monitoring Rules

- all important actions must be logged:
  - signals
  - trades
  - errors
- logging must be structured and readable
- system must support:
  - basic health checks
  - error visibility
- include ability to stop trading (kill switch)

---

## Testing Rules

- write tests for:
  - strategy logic
  - risk calculations
  - data loading
- keep core modules testable
- avoid tightly coupled code that cannot be tested

---

## Environment & Dependency Rules

- keep dependencies minimal
- avoid heavy frameworks unless necessary
- use standard Python libraries where possible
- do not introduce new dependencies without justification

---

## AI / Cursor Usage Rules

- always ask for a plan before generating code
- generate one module at a time
- review output before proceeding
- refactor after each step if needed
- do not allow the agent to:
  - create overly complex designs
  - introduce unnecessary patterns
  - generate large amounts of unused code

---

## Versioning Rules

- track major changes to:
  - strategy logic
  - risk parameters
- do not change live strategy frequently
- maintain consistency during track record phase

---

## Out of Scope (v1)

- machine learning
- multi-market live trading
- high-frequency strategies
- complex UI or dashboards
- automated scaling systems
- advanced optimization frameworks

---

## Decision Priority

When unsure, prioritize in this order:

1. safety (risk control)
2. simplicity
3. clarity
4. correctness
5. performance
6. scalability

---

## Summary

This project must remain:

- simple
- structured
- testable
- disciplined
- risk-aware

The goal is not to build the most advanced trading bot.

The goal is to build a clean, reliable system that can:
- run safely
- be understood easily
- be improved over time
- support a real track record