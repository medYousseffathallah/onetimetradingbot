"""Tests for BVMT market data gateway, provider adapters, and lifecycle orchestration."""

import json
import urllib.error
from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bvmt.gateway import (
    LocalArchiveProvider,
    MarketDataGateway,
    OanorMarketDataProvider,
    OfficialBvmtNdjsonProvider,
)


def _sample_session_envelope(session_str: str = "2026-11-06") -> str:
    return json.dumps(
        {
            "seance": session_str,
            "data": [
                {
                    "dateSeance": session_str,
                    "codeISIN": "TN0001900604",
                    "mnemo": "BH",
                    "valeur": "BH BANK",
                    "coursOuvert": "13.090",
                    "plusHaut": "13.100",
                    "plusBas": "13.060",
                    "cloture": "13.090",
                    "quantites": "12450",
                    "capitaux": "162985.500",
                    "echanges": "42",
                    "groupe": "11",
                },
                {
                    "dateSeance": session_str,
                    "codeISIN": "TN0001800457",
                    "mnemo": "SFBT",
                    "valeur": "SFBT",
                    "coursOuvert": "12.500",
                    "plusHaut": "12.600",
                    "plusBas": "12.450",
                    "cloture": "12.550",
                    "quantites": "25000",
                    "capitaux": "313750.000",
                    "echanges": "65",
                    "groupe": "11",
                },
            ],
        }
    )


def test_sanitize_ndjson_tail_discards_truncated_leading_line():
    provider = OfficialBvmtNdjsonProvider()
    envelope_1 = _sample_session_envelope("2026-11-05")
    envelope_2 = _sample_session_envelope("2026-11-06")

    # Simulate byte boundary cut mid-envelope
    truncated_leading = ',"groupe":"11"}]}'
    raw_tail = f"{truncated_leading}\n{envelope_1}\n{envelope_2}\n".encode()

    sanitized = provider.sanitize_ndjson_tail(raw_tail)
    lines = [line for line in sanitized.splitlines() if line.strip()]
    assert len(lines) == 2
    assert json.loads(lines[0])["seance"] == "2026-11-05"
    assert json.loads(lines[1])["seance"] == "2026-11-06"


def test_sanitize_ndjson_tail_raises_when_no_valid_envelope():
    provider = OfficialBvmtNdjsonProvider()
    raw_tail = b"broken random noise without json\nsecond line garbage"
    with pytest.raises(ValueError, match="No valid session envelopes found"):
        provider.sanitize_ndjson_tail(raw_tail)


def test_official_provider_health_check_healthy():
    provider = OfficialBvmtNdjsonProvider()
    mock_resp = MagicMock()
    mock_resp.headers = {
        "ETag": '"abc123etag"',
        "Last-Modified": "Fri, 06 Nov 2026 14:45:02 GMT",
        "Content-Length": "222319563",
        "Accept-Ranges": "bytes",
    }
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        health = provider.check_health()
        assert health.status == "HEALTHY"
        assert health.etag == "abc123etag"
        assert health.last_modified_header == "Fri, 06 Nov 2026 14:45:02 GMT"
        assert health.content_length == 222319563


def test_official_provider_health_check_offline():
    provider = OfficialBvmtNdjsonProvider(max_retries=1)
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Connection refused")):
        health = provider.check_health()
        assert health.status == "OFFLINE"
        assert "Connection refused" in health.message


def test_official_provider_sync_skips_when_etag_and_modified_match(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    output_dir = tmp_path / "processed"
    staging_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    # Write existing canonical file and metadata
    canonical_csv = output_dir / "daily_bars.canonical.csv"
    canonical_csv.write_text(
        "instrument_id,symbol,session_date,open,high,low,close,volume_shares,turnover_tnd,status,source_id,published_at,ingested_at\n"
        "TN0001900604,BH,2026-11-06,13.090,13.100,13.060,13.090,12450,162985.500,traded,src,,2026-11-06T15:00:00+00:00\n",
        encoding="utf-8",
    )
    staging_tail = staging_dir / "market_resume_tail.ndjson"
    staging_tail.write_text(_sample_session_envelope("2026-11-06") + "\n", encoding="utf-8")

    meta_file = staging_dir / "official_ndjson_head.json"
    meta_file.write_text(
        json.dumps(
            {
                "etag": "etag_unchanged",
                "last_modified": "Fri, 06 Nov 2026 14:45:02 GMT",
                "last_synced_at": "2026-11-06T15:05:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    provider = OfficialBvmtNdjsonProvider(staging_dir=staging_dir)

    mock_head = MagicMock()
    mock_head.headers = {
        "ETag": '"etag_unchanged"',
        "Last-Modified": "Fri, 06 Nov 2026 14:45:02 GMT",
        "Content-Length": "222319563",
    }
    mock_head.status = 200
    mock_head.__enter__.return_value = mock_head

    with patch("urllib.request.urlopen", return_value=mock_head) as mock_url:
        result = provider.sync_daily_bars(output_dir=output_dir, as_of=date(2026, 11, 6))
        assert result.new_bars_count == 0
        assert result.total_bars_count == 1
        # urlopen was called once for HEAD, and GET Range was NOT called
        assert mock_url.call_count == 1


def test_official_provider_sync_downloads_and_merges_when_modified(tmp_path: Path):
    staging_dir = tmp_path / "staging"
    output_dir = tmp_path / "processed"
    staging_dir.mkdir(parents=True)
    output_dir.mkdir(parents=True)

    provider = OfficialBvmtNdjsonProvider(staging_dir=staging_dir)

    mock_head = MagicMock()
    mock_head.headers = {
        "ETag": '"etag_new_session"',
        "Last-Modified": "Fri, 06 Nov 2026 15:00:00 GMT",
        "Content-Length": "222320000",
    }
    mock_head.status = 200
    mock_head.__enter__.return_value = mock_head

    envelope = _sample_session_envelope("2026-11-06")
    mock_range = MagicMock()
    mock_range.read.return_value = f"truncated_line\n{envelope}\n".encode()
    mock_range.status = 206
    mock_range.__enter__.return_value = mock_range

    def urlopen_side_effect(req, *args, **kwargs):
        if getattr(req, "method", None) == "HEAD":
            return mock_head
        return mock_range

    with patch("urllib.request.urlopen", side_effect=urlopen_side_effect):
        result = provider.sync_daily_bars(output_dir=output_dir, as_of=date(2026, 11, 6))
        assert result.new_bars_count == 2
        assert result.total_bars_count == 2
        assert result.total_sessions_count == 1
        assert (output_dir / "daily_bars.canonical.csv").exists()


def test_oanor_provider_unconfigured_safeguard():
    provider = OanorMarketDataProvider(api_key=None)
    health = provider.check_health()
    assert health.status == "UNCONFIGURED"
    assert "OANOR API key not provided" in health.message
    quotes = provider.fetch_latest_quotes(["BH"])
    assert quotes == []


def test_oanor_provider_parses_quotes_with_api_key():
    provider = OanorMarketDataProvider(api_key="test_dummy_key")
    mock_resp = MagicMock()
    payload = {
        "quotes": [
            {
                "code": "BH",
                "price": 13.09,
                "open": 13.09,
                "high": 13.10,
                "low": 13.06,
                "volume": 12450,
                "turnover": 162985.5,
            }
        ]
    }
    mock_resp.read.return_value = json.dumps(payload).encode("utf-8")
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        quotes = provider.fetch_latest_quotes(["BH"])
        assert len(quotes) == 1
        q = quotes[0]
        assert q.symbol == "BH"
        assert q.close == Decimal("13.09")
        assert q.is_delayed is True
        assert q.provenance == "OANOR BVMT API (TradingView Upstream)"


def test_local_archive_provider_and_gateway_status(tmp_path: Path):
    canonical_csv = tmp_path / "daily_bars.canonical.csv"
    canonical_csv.write_text(
        "instrument_id,symbol,session_date,open,high,low,close,volume_shares,turnover_tnd,status,source_id,published_at,ingested_at\n"
        "TN0001900604,BH,2026-11-06,13.090,13.100,13.060,13.090,12450,162985.500,traded,src,,2026-11-06T15:00:00+00:00\n",
        encoding="utf-8",
    )
    provider = LocalArchiveProvider(canonical_csv)
    health = provider.check_health()
    assert health.status == "HEALTHY"

    gateway = MarketDataGateway(provider=provider, output_dir=tmp_path)
    status = gateway.get_status(as_of=date(2026, 11, 6))
    assert status.health_status == "HEALTHY"
    assert status.total_bars_count == 1
    assert status.latest_session_date == "2026-11-06"
    assert status.sessions_behind == 0
    assert status.is_data_fresh is True


def test_market_gateway_strict_ledger_isolation(tmp_path: Path):
    """Guarantees that market gateway operations NEVER mutate the real competition ledger."""
    portfolio_dir = tmp_path / "portfolio"
    portfolio_dir.mkdir(parents=True)
    real_ledger_file = portfolio_dir / "real_competition_ledger.json"
    original_ledger_content = json.dumps({"cash": "49608.050", "holdings": {"BH": 30}})
    real_ledger_file.write_text(original_ledger_content, encoding="utf-8")

    archive_csv = tmp_path / "archive.csv"
    archive_csv.write_text(
        "instrument_id,symbol,session_date,open,high,low,close,volume_shares,turnover_tnd,status,source_id,published_at,ingested_at\n"
        "TN0001900604,BH,2026-11-06,13.090,13.100,13.060,13.090,12450,162985.500,traded,src,,2026-11-06T15:00:00+00:00\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "market_data"

    provider = LocalArchiveProvider(archive_csv)
    gateway = MarketDataGateway(provider=provider, output_dir=output_dir)

    # Perform refresh
    res = gateway.refresh()
    assert res.total_bars_count == 1

    # Assert real competition ledger is completely untouched
    assert real_ledger_file.read_text(encoding="utf-8") == original_ledger_content
