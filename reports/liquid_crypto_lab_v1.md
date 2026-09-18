# Liquid Crypto Lab — First Release Report (v1)

**Generated:** 2026-09-18T14:03:23.309258+00:00 UTC
**Strategy freeze:** `2026-09-18T13:50:20.771955+00:00`
**GitHub:** https://github.com/chickenpasta99/liquid-crypto-lab

> Paper research only. No live trading, no keys, no orders. Not financial advice.
> Independent of Solana/memecoin `strategy-lab` — results not merged; that ingest was left running.

## Experiment integrity

- All pre-registered variants frozen at tournament time; **no param changes after seeing OOS**.
- Selection rule: implement families A–J (few variants each) + BASE benchmarks; score on frozen splits with costs; prefer killing.
- `reports/variant_log.csv` lists every variant (incl. post-hoc multi-seed random benchmarks).
- Original `verdict` column preserved; `fail_reason` + `explanation` added for interpretability.
- Sharpe ladder = **screening only**. Survivors need fresh forward paper trading with frozen rules. Passing ≠ established edge.

## A. Data source review (free only)

| Source | HTTP | OK? | Notes |
|--------|------|-----|-------|
| binance_klines | 451 | no | `{   "code": 0,   "msg": "Service unavailable from a restricted location according to 'b. E` |
| okx_candles | 200 | yes | `{"code":"0","data":[["1789736400000","78050","78086.6","78034.1","78037.8","1.44274702","1` |
| bybit_kline | 403 | no | `{     error:The Amazon CloudFront distribution is configured to block access from your cou` |
| kraken_ohlc | 200 | yes | `{"error":[],"result":{"XXBTZUSD":[[1787144400,"64827.0","65150.0","64729.3","64940.7","649` |
| coinbase_candles | 200 | yes | `[[1789736400,77963.95,78015.59,77977.65,77976.68,3.99807027],[1789732800,77913.68,78124.09` |
| coingecko_markets | 429 | no | `{"status":{"error_code":429,"error_message":"You've exceeded the Rate Limit. Please visit ` |
| defillama_protocols | 200 | yes | `[{"id":"2269","name":"Binance CEX","address":null,"symbol":"BNB","url":"https://www.binanc` |
| okx_funding | 200 | yes | `{"code":"0","data":[{"formulaType":"withRate","fundingRate":"0.000059534112371","fundingTi` |

**Primary prices:** OKX public spot `history-candles` (1H).
**Universe:** OKX spot tickers by 24h quote volume.
**Funding (H):** OKX `funding-rate-history` BTC-USDT-SWAP — **shallow** (see §E/H).
**Blocked / limited:** Binance 451 geo; Bybit 403 CF geo; CoinGecko 429 at probe.
**Secondary reachable:** Kraken 200, Coinbase 200, DefiLlama 200 — not used for v1 price panel (OKX depth preferred).
UK retail note: research data is OKX; live UK retail more likely Coinbase/Kraken — costs stressed 1.5×/2×.

## B. Universe (50–100 liquid assets)

- **N = 62** USDT spot pairs (excl. stables / equity-wrapper junk where identified).
- Eligibility: ADV 24h quote vol ≥ $2,000,000 at fetch; ≥ 2160 hourly bars saved.
- **Survivorship:** point-in-time top ADV at fetch (2026-09-18). No historical reconstitution → **survivorship bias** (delisted losers under-represented). Documented, not cured.

<details><summary>Universe symbols</summary>

AAVE-USDT, ADA-USDT, APT-USDT, AR-USDT, ARB-USDT, AVAX-USDT, BABY-USDT, BCH-USDT, BNB-USDT, BTC-USDT, CC-USDT, CHIP-USDT, CRV-USDT, DASH-USDT, DOGE-USDT, DOT-USDT, ENA-USDT, ETC-USDT, ETH-USDT, ETHFI-USDT, FET-USDT, FIL-USDT, HBAR-USDT, HYPE-USDT, ICP-USDT, INJ-USDT, JUP-USDT, LINK-USDT, LIT-USDT, LSK-USDT, LTC-USDT, MINA-USDT, MON-USDT, NEAR-USDT, OKB-USDT, ONDO-USDT, ONE-USDT, OP-USDT, ORDI-USDT, PENGU-USDT, PEPE-USDT, PI-USDT, POL-USDT, PUMP-USDT, RAY-USDT, SHIB-USDT, SOL-USDT, STRK-USDT, SUI-USDT, SUSHI-USDT, TIA-USDT, TRUMP-USDT, TRX-USDT, UNI-USDT, VIRTUAL-USDT, WLD-USDT, XLM-USDT, XPL-USDT, XRP-USDT, ZAMA-USDT, ZEC-USDT, ZRO-USDT

</details>

## C. Dataset stats

| Field | Value |
|-------|-------|
| Assets | 62 |
| Panel rows (long) | 1298829 |
| Wide shape | 26000 hours × 62 assets |
| Range | 2023-10-01 06:00:00+00:00 → 2026-09-18 13:00:00+00:00 |
| Granularity | 1 hour |
| BTC gap hours | 0 (continuous grid vs BTC prints) |
| Source | OKX public history-candles |
| Storage | `data/processed/*.parquet` + meta JSON |
| Funding rows | 279 (2026-06-17 16:00:00+00:00 → 2026-09-18 08:00:00+00:00) |

## D. Train / Validation / OOS (+ prospective)

| Split | Dates (UTC) | Role |
|-------|-------------|------|
| Train | ≤ 2024-06-30 | Context only (few pre-registered variants; no grid search) |
| Validation | 2024-07-01 → 2024-12-31 | Kill gate (e.g. val Sharpe &lt; -0.5) |
| OOS | ≥ 2025-01-01 | Primary evidence |
| Prospective | after freeze `2026-09-18T13:50:20.771955+00:00` | Future paper tape |

Rationale: OKX hourly history from ~2023-07; train through 2024-H1, val 2024-H2, OOS 2025+
Splits never silently mixed; metrics reported per split.

## Backtest mechanics (verified)

1. **Signals on completed candles only:** at rebalance hour `t`, features use `close[t]` and history through `t`.
2. **Execution at next bar:** portfolio return uses `weights.shift(1) * asset_returns`, so weights set at `t` first earn the `t→t+1` bar return (next tradable hourly close-to-close).
3. **Costs:** turnover-based — on `|Δw|` each bar, one-way bps = `(taker {cfg.TAKER_FEE_BPS} + half-spread {cfg.HALF_SPREAD_BPS} + slip) × stress`, with `slip = {cfg.SLIPPAGE_BASE_BPS} + {cfg.SLIPPAGE_K}×√(notional/ADV)`.
4. **Hourly Sharpe annualisation:** `√(24×365) = √8760`; `ann_ret = (1+μ)^8760 - 1`. Documented formula (crypto trades 24/7).
5. **Long/cash only** (spot UK retail realism). No leverage. Shorts not used in v1 fills.
6. **Rebalance:** every 24 hours; top-N equal weight; max weight 25%.

## E. Tournament v1 (families A–J)

### Cost model (frozen)
- Taker 15.0 bps + half-spread 5.0 bps + slippage fn; stress (1.0, 1.5, 2.0).
- Bankroll reference £500 (USD-equivalent assumption).

### Benchmarks (shown separately)

Cash Sharpe is undefined (OK). Random: five FIXED seeds; report each + mean.

| name | verdict | fail_reason | oos_sharpe | oos_ret | oos_max_dd | exposure |
|------|---------|-------------|-----------|---------|------------|----------|
| BTC_buyhold | FAILED | negative_oos_return;non_positive_oos_sharpe | -0.021 | -0.166 | -0.537 | 1.000 |
| equal_weight | FAILED | negative_oos_return;non_positive_oos_sharpe | -0.287 | -0.578 | -0.786 | 1.000 |
| cash | FAILED | invalid_metrics |  | 0.000 | 0.000 | 0.000 |
| random_top5 | FAILED | negative_oos_return;non_positive_oos_sharpe | -2.355 | -0.965 | -0.982 | 1.000 |
| random_top5_seed42 | FAILED | negative_oos_return;non_positive_oos_sharpe | -2.355 | -0.965 | -0.982 | 1.000 |
| random_top5_seed43 | FAILED | negative_oos_return;non_positive_oos_sharpe | -2.278 | -0.958 | -0.972 | 1.000 |
| random_top5_seed44 | FAILED | negative_oos_return;non_positive_oos_sharpe | -2.366 | -0.963 | -0.974 | 1.000 |
| random_top5_seed45 | FAILED | negative_oos_return;non_positive_oos_sharpe | -2.317 | -0.965 | -0.977 | 1.000 |
| random_top5_seed46 | FAILED | negative_oos_return;non_positive_oos_sharpe | -2.168 | -0.955 | -0.970 | 1.000 |

**Random seeds mean OOS Sharpe:** -2.297; **mean OOS return:** -0.961.

### Strategy results (OOS primary) + fail_reason

| name | fam | verdict | fail_reason | tr_sh | va_sh | oos_sh | oos_ret | oos_dd | trades | expos | turn |
|------|-----|---------|-------------|-------|-------|--------|---------|--------|--------|-------|------|
| A_mom_30d | A | FAILED | negative_oos_return;non_positive_oos_sharpe | 2.805 | 2.044 | -0.471 | -0.766 | -0.894 | 431 | 1.000 | 0.337 |
| A_mom_7d | A | FAILED | negative_oos_return;non_positive_oos_sharpe | 2.808 | 1.924 | -0.337 | -0.729 | -0.888 | 568 | 1.000 | 0.647 |
| B_ma_20_100 | B | FAILED | negative_oos_return | 1.846 | 2.416 | 0.064 | -0.368 | -0.774 | 228 | 0.810 | 0.159 |
| C_mr_24h | C | FAILED | negative_oos_return;non_positive_oos_sharpe;poor_validation | 0.697 | -1.159 | -1.694 | -0.958 | -0.972 | 626 | 1.000 | 1.704 |
| C_mr_72h | C | FAILED | negative_oos_return;non_positive_oos_sharpe | 0.507 | 0.008 | -1.417 | -0.936 | -0.960 | 622 | 1.000 | 1.091 |
| D_vol_break | D | FAILED | negative_oos_return;non_positive_oos_sharpe | 0.330 | 0.128 | -2.118 | -0.924 | -0.946 | 626 | 1.000 | 1.415 |
| E_btc_alt | E | FAILED | negative_oos_return;non_positive_oos_sharpe | 2.987 | 2.536 | -0.519 | -0.686 | -0.828 | 293 | 1.000 | 0.483 |
| F_rev_7d | F | FAILED | negative_oos_return;non_positive_oos_sharpe | 0.664 | 0.343 | -0.893 | -0.871 | -0.929 | 596 | 1.000 | 0.745 |
| I_mom_btc_filter | I | TESTING | n/a_survivor | 2.238 | 1.843 | 0.449 | 0.136 | -0.504 | 194 | 0.436 | 0.170 |
| J_eth_btc_mr | J | FAILED | negative_oos_return;non_positive_oos_sharpe | 0.711 | 0.731 | -0.351 | -0.162 | -0.361 | 176 | 0.249 | 0.144 |
| J_sol_eth_mr | J | FAILED | negative_oos_return;non_positive_oos_sharpe;poor_validation | 0.296 | -0.653 | -0.047 | -0.080 | -0.343 | 170 | 0.278 | 0.138 |
| J_eth_btc_mom | J | FAILED | negative_oos_return;non_positive_oos_sharpe | 1.548 | 1.530 | -0.059 | -0.072 | -0.435 | 170 | 0.377 | 0.145 |
| G_vol_surge | G | FAILED | negative_oos_return;non_positive_oos_sharpe | 1.420 | 2.084 | -0.415 | -0.648 | -0.843 | 567 | 0.463 | 0.803 |
| H_funding_spot | H | EXPLORATORY | incomplete_implementation |  |  | 0.370 | 0.084 | -0.166 | 10 | 0.148 | 0.028 |

Full evidence columns (val/OOS trade counts, turnover, cost stress, explanations): `reports/tournament_v1.csv`.

### Family coverage

| Family | Status |
|--------|--------|
| A XS momentum | implemented (2 variants) |
| B TS momentum / MA | implemented |
| C mean-rev | implemented (2) |
| D vol breakout | implemented |
| E BTC→alt rotation | implemented |
| F XS reversal | implemented |
| G volume surge | implemented |
| H funding→spot | **partial** — free funding history too short for Train/Val; see anomaly note |
| I BTC regime filter | implemented (pre-registered on A mom) |
| J pairs | implemented (3) |

### Anomaly investigation (survivors)

#### `I_mom_btc_filter` — TESTING

Pre-registered: cross-sectional 30d momentum top-5, only when BTC > 100d MA; else cash.

- OOS Sharpe **0.449**, OOS net ret **0.136**, max DD see CSV.
- Mean exposure OOS **0.44**; cash **56%** of OOS hours (regime filter).
- OOS rebalance trade events: **194**.
- **2× cost stress:** Sharpe=0.24728685259122515, ret=-0.10308954522848945.
- **Exceptional-trade dependence:** zeroing top 1% OOS hourly returns → total ret **-0.989** (from 0.136). Extremely fragile to a few hours.
- Monthly OOS returns (net):

| Month | Return |
|-------|--------|
| 2025-01-31 | +0.068 |
| 2025-02-28 | -0.319 |
| 2025-03-31 | +0.000 |
| 2025-04-30 | +0.128 |
| 2025-05-31 | -0.093 |
| 2025-06-30 | -0.040 |
| 2025-07-31 | +0.354 |
| 2025-08-31 | +0.080 |
| 2025-09-30 | -0.070 |
| 2025-10-31 | -0.237 |
| 2025-11-30 | +0.000 |
| 2025-12-31 | +0.000 |
| 2026-01-31 | +0.000 |
| 2026-02-28 | +0.000 |
| 2026-03-31 | +0.000 |
| 2026-04-30 | -0.058 |
| 2026-05-31 | +0.084 |
| 2026-06-30 | -0.016 |
| 2026-07-31 | +0.000 |
| 2026-08-31 | +0.056 |
| 2026-09-30 | +0.443 |

**Interpretation:** Clears frozen TESTING screen (positive OOS Sharpe & return with costs) but **not** a CANDIDATE. Path-dependent, high cash time, and top-tail dependence. Treat as lead for **forward paper trading only**.

#### `H_funding_spot` — EXPLORATORY (incomplete data)

- Public funding series only **279** points from **2026-06-17 16:00:00+00:00**.
- Train & Val: **100% cash** (no signal). OOS cash until first funding print, then ~3 months.
- OOS invested fraction ≈ **14.8%**. Positive OOS ≠ full-period edge.
- `fail_reason=incomplete_implementation`. **Incomplete ≠ proof of loss; also ≠ proof of edge.**

## F. Robustness

CSV columns: `oos_sharpe_cost_1.0x/1.5x/2.0x`, `oos_sharpe_drop_best_asset`.

- Non-BASE variants with OOS Sharpe > 0 at **2× costs:** 2 → I_mom_btc_filter, H_funding_spot
- Drop-best-asset: LIT-USDT was strongest OOS average asset in panel leave-one-out check (see CSV).
- Regimes: family I is the pre-registered BTC MA gate. Explicit bull/bear tables beyond that deferred.

## G. £500 bankroll simulation

**Pre-registered bar:** £500 OOS sim only for verdict **TESTING / PROMISING / CANDIDATE** (not lowered after seeing results). EXPLORATORY (incl. H) excluded.

| name | verdict | oos_sharpe | oos_ret | end_£ | min_£ | sizing note |
|------|---------|-----------|---------|-------|-------|-------------|
| I_mom_btc_filter | TESTING | 0.449 | 0.136 | 567.85 | 312.92 | £500 start; equal-weight top-5 → ~£100/name; assumes venue min order ≤ £10 and no leverage. GBP≈USD for sim. |

Min-order realism: ~£100/name at top-5; assumes venue minimum ≤ £10 and spot-only. This is a **path simulation under research fills**, not a broker backtest.

## H. Verdicts

Scale: FAILED / EXPLORATORY / TESTING / PROMISING / CANDIDATE (last two used sparingly — **none** this release).

- **FAILED**: 16
- **EXPLORATORY**: 1
- **TESTING**: 1
- **PROMISING**: 0
- **CANDIDATE**: 0

### Per-strategy (frozen set) with fail_reason

- `A_mom_30d` (A): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.470630695936557, ret=-0.7658460990512268
  - OOS net return -0.766 ≤ 0 after costs. OOS Sharpe -0.470630695936557 ≤ 0 (or NaN).
- `A_mom_7d` (A): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.33704095798289996, ret=-0.728693497004411
  - OOS net return -0.729 ≤ 0 after costs. OOS Sharpe -0.3370409579828999 ≤ 0 (or NaN).
- `B_ma_20_100` (B): **FAILED** | `negative_oos_return` | OOS sh=0.06386210215489134, ret=-0.36790751890539064
  - OOS net return -0.368 ≤ 0 after costs.
- `BTC_buyhold` (BASE): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.02109490698509708, ret=-0.16613755822242182
  - OOS net return -0.166 ≤ 0 after costs. OOS Sharpe -0.021094906985097 ≤ 0 (or NaN).
- `cash` (BASE): **FAILED** | `invalid_metrics` | OOS sh=NA, ret=0.0
  - Cash has ~0 volatility → Sharpe undefined (NaN). Not evidence of loss; cash is a flat benchmark (0 return, 0 DD).
- `equal_weight` (BASE): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.2870848958219845, ret=-0.577546091908187
  - OOS net return -0.578 ≤ 0 after costs. OOS Sharpe -0.2870848958219845 ≤ 0 (or NaN).
- `random_top5` (BASE): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-2.3554312337463688, ret=-0.9653350719609798
  - OOS net return -0.965 ≤ 0 after costs. OOS Sharpe -2.3554312337463688 ≤ 0 (or NaN).
- `C_mr_24h` (C): **FAILED** | `negative_oos_return;non_positive_oos_sharpe;poor_validation` | OOS sh=-1.693737692355681, ret=-0.9582417696889818
  - OOS net return -0.958 ≤ 0 after costs. OOS Sharpe -1.693737692355681 ≤ 0 (or NaN). Validation Sharpe -1.159 < -0.5 kill gate.
- `C_mr_72h` (C): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-1.4174097873548348, ret=-0.935540979980082
  - OOS net return -0.936 ≤ 0 after costs. OOS Sharpe -1.4174097873548348 ≤ 0 (or NaN).
- `D_vol_break` (D): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-2.118234291089239, ret=-0.9236942360731396
  - OOS net return -0.924 ≤ 0 after costs. OOS Sharpe -2.118234291089239 ≤ 0 (or NaN).
- `E_btc_alt` (E): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.5191336717884735, ret=-0.6862678428631976
  - OOS net return -0.686 ≤ 0 after costs. OOS Sharpe -0.5191336717884735 ≤ 0 (or NaN).
- `F_rev_7d` (F): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.8931169370157935, ret=-0.8712192849251884
  - OOS net return -0.871 ≤ 0 after costs. OOS Sharpe -0.8931169370157935 ≤ 0 (or NaN).
- `G_vol_surge` (G): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.4147845462756733, ret=-0.647775427224067
  - OOS net return -0.648 ≤ 0 after costs. OOS Sharpe -0.4147845462756733 ≤ 0 (or NaN).
- `H_funding_spot` (H): **EXPLORATORY** | `incomplete_implementation` | OOS sh=0.36989085620013695, ret=0.08394901063571125
  - OKX public funding-rate history only covers 2026-06-17→2026-09-18 (279 rows). Train+Val were 100% cash; OOS was cash until 2026-06-18 then ~3 months trading. Positive OOS is NOT full-window evidence. Incomplete data ≠ proof the idea loses money; also ≠ established edge. Verdict left EXPLORATORY as frozen.
- `I_mom_btc_filter` (I): **TESTING** | `n/a_survivor` | OOS sh=0.44904122168819643, ret=0.1357096497705843
  - Passed frozen screening bar for this label. Screening only — not established edge. Requires fresh forward paper trading with frozen rules.
- `J_eth_btc_mom` (J): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.05884665429056742, ret=-0.07228894507412631
  - OOS net return -0.072 ≤ 0 after costs. OOS Sharpe -0.0588466542905674 ≤ 0 (or NaN).
- `J_eth_btc_mr` (J): **FAILED** | `negative_oos_return;non_positive_oos_sharpe` | OOS sh=-0.350727323002381, ret=-0.16235569293699248
  - OOS net return -0.162 ≤ 0 after costs. OOS Sharpe -0.350727323002381 ≤ 0 (or NaN).
- `J_sol_eth_mr` (J): **FAILED** | `negative_oos_return;non_positive_oos_sharpe;poor_validation` | OOS sh=-0.04675862865763833, ret=-0.07970560702766749
  - OOS net return -0.080 ≤ 0 after costs. OOS Sharpe -0.0467586286576383 ≤ 0 (or NaN). Validation Sharpe -0.653 < -0.5 kill gate.

### Overall takeaway

Honest v1 result: **majority FAILED** after fees/spread/slippage. One TESTING lead (`I_mom_btc_filter`) is fragile (tail-hour dependence, long cash spells). One EXPLORATORY (`H_funding_spot`) is an **incomplete-data artefact**, not edge. No PROMISING/CANDIDATE. Do not trade live. Next step if any: forward paper tape with frozen I rules only.

---

## Appendix — Solana lab note (untouched)

- `/workspace/strategy-lab` ingest left running (pid observed live). Swaps in DB at report time: **9489** (user cited ~9484).
- Liquid Crypto Lab did **not** modify Solana strategies, shut down ingest, or merge memecoin results.
- When reporting Solana later: keep strategies frozen through 10k swaps; report **cumulative** + **incremental since prior checkpoint** + **calendar span**; distinguish **ingested swaps** vs **eligible signals** vs **simulated fills**.

*End of v1 report.*