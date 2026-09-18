# Backtest engine versions

## v1 (frozen)
- File: `engine.py`
- Metrics: `reports/tournament_v1.csv`, `reports/liquid_crypto_lab_v1.md`
- Fill: optimistic same-bar close (`w.shift(1) * close.pct_change()` with signal at close[t])
- Weights: ffill constant between rebalances; costs on target Δw only

## v1b (audit correction, 2026-09-18)
- File: `engine_v1b.py`
- Metrics: `reports/tournament_v1b_delta.csv`, `reports/liquid_crypto_lab_v1b_delta.md`
- Fill: open[t+1] after signal close[t]; fallback close-fill with explicit lag
- Weights: quantity hold / drift between rebalances
- Does not overwrite v1
