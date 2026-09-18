# Liquid Crypto Lab — v1b engine delta (vs frozen v1)

**Generated:** 2026-09-18 (Europe/London)  
**Purpose:** Compare the same pre-registered variants under corrected timing + drift accounting.  
**Does not replace v1.** Frozen: `tournament_v1.csv`, `liquid_crypto_lab_v1.md`.

## Exact engine diffs

Source: `liquid_crypto_lab/backtest/engine_v1b.py` vs `engine.py`.

1. **Fill timing:** signal `close[t]` → fill `open[t+1]` (fallback: close-fill with explicit lag). v1 filled at `close[t]` (optimistic same-bar).
2. **Drift:** quantity hold between daily rebalances. v1 used constant ffill weights (implicit free hourly restore for PnL).
3. **Costs:** charged on `|Δw|` vs drifted weights at execution bars only (still daily cadence for trades).

No new strategies; no param search; same splits/costs/universe.

## Headline — `I_mom_btc_filter`

| Metric | v1 | v1b | Δ |
|--------|----|-----|---|
| OOS Sharpe | 0.449 | 0.390 | −0.059 |
| OOS total ret | **+13.57%** | **+1.55%** | **−12.02 pp** |
| OOS max DD | −50.42% | −51.45% | −1.0 pp |
| OOS ret @ 1.5× costs | +0.93% | −10.20% | |
| OOS Sharpe @ 2× costs | 0.247 | 0.206 | |
| OOS ret @ 2× costs | **−10.31%** | **−20.60%** | still **FAILED** return gate |
| Sep 2026 (partial) | +44.26% | +33.18% | |
| OOS thru Aug 2026 | −21.28% | −23.75% | |

**Screening label:** remains **TESTING** on frozen v1. Under v1b, OOS ret is barely positive at 1× costs — still not PROMISING/CANDIDATE; 2× return gate fails harder. Fragility (LSK Sep spike, top-period dependence) unchanged in nature.

## Benchmarks & families (OOS, stress 1.0×)

| name | family | v1 sharpe | v1 ret | v1b sharpe | v1b ret | Δ sharpe | Δ ret |
|------|--------|-----------|--------|------------|---------|----------|-------|
| BTC_buyhold | BASE | −0.021 | −0.166 | −0.021 | −0.166 | 0.000 | 0.000 |
| equal_weight | BASE | −0.287 | −0.578 | −0.287 | −0.580 | +0.000 | −0.002 |
| cash | BASE | NaN | 0.000 | NaN | 0.000 | — | — |
| random_top5 | BASE | −2.355 | −0.965 | −2.365 | −0.966 | −0.009 | −0.000 |
| A_mom_30d | A | −0.471 | −0.766 | −0.443 | −0.795 | +0.027 | −0.029 |
| A_mom_7d | A | −0.337 | −0.729 | −0.293 | −0.752 | +0.044 | −0.024 |
| B_ma_20_100 | B | +0.064 | −0.368 | +0.008 | −0.471 | −0.055 | −0.103 |
| C_mr_24h | C | −1.694 | −0.958 | −1.728 | −0.961 | −0.034 | −0.002 |
| C_mr_72h | C | −1.417 | −0.936 | −1.480 | −0.942 | −0.063 | −0.006 |
| D_vol_break | D | −2.118 | −0.924 | −2.126 | −0.924 | −0.008 | −0.000 |
| E_btc_alt | E | −0.519 | −0.686 | −0.522 | −0.690 | −0.003 | −0.004 |
| F_rev_7d | F | −0.893 | −0.871 | −0.961 | −0.884 | −0.068 | −0.012 |
| I_mom_btc_filter | I | +0.449 | +0.136 | +0.390 | +0.015 | −0.059 | −0.120 |
| J_eth_btc_mr | J | −0.351 | −0.162 | −0.384 | −0.168 | −0.033 | −0.005 |
| J_sol_eth_mr | J | −0.047 | −0.080 | −0.032 | −0.072 | +0.015 | +0.008 |
| J_eth_btc_mom | J | −0.059 | −0.072 | −0.031 | −0.063 | +0.028 | +0.009 |
| G_vol_surge | G | −0.415 | −0.648 | −0.261 | −0.632 | +0.154 | +0.016 |
| H_funding_spot | H | +0.370 | +0.084 | +0.357 | +0.080 | −0.013 | −0.004 |

Full CSV: `reports/tournament_v1b_delta.csv`.

## Interpretation

- Timing + drift correction **removes most of I_mom’s OOS edge** (+13.6% → +1.5%) while leaving the **path dependence** (Sep LSK) intact at smaller amplitude.
- Majority FAILED strategies remain FAILED.
- H remains EXPLORATORY (incomplete funding data) under both engines.
- **Do not promote I_mom.** Forward paper tape with frozen rules only if continued; prefer v1b fills for any forward sim.

## How to reproduce

```bash
cd /workspace/liquid-crypto-lab
.venv/bin/python -c "from liquid_crypto_lab.backtest.engine_v1b import run_backtest_v1b, wide_ohlc; ..."
```

See audit addendum for methodology.

*End of v1b delta.*
