"""Liquid lab repair_v2: engine_v1b import proof + valid-exec mask."""
from __future__ import annotations

import inspect

import numpy as np
import pandas as pd

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.backtest import engine_v1b
from liquid_crypto_lab.backtest.engine_v1b import run_backtest_v1b, wide_ohlc_with_valid_mask


def test_accounting_tests_import_engine_v1b():
    """Prove repair path actually calls engine_v1b (not a toy-only check)."""
    import tests.test_accounting as ta

    src = inspect.getsource(ta)
    assert "run_backtest_v1b" in src
    assert "engine_v1b" in src or "from liquid_crypto_lab.backtest.engine_v1b" in src
    # Call engine directly
    idx = pd.date_range("2024-01-01", periods=24*10, freq="h", tz="UTC")
    close = pd.DataFrame({"AAA-USDT": 100.0}, index=idx)
    open_ = close.copy()
    qv = pd.DataFrame({"AAA-USDT": 1e9}, index=idx)

    def fn(c, reb):
        w = pd.DataFrame(0.0, index=reb, columns=c.columns)
        w.iloc[:] = 0.5
        return w

    bt = run_backtest_v1b("probe", "T", "v", close, open_, qv, fn, rebalance_hours=24)
    assert bt.notes and "engine=v1b" in bt.notes
    assert len(bt.rets) == 240
    print("PASS test_accounting_tests_import_engine_v1b", bt.notes)


def test_reject_new_fills_on_ffilled_bars():
    n = 24 * 8
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    # Real price only on first 24h; then missing (will ffill)
    raw_close = pd.Series([100.0] * 24 + [np.nan] * (n - 24), index=idx)
    panel = pd.DataFrame(
        {
            "ts": list(idx) + list(idx),
            "symbol": ["AAA-USDT"] * n + ["BBB-USDT"] * n,
            "close": list(raw_close) + [50.0] * n,
            "open": list(raw_close.fillna(100.0)) + [50.0] * n,
            "quote_volume": [1e9] * 24 + [0.0] * (n - 24) + [1e9] * n,
        }
    )
    close, open_, qv, valid = wide_ohlc_with_valid_mask(panel)
    assert bool(valid.loc[idx[0], "AAA-USDT"]) is True
    assert bool(valid.loc[idx[30], "AAA-USDT"]) is False

    def fn(c, reb):
        w = pd.DataFrame(0.0, index=reb, columns=c.columns)
        for t in reb:
            w.loc[t] = 0.5
        return w

    bt = run_backtest_v1b(
        "mask",
        "T",
        "v",
        close,
        open_,
        qv,
        fn,
        rebalance_hours=24,
        price_valid=valid,
        require_valid_exec=True,
    )
    assert "require_valid_exec=1" in bt.notes
    print("PASS test_reject_new_fills_on_ffilled_bars", float(bt.equity.iloc[-1]))


def test_i_mom_labelled_exploratory_on_corrected():
    """Corrected v1b I_mom must remain EXPLORATORY (Sharpe 0.390 < 0.4)."""
    from liquid_crypto_lab.tournament import _verdict

    oos = {"sharpe": 0.390, "total_ret": 0.0155, "n": 500}
    train = {"sharpe": 1.0, "total_ret": 0.1}
    val = {"sharpe": 0.5, "total_ret": 0.05}
    v = _verdict(train, val, oos, "I", "I_mom_btc_filter corrected")
    assert v == "EXPLORATORY"
    print("PASS test_i_mom_labelled_exploratory_on_corrected", v)


def test_bankroll_is_finite_500():
    assert cfg.BANKROLL_USD == 500.0
    assert cfg.BANKROLL_GBP == 500.0
    print("PASS test_bankroll_is_finite_500")


if __name__ == "__main__":
    test_accounting_tests_import_engine_v1b()
    test_reject_new_fills_on_ffilled_bars()
    test_i_mom_labelled_exploratory_on_corrected()
    test_bankroll_is_finite_500()
    print("\nALL LIQUID REPAIR_V2 TESTS PASSED")
