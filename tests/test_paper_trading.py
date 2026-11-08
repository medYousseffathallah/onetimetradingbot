"""Forward journal accounting, cutoff isolation, persistence and failure cases."""

import csv
import json
from dataclasses import asdict, replace
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from bvmt.calendar import ExchangeSession, InstrumentRecord
from bvmt.data import DailyBar, format_canonical_csv
from bvmt.paper_trading import (
    PaperJournalState,
    _signal,
    load_or_init_paper_journal,
    record_forward_paper_signal,
)

D = Decimal


@pytest.fixture
def market(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    days = [date(2026, 1, 1) + timedelta(days=i) for i in range(66)]
    stamp = datetime(2025, 12, 31, tzinfo=UTC)
    bars = [
        DailyBar(
            "X",
            "X",
            day,
            D(10),
            D(20),
            D(5),
            D(10) + D(i) / 100,
            100000,
            D(1000000),
            "traded",
            "synthetic-fixture",
            stamp,
            stamp,
        )
        for i, day in enumerate(days)
    ]
    master = [
        InstrumentRecord(
            "X", None, "X", days[0], None, days[0], None, "principal", "TND", "fixture"
        )
    ]
    calendar = [
        ExchangeSession(
            day,
            True,
            "regular",
            datetime.combine(day, time(9), UTC),
            datetime.combine(day, time(14), UTC),
            "Africa/Tunis",
            "fixture",
        )
        for day in days
    ]
    paths = {
        "bars_path": tmp_path / "bars.csv",
        "instruments_path": tmp_path / "master.csv",
        "calendar_path": tmp_path / "calendar.csv",
    }
    for name, records in (("instruments_path", master), ("calendar_path", calendar)):
        rows = [
            {
                k: "" if v is None else v.isoformat() if hasattr(v, "isoformat") else v
                for k, v in asdict(r).items()
            }
            for r in records
        ]
        with paths[name].open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    clock = [datetime.combine(days[60], time(16), UTC)]
    monkeypatch.setattr("bvmt.paper_trading._now", lambda: clock[0])
    paths["bars_path"].write_text(format_canonical_csv(bars[:61]), encoding="utf-8")
    return {
        "paths": paths,
        "journal": tmp_path / "paper.json",
        "bars": bars,
        "master": master,
        "calendar": calendar,
        "clock": clock,
        "days": days,
    }


def advance(market: dict[str, Any], count: int) -> None:
    market["paths"]["bars_path"].write_text(
        format_canonical_csv(market["bars"][:count]), encoding="utf-8"
    )
    market["clock"][0] = datetime.combine(market["days"][count - 1], time(16), UTC)


def test_inception_is_cash_with_immutable_pending_signal(market: dict[str, Any]) -> None:
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    assert state.is_paper_only and not state.autonomous_trading_enabled
    assert state.cash_tnd == state.total_equity_tnd == "50000.000"
    assert state.holdings == {}
    assert len(state.equity_history) == len(state.signal_snapshots) == 1
    assert state.latest_settled_session == market["days"][60].isoformat()
    snapshot = state.signal_snapshots[0]
    assert len(snapshot.config_hash) == len(snapshot.data_hash) == len(snapshot.code_sha256) == 64
    assert snapshot.signal_timestamp == market["clock"][0].isoformat()
    assert len(state.orders) == 1
    order = state.orders[0]
    assert order.status == "PENDING_NEXT_SESSION" and order.filled_shares == 0
    assert order.execution_session_date is None
    assert order.remaining_shares == order.requested_shares
    before = market["journal"].read_bytes()
    again = record_forward_paper_signal(market["journal"], **market["paths"])
    assert asdict(again) == asdict(state)
    assert market["journal"].read_bytes() == before


def test_next_open_hand_accounting_and_snapshot_immutability(market: dict[str, Any]) -> None:
    first = load_or_init_paper_journal(market["journal"], **market["paths"])
    snapshot = asdict(first.signal_snapshots[0])
    requested = first.orders[0].requested_shares
    advance(market, 62)
    state = record_forward_paper_signal(market["journal"], **market["paths"])
    order = state.orders[0]
    assert order.status == "FILLED" and order.filled_shares == requested
    assert order.execution_session_date == market["days"][61].isoformat()
    assert D(order.execution_price_tnd or "0") == D("10.010")
    notional = D(requested) * D("10.010")
    fee = (notional * D(".005")).quantize(D(".001"))
    assert D(order.fee_tnd) == fee
    assert D(state.cash_tnd) == D(50000) - notional - fee
    assert D(state.average_cost_tnd["X"]) * requested == notional + fee
    assert D(state.total_equity_tnd) == D(state.cash_tnd) + requested * market["bars"][61].close
    assert asdict(state.signal_snapshots[0]) == snapshot
    assert state.signal_snapshots[0].intended_orders[0].status == "PENDING_NEXT_SESSION"
    assert len(state.signal_snapshots) == 2
    assert state.equity_history[-1]["cash_benchmark_equity_tnd"] == "50000.000"
    assert D(state.equity_history[-1]["equal_weight_benchmark_equity_tnd"]) > D(50000)


@pytest.mark.parametrize(
    "volume,status,expected,filled",
    [
        (100, "traded", "PARTIALLY_FILLED", 10),
        (0, "no_trade", "BLOCKED_ZERO_VOLUME", 0),
        (1, "traded", "EXPIRED", 0),
    ],
)
def test_capacity_and_no_carry(
    market: dict[str, Any], volume: int, status: str, expected: str, filled: int
) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    market["bars"][61] = replace(
        market["bars"][61], volume_shares=volume, turnover_tnd=D(volume * 10), status=status
    )
    advance(market, 64)
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    assert state.orders[0].status == expected
    assert state.orders[0].filled_shares == filled
    assert state.holdings.get("X", 0) == filled
    assert len(state.signal_snapshots) == 1
    assert len(state.equity_history) == 4


def test_missing_next_bar_expires_instead_of_filling_later(market: dict[str, Any]) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    advance(market, 64)
    market["paths"]["bars_path"].write_text(
        format_canonical_csv([b for i, b in enumerate(market["bars"][:64]) if i != 61]),
        encoding="utf-8",
    )
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    assert state.orders[0].status == "EXPIRED"
    assert state.holdings == {}
    assert "Missing" in state.orders[0].notes


def test_out_of_range_slippage_blocks_fill(market: dict[str, Any]) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    market["bars"][61] = replace(market["bars"][61], open=D(10), close=D(10), high=D(10), low=D(10))
    advance(market, 62)
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    assert state.orders[0].status == "EXPIRED"
    assert "outside_observed_bar" in state.orders[0].notes


def test_gap_concentration_cap(market: dict[str, Any]) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    market["bars"][61] = replace(market["bars"][61], open=D(19), close=D(19), high=D(20))
    advance(market, 62)
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    assert state.orders[0].status == "PARTIALLY_FILLED"
    assert D(state.holdings["X"]) * D("19.019") <= D(state.total_equity_tnd) * D(".10")
    assert D(state.cash_tnd) >= 0


def test_sell_signal_and_two_sided_commissions(market: dict[str, Any]) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    # Keep the next-open tradable, but make close momentum negative to schedule an exit.
    market["bars"][61] = replace(market["bars"][61], close=D(8))
    advance(market, 62)
    first = record_forward_paper_signal(market["journal"], **market["paths"])
    assert first.orders[-1].side == "sell"
    advance(market, 63)
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    buy, sell = state.orders
    assert sell.status == "FILLED"
    assert sell.filled_shares == buy.filled_shares
    assert D(sell.execution_price_tnd or "0") == D("9.990")
    assert state.holdings["X"] == 0
    assert D(state.total_fees_tnd) == D(buy.fee_tnd) + D(sell.fee_tnd)
    assert D(state.total_equity_tnd) == D(state.cash_tnd)
    assert state.net_return_pct < 0
    assert state.max_drawdown_pct > 0


@pytest.mark.parametrize("offset", [-1, 1])
def test_historical_and_future_recording_rejected_without_mutation(
    market: dict[str, Any], offset: int
) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    before = market["journal"].read_bytes()
    with pytest.raises(ValueError, match="historical or future"):
        record_forward_paper_signal(
            market["journal"], as_of_session=market["days"][60 + offset], **market["paths"]
        )
    assert market["journal"].read_bytes() == before


def test_new_journal_cannot_backdate_signal(market: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        record_forward_paper_signal(
            market["journal"], as_of_session=market["days"][59], **market["paths"]
        )
    assert not market["journal"].exists()


def test_future_rows_do_not_change_signal_hash(market: dict[str, Any]) -> None:
    first = load_or_init_paper_journal(market["journal"], **market["paths"])
    # Future rows exist physically but are not inputs to the cutoff-bounded signal.
    market["paths"]["bars_path"].write_text(format_canonical_csv(market["bars"]), encoding="utf-8")
    second = load_or_init_paper_journal(
        market["journal"].with_name("other.json"), **market["paths"]
    )
    assert first.signal_snapshots[0] == second.signal_snapshots[0]
    with pytest.raises(ValueError, match="Future bar"):
        _signal(
            PaperJournalState(),
            market["days"][60],
            market["bars"],
            market["master"],
            market["calendar"],
        )


def test_no_backfilled_fills_when_next_session_predates_recording(market: dict[str, Any]) -> None:
    market["clock"][0] = datetime.combine(market["days"][63], time(16), UTC)
    first = load_or_init_paper_journal(market["journal"], **market["paths"])
    advance(market, 64)
    state = load_or_init_paper_journal(market["journal"], **market["paths"])
    assert state.orders[0].status == "EXPIRED"
    assert "before the signal was recorded" in state.orders[0].notes
    assert first.holdings == state.holdings == {}


@pytest.mark.parametrize("kind", ["edit", "truncate", "remove"])
def test_input_revision_is_blocked(market: dict[str, Any], kind: str) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    before = market["journal"].read_bytes()
    bars = market["bars"][:61]
    if kind == "edit":
        bars[0] = replace(bars[0], close=D(11))
    elif kind == "truncate":
        bars = bars[:-1]
    else:
        bars = bars[1:]
    market["paths"]["bars_path"].write_text(format_canonical_csv(bars), encoding="utf-8")
    with pytest.raises(ValueError, match="revised or removed"):
        load_or_init_paper_journal(market["journal"], **market["paths"])
    assert market["journal"].read_bytes() == before


def test_corruption_and_strategy_change_rejected(market: dict[str, Any]) -> None:
    load_or_init_paper_journal(market["journal"], **market["paths"])
    with pytest.raises(ValueError, match="change the strategy"):
        record_forward_paper_signal(
            market["journal"], strategy_id="D_MOMENTUM_20S", **market["paths"]
        )
    payload = json.loads(market["journal"].read_text(encoding="utf-8"))
    payload["journal"]["cash_tnd"] = "99999.000"
    market["journal"].write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="integrity"):
        load_or_init_paper_journal(market["journal"], **market["paths"])


def test_unknown_strategy_no_journal(market: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="Unknown"):
        record_forward_paper_signal(market["journal"], strategy_id="bad", **market["paths"])
    assert not market["journal"].exists()


def test_load_retains_explicitly_selected_strategy(market: dict[str, Any]) -> None:
    state = record_forward_paper_signal(
        market["journal"], strategy_id="D_MOMENTUM_20S", **market["paths"]
    )
    assert (
        load_or_init_paper_journal(market["journal"], **market["paths"]).strategy_id
        == state.strategy_id
    )


def test_future_ingestion_cannot_enter_forward_signal(market: dict[str, Any]) -> None:
    market["bars"][60] = replace(
        market["bars"][60], ingested_at=market["clock"][0] + timedelta(hours=1)
    )
    advance(market, 61)
    with pytest.raises(ValueError, match="not available"):
        load_or_init_paper_journal(market["journal"], **market["paths"])
    assert not market["journal"].exists()


def test_writer_lock_and_cleanup(market: dict[str, Any]) -> None:
    lock = market["journal"].with_suffix(".json.lock")
    lock.write_text("busy", encoding="utf-8")
    with pytest.raises(ValueError, match="busy"):
        load_or_init_paper_journal(market["journal"], **market["paths"])
    lock.unlink()
    load_or_init_paper_journal(market["journal"], **market["paths"])
    assert not lock.exists()
    assert not market["journal"].with_suffix(".json.tmp").exists()


def test_api_forward_journal_round_trip(market: dict[str, Any]) -> None:
    from fastapi.testclient import TestClient

    from bvmt.api import create_app

    application = create_app(
        paper_journal_path=market["journal"],
        paper_bars_path=market["paths"]["bars_path"],
        paper_instruments_path=market["paths"]["instruments_path"],
        paper_calendar_path=market["paths"]["calendar_path"],
    )
    with TestClient(application) as client:
        initial = client.get("/api/paper-trading")
        assert initial.status_code == 200
        assert initial.json()["journal"]["orders"][0]["status"] == "PENDING_NEXT_SESSION"
        advance(market, 62)
        settled = client.post("/api/paper-trading/record-signal", json={})
        assert settled.status_code == 200
        journal = settled.json()["journal"]
        assert journal["orders"][0]["status"] == "FILLED"
        assert len(journal["signal_snapshots"]) == 2
        assert client.get("/api/paper-trading").json()["journal"] == journal
        assert (
            client.post(
                "/api/paper-trading/record-signal",
                json={"as_of_session": market["days"][60].isoformat()},
            ).status_code
            == 400
        )
