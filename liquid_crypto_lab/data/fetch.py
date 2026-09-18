"""Ingest liquid universe + hourly OHLCV from free public APIs (OKX primary)."""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

import pandas as pd
import requests

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.data import store
from liquid_crypto_lab.data.probe import probe_sources

STABLE_BASES = cfg.EXCLUDE_STABLES
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "liquid-crypto-lab/0.1 (research; paper-only)"})


def _okx_get(path: str, params: dict | None = None, retries: int = 4) -> dict:
    url = f"https://www.okx.com{path}"
    last = None
    for i in range(retries):
        try:
            r = SESSION.get(url, params=params, timeout=45)
            if r.status_code == 429:
                time.sleep(1.5 * (i + 1))
                continue
            r.raise_for_status()
            j = r.json()
            if j.get("code") not in ("0", 0, None) and j.get("code") != "0":
                # OKX uses string "0"
                if str(j.get("code")) != "0":
                    raise RuntimeError(f"OKX error: {j}")
            return j
        except Exception as e:
            last = e
            time.sleep(0.5 * (i + 1))
    raise RuntimeError(f"OKX failed {path}: {last}")


def select_universe(n: int = cfg.TARGET_UNIVERSE) -> list[dict[str, Any]]:
    """Top liquid OKX USDT spot pairs by 24h quote volume, no stables."""
    tickers = _okx_get("/api/v5/market/tickers", {"instType": "SPOT"})["data"]
    rows = []
    for t in tickers:
        inst = t["instId"]
        if not inst.endswith("-USDT"):
            continue
        base = inst.split("-")[0]
        if base in STABLE_BASES or base.endswith("USD"):
            continue
        try:
            vol = float(t.get("volCcy24h") or 0)
            last = float(t.get("last") or 0)
        except (TypeError, ValueError):
            continue
        if vol < cfg.MIN_ADV_USD:
            continue
        rows.append(
            {
                "symbol": inst,
                "base": base,
                "quote": "USDT",
                "last": last,
                "adv_usd_approx": vol,
                "source": "okx_spot",
            }
        )
    rows.sort(key=lambda x: x["adv_usd_approx"], reverse=True)
    # Prefer majors + diversity: take top n
    selected = rows[:n]
    return selected


def fetch_ohlcv_okx(inst_id: str, target_bars: int = 28000) -> pd.DataFrame:
    """Paginate OKX history-candles (1H). Columns: ts,o,h,l,c,volume,quote_volume."""
    allc: list[list] = []
    after = None
    while len(allc) < target_bars:
        params: dict[str, Any] = {"instId": inst_id, "bar": "1H", "limit": 100}
        if after is not None:
            params["after"] = after
        j = _okx_get("/api/v5/market/history-candles", params)
        data = j.get("data") or []
        if not data:
            break
        allc.extend(data)
        after = data[-1][0]
        if len(data) < 100:
            break
        time.sleep(cfg.OKX_SLEEP_S)
    if not allc:
        return pd.DataFrame(columns=["ts", "open", "high", "low", "close", "volume", "quote_volume"])
    # OKX: [ts, o, h, l, c, vol, volCcy, volCcyQuote, confirm]
    rows = []
    seen = set()
    for row in allc:
        ts = int(row[0])
        if ts in seen:
            continue
        seen.add(ts)
        rows.append(
            {
                "ts": datetime.fromtimestamp(ts / 1000, tz=timezone.utc),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "quote_volume": float(row[6]) if len(row) > 6 else float(row[5]) * float(row[4]),
            }
        )
    df = pd.DataFrame(rows).sort_values("ts").drop_duplicates("ts").reset_index(drop=True)
    return df


def fetch_funding_history(inst_swap: str = "BTC-USDT-SWAP", max_pages: int = 40) -> pd.DataFrame:
    """OKX public funding-rate history (8h). Stub-friendly if thin."""
    allr: list[dict] = []
    after = None
    for _ in range(max_pages):
        params: dict[str, Any] = {"instId": inst_swap, "limit": 100}
        if after is not None:
            params["after"] = after
        try:
            j = _okx_get("/api/v5/public/funding-rate-history", params)
        except Exception:
            break
        data = j.get("data") or []
        if not data:
            break
        allr.extend(data)
        after = data[-1]["fundingTime"]
        time.sleep(cfg.OKX_SLEEP_S)
        if len(data) < 100:
            break
    if not allr:
        return pd.DataFrame()
    df = pd.DataFrame(allr)
    df["ts"] = pd.to_datetime(df["fundingTime"].astype(int), unit="ms", utc=True)
    df["funding_rate"] = df["fundingRate"].astype(float)
    return df[["ts", "funding_rate", "instId"]].sort_values("ts").drop_duplicates("ts")


def run_fetch(max_assets: int | None = None, target_bars: int = 28000) -> dict[str, Any]:
    store.ensure_dirs()
    probe = probe_sources()
    store.write_meta("source_probe.json", probe)

    n = max_assets or cfg.TARGET_UNIVERSE
    universe = select_universe(n)
    store.write_meta("universe.json", {"selected": universe, "n": len(universe), "rule": "top_adv_usdt_excl_stables"})

    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _one(u):
        sym = u["symbol"]
        df = fetch_ohlcv_okx(sym, target_bars=target_bars)
        if len(df) < cfg.MIN_HISTORY_BARS:
            return {"symbol": sym, "rows": len(df), "status": "too_short", "adv_usd_approx": u["adv_usd_approx"]}
        store.save_ohlcv(sym, df)
        return {
            "symbol": sym,
            "rows": len(df),
            "start": str(df["ts"].iloc[0]),
            "end": str(df["ts"].iloc[-1]),
            "adv_usd_approx": u["adv_usd_approx"],
            "status": "ok",
        }

    stats = []
    # 3 workers to respect rate limits while cutting wall time
    with ThreadPoolExecutor(max_workers=3) as ex:
        futs = {ex.submit(_one, u): u for u in universe}
        done = 0
        for fut in as_completed(futs):
            done += 1
            u = futs[fut]
            try:
                st = fut.result()
                stats.append(st)
                print(f"[{done}/{len(universe)}] {st['symbol']}: {st['status']} rows={st.get('rows')}", flush=True)
            except Exception as e:
                stats.append({"symbol": u["symbol"], "rows": 0, "status": f"error:{e}"})
                print(f"[{done}/{len(universe)}] FAIL {u['symbol']}: {e}", flush=True)

    # Funding for strategy H
    print("fetching BTC funding history...", flush=True)
    try:
        fdf = fetch_funding_history("BTC-USDT-SWAP", max_pages=50)
        if len(fdf):
            path = cfg.PROCESSED / "funding_BTC_USDT_SWAP.parquet"
            fdf.to_parquet(path, index=False)
            funding_meta = {"rows": len(fdf), "start": str(fdf["ts"].iloc[0]), "end": str(fdf["ts"].iloc[-1])}
        else:
            funding_meta = {"rows": 0, "note": "empty"}
    except Exception as e:
        funding_meta = {"rows": 0, "error": str(e)}

    ok = [s for s in stats if s["status"] == "ok"]
    summary = {
        "n_requested": len(universe),
        "n_ok": len(ok),
        "stats": stats,
        "funding": funding_meta,
        "probe_ok": [p["name"] for p in probe if p["ok"]],
        "probe_fail": [p["name"] for p in probe if not p["ok"]],
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "granularity": "1H",
        "primary_source": "okx_public_history_candles",
        "survivorship_note": (
            "Universe = current top ADV at fetch time (point-in-time snapshot). "
            "Not historical reconstitutions — survivorship bias present; documented."
        ),
    }
    store.write_meta("fetch_summary.json", summary)
    store.write_meta(
        "splits.json",
        {
            "train_end": cfg.TRAIN_END,
            "val_start": cfg.VAL_START,
            "val_end": cfg.VAL_END,
            "oos_start": cfg.OOS_START,
            "rationale": "OKX hourly history from ~2023-07; train through 2024-H1, val 2024-H2, OOS 2025+",
        },
    )
    print(f"DONE: {len(ok)}/{len(universe)} assets", flush=True)
    return summary
