# Repair v2 — Liquid Crypto Lab

**Generated:** 2026-09-18 ~15:50 BST (Europe/London)

## PASS / FAIL

| # | Item | Result | Evidence |
|---|------|--------|----------|
| 1 | Accounting tests import/call `engine_v1b` | **PASS** | `tests/test_accounting.py` + `tests/test_repair_v2_liquid.py` |
| 2 | Reject NEW fills on missing/ffilled bars | **PASS (opt-in)** | `run_backtest_v1b(..., price_valid=..., require_valid_exec=True)` |
| 3 | Bar volume = min eligibility, not liquidity proof | **PASS (documented)** | Mask requires `quote_volume > 0` but notes it is not proof |
| 4 | I_mom labelled EXPLORATORY on corrected metrics | **PASS** | Verdict test + frozen v1b Sharpe 0.390 |
| 5 | Finite £500 / $500 bankroll | **PASS** | `config.BANKROLL_USD == 500` |
| 6 | Frozen v1 reports / CSVs not overwritten | **PASS** | Only new status + repair md |

## Code changes

- `liquid_crypto_lab/backtest/engine_v1b.py`
  - `wide_ohlc_with_valid_mask()` — observed-close mask before ffill
  - `require_valid_exec` / `price_valid` — block **weight increases** on invalid bars
- `tests/test_repair_v2_liquid.py` (new)
- `tests/test_accounting.py` — docstring notes REPAIR_V2 engine_v1b usage
- `reports/simulator_validation_status.md` (new)
- `reports/repair_v2_liquid.md` (this file)

## Remaining blockers

1. Default tournament / v1b delta path does **not** yet pass `require_valid_exec=True` (would change metrics; no re-score this turn).
2. ADV `$2m` floor remains in cost model when volume missing — still optimistic if mask off.
3. Next-open fill remains an assumption (latency/slippage sensitivity not expanded here).
