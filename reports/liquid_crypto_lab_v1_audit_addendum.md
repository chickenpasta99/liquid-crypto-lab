# Liquid Crypto Lab — v1 Audit Addendum

**Audit date:** 2026-09-18 (Europe/London)  
**Scope:** Paper-only targeted audit of frozen v1. No strategy-search expansion.  
**Frozen preserved:** `reports/liquid_crypto_lab_v1.md`, `reports/tournament_v1.csv` (untouched).  
**Corrected engine:** versioned `liquid_crypto_lab/backtest/engine_v1b.py` + `reports/liquid_crypto_lab_v1b_delta.md` / `tournament_v1b_delta.csv`.  
**Solana:** `/workspace/strategy-lab` ingest left running; not modified.

> Paper research only. Not financial advice.

---

## Confirmed bugs

1. **Optimistic same-bar close fill (execution timing)**  
   OKX 1H candles are **open-labeled** (`ts` = candle open). `close[t]` is only known at `t+1h`.  
   v1 sets weights from `close[t]` at index `t`, then `port = (w.shift(1) * close.pct_change()).sum()` so the first earned return is `close[t]→close[t+1]`. That is economically a **fill at `close[t]`** — the same print used for the signal — not a next-bar open fill.  
   The v1 report text (“Execution at next bar”) is **misleading**; the code is same-close fill.  
   **Classification:** bug relative to stated mechanics / realistic fill; also a material optimism bias.

2. **Inter-rebalance constant-weight returns without restoration costs**  
   Weights are `ffill`’d constant between daily rebalances; `dw = w.diff()` ⇒ turnover ≈ 0 on non-rebalance hours.  
   The return formula `sum(w_const * r)` is the **continuously rebalanced** (constant-weight) return. True daily buy-and-hold lets weights **drift**; restoring targets hourly would require turnover the engine never charges.  
   **Classification:** bug relative to “rebalance every 24h” claim (engine behaves like free hourly restoration for PnL, daily-only for fees).  
   See worked example below.

---

## Limitations (not bugs)

1. **Survivorship / point-in-time universe** — top ADV at Sep 2026 fetch; not historically reconstituted (already in v1).  
2. **Missing bars** — panel builds a union grid; `close`/`open` are forward-filled across gaps; `quote_volume` missing → 0 then ADV floor `MIN_ADV_USD`. Eligibility at tournament: drop symbols with `< MIN_HISTORY_BARS` (2160) non-null closes. No per-rebalance ADV re-filter (ADV gate only at fetch).  
3. **£500 path** — **approximate equity rescaling** of unit net returns × £500. No FX (GBP≈USD assumption), no venue min-order, no lot/qty rounding. Label: *approximate equity rescaling*, not a broker backtest.  
4. **Cost model** — stylized taker+half-spread+slippage; not venue-specific UK retail fills.  
5. **Family H funding** — incomplete public history (already EXPLORATORY).  
6. **Drop-best-asset robustness** — drops highest **universe average** OOS asset return (LIT-USDT), **not** the largest strategy contributor (see concentration). Misleading as “strategy concentration” stress.

---

## Reporting corrections

| Item | v1 text / artifact | Correction |
|------|-------------------|------------|
| Cost placeholders | ``{cfg.TAKER_FEE_BPS}`` etc. left unresolved in §D mechanics | **TAKER_FEE_BPS=15**, **HALF_SPREAD_BPS=5**, **SLIPPAGE_BASE_BPS=2**, **SLIPPAGE_K=8**, **MIN_ADV_USD=2_000_000**, stress ∈ {1.0, 1.5, 2.0} |
| Execution wording | “Execution at next bar” | Actually **optimistic same-bar close fill** (see bugs) |
| I_mom 2× costs | Notes Sharpe>0 at 2×; ret=−10.3% | **Doubled-cost return gate FAILED** (positive stressed Sharpe ≠ passed return gate). Original **TESTING** screening label **preserved** |
| £500 sim | Implied precision | Relabel **approximate equity rescaling** |
| Universe | Implied general | Selected at **2026-09-18 OKX fetch**, not historically reconstructed |
| LIT drop-best | Implied strategy keystone | LIT OOS **strategy** contrib ≈ **−0.045** (sum w·r); universe avg ret leader ≠ strategy contributor |

---

## Timing worked examples

Convention: candle `ts` = OKX open time; `close[t]` known at `t+1h` (= open time of next candle).

| candle_ts (open label) | signal_available_ts | assumed_fill_ts (v1) | fill_price (v1=close[t]) | realistic fill (v1b) | next_mark close[t+1] | symbol | v1 first ret close→close | v1b first ret open→close | gap close[t]→open[t+1] |
|------------------------|---------------------|----------------------|--------------------------|----------------------|----------------------|--------|--------------------------|--------------------------|------------------------|
| 2024-09-24 06:00 UTC | 2024-09-24 07:00 | close 06:00 (optimistic) | 168.17 | open 07:00 = 168.23 | 169.17 | AAVE-USDT | +0.595% | +0.559% | +0.036% |
| 2024-12-08 06:00 UTC | 2024-12-08 07:00 | close 06:00 | 1.1684 | open 07:00 = 1.1689 | 1.1742 | CRV-USDT | +0.496% | +0.453% | +0.043% |
| 2025-07-10 06:00 UTC | 2025-07-10 07:00 | close 06:00 | 513.6 | open 07:00 = 513.6 | 515.4 | BCH-USDT | +0.350% | +0.350% | 0 |
| 2026-04-17 06:00 UTC | 2026-04-17 07:00 | close 06:00 | 0.13046 | open 07:00 = 0.13051 | 0.13166 | ARB-USDT | +0.920% | +0.881% | +0.038% |
| 2026-09-12 06:00 UTC | 2026-09-12 07:00 | close 06:00 | 0.20883 | open 07:00 = 0.20924 | 0.19059 | LSK-USDT | −8.73% | −8.91% | +0.20% |
| 2026-09-13 02:00 UTC | 2026-09-13 03:00 | (already holding) | 0.49520 | open 03:00 = 0.49520 | 1.06634 | LSK-USDT | **+115.3%** | **+115.3%** | 0 |

**Verdict:** same-close fill confirmed. Document as **optimistic same-bar close fill** (limitation/bug). Mid-holding spikes (e.g. LSK +115% on 2026-09-13 03:00) are *not* created by the fill bug — they are earned under either engine if already long — but **rebalance-bar gaps** and **free drift restoration** still bias v1.

CSV: `reports/audit_work/timing_examples_corrected.csv`.

---

## Accounting worked example

Setting: I_mom targets, bankroll **$500**, rebalance signal `2024-12-07 06:00` → v1b fill `07:00`, same names next day (shows pure drift/restoration).

**One-way cost bps** ≈ `(15 + 5 + 2 + 8·√(notional/ADV))` ≈ **22 bps** at £100 notionals vs multi-million ADV.

| Time (UTC) | Event | Quantities (ex) | Cash | Portfolio E | Fees (return) | Notes |
|------------|-------|-----------------|------|-------------|---------------|-------|
| 2024-12-07 07:00 | Fill open → target 20%×5 | CRV 82.98, HBAR 288.9, ONE 2253, XLM 205.6, XRP 41.12 | ~0 | 501.10 after cost from 500 | **−0.2207%** | Enter from cash |
| 2024-12-07 07:00 close | Mark | same qty | 0 | 490.90 | 0 | open→close −2.04% |
| 2024-12-07 08:00 | Buy & hold | same qty | 0 | 494.98 | 0 | drift_w e.g. CRV 0.203, HBAR 0.195, … |
| 2024-12-07 09:00 | Buy & hold | same qty | 0 | 493.86 | 0 | weights keep drifting |
| … | … | … | … | … | **v1 charges $0** | v1 keeps w≡0.2 and uses const-w returns |
| 2024-12-08 07:00 open | Revalue + restore to 0.2 | trade \|Δw\|sum≈**0.027** | 0 | 496.38 → 496.41 | **−0.006%** | Drift restoration only (names unchanged) |
| 2024-12-08 07:00 close | Mark new qty | updated qty | 0 | 497.47 | 0 | |

**v1 on non-rebalance hours:** `dw≈0`, **no fee**, but PnL uses **constant 0.2 weights** (as if restored for free).  
**Confirmed:** this is a **bug** vs stated daily rebalance (not a harmless notation). Magnitude per quiet day is small (~few bps of turnover); it compounds over OOS and interacts with timing optimism.

Sep 11→12 name change (LIT→LSK) shows the same pattern plus real name turnover both engines charge — but only v1b holds drifting qty overnight.

---

## I_mom downside + 2× cost gate

| Metric | v1 (frozen) | Gate |
|--------|-------------|------|
| OOS net return | **+13.57%** | screening pass |
| OOS max DD | **−50.42%** | large |
| OOS Sharpe | **0.449** | screening pass |
| 2× cost Sharpe | **0.247** | >0 |
| 2× cost return | **−10.31%** | **FAILED return gate** |

- Original verdict label **TESTING** is **preserved** (screening-only).  
- Explicit annotation: **doubled-cost return gate FAILED** — positive stressed Sharpe must not be read as “passed 2× costs.”  
- See `reports/audit_work/i_mom_testing_annotation.md`.

---

## September attribution

**Verified (v1 path):**

| Slice | Net compound return |
|-------|---------------------|
| OOS through Aug 2026 | **−21.28%** |
| Sep 2026 (partial through ~18th, 422 hours) | **+44.26%** |
| Full OOS | **+13.57%** |
| Check: `(1−0.2128)×(1+0.4426)−1` | **+13.57%** ✓ |

**Asset contributors (Sep, sum of hourly w·r, additive ≈ +45.2% vs port sum):**

| Asset | Sep contrib (Σ w·r) |
|-------|---------------------|
| **LSK-USDT** | **+0.282** |
| ZEC-USDT | +0.088 |
| RAY-USDT | +0.050 |
| MINA-USDT | +0.023 |
| ARB-USDT | +0.016 |

**Headline:** September gains are dominated by **LSK-USDT** inside the 2026-09-12 rebalance sleeve `[CHIP, LSK, MINA, RAY, ZEC]`, especially:

- 2026-09-13 01:00: LSK hour ret **+45.7%** (portfolio net ~+9.4%)  
- 2026-09-13 03:00: LSK hour ret **+115.3%** (H=1.413, C=1.06634 on OKX spot) → portfolio net **~+23.5%** in one hour  

**OKX spot-check:** LSK candles on disk match continuous OHLC with huge range on 03:00 bar (not a panel join artifact). ZEC same window was calm (~flat). This is a real printed spike / illiquidity event in the research feed — **not** evidence of a robust edge.

Best single **rebalance period** OOS: `2026-09-12 06:00` → **+36.3%** net; removing it alone drops OOS total ret from +13.6% to **−16.7%**.

---

## Improved concentration

Best **1% of hours** (~150): compound enormous; zeroing them → OOS ret **−98.9%** (v1 report). That hour metric is weak for interpretation.

**Best rebalance periods (OOS net compound of those periods):**

| Top-k periods | Compound of those periods | OOS ret if removed |
|---------------|---------------------------|--------------------|
| 1 | +36.3% | −16.7% |
| 5 | +114.2% | −47.0% |
| 10 | +249.9% | −67.5% |

Top period holdings: CHIP, LSK, MINA, RAY, ZEC (Sep 12).

**Strongest assets actually held by I_mom (OOS Σ w·r), not universe averages:**

| Rank | Symbol | Strategy contrib Σw·r | Hours held (w>0) |
|------|--------|----------------------|------------------|
| 1 | PENGU-USDT | +0.388 | 2328 |
| 2 | LSK-USDT | +0.260 | (mostly Sep) |
| 3 | ZEC-USDT | +0.216 | 1711 |
| 4 | PUMP-USDT | +0.133 | 936 |
| 5 | CRV-USDT | +0.118 | 1207 |

**LIT-USDT:** highest universe OOS *average asset return* in leave-one-out label, but strategy contrib **−0.045**. Do not confuse the two.

---

## What would change in a v1b rerun (exact engine diffs)

Code: `liquid_crypto_lab/backtest/engine_v1b.py` (`ENGINE_VERSION=v1b`).

| Component | v1 `engine.py` | v1b |
|-----------|----------------|------|
| Signal | `weights_fn(close, reb_times)` at `t` using `close[t]` | **unchanged** |
| Weight application | `w = w_reb.reindex(idx).ffill()`; earn via `w.shift(1)*pct_change` | `w_exec = w_signal.shift(1)`; fill at **`open[t+1]`** (else close-fill with 0 same-bar earn = explicit lag) |
| First bar after signal | `close[t]→close[t+1]` | `open[t+1]→close[t+1]` |
| Between rebalances | Constant target w; `dw≈0` | **Quantity hold**; weights drift; no hourly restore |
| Costs | On `\|Δw\|` of ffilled targets (≈ rebalance bars only) | On `\|Δw\|` vs **drifted** weights at exec bars only |
| Outputs | frozen `tournament_v1.*` | `tournament_v1b_delta.csv` + delta report |

**I_mom under v1b (stress 1×):** OOS Sharpe **0.390** (was 0.449), OOS ret **+1.55%** (was +13.6%), max DD **−51.4%**.  
**2× costs v1b:** Sharpe 0.206, ret **−20.6%** (return gate still failed).  
Sep 2026 under v1b: **+33.2%** (still large; LSK path remains). Thru Aug: **−23.8%**.

Benchmarks (BTC buy&hold, cash) unchanged; equal-weight nearly unchanged (tiny drift effect).

---

## Reproducibility notes (config + data)

```
TAKER_FEE_BPS = 15.0
HALF_SPREAD_BPS = 5.0
SLIPPAGE_BASE_BPS = 2.0
SLIPPAGE_K = 8.0
MIN_ADV_USD = 2_000_000
COST_STRESS_MULTS = (1.0, 1.5, 2.0)
REBALANCE_HOURS = 24
N_LONG = 5
MAX_WEIGHT = 0.25
MIN_HISTORY_BARS = 2160
BANKROLL_GBP = 500  # research path = approximate equity rescaling; GBP≈USD
```

**Missing-data / eligibility:**  
- Fetch: OKX top ADV USDT spot excl. stables; skip symbols with `<2160` rows.  
- Panel: per-symbol parquet → wide pivot; `close`/`open` ffill; `quote_volume` fillna(0); ADV floor for costs.  
- Each rebalance: strategy scores use history through `t`; NaN scores excluded from top-N; no live ADV re-screen.  
- **Universe stamped at Sep 2026 fetch** (survivorship bias).

---

## Files touched by this audit

| Path | Role |
|------|------|
| `reports/liquid_crypto_lab_v1.md` | **Frozen** (not modified) |
| `reports/tournament_v1.csv` | **Frozen** |
| `reports/liquid_crypto_lab_v1_audit_addendum.md` | This document |
| `reports/liquid_crypto_lab_v1b_delta.md` | v1 vs v1b metrics |
| `reports/tournament_v1b_delta.csv` | Per-strategy delta table |
| `reports/audit_work/*` | Timing/attribution working CSVs |
| `liquid_crypto_lab/backtest/engine_v1b.py` | Versioned corrected engine |
| `reports/audit_work/i_mom_testing_annotation.md` | TESTING + 2× return gate note |

*End of audit addendum.*
