"""CLI: fetch | tournament | report."""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="liquid_crypto_lab", description="Liquid Crypto Lab (paper research)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_fetch = sub.add_parser("fetch", help="Probe sources + ingest OHLCV")
    p_fetch.add_argument("--max-assets", type=int, default=None)
    p_fetch.add_argument("--bars", type=int, default=28000, help="Target hourly bars per asset")

    sub.add_parser("tournament", help="Run strategy tournament v1")
    sub.add_parser("report", help="Write reports/liquid_crypto_lab_v1.md")

    args = parser.parse_args(argv)

    if args.cmd == "fetch":
        from liquid_crypto_lab.data.fetch import run_fetch

        run_fetch(max_assets=args.max_assets, target_bars=args.bars)
        return 0
    if args.cmd == "tournament":
        from liquid_crypto_lab.tournament import run_tournament

        s = run_tournament()
        print(s)
        return 0
    if args.cmd == "report":
        from liquid_crypto_lab.report.generate import write_report

        path = write_report()
        print(f"Wrote {path}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
