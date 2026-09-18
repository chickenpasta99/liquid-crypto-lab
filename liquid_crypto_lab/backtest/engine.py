"""Spot long/cash backtest engine with costs."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.costs import turnover_cost_return


@dataclass
class BTResult:
    name: str
    family: str
    variant: str
    equity: pd.Series
    rets: pd.Series
    metrics_by_split: dict
    notes: str = ""


def split_mask(idx: pd.DatetimeIndex) -> dict[str, pd.Series]:
    train_end = pd.Timestamp(cfg.TRAIN_END, tz="UTC")
    val_start = pd.Timestamp(cfg.VAL_START, tz="UTC")
    val_end = pd.Timestamp(cfg.VAL_END, tz="UTC")
    oos_start = pd.Timestamp(cfg.OOS_START, tz="UTC")
    ts = pd.Series(idx, index=idx)
    return {
        "train": ts <= train_end,
        "val": (ts >= val_start) & (ts <= val_end),
        "oos": ts >= oos_start,
        "full": pd.Series(True, index=idx),
    }


def metrics(rets: pd.Series) -> dict:
    r = rets.dropna()
    if len(r) < 10:
        return {"n": len(r), "ann_ret": np.nan, "ann_vol": np.nan, "sharpe": np.nan,
                "max_dd": np.nan, "hit_rate": np.nan, "total_ret": np.nan}
    # hourly → annualize with 24*365
    mu = r.mean()
    sd = r.std(ddof=1)
    ann = 24 * 365
    ann_ret = float((1 + mu) ** ann - 1) if mu > -1 else np.nan
    ann_vol = float(sd * np.sqrt(ann))
    sharpe = float(mu / sd * np.sqrt(ann)) if sd > 0 else np.nan
    eq = (1 + r).cumprod()
    peak = eq.cummax()
    dd = eq / peak - 1
    return {
        "n": int(len(r)),
        "ann_ret": ann_ret,
        "ann_vol": ann_vol,
        "sharpe": sharpe,
        "max_dd": float(dd.min()),
        "hit_rate": float((r > 0).mean()),
        "total_ret": float(eq.iloc[-1] - 1),
    }


def wide_prices(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return close and quote_volume wide matrices indexed by ts."""
    close = panel.pivot_table(index="ts", columns="symbol", values="close", aggfunc="last")
    qv = panel.pivot_table(index="ts", columns="symbol", values="quote_volume", aggfunc="last")
    close = close.sort_index().ffill()
    qv = qv.reindex(close.index).fillna(0)
    return close, qv


def run_backtest(
    name: str,
    family: str,
    variant: str,
    close: pd.DataFrame,
    quote_vol: pd.DataFrame,
    weights_fn: Callable[[pd.DataFrame, pd.DatetimeIndex], pd.DataFrame],
    stress: float = 1.0,
    rebalance_hours: int = cfg.REBALANCE_HOURS,
    notes: str = "",
) -> BTResult:
    """
    weights_fn(close, rebalance_times) -> DataFrame aligned to rebalance_times x symbols,
    rows sum to <= 1 (cash = residual). Long-only spot.
    """
    idx = close.index
    # Rebalance at every Nth hour
    reb_mask = np.arange(len(idx)) % rebalance_hours == 0
    reb_times = idx[reb_mask]
    if len(reb_times) < 5:
        empty = pd.Series(dtype=float)
        return BTResult(name, family, variant, empty, empty, {}, notes="too_few_rebals")

    w_reb = weights_fn(close, reb_times)
    w_reb = w_reb.reindex(columns=close.columns).fillna(0.0)
    # clip and renormalize if sum > 1
    row_sum = w_reb.sum(axis=1).clip(lower=1e-12)
    over = row_sum > 1.0
    w_reb.loc[over] = w_reb.loc[over].div(row_sum.loc[over], axis=0)

    # Forward-fill weights to hourly
    w = w_reb.reindex(idx).ffill().fillna(0.0)

    rets_asset = close.pct_change().fillna(0.0)
    # Gross portfolio return
    port = (w.shift(1).fillna(0.0) * rets_asset).sum(axis=1)

    # Cost on weight changes at each bar (usually only rebalance bars)
    dw = w.diff().abs().fillna(w.abs())
    # ADV: rolling 24h quote volume mean
    adv = quote_vol.rolling(24, min_periods=1).mean().replace(0, np.nan).fillna(cfg.MIN_ADV_USD)
    equity = cfg.BANKROLL_USD
    cost = pd.Series(0.0, index=idx)
    for t in idx:
        delta = dw.loc[t]
        if delta.sum() <= 1e-12:
            continue
        # approximate ADV as cross-sectional median that bar
        adv_t = float(adv.loc[t].median()) if t in adv.index else cfg.MIN_ADV_USD
        c = 0.0
        for sym, d in delta.items():
            if d <= 0:
                continue
            c += turnover_cost_return(float(d), equity, float(adv.loc[t, sym]) if sym in adv.columns else adv_t, stress=stress)
        cost.loc[t] = c

    net = port + cost
    eq = (1 + net).cumprod() * cfg.BANKROLL_USD
    masks = split_mask(idx)
    msplit = {k: metrics(net[m.values if hasattr(m, "values") else m]) for k, m in masks.items()}
    # Also store without full for clarity
    return BTResult(
        name=name,
        family=family,
        variant=variant,
        equity=eq,
        rets=net,
        metrics_by_split=msplit,
        notes=notes,
    )
