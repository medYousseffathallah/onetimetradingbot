from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal as D

import pytest

from bvmt_v2.backtester import EXIT_POLICIES, FAMILIES, Backtester, Bar, Book, Order, folds


def tape(n=92, ids=("A", "B"), delayed=False):
    sessions = tuple(date(2026, 1, 1) + timedelta(days=i) for i in range(n))
    bars = {}
    for number, ident in enumerate(ids):
        rows = []
        for i, session in enumerate(sessions):
            close = D(10 + number) + D(i) / 100
            available = datetime.combine(sessions[-1] if delayed else session, time(12), UTC)
            rows.append(Bar(session, close, close, D(100000), 10000, "traded", available))
        bars[ident] = tuple(rows)
    return Backtester(sessions, bars, frozenset(ids))


def test_folds_and_training_purge():
    f = folds(202, 10)
    assert len(f) == 14
    assert (f[0].decision, f[0].entry, f[0].end) == (61, 62, 71)
    assert f[0].last_training_decision + 10 < f[0].decision - 1
    assert all(a.end < b.entry for a, b in zip(f, f[1:], strict=False))


def test_golden_cash_and_fills():
    bt = tape()
    bar = bt.series["A"][62]
    b = Book(D("1000"))
    # Decision-time share request is already capped at 10% trailing volume.
    o = Order("A", "BUY", 1000, 8)
    b.execute(o, bar, 62, D(0), 0, 10_000, D(1000))
    assert b.fills[0].quantity == 8
    assert b.fills[0].price == D("10.620")
    assert b.fills[0].fee == D("0.425")
    assert b.cash == D("914.615")
    b.execute(Order("B", "BUY", 200, 1000), bar, 62, D(0), 0, 10000, D(1000))
    assert b.fills[-1].quantity == 9
    b.execute(Order("B", "SELL", 9, 1000), bar, 63, D(0), 3, 30, D(1000))
    assert b.fills[-1].quantity == 3
    assert b.unsettled[66] == D("31.701")
    before = b.cash
    b.settle(65)
    assert b.cash == before
    b.settle(66)
    assert b.cash == before + D("31.701")


@pytest.mark.parametrize(
    "volume,status,opening,closing",
    [
        (0, "traded", 10, 10),
        (100, "untraded", 10, 10),
        (100, "traded", 0, 10),
        (100, "traded", 10, 0),
    ],
)
def test_invalid_bar_never_fills(volume, status, opening, closing):
    b = Book(D(1000))
    bar = Bar(date(2026, 1, 1), D(opening), D(closing), D(0), volume, status, None)
    b.execute(Order("A", "BUY", 5, 10), bar, 1, D(0), 0, volume, D(1000))
    assert b.cash == 1000 and not b.fills


def test_single_cash_pool_and_session_capacity():
    b = Book(D(100))
    bar = tape().series["A"][62]
    for i in range(20):
        b.execute(Order(str(i), "BUY", 100, 100), bar, 62, D(100), 0, 10000, D(1000))
    assert D(0) <= b.cash < bar.open
    assert sum(f.gross + f.fee for f in b.fills) + b.cash == 100
    b = Book(D(1000))
    for _ in range(2):
        b.execute(Order("A", "BUY", 6, 8), bar, 62, D(0), 0, 80, D(1000))
    assert b.quantity["A"] == 8


def test_next_open_and_exclusion_rerun():
    bt = tape()
    report = bt.run("BL-EW-CHAL", 10)
    sim = bt.simulate("BL-EW-CHAL", 10)
    assert sim.book.fills[0].session_index == 62
    assert report.top1_excluded_instrument
    rerun = bt.simulate("BL-EW-CHAL", 10, excluded=report.top1_excluded_instrument)
    assert report.top1_excluded_return_pct.value == rerun.net
    assert bt.run("BL-EW-CHAL", 10) == report


def test_availability_delayed_and_phase_sweep():
    assert not tape(delayed=True).simulate("BL-EW-CHAL", 10).book.fills
    bt = tape(110)
    for cadence in (5, 10, 19, 20):
        sensitivity = bt.phase_sensitivity("BL-MOM20", min(10, cadence), cadence=cadence)
        assert len(sensitivity.phase_returns) == cadence
        assert sensitivity.minimum.value <= sensitivity.median.value <= sensitivity.maximum.value
        assert sensitivity.iqr_pp.value == sensitivity.p75.value - sensitivity.p25.value
    with pytest.raises(ValueError, match="overlapping fold"):
        folds(110, 10, cadence=5)


def test_strategy_and_exit_suite():
    bt = tape()
    for family in FAMILIES:
        report = bt.run(family, 10)
        assert report.provenance_status == "SIMULATED"
    reports = bt.compare_exit_policies("A", 10)
    assert set(reports) == set(EXIT_POLICIES)
    assert all(r.feasibility_pct.value == 100 for r in reports.values())
    assert reports["fixed_horizon"].missed_subsequent_upside_pct.value == 0


def test_gap_slippage_and_both_capacity_limits():
    from dataclasses import replace

    data = tape(85, ("A",))
    rows = list(data.series["A"])
    # At t close only the trailing 20-session median volume of 130 is visible.
    for i in range(42, 62):
        rows[i] = replace(rows[i], volume=130)
    # Open gaps; the completed day's low capacity clips 13 requested shares to 8.
    rows[62] = replace(rows[62], open=D("12.000"), close=D("9.000"), volume=80)
    bt = Backtester(data.sessions, {"A": tuple(rows)}, data.challenge)
    sim = bt.simulate("BL-EW-CHAL", 10, bps=D(100))
    first = sim.book.fills[0]
    assert (first.price, first.gross, first.fee, first.quantity) == (
        D("12.120"),
        D("96.960"),
        D("0.485"),
        8,
    )
    assert sim.equities[2] == D("49974.555")
    rows[62] = replace(rows[62], volume=10000)
    bt = Backtester(data.sessions, {"A": tuple(rows)}, data.challenge)
    assert bt.simulate("BL-EW-CHAL", 10).book.fills[0].quantity == 13


def test_awakening_requires_a_positive_direction_and_prior_volume():
    from dataclasses import replace

    original = tape(74, ("A",))
    series = list(original.series["A"])
    series[61] = replace(series[61], volume=35000)

    def evaluate():
        bt = Backtester(original.sessions, {"A": tuple(series)}, original.challenge)
        return bt.simulate("V2-G-AWAKENING", 10).book.fills

    assert evaluate()
    series[61] = replace(series[61], close=series[60].close)
    assert not evaluate()
    series[61] = replace(series[61], close=D("12"))
    for i in range(41, 47):
        series[i] = replace(series[i], volume=0)
    assert not evaluate()


def test_trailing_profit_uses_next_open_after_a_drop():
    from dataclasses import replace

    orig = tape(74, ("A",))
    rows = list(orig.series["A"])
    for i, price in [(63, "14"), (64, "13"), (65, "13.1"), (72, "15")]:
        rows[i] = replace(rows[i], close=D(price), open=D(price))
    bt = Backtester(orig.sessions, {"A": tuple(rows)}, orig.challenge)
    results = bt.compare_exit_policies("A", 10)
    trail = results["trailing_profit_5pct"]
    assert trail.false_exit_rate_pct.value == 100
    assert trail.missed_subsequent_upside_pct.value > 0
    assert trail.net_return_pct.value < results["fixed_horizon"].net_return_pct.value
    assert trail.feasibility_pct.value == 100
