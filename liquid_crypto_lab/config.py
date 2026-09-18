"""Frozen configuration for Liquid Crypto Lab v1."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RAW = DATA / "raw"
PROCESSED = DATA / "processed"
META = DATA / "meta"
REPORTS = ROOT / "reports"

# --- Splits (frozen for v1; adjusted to OKX history starting ~2023-07) ---
TRAIN_END = "2024-06-30"  # inclusive end of train
VAL_START = "2024-07-01"
VAL_END = "2024-12-31"
OOS_START = "2025-01-01"
# Prospective = bars after STRATEGY_FREEZE_TS written at tournament time

# --- Cost model (frozen; documented in report) ---
# OKX-like taker ~10 bps; UK retail (Coinbase/Kraken) often higher — use 15 bps base.
TAKER_FEE_BPS = 15.0
# Half-spread estimate for liquid majors; scaled by ADV in slippage fn
HALF_SPREAD_BPS = 5.0
# Slippage: base + k * sqrt(notional / ADV_usd)
SLIPPAGE_BASE_BPS = 2.0
SLIPPAGE_K = 8.0  # bps when notional == ADV (scaled by sqrt)
MIN_ADV_USD = 2_000_000.0  # filter illiquid
COST_STRESS_MULTS = (1.0, 1.5, 2.0)

# --- Universe ---
TARGET_UNIVERSE = 70
MIN_HISTORY_BARS = 24 * 90  # ~90 days hourly before usable
EXCLUDE_STABLES = {
    "USDT", "USDC", "USD", "DAI", "TUSD", "FDUSD", "USDE", "USDD",
    "BUSD", "PYUSD", "EUR", "EURC", "USDP", "GUSD", "LUSD", "FRAX",
    "USTC", "USDJ", "AEUR", "EURI",
}
QUOTE = "USDT"

# --- Portfolio / bankroll ---
BANKROLL_GBP = 500.0
# Research assumption: GBP≈USD for sim simplicity (document)
BANKROLL_USD = 500.0
REBALANCE_HOURS = 24  # daily rebalance for cross-sectional
MAX_WEIGHT = 0.25
N_LONG = 5

# Rate limits
OKX_SLEEP_S = 0.05
