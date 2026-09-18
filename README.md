# Liquid Crypto Lab

**Paper research only.** Systematic strategy tournament across liquid spot crypto for a UK experimental ~£500 bankroll.

- No live trading, no API keys for trading, no paid APIs without approval.
- Independent of `/workspace/strategy-lab` (Solana/memecoin lab) — do not merge results.

## CLI

```bash
source .venv/bin/activate
python -m liquid_crypto_lab fetch
python -m liquid_crypto_lab tournament
python -m liquid_crypto_lab report
```

## Data

Primary: OKX public spot klines (hourly). CoinGecko/Binance/Bybit probed; see report §A for blockers.

## License

Research / educational. Not financial advice.
