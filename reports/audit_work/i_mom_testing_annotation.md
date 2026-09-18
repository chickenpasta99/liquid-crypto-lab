# Annotation: `I_mom_btc_filter` screening label

**Frozen tournament verdict:** `TESTING` (`fail_reason=n/a_survivor`) — **do not erase.**

**Addendum (2026-09-18 audit):**

| Gate | Result |
|------|--------|
| OOS Sharpe > 0 (1× costs) | PASS (0.449) — screening only |
| OOS return > 0 (1× costs) | PASS (+13.6%) — screening only |
| OOS max DD | −50.4% (prominence: severe) |
| **2× cost return > 0** | **FAILED (−10.3%)** |
| 2× cost Sharpe > 0 | 0.247 (positive Sharpe ≠ passed return gate) |

**Wording for reports:**  
Keep **TESTING** as the original screening label. Explicitly state **doubled-cost return gate FAILED**. Positive stressed Sharpe must not be summarized as “survives 2× costs.”

Under engine **v1b** (open-next fill + qty drift): OOS ret +1.55% / Sharpe 0.390 at 1×; 2× ret −20.6%. Still not PROMISING/CANDIDATE.
