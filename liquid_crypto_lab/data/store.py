"""Parquet / JSON meta storage."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from liquid_crypto_lab import config as cfg


def ensure_dirs() -> None:
    for p in (cfg.RAW, cfg.PROCESSED, cfg.META, cfg.REPORTS):
        p.mkdir(parents=True, exist_ok=True)


def write_meta(name: str, obj: Any) -> Path:
    ensure_dirs()
    path = cfg.META / name
    path.write_text(json.dumps(obj, indent=2, default=str))
    return path


def read_meta(name: str) -> Any:
    return json.loads((cfg.META / name).read_text())


def save_ohlcv(symbol: str, df: pd.DataFrame) -> Path:
    ensure_dirs()
    path = cfg.PROCESSED / f"{symbol.replace('-', '_')}.parquet"
    df.to_parquet(path, index=False)
    return path


def load_ohlcv(symbol: str) -> pd.DataFrame:
    path = cfg.PROCESSED / f"{symbol.replace('-', '_')}.parquet"
    return pd.read_parquet(path)


def list_symbols() -> list[str]:
    return sorted(p.stem.replace("_", "-") for p in cfg.PROCESSED.glob("*.parquet"))


def load_panel(symbols: list[str] | None = None) -> pd.DataFrame:
    """Long-form panel: ts, symbol, open, high, low, close, volume, quote_volume."""
    syms = symbols or list_symbols()
    frames = []
    for s in syms:
        try:
            df = load_ohlcv(s)
            df["symbol"] = s
            frames.append(df)
        except Exception:
            continue
    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["ts"] = pd.to_datetime(out["ts"], utc=True)
    return out.sort_values(["ts", "symbol"]).reset_index(drop=True)
