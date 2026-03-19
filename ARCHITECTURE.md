# Architecture

## Project goal

Build a Python + MT5 trading system for a rule-based ICC strategy.

Initial objective:
- trade one market only: EURUSD
- use one timeframe only: M15
- use Python for research, backtesting, orchestration, and reporting
- use MT5 for broker connectivity and live execution
- first prove the system on backtest and demo
- then run tiny-size live trading
- then aim for a 6–9 month real-money track record
- only later consider copy-trading monetization

This project is being built in stages.
The first priority is correctness, safety, and clarity.
The second priority is profitability.
The third priority is scalability and monetization.

---

## Core principles

- keep the first version simple
- one market first
- one strategy first
- no machine learning in v1
- no overengineering
- no live execution until backtest and demo validation are complete
- separate research, strategy, risk, execution, and monitoring concerns
- make all important logic testable
- prefer explicit rule-based logic over vague trading concepts
- risk management is more important than entry quality
- do not constantly change live strategy logic

---

## System overview

The trading system is split into six core systems:

1. Research system
2. Strategy system
3. Risk system
4. Execution system
5. Monitoring system
6. Reporting/commercial-readiness system

These are separate concerns and should remain separate in code.

---

## 1. Research system

### Purpose
The research system is responsible for:
- pulling and preparing historical market data
- exploring and testing strategy ideas
- running backtests
- generating performance reports
- comparing strategy versions

### Responsibilities
- data ingestion from MT5
- historical data normalization
- feature calculation
- backtest execution
- performance metrics
- experiment output

### Non-responsibilities
- placing live trades
- direct broker order execution
- account management

### Notes
This is where strategy ideas are tested before anything goes near live trading.

---

## 2. Strategy system

### Purpose
The strategy system converts ICC logic into explicit, machine-readable trade rules.

### Responsibilities
- define indication rules
- define correction rules
- define continuation rules
- generate BUY, SELL, or NONE decisions
- provide proposed stop loss and take profit levels

### Non-responsibilities
- position sizing
- broker connectivity
- order placement
- logging infrastructure

### Notes
The strategy layer should only answer:
- is there a setup?
- what direction?
- where is the invalidation?
- where is the target?

It should not decide lot size or talk to MT5.

---

## 3. Risk system

### Purpose
The risk system protects the account from bad sizing, bad conditions, and excessive losses.

### Responsibilities
- calculate position size from account equity and risk %
- enforce max number of open trades
- enforce spread thresholds
- enforce max daily loss
- enforce no-trade conditions
- reject unsafe trade requests

### Non-responsibilities
- deciding market direction
- calculating indicators
- sending orders

### Notes
Risk controls must be applied before any order is sent.

---

## 4. Execution system

### Purpose
The execution system handles communication with MT5 and live trading actions.

### Responsibilities
- initialize MT5 connection
- fetch account and symbol information
- place orders
- modify or close orders if needed
- check for open positions
- confirm execution results
- return structured execution responses

### Non-responsibilities
- deciding whether a strategy is good
- performing backtests
- defining risk policy

### Notes
Execution should be thin, explicit, and easy to audit.
It should never contain hidden strategy logic.

---

## 5. Monitoring system

### Purpose
The monitoring system ensures the bot is healthy and observable while running.

### Responsibilities
- structured logging
- bot health checks
- error tracking
- signal logs
- trade logs
- runtime alerts
- kill switch triggers

### Non-responsibilities
- strategy generation
- backtest calculations
- business/marketing tasks

### Notes
A trading bot is not complete without monitoring.
A profitable strategy can still fail operationally if the system is not observable.

---

## 6. Reporting and commercial-readiness system

### Purpose
This system prepares the project for long-term evaluation and eventual copy-trading readiness.

### Responsibilities
- track record summaries
- equity curve generation
- drawdown summaries
- monthly performance reporting
- trade journal export
- strategy version tracking
- run metadata and configuration snapshots

### Non-responsibilities
- direct marketing
- legal/compliance advice
- broker execution

### Notes
This is not for monetization at the start.
It exists so performance is documented honestly and consistently over time.

---

## Initial live strategy scope

Version 1 scope:

- market: EURUSD
- timeframe: M15
- style: rule-based ICC
- deployment: one market only
- execution: MT5
- research/backtesting: Python
- trade frequency: low to moderate
- risk per trade: small and fixed
- live goal: tiny-size validation first

This scope is intentionally narrow.

---

## ICC strategy interpretation

In this project, ICC is implemented in simplified rule-based form:

- Indication:
  defines market direction or bias
  example: price above or below 200 EMA

- Correction:
  defines pullback or retracement into value
  example: pullback into EMA zone or retracement range

- Continuation:
  defines the trigger for entry in the trend direction
  example: break of recent structure or prior candle high/low

This interpretation must remain explicit and testable.
No vague “smart money” logic should exist in code without precise rule definitions.

---

## Data flow

High-level flow:

1. pull recent bars from MT5
2. normalize bars into a standard dataframe shape
3. calculate strategy context
4. evaluate ICC rules
5. generate trade idea or no-trade result
6. pass candidate trade to risk system
7. if approved, pass trade request to execution system
8. log decision and result
9. update reporting/monitoring outputs

---

## Runtime modes

The system should support multiple modes over time:

### 1. Research mode
Used for:
- historical testing
- strategy experiments
- metrics generation

### 2. Signal mode
Used for:
- real-time signal generation
- no live orders yet
- operational validation

### 3. Demo mode
Used for:
- paper/demo execution through MT5
- validating order flow and timing

### 4. Live mode
Used for:
- real-money execution with strict safeguards

Each mode should behave clearly and predictably.

---

## Folder responsibilities

Suggested mapping:

- `src/app/`
  entry points and orchestration

- `src/config/`
  settings, constants, environment loading

- `src/data/`
  MT5 client, market data retrieval, normalization

- `src/strategies/`
  ICC strategy logic only

- `src/backtest/`
  historical simulation and metrics

- `src/execution/`
  live trade execution and broker interaction

- `src/risk/`
  sizing and trade safety rules

- `src/utils/`
  shared helpers such as logging and common utilities

- `tests/`
  unit and integration tests

- `scripts/`
  task runners for manual workflows

---

## Design constraints

- keep modules small and focused
- avoid mixing strategy code with broker code
- avoid hidden global state
- use structured logging
- prefer explicit data contracts between modules
- code should be readable by a solo developer
- every important module should be testable in isolation
- minimize dependency count
- no ML in v1
- no multi-market live trading in v1

---

## Versioning and change control

Once the bot reaches demo or live validation:
- strategy logic should be versioned
- config changes should be tracked
- results should be tied to strategy version and config snapshot

This is required so that track record remains honest and interpretable.

---

## Safety-first rules

Before any live execution:
- backtest must run successfully
- strategy output must be understandable
- risk system must validate trade requests
- demo mode must pass basic operational checks
- logging must be active
- a manual kill switch must exist

Live trading is never the first stage.

---

## Future expansion

Possible future additions after v1:
- improved ICC rules
- more robust validation tooling
- better dashboards
- multi-market research
- ML as a setup filter only
- copy-trading readiness workflows

These are explicitly out of scope for the first implementation.

---

## Summary

This architecture exists to keep the project:
- simple
- testable
- safe
- maintainable
- honest

The initial goal is not to build a complex trading platform.
The initial goal is to build one clean, rule-based EURUSD M15 ICC trading system that can be researched, tested, run safely, and evaluated over time.