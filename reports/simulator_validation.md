# Simulator validation (paper only)

**Generated:** 2026-09-18 ~15:45 BST (Europe/London)  
**Scope:** Liquid Crypto Lab accounting / verdict / tradability + Solana Strategy Lab P&L / lookahead / counts / event-time.  
**Constraints honored:** no live trading; no strategy expansion; no grow-score / tournament / stress re-scores; Solana ingest left running; frozen v1 reports / tournament CSVs / Solana checkpoint / stress packs **not overwritten**.

> Paper research only. Not financial advice.

---

## PASS/FAIL table

| # | Check | Result | Evidence |
|---|-------|--------|----------|
| 1 | Accounting example ($500→$501.10; $496.38→$496.41) | **PASS (reporting error)** | Machine ledger: entry after fees = **$498.90**, not $501.10. $501.10 = `500×(1+∣fee∣)` (fee sign flipped). Restore levels ~$494.16 after fees (addendum levels not reproduced). |
| 2 | Accounting tests | **PASS** | `tests/test_accounting.py` — all 7 checks PASS |
| 3 | Separate original vs corrected verdicts (`I_mom_btc_filter`) | **PASS** | v1 **TESTING** (Sharpe 0.449). v1b Sharpe **0.390** under existing `_verdict` → **EXPLORATORY** (threshold `oos_sharpe > 0.4` unchanged, not met). |
| 4 | Historical tradability (ffill ≠ fillable; ADV floor ≠ volume) | **UNVALIDATED** | Engines `ffill` close/open; `quote_volume` missing→0 then `fillna(MIN_ADV_USD=$2m)`. Gap/low-volume fills lack `quote_volume` evidence. |
| 5 | Next-open still an assumption | **PASS (limitation noted)** | v1b is **not** fully realistic; latency/slippage sensitivity required; do not overclaim. |
| 6 | Audit ten largest P&L contributors (Solana A) | **PASS (artefact)** | Top PnL dominated by broken USD tape + `open_mark`; see §6. |
| 7 | Separate realised vs mark vs unverified | **PASS** | Must not combine `open_mark` with realised into one EV/PF. Extremes retained, not capped. |
| 8 | Lookahead (Strategy A leader realised rounds) | **FAIL (lookahead present)** | Full-history `min_closed` gate retrospectively enables earlier rounds. |
| 9 | Reconcile counts / P&L off-by-one | **PASS (explained)** | 1358 − 266 = **1092**, reported fills **1091** → residual **1**. |
| 10 | Event time vs ingestion time / 10k “OOS” | **UNVALIDATED (prospective)** | Late-arriving rows can describe older events; 10k OOS ≈ **~25h same-day tape**, not true multi-day prospective. |

---

## 1. Accounting example — reporting mistake (not engine fee sign bug)

**Claim (addendum):** $500 → $501.10 solely after deducting fees; $496.38 → $496.41 with a fee deduction.

**Machine ledger:** `reports/audit_work/accounting_ledger_dec2024.csv`  
(also `reports/audit_work/machine_ledger_rebalance_hours.csv`)

Columns: `time, symbol, qty, exec_price, cash, fees, equity, event` spanning 2024-12-07 06:00 → 2024-12-08 09:00 UTC (entry + hold + next-day restore) for `I_mom` sleeve `{CRV,HBAR,ONE,XLM,XRP}` @ 20% each, bankroll $500, v1b open-next fill.

| Checkpoint | Addendum | Machine ledger | Interpretation |
|------------|----------|----------------|----------------|
| After entry fees | **$501.10** | **$498.8967** | Addendum applied fee magnitude with **wrong sign** (`500×(1+0.002207)`). Correct: `500×(1−0.002207)≈498.90`. |
| Entry fee USD | (implied) | **$1.1033** | Matches ~22.07 bps one-way × full turnover from cash. |
| Next-day restore | $496.38→$496.41 | ~$494.194→$494.165 | Same wrong-sign pattern on a tiny restore fee (~$0.03); absolute levels in addendum **not reproduced** (hand-rounded / wrong path). |

**Verdict:** **reporting mistake** in the worked example (fee sign / invented levels). Engine `turnover_cost_return` correctly returns a **negative** drag. Not an engine bug that credits fees.

Reproduce:
```bash
cd /workspace/liquid-crypto-lab && PYTHONPATH=. python3 tests/test_accounting.py
# see test_addendum_501_10_is_fee_sign_error
```

---

## 2. Accounting tests

File: `tests/test_accounting.py` (does not touch frozen reports).

| Test | Result |
|------|--------|
| Flat prices + trading → lose exactly charged costs | **PASS** (total = −0.0022004) |
| No trades → no trading costs | **PASS** |
| Unchanged quantities → buy-and-hold (price drift only) | **PASS** |
| Purchases + fees → no negative cash (unlevered) | **PASS** |
| Multi-asset qty×price + cash = equity | **PASS** |
| Addendum $501.10 fee-sign reproduction | **PASS** |
| ffill + ADV floor optimistic tradability probe | **PASS** (documents UNVALIDATED fills) |

---

## 3. Original vs corrected verdicts — `I_mom_btc_filter`

Existing `_verdict` (unchanged thresholds) in `liquid_crypto_lab/tournament.py`:

- Kill if OOS Sharpe ≤ 0 or OOS ret ≤ 0  
- `TESTING` if `oos_sharpe > 0.4` and `oos_ret > 0`  
- else if `oos_sharpe > 0` → `EXPLORATORY`

| | v1 (frozen) | v1b (corrected engine) |
|--|-------------|-------------------------|
| OOS Sharpe | **0.449** | **0.390** |
| OOS total ret | **+13.57%** | **+1.55%** |
| OOS max DD | −50.42% | −51.45% |
| 2× cost ret | −10.31% (gate FAIL) | −20.60% (gate FAIL) |
| **`_verdict` label** | **TESTING** | **EXPLORATORY** |

**Side-by-side:** original screening label **TESTING** preserved on frozen v1 artefacts. Corrected application of the **same** rules to v1b metrics: **EXPLORATORY** because 0.390 does **not** meet `> 0.4`. Do not promote.

---

## 4. Historical tradability — UNVALIDATED

Code (`engine.py` / `engine_v1b.py`):

- `close` / `open` → `.ffill()` across missing bars  
- `quote_volume` → `.fillna(0)` then ADV `.fillna(MIN_ADV_USD)` with **`$2,000,000` floor**

**Implication:** forward-filled prices do **not** automatically permit fills; ADV floor must **not** substitute for actual volume. Fills during missing/low-volume periods are **UNVALIDATED** unless `quote_volume` evidence exists on that bar.

Minimum extra data to validate: per-bar true `quote_volume` (no floor), gap flags, and a no-fill / reject rule when `qv==0` or bar is ffilled.

---

## 5. Next-open is still an assumption

v1b replaces optimistic same-close fill with **open[t+1]** (else explicit lag). That is better, **not** “fully realistic.”

Required sensitivity note (do not overclaim):

- No exchange latency, queue position, or partial-fill model  
- Slippage is stylized (`SLIPPAGE_BASE_BPS + K√(notional/ADV)`), not venue micro-structure  
- UK retail fees/spreads may exceed the frozen 15+5+2 bps base  
- Stress already shows 1.5× / 2× costs kill I_mom returns  

Label any forward paper tape: **assumed next-open fill + stylized costs**.

---

## 6–7. Solana — top-10 P&L audit & separation of marks

Source fills (frozen checkpoint export): `strategy-lab/data/analysis/strategy_a_fills_at_10000.csv` (1091 rows).  
DB: `strategy-lab/data/strategy_lab.db` `swaps` rows.  
Detail JSON: `strategy-lab/reports/audit_work/top10_pnl_audit.json`.

### Headline

**Top contributors are not a tradable edge — they are USD price-tape / mark artefacts** (microprice entries vs sane leader buys, pool price spans of 10³–10⁹×, and one multi-million `open_mark`).

| Rank | Approx PnL | Status | Why extreme |
|-----:|-----------:|--------|-------------|
| 1 | ~$2.27M | **open_mark** | Mark-to-last ESTIMATE; sim entry ~3.5e-6 → mark ~0.16 (×45k); leader buy in DB ~$0.087 — tape inconsistent |
| 2 | ~$483k | filled | Same mint, other pool; entry microprice vs exit print ×9.6k; pool span huge |
| 3–5 | ~$34.7k each | filled | Same pool cluster; ×695 ratios; leader buy ≠ sim entry print |
| 6–9 | $2.5k–$26k | filled | Same family: broken pool USD scaling / thin prints |
| 10 | ~$305 | filled | Large but smaller ratio (~7×); still suspect on thin memecoin tape |

### Separation (required)

| Bucket | n @10k A | Net PnL (approx) | Use in EV/PF? |
|--------|---------:|-----------------:|---------------|
| Realised `filled` | 847 | ~+$621k | Separate only; still contaminated by bad prints |
| Executable estimated liquidation | — | — | Not modeled as venue exit beyond next-print |
| Unverified `open_mark` | 244 | ~+$2.27M | **Exclude from EV/PF**; label ESTIMATE |

**Do not** combine `open_mark` with realised into one EV/PF. **Do not** cap/delete extremes — disclose them.

---

## 8. Lookahead — FAIL

Strategy A path (`tournament_v2.py` `_sim_copy` / `strategies/a_raw_copy.py` + `rounds.py` + `costs.py`):

```text
tournament_v2.py ~51–68:
  rounds = realised_rounds(swaps)          # completed buy→sell only
  if len(rounds) < min_closed: continue    # evaluated on FULL wallet history
  for rd in rounds:
      paper_round_trip(tape, rd["entry_ts"], rd["exit_ts"], delay)

costs.paper_round_trip:
  fills only at/after signal_ts+delay     # print timing OK
  but signal set exists only for rounds that eventually close
```

**Two lookahead channels:**

1. **Eligibility:** `min_closed` on the full history — a round that closes later can make **earlier** rounds eligible retrospectively.  
2. **Round construction:** `realised_rounds` only emits rounds after the sell exists — entry decision at `entry_ts` is conditioned on knowing a closing sell occurs.

Fill **prices** are not look-ahead (next trade after delay). **Selection** is.

**Verdict:** **FAIL** — not clean prospective copy at signal time.

Minimum fix: as-of `min_closed` using only rounds with `exit_ts <= signal_ts`, and emit signals only when the leader sell is already observed (or run a live eligibility state).

---

## 9. Counts / P&L reconcile — off-by-one

Checkpoint (`solana_checkpoint_10k.md`):

| Layer | Count |
|-------|------:|
| Eligible signals (A) | **1358** |
| Failed entry | **266** |
| Simulated fills (`filled`\|`open_mark`) | **1091** |

Arithmetic: `1358 − 266 = 1092 ≠ 1091`. **Residual = 1.**

CSV confirms **1091** fill rows (847 filled + 244 open_mark). Live engine currently emits no `failed_exit` (0).  

**Best explanation:** one eligible signal produced neither `failed_entry` nor a counted fill (or the signal tally is high by 1). Not explained by combining open_mark into fills (already included).  

**Vs prior checkpoints:** more positions from continued ingest; exits/marks updated as tape grew; bootstrap + RPC backfill added older event rows after process start; no deletion of extremes. Cumulative OOS EV explosion is mark/tape concentration (see §6), not a robust incremental edge (incremental since 6k dies after removing best 1 winner — prior stress pack).

---

## 10. Event time vs ingestion time

| Fact | Evidence |
|------|----------|
| Swap schema stores **event** `ts`, not ingest time | `swaps.ts`; ingest_runs have `started_at`/`ended_at` |
| Raw JSON file mtime often **minutes after** event_ts | Sample RPC deltas ~10–100s+ |
| First continuous ingest_run started **after** many bootstrap event timestamps | Bootstrap events 2026-09-16… can be scored in a freeze that began 2026-09-18 |
| Train cutoff frozen | `TRAIN_CUTOFF_TS=1789650298` = 2026-09-17 14:04:58 BST |
| 10k “OOS” window | ~**25.1 hours** of same-day tape after cutoff — **not** true multi-day prospective OOS |

Call results **prospective only** where the signal row is known to have been recorded before the outcome was observed. Default 10k OOS metrics are **same-day retrospective tape under a frozen cutoff**, not live prospective trading.

---

## Artefacts added (frozen files untouched)

| Path | Role |
|------|------|
| `liquid-crypto-lab/reports/simulator_validation.md` | This report |
| `liquid-crypto-lab/reports/audit_work/accounting_ledger_dec2024.csv` | Machine ledger |
| `liquid-crypto-lab/tests/test_accounting.py` | Accounting PASS/FAIL tests |
| `strategy-lab/reports/simulator_validation.md` | Copy/symlink summary |
| `strategy-lab/reports/audit_work/top10_pnl_audit.json` | Top-10 DB audit |

**Preserved:** `liquid_crypto_lab_v1.md`, `tournament_v1.csv`, `tournament_v1b_delta.*`, Solana `solana_checkpoint_10k.*`, `tournament_v2_at_*.md`, stress packs.

**Ingest:** left running (`python3 -m strategy_lab ingest --continuous …`).

---

*End of simulator validation.*
