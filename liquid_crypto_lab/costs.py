"""Frozen transaction cost model."""
from __future__ import annotations

import numpy as np

from liquid_crypto_lab import config as cfg


def round_trip_cost_bps(
    notional_usd: float,
    adv_usd: float,
    stress: float = 1.0,
) -> float:
    """One-way entry OR exit cost in bps, then caller applies per trade side.

    Model (documented):
      one_way_bps = (taker + half_spread + slip) * stress
      slip = SLIPPAGE_BASE + SLIPPAGE_K * sqrt(notional / max(adv, 1))
    For £500 bankroll, notional per name is small vs ADV → slip near base.
    """
    adv = max(float(adv_usd), 1.0)
    notional = max(float(notional_usd), 0.0)
    slip = cfg.SLIPPAGE_BASE_BPS + cfg.SLIPPAGE_K * np.sqrt(notional / adv)
    one_way = (cfg.TAKER_FEE_BPS + cfg.HALF_SPREAD_BPS + slip) * float(stress)
    return float(one_way)


def turnover_cost_return(
    weight_delta_abs: float,
    equity_usd: float,
    adv_usd: float,
    stress: float = 1.0,
) -> float:
    """Portfolio return drag from trading |Δw| of equity (one-way on traded notional)."""
    traded = abs(weight_delta_abs) * equity_usd
    if traded <= 0:
        return 0.0
    bps = round_trip_cost_bps(traded, adv_usd, stress=stress)
    return -(bps / 10_000.0) * abs(weight_delta_abs)
