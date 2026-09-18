# Simulator validation status (Liquid Crypto Lab) — repair_v2

**Generated:** 2026-09-18 ~15:50 BST (Europe/London)  
**Companion to:** `reports/simulator_validation.md` (not overwritten)

> Paper research only. Not financial advice.

---

## CLEAR SEPARATION

| Layer | Meaning | State |
|-------|---------|-------|
| **AUDIT COMPLETED** | Accounting example, tests, I_mom verdict, tradability, next-open limits | **YES** |
| **SYSTEM PASSED** | Valid-exec mask + engine_v1b-proven tests close tradability gap | **PARTIAL** — mask available behind `require_valid_exec=True`; default tournament path unchanged |

### Explicit items

| Item | Status |
|------|--------|
| Accounting $501.10 | Audit complete — reporting error; engine fee sign OK |
| I_mom on corrected metrics | Must stay **EXPLORATORY** (OOS Sharpe 0.390 ≤ 0.4) |
| ffill / ADV-floor fills | Still **UNVALIDATED** unless `require_valid_exec=True` + `price_valid` mask |
| Solana pricing / Strategy A | Tracked in strategy-lab status (FAILED until repairs wired) |

See `reports/repair_v2_liquid.md`.
