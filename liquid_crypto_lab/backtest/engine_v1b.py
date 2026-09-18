"""Versioned engine v1b — corrected execution timing + inter-rebalance drift.

Changelog vs ``engine.py`` (frozen v1):
1. **Timing (optimistic same-bar close fill → open-next fill)**
   - Signal still uses ``close[t]`` at rebalance index ``t`` (OKX 1H candles are
     open-labeled; ``close[t]`` is only known at ``t+1h``).
   - v1: ``port = (w.shift(1) * close.pct_change()).sum()`` with ``w`` set at ``t``
     ⇒ first earns ``close[t]→close[t+1]`` = **optimistic same-bar close fill**.
   - v1b: apply weights from bar ``t+1``; fill at ``open[t+1]`` when available;
     first mark ``open[t+1]→close[t+1]``; later bars close-to-close.
   - If ``open`` missing/invalid: fill at ``close[t+1]`` and first earn
     ``close[t+1]→close[t+2]`` (explicit extra lag).

2. **Inter-rebalance drift**
   - v1: ``w`` ffilled constant; ``dw=w.diff()`` ≈ 0 between daily rebalances ⇒
     constant-weight (implicit hourly restore) returns **without** charging
     restoration turnover.
   - v1b: after each fill, hold **quantities** (drifting weights) until the next
     rebalance; costs only when target weights change at execution bars.

Does **not** overwrite v1 metrics. Use ``run_backtest_v1b`` only.
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.backtest.engine import BTResult, metrics, split_mask
from liquid_crypto_lab.costs import turnover_cost_return

ENGINE_VERSION = "v1b"


def wide_ohlc(panel: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    close = panel.pivot_table(index="ts", columns="symbol", values="close", aggfunc="last")
    open_ = panel.pivot_table(index="ts", columns="symbol", values="open", aggfunc="last")
    qv = panel.pivot_table(index="ts", columns="symbol", values="quote_volume", aggfunc="last")
    close = close.sort_index().ffill()
    open_ = open_.reindex(close.index).ffill()
    qv = qv.reindex(close.index).fillna(0.0)
    return close, open_, qv


def run_backtest_v1b(
    name: str,
    family: str,
    variant: str,
    close: pd.DataFrame,
    open_px: pd.DataFrame,
    quote_vol: pd.DataFrame,
    weights_fn: Callable[[pd.DataFrame, pd.DatetimeIndex], pd.DataFrame],
    stress: float = 1.0,
    rebalance_hours: int = cfg.REBALANCE_HOURS,
    notes: str = "",
    fill_mode: str = "open_next",
) -> BTResult:
    """v1b backtest. See module docstring for diffs vs v1."""
    idx = close.index
    open_px = open_px.reindex(index=idx, columns=close.columns)
    reb_mask = np.arange(len(idx)) % rebalance_hours == 0
    reb_times = idx[reb_mask]
    if len(reb_times) < 5:
        empty = pd.Series(dtype=float)
        return BTResult(name, family, variant, empty, empty, {}, notes="too_few_rebals")

    w_reb = weights_fn(close, reb_times)
    w_reb = w_reb.reindex(columns=close.columns).fillna(0.0)
    row_sum = w_reb.sum(axis=1).clip(lower=1e-12)
    over = row_sum > 1.0
    w_reb.loc[over] = w_reb.loc[over].div(row_sum.loc[over], axis=0)

    # Signal at reb bar t; execution starts next bar
    w_signal = w_reb.reindex(idx).ffill().fillna(0.0)
    w_exec_target = w_signal.shift(1).fillna(0.0)

    rets_cc = close.pct_change()
    rets_oc = (close / open_px - 1.0).replace([np.inf, -np.inf], np.nan)

    adv = quote_vol.rolling(24, min_periods=1).mean().replace(0, np.nan).fillna(cfg.MIN_ADV_USD)

    n, m = close.shape
    cols = close.columns
    W_targ = w_exec_target.to_numpy(dtype=float)
    R_cc = rets_cc.to_numpy(dtype=float)
    R_oc = rets_oc.to_numpy(dtype=float)
    O = open_px.to_numpy(dtype=float)
    C = close.to_numpy(dtype=float)
    ADV = adv.reindex(index=idx, columns=cols).to_numpy(dtype=float)

    # Execution bars = target change
    exec_bar = np.zeros(n, dtype=bool)
    if n > 1:
        exec_bar[1:] = np.abs(W_targ[1:] - W_targ[:-1]).sum(axis=1) > 1e-12
    exec_bar[0] = W_targ[0].sum() > 1e-12

    # Open availability per bar (any held name)
    open_ok = np.isfinite(O) & (O > 0)

    net = np.zeros(n)
    w = np.zeros(m)  # current drifted portfolio weights (sum <= 1; cash residual)

    for i in range(n):
        if i == 0:
            continue

        if exec_bar[i]:
            target = np.nan_to_num(W_targ[i], nan=0.0)
            # Fill prices
            if fill_mode == "open_next":
                use_open = open_ok[i]
                # If open missing for a name we need, fall back: treat as close-fill
                # and earn 0 on this bar for that name (lag into next cc bar).
                fill_r = np.where(use_open, np.nan_to_num(R_oc[i], nan=0.0), 0.0)
            else:
                # close_next: skip earning this bar on new weights; set w=target at close
                fill_r = np.zeros(m)

            # Turnover from current drifted w → target (one-way on |Δw|)
            delta = np.abs(target - w)
            c_sum = 0.0
            if delta.sum() > 1e-12:
                for j in np.where(delta > 1e-15)[0]:
                    adv_j = float(ADV[i, j]) if np.isfinite(ADV[i, j]) else cfg.MIN_ADV_USD
                    c_sum += turnover_cost_return(
                        float(delta[j]), cfg.BANKROLL_USD, adv_j, stress=stress
                    )
            # Gross return on new weights for fill bar
            if fill_mode == "open_next":
                gross = float(np.dot(target, fill_r))
            else:
                gross = 0.0  # first earn next bar cc
            net[i] = gross + c_sum
            w = target.copy()
            if fill_mode == "open_next":
                # Drift weights through this bar's open→close move
                growth = 1.0 + fill_r
                invested = float(w.sum())
                if invested > 0:
                    w = w * growth
                    port_g = float(np.dot(target, fill_r))  # same as gross before cash
                    # Renormalize invested sleeve relative to total equity move
                    # equity factor = 1 + gross (cash earns 0); invested value scales by (1+port_g_invested)
                    # Simpler: w_j' = target_j * (1+r_j) / (1+gross_total) * invested_frac_after
                    denom = 1.0 + gross
                    if denom > 0:
                        w = target * growth / denom
                        # cash residual = 1 - invested'; keep weight sum = invested sleeve only
                        # After move, invested fraction = invested * (1+dot(target_norm, r)) / (1+gross)
                        # With cash: total gross = sum(target*r); new invested w sum = sum(target*(1+r))/(1+gross)
                        pass
            continue

        # Non-exec bar: close-to-close on drifted weights
        r = np.nan_to_num(R_cc[i], nan=0.0)
        gross = float(np.dot(w, r))
        net[i] = gross  # no cost
        denom = 1.0 + gross
        if denom > 0 and w.sum() > 0:
            w = w * (1.0 + r) / denom
            # Numerical hygiene: zero tiny weights
            w[w < 1e-15] = 0.0

    net_s = pd.Series(net, index=idx).replace([np.inf, -np.inf], 0.0).fillna(0.0)
    eq = (1 + net_s).cumprod() * cfg.BANKROLL_USD
    masks = split_mask(idx)
    msplit = {
        k: metrics(net_s[m.values if hasattr(m, "values") else m]) for k, m in masks.items()
    }
    note = f"{notes} | engine={ENGINE_VERSION} fill={fill_mode} drift=qty_hold".strip(" |")
    return BTResult(
        name=name,
        family=family,
        variant=variant,
        equity=eq,
        rets=net_s,
        metrics_by_split=msplit,
        notes=note,
    )
