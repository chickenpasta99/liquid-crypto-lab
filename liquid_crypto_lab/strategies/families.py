"""Strategy families A–J + baselines. Few variants; long/cash spot."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd

from liquid_crypto_lab import config as cfg


@dataclass
class Variant:
    name: str
    family: str
    variant: str
    weights_fn: Callable
    notes: str = ""
    research_only_short: bool = False


def _top_n_long(scores: pd.DataFrame, n: int = cfg.N_LONG, max_w: float = cfg.MAX_WEIGHT) -> pd.DataFrame:
    """Equal-weight top-N by score (higher better); NaN scores excluded."""
    out = pd.DataFrame(0.0, index=scores.index, columns=scores.columns)
    for t, row in scores.iterrows():
        s = row.dropna().sort_values(ascending=False)
        if s.empty:
            continue
        picks = s.head(n).index
        w = min(1.0 / len(picks), max_w)
        out.loc[t, picks] = w
    return out


def _bottom_n_as_cash_signal(scores: pd.DataFrame, n: int) -> pd.DataFrame:
    """Research: underperformers get zero weight (spot can't short easily) — same as exclude."""
    return _top_n_long(scores, n=n)


# --- Baselines ---

def baseline_btc_bh(close: pd.DataFrame, reb_times: pd.DatetimeIndex) -> pd.DataFrame:
    cols = close.columns
    btc = [c for c in cols if c.startswith("BTC-")]
    w = pd.DataFrame(0.0, index=reb_times, columns=cols)
    if btc:
        w[btc[0]] = 1.0
    return w


def baseline_equal_weight(close: pd.DataFrame, reb_times: pd.DatetimeIndex) -> pd.DataFrame:
    # equal weight among assets with non-null close at rebalance
    w = pd.DataFrame(0.0, index=reb_times, columns=close.columns)
    for t in reb_times:
        avail = close.loc[:t].iloc[-1].dropna()
        if avail.empty:
            continue
        # only assets present
        syms = [s for s in avail.index if s in w.columns]
        if not syms:
            continue
        w.loc[t, syms] = 1.0 / len(syms)
    # Cap max weight by spreading only top-liquidity already in universe; clip
    return w.clip(upper=cfg.MAX_WEIGHT)


def baseline_cash(close: pd.DataFrame, reb_times: pd.DatetimeIndex) -> pd.DataFrame:
    return pd.DataFrame(0.0, index=reb_times, columns=close.columns)


def baseline_random(close: pd.DataFrame, reb_times: pd.DatetimeIndex, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    w = pd.DataFrame(0.0, index=reb_times, columns=close.columns)
    cols = list(close.columns)
    for t in reb_times:
        picks = rng.choice(cols, size=min(cfg.N_LONG, len(cols)), replace=False)
        w.loc[t, picks] = 1.0 / len(picks)
    return w


# --- A Cross-sectional momentum ---

def A_xs_mom(lookback_h: int = 24 * 30, n: int = cfg.N_LONG):
    def fn(close, reb_times):
        # use only past data: momentum = close/close.shift(lb) - 1 at reb time
        mom = close / close.shift(lookback_h) - 1
        scores = mom.reindex(reb_times)
        return _top_n_long(scores, n=n)
    return fn


# --- B Time-series momentum / MA ---

def B_ts_mom(fast: int = 24 * 20, slow: int = 24 * 100):
    def fn(close, reb_times):
        f = close.rolling(fast, min_periods=fast // 2).mean()
        s = close.rolling(slow, min_periods=slow // 2).mean()
        signal = (f > s).astype(float)
        # equal weight among assets in uptrend
        scores = signal.replace(0, np.nan)
        # rank by distance above MA
        dist = (close / s - 1).where(signal > 0)
        scores = dist.reindex(reb_times)
        return _top_n_long(scores, n=cfg.N_LONG)
    return fn


# --- C Mean reversion short-horizon ---

def C_mean_rev(lookback_h: int = 24, n: int = cfg.N_LONG):
    def fn(close, reb_times):
        # buy short-term losers
        ret = close / close.shift(lookback_h) - 1
        scores = (-ret).reindex(reb_times)
        return _top_n_long(scores, n=n)
    return fn


# --- D Vol breakout after compression ---

def D_vol_breakout(comp_h: int = 24 * 10, break_h: int = 24):
    def fn(close, reb_times):
        rets = close.pct_change()
        vol = rets.rolling(comp_h, min_periods=comp_h // 2).std()
        vol_rank = vol.rank(axis=1, pct=True)
        # compression: low vol rank, then positive breakout over break_h
        br = close / close.shift(break_h) - 1
        scores = br.where(vol_rank < 0.3)
        return _top_n_long(scores.reindex(reb_times), n=cfg.N_LONG)
    return fn


# --- E Relative strength / BTC→alt rotation ---

def E_btc_alt_rotation(lb: int = 24 * 14):
    def fn(close, reb_times):
        btc_cols = [c for c in close.columns if c.startswith("BTC-")]
        if not btc_cols:
            return pd.DataFrame(0.0, index=reb_times, columns=close.columns)
        btc = btc_cols[0]
        mom = close / close.shift(lb) - 1
        btc_mom = mom[btc]
        # if BTC mom > 0: hold alts with highest relative strength vs BTC; else cash/BTC
        rel = mom.subtract(btc_mom, axis=0)
        w = pd.DataFrame(0.0, index=reb_times, columns=close.columns)
        for t in reb_times:
            if t not in mom.index:
                continue
            bm = btc_mom.loc[t] if t in btc_mom.index else np.nan
            if pd.isna(bm):
                continue
            if bm <= 0:
                w.loc[t, btc] = 1.0  # risk-off to BTC
            else:
                row = rel.loc[t].drop(labels=[btc], errors="ignore").dropna()
                picks = row.sort_values(ascending=False).head(cfg.N_LONG).index
                if len(picks):
                    w.loc[t, picks] = 1.0 / len(picks)
        return w
    return fn


# --- F Cross-sectional reversal ---

def F_xs_reversal(lb: int = 24 * 7, n: int = cfg.N_LONG):
    def fn(close, reb_times):
        ret = close / close.shift(lb) - 1
        scores = (-ret).reindex(reb_times)  # buy recent losers xs
        return _top_n_long(scores, n=n)
    return fn


# --- G Volume surge ---

def G_volume_surge(vol_lb: int = 24 * 20, ret_lb: int = 24):
    def fn(close, reb_times, quote_vol=None):
        # weights_fn signature is (close, reb_times); volume attached via closure if needed
        # Use dollar volume proxy from close*proxy — actual quote_vol injected in tournament
        raise NotImplementedError
    return fn


def make_G(quote_vol: pd.DataFrame, vol_lb: int = 24 * 20, ret_lb: int = 24):
    def fn(close, reb_times):
        adv = quote_vol.rolling(vol_lb, min_periods=vol_lb // 2).mean()
        surge = (quote_vol / adv).replace([np.inf, -np.inf], np.nan)
        mom = close / close.shift(ret_lb) - 1
        # volume surge with positive short mom
        scores = (surge * mom).where(surge > 2.0).where(mom > 0)
        return _top_n_long(scores.reindex(reb_times), n=cfg.N_LONG)
    return fn


# --- H Funding → spot (needs funding series) ---

def make_H(funding: pd.DataFrame | None):
    """If funding available: when funding very positive, reduce risk / prefer under-funded alts.
    Spot-only approximation: if BTC funding > threshold, hold cash; if negative, hold BTC+alts mom.
    """
    def fn(close, reb_times):
        w = pd.DataFrame(0.0, index=reb_times, columns=close.columns)
        btc_cols = [c for c in close.columns if c.startswith("BTC-")]
        if funding is None or funding.empty or not btc_cols:
            return w  # stub empty → cash
        btc = btc_cols[0]
        f = funding.set_index("ts")["funding_rate"].sort_index()
        f_h = f.reindex(close.index, method="ffill")
        mom = close / close.shift(24 * 7) - 1
        for t in reb_times:
            fr = f_h.loc[t] if t in f_h.index else np.nan
            if pd.isna(fr):
                continue
            if fr > 0.0005:  # crowded long → cash
                continue
            elif fr < 0:
                # negative funding → longs paid → hold top mom
                row = mom.loc[t].dropna().sort_values(ascending=False).head(cfg.N_LONG)
                if len(row):
                    w.loc[t, row.index] = 1.0 / len(row)
            else:
                w.loc[t, btc] = 1.0
        return w
    return fn


# --- I BTC regime filter on base strat ---

def make_I(base_fn, btc_ma: int = 24 * 100):
    """Pre-registered: only take base weights when BTC > MA; else cash."""
    def fn(close, reb_times):
        base = base_fn(close, reb_times)
        btc_cols = [c for c in close.columns if c.startswith("BTC-")]
        if not btc_cols:
            return base * 0
        btc = btc_cols[0]
        ma = close[btc].rolling(btc_ma, min_periods=btc_ma // 2).mean()
        risk_on = (close[btc] > ma).reindex(reb_times).fillna(False)
        out = base.copy()
        out.loc[~risk_on] = 0.0
        return out
    return fn


# --- J Pairs ---

def J_pairs(pair=("ETH-USDT", "BTC-USDT"), mode="meanrev", lb=24 * 14):
    def fn(close, reb_times):
        w = pd.DataFrame(0.0, index=reb_times, columns=close.columns)
        a, b = pair
        if a not in close.columns or b not in close.columns:
            # try fuzzy
            def find(pfx):
                for c in close.columns:
                    if c.startswith(pfx.split("-")[0] + "-"):
                        return c
                return None
            a = find(a) or a
            b = find(b) or b
        if a not in close.columns or b not in close.columns:
            return w
        ratio = close[a] / close[b]
        mu = ratio.rolling(lb, min_periods=lb // 2).mean()
        sd = ratio.rolling(lb, min_periods=lb // 2).std()
        z = (ratio - mu) / sd.replace(0, np.nan)
        for t in reb_times:
            if t not in z.index or pd.isna(z.loc[t]):
                continue
            zv = z.loc[t]
            if mode == "meanrev":
                if zv < -1.0:
                    w.loc[t, a] = 0.5  # a cheap vs b
                    # spot: can't short b; hold a + cash
                elif zv > 1.0:
                    w.loc[t, b] = 0.5
            else:  # momentum of ratio
                if zv > 0.5:
                    w.loc[t, a] = 0.5
                elif zv < -0.5:
                    w.loc[t, b] = 0.5
        return w
    return fn


def build_variants(quote_vol: pd.DataFrame | None = None, funding: pd.DataFrame | None = None) -> list[Variant]:
    """Few variants per family. quote_vol/funding injected at tournament time."""
    variants: list[Variant] = [
        Variant("BTC_buyhold", "BASE", "btc_bh", baseline_btc_bh, "BTC 100% hold"),
        Variant("equal_weight", "BASE", "ew", baseline_equal_weight, "Equal-weight universe"),
        Variant("cash", "BASE", "cash", baseline_cash, "100% cash"),
        Variant("random_top5", "BASE", "random", baseline_random, "Random top-5 long"),
        Variant("A_mom_30d", "A", "mom_30d_top5", A_xs_mom(24 * 30, 5), "XS mom 30d"),
        Variant("A_mom_7d", "A", "mom_7d_top5", A_xs_mom(24 * 7, 5), "XS mom 7d"),
        Variant("B_ma_20_100", "B", "ma_20_100", B_ts_mom(24 * 20, 24 * 100), "TS MA cross"),
        Variant("C_mr_24h", "C", "mr_24h", C_mean_rev(24, 5), "24h mean-rev"),
        Variant("C_mr_72h", "C", "mr_72h", C_mean_rev(72, 5), "72h mean-rev"),
        Variant("D_vol_break", "D", "comp10d_brk1d", D_vol_breakout(), "Vol compression breakout"),
        Variant("E_btc_alt", "E", "rot_14d", E_btc_alt_rotation(24 * 14), "BTC→alt rotation"),
        Variant("F_rev_7d", "F", "rev_7d", F_xs_reversal(24 * 7, 5), "XS reversal 7d"),
        Variant("I_mom_btc_filter", "I", "A30d_btc_ma", make_I(A_xs_mom(24 * 30, 5)), "A mom + BTC MA regime"),
        Variant("J_eth_btc_mr", "J", "eth_btc_mr", J_pairs(("ETH-USDT", "BTC-USDT"), "meanrev"), "ETH/BTC mean-rev"),
        Variant("J_sol_eth_mr", "J", "sol_eth_mr", J_pairs(("SOL-USDT", "ETH-USDT"), "meanrev"), "SOL/ETH mean-rev"),
        Variant("J_eth_btc_mom", "J", "eth_btc_mom", J_pairs(("ETH-USDT", "BTC-USDT"), "mom"), "ETH/BTC mom"),
    ]
    if quote_vol is not None:
        variants.append(Variant("G_vol_surge", "G", "surge2x_pos", make_G(quote_vol), "Volume surge + pos mom"))
    else:
        variants.append(Variant("G_vol_surge", "G", "surge2x_pos", A_xs_mom(24), "PLACEHOLDER until vol loaded"))
    if funding is not None and len(funding):
        variants.append(Variant("H_funding_spot", "H", "btc_funding", make_H(funding), "Funding→spot risk"))
    else:
        variants.append(
            Variant(
                "H_funding_spot",
                "H",
                "stub",
                make_H(None),
                "STUB: funding series missing or empty",
            )
        )
    return variants
