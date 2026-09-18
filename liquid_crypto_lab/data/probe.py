"""Document which free sources work from this IP."""
from __future__ import annotations

import time
from typing import Any

import requests

PROBES = [
    ("binance_klines", "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=1"),
    ("okx_candles", "https://www.okx.com/api/v5/market/candles?instId=BTC-USDT&bar=1H&limit=1"),
    ("bybit_kline", "https://api.bybit.com/v5/market/kline?category=spot&symbol=BTCUSDT&interval=60&limit=1"),
    ("kraken_ohlc", "https://api.kraken.com/0/public/OHLC?pair=XBTUSD&interval=60"),
    ("coinbase_candles", "https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=3600"),
    ("coingecko_markets", "https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&per_page=1&page=1"),
    ("defillama_protocols", "https://api.llama.fi/protocols"),
    ("okx_funding", "https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=1"),
]


def probe_sources(timeout: float = 20.0) -> list[dict[str, Any]]:
    results = []
    for name, url in PROBES:
        t0 = time.time()
        try:
            r = requests.get(url, timeout=timeout)
            body = r.text[:180].replace("\n", " ")
            results.append(
                {
                    "name": name,
                    "status": r.status_code,
                    "ok": r.status_code == 200,
                    "ms": int((time.time() - t0) * 1000),
                    "snippet": body,
                }
            )
        except Exception as e:
            results.append(
                {"name": name, "status": None, "ok": False, "ms": None, "snippet": str(e)[:180]}
            )
        time.sleep(0.2)
    return results
