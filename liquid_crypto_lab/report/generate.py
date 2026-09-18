"""Write or refresh reports/liquid_crypto_lab_v1.md from frozen CSVs/meta."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.data import store


def write_report() -> Path:
    """If a full v1 report already exists with fail_reason columns in CSV, keep/refresh header.
    Prefer the shipped release report; this CLI regenerates a summary from CSV if needed.
    """
    store.ensure_dirs()
    path = cfg.REPORTS / "liquid_crypto_lab_v1.md"
    tcsv = cfg.REPORTS / "tournament_v1.csv"
    if path.exists() and tcsv.exists():
        df = pd.read_csv(tcsv)
        # Refresh generation stamp only if report already complete (has section A)
        text = path.read_text()
        if "## A. Data source review" in text and "fail_reason" in df.columns:
            # bump generated timestamp line
            lines = text.splitlines()
            out = []
            for line in lines:
                if line.startswith("**Generated:**"):
                    out.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()} UTC (refresh)")
                else:
                    out.append(line)
            path.write_text("\n".join(out) + "\n")
            return path
    # Fallback minimal stub pointing operator to re-run release postprocess
    path.write_text(
        "# Liquid Crypto Lab v1\n\n"
        "Full A–H report missing or CSV incomplete. "
        "Ensure `tournament_v1.csv` has fail_reason columns and re-run release postprocess.\n"
    )
    return path
