# Project Plan

## Objective

Build a Python + MT5 trading system for a rule-based ICC strategy.

Primary goal:
- create a working trading system
- validate it through backtesting and demo
- run it live with small capital
- build a 6–9 month real-money track record
- only then consider copy-trading monetization

This is a **phased engineering project**, not a quick trading experiment.

---

## Guiding Principles

- one market first (EURUSD)
- one timeframe (M15)
- rule-based ICC logic only
- no machine learning in v1
- risk-first approach
- simple before complex
- test everything important
- no live trading until validated
- avoid constant strategy changes once live

---

## High-Level Phases

---

## Phase 1 — Repo & Environment Setup

### Goal
Create a clean, structured, production-ready foundation.

### Tasks
- create project structure (src layout)
- create README.md
- create ARCHITECTURE.md
- create RULES.md
- create PROJECT_PLAN.md
- create .gitignore
- create pyproject.toml
- set up virtual environment
- install base dependencies (pandas, numpy, MetaTrader5, etc.)
- create placeholder modules
- create basic logging utility
- create config/settings module

### Deliverable
Clean repo with working Python environment and structure.

---

## Phase 2 — Core Architecture Alignment

### Goal
Ensure code structure matches system design.

### Tasks
- validate folder responsibilities
- ensure separation of:
  - data
  - strategy
  - risk
  - execution
  - backtest
- add docstrings and TODOs
- ensure modules are importable and clean

### Deliverable
Clear, maintainable architecture aligned with ARCHITECTURE.md.

---

## Phase 3 — MT5 Connectivity & Data Layer

### Goal
Access and normalize market data.

### Tasks
- connect to MT5 terminal
- verify account connection
- fetch EURUSD M15 data
- convert to pandas DataFrame
- standardize columns (time, open, high, low, close, volume)
- handle time conversion
- basic error handling

### Deliverable
Reusable data loader that returns clean market data.

---

## Phase 4 — Strategy Definition (ICC)

### Goal
Turn ICC into explicit rules.

### Tasks
- define Indication (trend)
- define Correction (pullback)
- define Continuation (entry trigger)
- implement signal output:
  - BUY
  - SELL
  - NONE
- define stop loss logic
- define take profit logic

### Deliverable
Clear, testable ICC strategy module.

---

## Phase 5 — Backtesting Engine

### Goal
Simulate trades and evaluate performance.

### Tasks
- loop through historical data
- apply strategy logic
- simulate entries/exits
- apply stop loss and take profit
- include basic cost assumptions
- track metrics:
  - profit
  - win rate
  - drawdown
  - trade count

### Deliverable
Working backtester with basic performance output.

---

## Phase 6 — Risk Management

### Goal
Ensure survivability.

### Tasks
- implement position sizing (risk %)
- enforce max open trades
- enforce spread threshold
- enforce max daily loss
- block unsafe trades

### Deliverable
Reusable risk manager integrated with strategy output.

---

## Phase 7 — Strategy Validation

### Goal
Avoid false positives.

### Tasks
- ensure sufficient trade count (300+)
- test across multiple time periods
- review drawdown behavior
- check sensitivity to parameters
- reject unstable strategies

### Deliverable
Validated strategy candidate for forward testing.

---

## Phase 8 — Live Signal Runner

### Goal
Run strategy in real-time without trading.

### Tasks
- detect new candles
- fetch latest data
- apply strategy
- output signal (BUY/SELL/NONE)
- log results

### Deliverable
Real-time signal system (no execution yet).

---

## Phase 9 — Demo Execution

### Goal
Test real-time trading behavior safely.

### Tasks
- connect signals to MT5 demo trading
- place demo trades
- set stop loss and take profit
- log trades and errors
- validate execution timing

### Deliverable
Working demo trading system.

---

## Phase 10 — Live Micro Trading

### Goal
Begin real-money validation.

### Tasks
- switch to live account
- use minimal position size
- enforce strict risk controls
- monitor closely
- log all activity

### Deliverable
Live trading bot operating with small risk.

---

## Phase 11 — Monitoring & Operations

### Goal
Ensure reliability over time.

### Tasks
- implement structured logging
- track bot health
- track open positions
- implement alerts (errors, disconnects)
- implement kill switch

### Deliverable
Operationally stable bot.

---

## Phase 12 — Stabilization Period (3–6 months)

### Goal
Prove consistency.

### Tasks
- run bot without frequent changes
- perform monthly reviews
- track:
  - equity curve
  - drawdown
  - consistency
- only fix bugs, not strategy logic

### Deliverable
Stable performance history.

---

## Phase 13 — Track Record (6–9 months)

### Goal
Build credibility.

### Tasks
- continue running unchanged strategy
- document performance
- store:
  - trade logs
  - monthly stats
  - configuration snapshots

### Deliverable
6–9 month real-money track record.

---

## Phase 14 — Copy Trading Evaluation

### Goal
Assess monetization readiness.

### Tasks
- evaluate:
  - drawdown
  - consistency
  - trade behavior
- ensure results are realistic and repeatable
- prepare performance summaries
- prepare clear explanation of strategy

### Deliverable
Decision on whether system is suitable for copy trading.

---

## Phase Dependencies

- Phase 1 must be complete before any coding
- Phase 3 required before strategy/backtest
- Phase 5 required before any live signals
- Phase 8 required before demo trading
- Phase 9 required before live trading
- Phase 12 required before monetization

---

## Out of Scope (for now)

- machine learning
- multi-market live trading
- high-frequency strategies
- complex UI/dashboard
- automated scaling
- aggressive optimization

---

## Success Criteria

A successful outcome is:

- a clean, maintainable codebase
- a working ICC strategy implementation
- a functioning backtester
- a stable live bot
- controlled drawdown
- consistent behavior over months
- a credible track record

---

## Summary

This project will be built in stages:

1. Build foundation  
2. Build data access  
3. Build strategy  
4. Test strategy  
5. Validate in real-time  
6. Run safely with real money  
7. Build track record  

Focus is on:
- discipline
- clarity
- risk control
- long-term consistency

Not speed or complexity.