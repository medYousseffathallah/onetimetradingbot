"""Immutable validation reuse must never stand in for PIT/risk evaluation."""

from dataclasses import FrozenInstanceError, asdict, replace
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from bvmt import data
from bvmt.calendar import evaluate_coverage, read_exchange_calendar, read_instrument_master
from bvmt.features import rank_session_baseline
from bvmt.perf_cache import invalidate_all_caches

ROOT = Path(__file__).resolve().parents[1]


def test_identical_batch_reuses_validation_and_returns_defensive_lists(bars):
    invalidate_all_caches()
    with patch.object(data, "validate_bar", wraps=data.validate_bar) as checked:
        first = data.validate_bars(bars)
        second = data.validate_bars(tuple(bars))
        assert checked.call_count == len(bars)
    first.clear()
    assert second == bars
    assert data.validate_bars(bars) == bars
    with pytest.raises(FrozenInstanceError):
        second[0].close = Decimal("0")


def test_mutable_input_and_changed_record_cannot_reuse_proof(bars):
    invalidate_all_caches()
    mutable = list(bars)
    data.validate_bars(mutable)
    mutable[0] = replace(mutable[0], close=Decimal("0"))
    with pytest.raises(ValueError, match="positive"):
        data.validate_bars(mutable)
    with pytest.raises(ValueError, match="positive"):
        data.validate_bars(mutable)  # rejected artifacts are never retained
    mutable[0] = bars[0]
    mutable.append(bars[0])
    with pytest.raises(ValueError, match="Duplicate"):
        data.validate_bars(mutable)


def test_global_generation_and_validation_version_force_revalidation(bars, monkeypatch):
    invalidate_all_caches()
    with patch.object(data, "validate_bar", wraps=data.validate_bar) as checked:
        data.validate_bars(bars)
        data.validate_bars(bars)
        assert checked.call_count == len(bars)
        invalidate_all_caches()
        data.validate_bars(bars)
        assert checked.call_count == 2 * len(bars)
        monkeypatch.setattr(data, "BAR_VALIDATION_VERSION", "test-new-validation-contract")
        data.validate_bars(bars)
        assert checked.call_count == 3 * len(bars)


def test_coverage_keeps_duplicate_and_empty_diagnostics(bars):
    calendar = read_exchange_calendar(ROOT / "tests/fixtures/exchange_calendar.csv")
    instruments = read_instrument_master(ROOT / "tests/fixtures/instrument_master.csv")
    duplicated = [bars[0], bars[0]]
    report = evaluate_coverage(instruments, calendar, duplicated)
    assert report == evaluate_coverage(instruments, calendar, [bars[0]])
    empty = evaluate_coverage(instruments, calendar, [])
    assert empty.classification_counts.get("missing_observation", 0) > 0
    with pytest.raises(ValueError, match="empty"):
        data.validate_bars([])


def test_cutoff_and_liquidity_changes_recompute_research(bars):
    calendar = read_exchange_calendar(ROOT / "tests/fixtures/exchange_calendar.csv")
    instruments = read_instrument_master(ROOT / "tests/fixtures/instrument_master.csv")
    invalidate_all_caches()
    options = dict(
        short_lookback=2,
        long_lookback=3,
        min_trade_frequency=0.5,
        min_median_turnover_tnd=Decimal("0"),
    )
    early = rank_session_baseline(
        instruments, calendar, bars, data.aware_timestamp("2026-01-08T17:00:00Z"), **options
    )
    later = rank_session_baseline(
        instruments, calendar, bars, data.aware_timestamp("2026-01-09T17:00:00Z"), **options
    )
    assert early.latest_open_session != later.latest_open_session
    blocked = rank_session_baseline(
        instruments,
        calendar,
        bars,
        data.aware_timestamp("2026-01-09T17:00:00Z"),
        **{**options, "min_median_turnover_tnd": Decimal("99999999")},
    )
    assert not blocked.candidates
    invalidate_all_caches()
    assert later == rank_session_baseline(
        instruments, calendar, bars, data.aware_timestamp("2026-01-09T17:00:00Z"), **options
    )


def test_csv_parser_version_and_changed_bytes_invalidate(tmp_path, monkeypatch):
    path = tmp_path / "bars.csv"
    path.write_bytes((ROOT / "tests/fixtures/daily_bars.csv").read_bytes())
    first = data.read_bars_csv(path)
    with patch.object(data, "_parse_canonical_row", wraps=data._parse_canonical_row) as parse:
        monkeypatch.setattr(data, "CANONICAL_PARSER_VERSION", "test-parser-next")
        assert data.read_bars_csv(path) == first
        assert parse.call_count == len(first)
    lines = path.read_text(encoding="utf-8").splitlines()
    path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    assert len(data.read_bars_csv(path)) == len(first) - 1


def test_value_equal_records_retain_source_representation(bars):
    invalidate_all_caches()
    data.validate_bars(bars)
    replacement = replace(bars[0], close=bars[0].close.quantize(Decimal(".000000")))
    changed = [replacement, *bars[1:]]
    assert changed == bars
    actual = data.validate_bars(changed)
    assert actual[0] is replacement
    assert actual[0].close.as_tuple() == replacement.close.as_tuple()


def test_mutable_field_subclass_is_never_reused(bars):
    class MutableSymbol(str):
        empty = False

        def strip(self, chars=None):
            return "" if self.empty else super().strip(chars)

    symbol = MutableSymbol("DEMO_A")
    bar = replace(bars[0], symbol=symbol)
    data.validate_bars([bar])
    symbol.empty = True
    with pytest.raises(ValueError, match="required"):
        data.validate_bars([bar])


def test_optimized_and_uncached_state_are_equivalent(tmp_path):
    from test_perf_cache import _setup_service

    service = _setup_service(tmp_path)
    invalidate_all_caches()
    with patch.object(data._VALIDATED_BAR_ARTIFACTS, "get", return_value=None):
        reference = service.load_state()
    reference.ledger.save(service.resolve_context().ledger_path)
    before = service.resolve_context().ledger_path.read_bytes()
    invalidate_all_caches()
    optimized = service.load_state()
    assert optimized.recommendations == reference.recommendations
    assert optimized.research_coverage.to_dict() == reference.research_coverage.to_dict()
    assert optimized.price_map == reference.price_map
    assert optimized.market_data_provenance == reference.market_data_provenance
    assert service.resolve_context().ledger_path.read_bytes() == before


def test_distinct_equal_records_require_new_validation(bars):
    invalidate_all_caches()
    with patch.object(data, "validate_bar", wraps=data.validate_bar) as checked:
        data.validate_bars(bars)
        clones = [replace(bar) for bar in bars]
        data.validate_bars(clones)
        assert checked.call_count == 2 * len(bars)


def test_cached_rows_have_no_mutable_instance_dictionary(bars):
    bar = replace(bars[0])
    data.validate_bars([bar])
    with pytest.raises(TypeError):
        vars(bar)
    with pytest.raises(FrozenInstanceError):
        bar.close = Decimal("0")
    assert asdict(bar)["close"] == bar.close
    revised = replace(bar, close=Decimal("0"))
    with pytest.raises(ValueError, match="positive"):
        data.validate_bars([revised])
