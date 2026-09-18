"""Tournament v1 runner with costs, robustness, variant log."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.backtest.engine import run_backtest, wide_prices, metrics, split_mask
from liquid_crypto_lab.data import store
from liquid_crypto_lab.strategies.families import build_variants


def _load_funding() -> pd.DataFrame | None:
    p = cfg.PROCESSED / "funding_BTC_USDT_SWAP.parquet"
    if p.exists():
        return pd.read_parquet(p)
    return None


def robustness_checks(close, quote_vol, weights_fn, name, family, variant) -> dict[str, Any]:
    """Cost stress, drop best asset, concentration."""
    out: dict[str, Any] = {}
    for mult in cfg.COST_STRESS_MULTS:
        bt = run_backtest(name, family, variant, close, quote_vol, weights_fn, stress=mult)
        out[f"oos_sharpe_cost_{mult}x"] = bt.metrics_by_split.get("oos", {}).get("sharpe")
        out[f"oos_ret_cost_{mult}x"] = bt.metrics_by_split.get("oos", {}).get("total_ret")

    # Remove best-performing asset in OOS (leave-one-out worst-case for concentration)
    oos_start = pd.Timestamp(cfg.OOS_START, tz="UTC")
    oos_rets = close.loc[close.index >= oos_start].pct_change().mean().sort_values(ascending=False)
    if len(oos_rets):
        best = oos_rets.index[0]
        close2 = close.drop(columns=[best])
        qv2 = quote_vol.drop(columns=[best], errors="ignore")

        def wf(c, rt, _orig=weights_fn):
            # run on reduced universe
            return _orig(c, rt)

        bt2 = run_backtest(name, family, variant, close2, qv2, wf, stress=1.0)
        out["oos_sharpe_drop_best_asset"] = bt2.metrics_by_split.get("oos", {}).get("sharpe")
        out["dropped_asset"] = best
    return out


def bankroll_sim(rets: pd.Series, start_gbp: float = cfg.BANKROLL_GBP) -> dict:
    r = rets.dropna()
    if r.empty:
        return {}
    eq = (1 + r).cumprod() * start_gbp
    return {
        "start_gbp": start_gbp,
        "end_gbp": float(eq.iloc[-1]),
        "min_gbp": float(eq.min()),
        "max_dd": float((eq / eq.cummax() - 1).min()),
        "n_hours": int(len(r)),
    }


def run_tournament() -> dict[str, Any]:
    store.ensure_dirs()
    freeze_ts = datetime.now(timezone.utc).isoformat()
    store.write_meta("strategy_freeze.json", {"freeze_ts": freeze_ts, "version": "v1"})

    panel = store.load_panel()
    if panel.empty:
        raise RuntimeError("No processed data — run fetch first")

    close, quote_vol = wide_prices(panel)
    # Require assets with enough history
    min_bars = cfg.MIN_HISTORY_BARS
    ok_cols = [c for c in close.columns if close[c].notna().sum() >= min_bars]
    close = close[ok_cols]
    quote_vol = quote_vol.reindex(columns=ok_cols).fillna(0)

    funding = _load_funding()
    variants = build_variants(quote_vol=quote_vol, funding=funding)

    rows = []
    equity_curves = {}
    rets_map = {}

    for v in variants:
        print(f"BT {v.name} ...", flush=True)
        # Fix placeholder G if needed
        bt = run_backtest(
            v.name, v.family, v.variant, close, quote_vol, v.weights_fn, stress=1.0, notes=v.notes
        )
        rob = {}
        try:
            rob = robustness_checks(close, quote_vol, v.weights_fn, v.name, v.family, v.variant)
        except Exception as e:
            rob = {"robustness_error": str(e)}

        oos = bt.metrics_by_split.get("oos", {})
        val = bt.metrics_by_split.get("val", {})
        train = bt.metrics_by_split.get("train", {})

        # Verdict logic (honest, prefer kill)
        verdict = _verdict(train, val, oos, v.family, v.notes)

        bank = {}
        if verdict in ("PROMISING", "CANDIDATE", "TESTING", "EXPLORATORY") and oos.get("n", 0) > 100:
            # Only meaningful OOS for £500 sim — EXPLORATORY+ with data
            oos_mask = split_mask(bt.rets.index)["oos"]
            bank = bankroll_sim(bt.rets[oos_mask.values])

        row = {
            "name": v.name,
            "family": v.family,
            "variant": v.variant,
            "notes": v.notes,
            "verdict": verdict,
            "train_sharpe": train.get("sharpe"),
            "val_sharpe": val.get("sharpe"),
            "oos_sharpe": oos.get("sharpe"),
            "train_ret": train.get("total_ret"),
            "val_ret": val.get("total_ret"),
            "oos_ret": oos.get("total_ret"),
            "oos_max_dd": oos.get("max_dd"),
            "oos_hit": oos.get("hit_rate"),
            "bankroll_end_gbp": bank.get("end_gbp"),
            "bankroll_min_gbp": bank.get("min_gbp"),
            **{k: rob.get(k) for k in rob},
        }
        rows.append(row)
        equity_curves[v.name] = bt.equity
        rets_map[v.name] = bt.rets
        print(f"  verdict={verdict} oos_sharpe={oos.get('sharpe')} oos_ret={oos.get('total_ret')}", flush=True)

    df = pd.DataFrame(rows)
    out_csv = cfg.REPORTS / "tournament_v1.csv"
    df.to_csv(out_csv, index=False)

    # Variant log
    vlog = cfg.REPORTS / "variant_log.csv"
    with vlog.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["timestamp", "name", "family", "variant", "notes", "verdict", "oos_sharpe", "oos_ret"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(
                {
                    "timestamp": freeze_ts,
                    "name": r["name"],
                    "family": r["family"],
                    "variant": r["variant"],
                    "notes": r["notes"],
                    "verdict": r["verdict"],
                    "oos_sharpe": r["oos_sharpe"],
                    "oos_ret": r["oos_ret"],
                }
            )

    # Save equity curves
    eq_df = pd.DataFrame(equity_curves)
    eq_df.to_parquet(cfg.PROCESSED / "equity_curves_v1.parquet")

    summary = {
        "freeze_ts": freeze_ts,
        "n_assets": len(ok_cols),
        "n_variants": len(rows),
        "symbols": ok_cols,
        "date_range": [str(close.index.min()), str(close.index.max())],
        "rows_panel": len(panel),
        "verdicts": df.groupby("verdict").size().to_dict() if len(df) else {},
        "csv": str(out_csv),
    }
    store.write_meta("tournament_summary.json", summary)
    return summary


def _verdict(train, val, oos, family, notes) -> str:
    if "STUB" in (notes or "").upper() or family == "H" and "stub" in (notes or "").lower():
        return "FAILED"
    os_ = oos.get("sharpe")
    vs = val.get("sharpe")
    ts = train.get("sharpe")
    oret = oos.get("total_ret")
    if os_ is None or (isinstance(os_, float) and np.isnan(os_)):
        return "FAILED"
    # Baselines: label informational
    if family == "BASE":
        if oret is not None and oret > 0 and os_ > 0:
            return "EXPLORATORY"
        return "FAILED"
    # Kill if OOS sharpe <= 0 or OOS total ret <= 0 after costs
    if os_ <= 0 or (oret is not None and oret <= 0):
        return "FAILED"
    # Kill if val and oos disagree badly (val strong, oos weak already caught)
    # Require val also non-terrible
    if vs is not None and not (isinstance(vs, float) and np.isnan(vs)) and vs < -0.5:
        return "FAILED"
    # Cost stress: handled in report; here use raw
    # PROMISING/CANDIDATE sparingly
    if os_ > 0.8 and vs is not None and vs > 0.3 and (oret or 0) > 0.05:
        return "PROMISING"
    if os_ > 0.4 and (oret or 0) > 0:
        return "TESTING"
    if os_ > 0:
        return "EXPLORATORY"
    return "FAILED"
