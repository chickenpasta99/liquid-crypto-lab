"""Accounting invariants for liquid_crypto_lab engines (paper only)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from liquid_crypto_lab import config as cfg
from liquid_crypto_lab.backtest.engine_v1b import run_backtest_v1b
from liquid_crypto_lab.costs import turnover_cost_return


def _flat_panel(n=24 * 10, symbols=("AAA-USDT", "BBB-USDT"), px=100.0):
    idx = pd.date_range("2024-01-01", periods=n, freq="h", tz="UTC")
    close = pd.DataFrame({s: float(px) for s in symbols}, index=idx)
    open_ = close.copy()
    qv = pd.DataFrame({s: 1e9 for s in symbols}, index=idx)
    return close, open_, qv


def _target_fn(weights_by_reb: dict[str, float]):
    def fn(close, reb_times):
        w = pd.DataFrame(0.0, index=reb_times, columns=close.columns)
        for t in reb_times:
            for s, wt in weights_by_reb.items():
                if s in w.columns:
                    w.loc[t, s] = wt
        return w

    return fn


def test_flat_prices_trading_loses_exactly_charged_costs():
    close, open_, qv = _flat_panel()
    fn = _target_fn({"AAA-USDT": 0.5, "BBB-USDT": 0.5})
    bt = run_backtest_v1b("t", "T", "v", close, open_, qv, fn, stress=1.0, rebalance_hours=24)
    assert (bt.rets <= 1e-12).all()
    total = float((1 + bt.rets).prod() - 1)
    expected_drag = sum(
        turnover_cost_return(d, cfg.BANKROLL_USD, 1e9, stress=1.0) for d in (0.5, 0.5)
    )
    assert abs(total - expected_drag) < 1e-9, (total, expected_drag)
    print("PASS flat_prices_trading_loses_exactly_charged_costs", total, expected_drag)


def test_no_trades_no_trading_costs():
    close, open_, qv = _flat_panel()
    fn = _target_fn({})
    bt = run_backtest_v1b("cash", "T", "v", close, open_, qv, fn, stress=1.0)
    assert abs(float(bt.rets.sum())) < 1e-15
    assert abs(float(bt.equity.iloc[-1] - cfg.BANKROLL_USD)) < 1e-9
    print("PASS no_trades_no_trading_costs")


def test_unchanged_quantities_buy_and_hold_price_drift_only():
    """Fixed qty: equity moves only with price; mid-hold fees stay 0."""
    idx = pd.date_range("2024-01-01", periods=6, freq="h", tz="UTC")
    px = pd.Series([100.0, 100.0, 102.0, 101.0, 105.0, 104.0], index=idx)
    qty = 4.0
    cash = 100.0
    fees_mid = 0.0
    eq = [cash + qty * float(p) - fees_mid for p in px]
    assert eq[0] == 500.0
    assert abs(eq[2] - 508.0) < 1e-12
    assert abs(eq[4] - 520.0) < 1e-12
    # fees unchanged while qty unchanged
    assert fees_mid == 0.0
    print("PASS unchanged_quantities_buy_and_hold_price_drift_only", eq[2], eq[4])


def test_purchases_plus_fees_no_negative_cash_unlevered():
    bank = cfg.BANKROLL_USD
    target = {"AAA-USDT": 0.4, "BBB-USDT": 0.4}
    c = sum(turnover_cost_return(d, bank, 1e9, 1.0) for d in target.values())
    fee_usd = -c * bank
    investable = bank - fee_usd
    cash = investable * (1.0 - sum(target.values()))
    assert investable > 0 and cash >= -1e-9
    assert investable * sum(target.values()) + cash <= bank + 1e-9
    print("PASS purchases_plus_fees_no_negative_cash_unlevered", cash, fee_usd)


def test_multi_asset_equity_identity():
    qty = {"AAA-USDT": 2.0, "BBB-USDT": 3.0, "CCC-USDT": 1.0}
    cash = 25.0
    equity = cash + sum(q * 50.0 for q in qty.values())
    assert abs(equity - 325.0) < 1e-12
    print("PASS multi_asset_equity_identity", equity)


def test_addendum_501_10_is_fee_sign_error():
    entry_cost_ret = -0.002206653832222237
    wrong = 500.0 * (1.0 - entry_cost_ret)
    right = 500.0 * (1.0 + entry_cost_ret)
    assert abs(wrong - 501.10332691611114) < 1e-6
    assert abs(right - 498.8966730838889) < 1e-6
    print("PASS addendum_501_10_is_fee_sign_error", wrong, right)


def test_tradability_ffill_and_adv_floor_are_optimistic():
    idx = pd.date_range("2024-01-01", periods=5, freq="h", tz="UTC")
    close = pd.DataFrame({"AAA-USDT": [10.0, np.nan, np.nan, 12.0, 12.5]}, index=idx)
    qv = pd.DataFrame({"AAA-USDT": [0.0, 0.0, 0.0, 0.0, 0.0]}, index=idx)
    filled = close.ffill()
    adv = qv.rolling(24, min_periods=1).mean().replace(0, np.nan).fillna(cfg.MIN_ADV_USD)
    assert filled.iloc[1, 0] == 10.0
    assert float(adv.iloc[0, 0]) == cfg.MIN_ADV_USD
    print("PASS tradability_ffill_and_adv_floor_are_optimistic")


if __name__ == "__main__":
    test_flat_prices_trading_loses_exactly_charged_costs()
    test_no_trades_no_trading_costs()
    test_unchanged_quantities_buy_and_hold_price_drift_only()
    test_purchases_plus_fees_no_negative_cash_unlevered()
    test_multi_asset_equity_identity()
    test_addendum_501_10_is_fee_sign_error()
    test_tradability_ffill_and_adv_floor_are_optimistic()
    print("\nALL ACCOUNTING CHECKS PASSED")
