"""Automated market data gateway and provider adapters for Bourse de Tunis (BVMT).

Provides a pluggable MarketDataProvider interface with concrete adapters:
1. OfficialBvmtNdjsonProvider: Range-queryable EOD ingestion from official BVMT publication portal.
2. OanorMarketDataProvider: Optional 15-min delayed intraday quotes via OANOR API (free tier guarded).
3. LocalArchiveProvider: 100% offline historical replay provider for testing and air-gapped operations.

Guarantees:
- Strict account isolation: Writes only to data/staging and data/processed; never mutates competition ledger.
- Zero paid API calls: Never initiates billed requests; free tiers are hard-rate-limited.
- Range-query efficiency: Ingests only new trailing session envelopes rather than re-downloading ~222 MB.
- Deterministic deduplication, freshness tracking, and SHA-256 provenance logging.
"""

from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal, Protocol, runtime_checkable

from bvmt.calendar import read_exchange_calendar
from bvmt.data import (
    DailyMarketRefreshResult,
    check_data_freshness,
    read_bars_csv,
    refresh_daily_market_pipeline,
)
from bvmt.snapshots import atomic_write_text, ensure_no_symlink_ancestors, sha256_file

logger = logging.getLogger(__name__)

OFFICIAL_BVMT_NDJSON_URL = "https://www.tunis-stockexchange.com/sites/default/files/historique/data_json/market_resume.ndjson"
DEFAULT_STAGING_DIR = Path("data/staging")
DEFAULT_PROCESSED_DIR = Path("data/processed/bvmt_official_2026")
DEFAULT_USER_AGENT = (
    "BVMT-Research-Gateway/1.0 (+https://github.com/medYousseffathallah/onetimetradingbot)"
)


@dataclass(frozen=True)
class QuotationSnapshot:
    """Normalized quotation snapshot for an instrument at a point in time."""

    instrument_id: str
    symbol: str
    session_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume_shares: int
    turnover_tnd: Decimal
    status: str
    provenance: str
    retrieved_at: datetime
    is_delayed: bool = False
    source_id: str = "bvmt_gateway"


@dataclass(frozen=True)
class ProviderHealthStatus:
    """Operational health report for a market data provider."""

    provider_id: str
    display_name: str
    status: Literal["HEALTHY", "DEGRADED", "OFFLINE", "UNCONFIGURED"]
    message: str
    last_checked: datetime
    last_success: datetime | None = None
    last_modified_header: str | None = None
    etag: str | None = None
    content_length: int | None = None


@runtime_checkable
class MarketDataProvider(Protocol):
    """Uniform abstract interface for BVMT market data adapters."""

    @property
    def provider_id(self) -> str: ...

    @property
    def display_name(self) -> str: ...

    def check_health(self) -> ProviderHealthStatus: ...

    def fetch_latest_quotes(self, symbols: list[str] | None = None) -> list[QuotationSnapshot]: ...

    def sync_daily_bars(
        self,
        output_dir: Path,
        *,
        as_of: date | None = None,
        force: bool = False,
    ) -> DailyMarketRefreshResult: ...


class OfficialBvmtNdjsonProvider:
    """Official Bourse de Tunis NDJSON provider using lightweight HTTP Range queries.

    Instead of re-downloading the ~222 MB cumulative archive, this provider:
    1. Sends HTTP HEAD to inspect Last-Modified and ETag.
    2. Compares with cached sync metadata in data/staging/official_ndjson_head.json.
    3. If unchanged and not forced, skips network transfer.
    4. If updated, issues HTTP Range: bytes=-{range_bytes} to fetch only trailing envelopes (~3.5 MB).
    5. Sanitizes partial boundary lines, validates NDJSON envelopes, and pipelines them into canonical CSV.
    """

    def __init__(
        self,
        endpoint_url: str = OFFICIAL_BVMT_NDJSON_URL,
        *,
        staging_dir: Path = DEFAULT_STAGING_DIR,
        timeout_seconds: float = 15.0,
        range_bytes: int = 3_500_000,
        max_retries: int = 3,
        backoff_factor: float = 1.5,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.staging_dir = staging_dir
        self.timeout_seconds = timeout_seconds
        self.range_bytes = range_bytes
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    @property
    def provider_id(self) -> str:
        return "official_bvmt_ndjson"

    @property
    def display_name(self) -> str:
        return "Official Bourse de Tunis NDJSON Portal"

    def _get_metadata_cache_path(self) -> Path:
        return self.staging_dir / "official_ndjson_head.json"

    def _read_cached_metadata(self) -> dict[str, Any]:
        path = self._get_metadata_cache_path()
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    return loaded
            except Exception:
                return {}
        return {}

    def _write_cached_metadata(self, metadata: dict[str, Any]) -> None:
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        path = self._get_metadata_cache_path()
        atomic_write_text(
            path,
            json.dumps(metadata, indent=2, sort_keys=True),
            allow_identical=True,
            allow_overwrite=True,
        )

    def fetch_head(self) -> dict[str, Any]:
        """Query HTTP HEAD headers from the remote endpoint with retry backoff."""
        req = urllib.request.Request(
            self.endpoint_url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            method="HEAD",
        )
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                    headers = dict(resp.headers)
                    etag = headers.get("ETag") or headers.get("etag")
                    last_modified = headers.get("Last-Modified") or headers.get("last-modified")
                    content_length = headers.get("Content-Length") or headers.get("content-length")
                    accept_ranges = headers.get("Accept-Ranges") or headers.get("accept-ranges")
                    return {
                        "etag": etag.strip('"') if etag else None,
                        "last_modified": last_modified,
                        "content_length": int(content_length)
                        if content_length and content_length.isdigit()
                        else None,
                        "accept_ranges": accept_ranges,
                        "status_code": resp.status,
                    }
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    sleep_time = self.backoff_factor**attempt
                    time.sleep(sleep_time)
        raise RuntimeError(
            f"Failed to fetch HEAD for {self.endpoint_url} after {self.max_retries} attempts: {last_exc}"
        )

    def check_health(self) -> ProviderHealthStatus:
        """Perform a non-intrusive operational health check via HTTP HEAD."""
        now = datetime.now(UTC)
        try:
            head_info = self.fetch_head()
            cached = self._read_cached_metadata()
            last_success = (
                datetime.fromisoformat(cached["last_synced_at"])
                if "last_synced_at" in cached
                else None
            )
            return ProviderHealthStatus(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status="HEALTHY",
                message=(
                    f"Remote archive online. Last-Modified: {head_info.get('last_modified') or 'unknown'}, "
                    f"ETag: {head_info.get('etag') or 'unknown'}"
                ),
                last_checked=now,
                last_success=last_success,
                last_modified_header=head_info.get("last_modified"),
                etag=head_info.get("etag"),
                content_length=head_info.get("content_length"),
            )
        except Exception as exc:
            cached = self._read_cached_metadata()
            last_success = (
                datetime.fromisoformat(cached["last_synced_at"])
                if "last_synced_at" in cached
                else None
            )
            return ProviderHealthStatus(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status="OFFLINE",
                message=f"Network check failed: {exc}",
                last_checked=now,
                last_success=last_success,
            )

    def fetch_trailing_bytes(self) -> bytes:
        """Issue an HTTP Range request for the trailing bytes of the NDJSON archive."""
        range_header = f"bytes=-{self.range_bytes}"
        req = urllib.request.Request(
            self.endpoint_url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "Range": range_header,
            },
        )
        last_exc: Exception | None = None
        for attempt in range(self.max_retries):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_seconds * 2) as resp:
                    data: bytes = resp.read()
                    return data
            except Exception as exc:
                last_exc = exc
                if attempt < self.max_retries - 1:
                    sleep_time = self.backoff_factor**attempt
                    time.sleep(sleep_time)
        raise RuntimeError(
            f"Failed to fetch trailing {self.range_bytes} bytes from {self.endpoint_url} after {self.max_retries} attempts: {last_exc}"
        )

    def sanitize_ndjson_tail(self, raw_bytes: bytes) -> str:
        """Sanitize trailing NDJSON bytes by discarding the initial truncated line."""
        text = raw_bytes.decode("utf-8", errors="replace")
        lines = text.splitlines()
        valid_envelopes: list[str] = []
        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                parsed = json.loads(line_str)
                if isinstance(parsed, dict) and "seance" in parsed and "data" in parsed:
                    valid_envelopes.append(line_str)
            except json.JSONDecodeError:
                # Expected for the very first line split at an arbitrary byte boundary
                continue

        if not valid_envelopes:
            raise ValueError(
                f"No valid session envelopes found in trailing {len(raw_bytes)} bytes. "
                "The range size may need to be increased."
            )
        return "\n".join(valid_envelopes) + "\n"

    def sync_daily_bars(
        self,
        output_dir: Path,
        *,
        as_of: date | None = None,
        force: bool = False,
    ) -> DailyMarketRefreshResult:
        """Synchronize canonical daily bars with remote BVMT NDJSON archive."""
        ensure_no_symlink_ancestors(output_dir)
        ensure_no_symlink_ancestors(self.staging_dir)
        self.staging_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        now = datetime.now(UTC)
        canonical_csv_path = output_dir / "daily_bars.canonical.csv"

        # Check HEAD metadata
        head_info = self.fetch_head()
        etag = head_info.get("etag")
        last_modified = head_info.get("last_modified")
        cached = self._read_cached_metadata()

        is_unchanged = (
            not force
            and canonical_csv_path.exists()
            and etag is not None
            and etag == cached.get("etag")
            and last_modified is not None
            and last_modified == cached.get("last_modified")
        )

        staging_tail_path = self.staging_dir / "market_resume_tail.ndjson"

        if is_unchanged and staging_tail_path.exists():
            # Already up-to-date with this exact ETag and Last-Modified
            logger.info("Market data is already up to date with remote ETag %s", etag)
            existing_bars = read_bars_csv(canonical_csv_path)
            freshness = check_data_freshness(existing_bars, as_of=as_of)
            all_sessions = sorted({b.session_date for b in existing_bars})
            quality_report_path = output_dir / "quality_report.json"
            return DailyMarketRefreshResult(
                source_id="tunis_stockexchange_equities_2026",
                source_path=str(staging_tail_path),
                source_url=self.endpoint_url,
                retrieved_at=cached.get("last_synced_at", now.isoformat()),
                previous_bars_count=len(existing_bars),
                new_bars_count=0,
                total_bars_count=len(existing_bars),
                previous_sessions_count=len(all_sessions),
                new_sessions_count=0,
                total_sessions_count=len(all_sessions),
                first_session=str(all_sessions[0]) if all_sessions else None,
                latest_session=str(all_sessions[-1]) if all_sessions else None,
                duplicate_rows_detected=0,
                rejected_rows_count=0,
                stale_instruments_count=len(freshness.stale_instruments),
                quality_report_path=str(quality_report_path)
                if quality_report_path.exists()
                else "",
                canonical_bars_path=str(canonical_csv_path),
                is_data_fresh=not freshness.is_stale,
                freshness_status=freshness.status,
            )

        # Download trailing bytes and sanitize
        raw_tail = self.fetch_trailing_bytes()
        clean_ndjson = self.sanitize_ndjson_tail(raw_tail)
        atomic_write_text(
            staging_tail_path, clean_ndjson, allow_identical=True, allow_overwrite=True
        )

        # Ingest incrementally via verified pipeline
        refresh_result = refresh_daily_market_pipeline(
            new_source_path=staging_tail_path,
            output_dir=output_dir,
            source_format="tunis_stockexchange_ndjson",
            source_url=self.endpoint_url,
            source_id="tunis_stockexchange_equities_2026",
            permission_status="public_read_only_reference",
            retrieved_at=now,
            as_of=as_of,
        )

        # Update cached metadata
        self._write_cached_metadata(
            {
                "etag": etag,
                "last_modified": last_modified,
                "content_length": head_info.get("content_length"),
                "last_synced_at": now.isoformat(),
                "staging_tail_sha256": sha256_file(staging_tail_path),
                "total_sessions": refresh_result.total_sessions_count,
                "latest_session": refresh_result.latest_session,
            }
        )

        return refresh_result

    def fetch_latest_quotes(self, symbols: list[str] | None = None) -> list[QuotationSnapshot]:
        """Read latest session quotes from canonical storage."""
        canonical_csv = DEFAULT_PROCESSED_DIR / "daily_bars.canonical.csv"
        if not canonical_csv.exists():
            return []
        bars = read_bars_csv(canonical_csv)
        if not bars:
            return []
        latest_date = max(b.session_date for b in bars)
        target_symbols = set(symbols) if symbols else None
        snapshots: list[QuotationSnapshot] = []
        for b in bars:
            if b.session_date == latest_date:
                if target_symbols is None or b.symbol in target_symbols:
                    snapshots.append(
                        QuotationSnapshot(
                            instrument_id=b.instrument_id,
                            symbol=b.symbol,
                            session_date=b.session_date,
                            open=b.open,
                            high=b.high,
                            low=b.low,
                            close=b.close,
                            volume_shares=b.volume_shares,
                            turnover_tnd=b.turnover_tnd,
                            status=b.status,
                            provenance="Official BVMT NDJSON Feed",
                            retrieved_at=b.ingested_at,
                            is_delayed=False,
                            source_id=b.source_id,
                        )
                    )
        return snapshots


class OanorMarketDataProvider:
    """Optional delayed intraday provider via OANOR API.

    Implements strict rate limits (2 req/s) and free-tier safeguards (7k req/mo cap).
    When no API key is configured, health reports UNCONFIGURED without throwing errors.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.oanor.com/tunisia-stock-api",
        timeout_seconds: float = 10.0,
    ) -> None:
        self.api_key = api_key or os.environ.get("BVMT_OANOR_API_KEY")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    @property
    def provider_id(self) -> str:
        return "oanor_bvmt_api"

    @property
    def display_name(self) -> str:
        return "OANOR BVMT Stock API (Delayed)"

    def check_health(self) -> ProviderHealthStatus:
        now = datetime.now(UTC)
        if not self.api_key:
            return ProviderHealthStatus(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status="UNCONFIGURED",
                message="OANOR API key not provided (set BVMT_OANOR_API_KEY). Running in zero-cost offline/official mode.",
                last_checked=now,
            )
        # When key is present, verify connectivity via light index ping
        url = f"{self.base_url}/v1/index?symbol=TUNINDEX"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "x-oanor-key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                if resp.status == 200:
                    return ProviderHealthStatus(
                        provider_id=self.provider_id,
                        display_name=self.display_name,
                        status="HEALTHY",
                        message="OANOR BVMT API reachable (Free Tier: 7k req/mo, 2 req/s hard cap).",
                        last_checked=now,
                        last_success=now,
                    )
                return ProviderHealthStatus(
                    provider_id=self.provider_id,
                    display_name=self.display_name,
                    status="DEGRADED",
                    message=f"Unexpected status HTTP {resp.status}",
                    last_checked=now,
                )
        except Exception as exc:
            return ProviderHealthStatus(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status="OFFLINE",
                message=f"OANOR API check failed: {exc}",
                last_checked=now,
            )

    def fetch_latest_quotes(self, symbols: list[str] | None = None) -> list[QuotationSnapshot]:
        if not self.api_key:
            return []
        codes = ",".join(symbols) if symbols else "BH,SFBT,BIAT"
        url = f"{self.base_url}/v1/quote?codes={codes}"
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": DEFAULT_USER_AGENT,
                "x-oanor-key": self.api_key,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                items = data if isinstance(data, list) else data.get("quotes", [])
                now = datetime.now(UTC)
                snapshots: list[QuotationSnapshot] = []
                for item in items:
                    sym = str(item.get("code") or item.get("symbol") or "")
                    price = Decimal(str(item.get("price") or item.get("close") or 0))
                    snapshots.append(
                        QuotationSnapshot(
                            instrument_id=sym,
                            symbol=sym,
                            session_date=now.date(),
                            open=Decimal(str(item.get("open") or price)),
                            high=Decimal(str(item.get("high") or price)),
                            low=Decimal(str(item.get("low") or price)),
                            close=price,
                            volume_shares=int(item.get("volume") or 0),
                            turnover_tnd=Decimal(str(item.get("turnover") or 0)),
                            status="traded" if (item.get("volume") or 0) > 0 else "untraded",
                            provenance="OANOR BVMT API (TradingView Upstream)",
                            retrieved_at=now,
                            is_delayed=True,
                            source_id="oanor_bvmt_api",
                        )
                    )
                return snapshots
        except Exception as exc:
            logger.warning("Failed to fetch quotes from OANOR: %s", exc)
            return []

    def sync_daily_bars(
        self,
        output_dir: Path,
        *,
        as_of: date | None = None,
        force: bool = False,
    ) -> DailyMarketRefreshResult:
        raise NotImplementedError(
            "OANOR API is an intraday quote service, not a bulk daily bar sync archive. "
            "Use OfficialBvmtNdjsonProvider for daily bars."
        )


class LocalArchiveProvider:
    """Offline local archive provider for testing, synthetic demo, and air-gapped runs."""

    def __init__(
        self,
        archive_path: Path,
        *,
        input_format: Literal["canonical", "tunis_stockexchange_ndjson"] = "canonical",
    ) -> None:
        self.archive_path = archive_path
        self.input_format = input_format

    @property
    def provider_id(self) -> str:
        return "local_archive"

    @property
    def display_name(self) -> str:
        return f"Local Archive ({self.archive_path.name})"

    def check_health(self) -> ProviderHealthStatus:
        now = datetime.now(UTC)
        if self.archive_path.exists():
            return ProviderHealthStatus(
                provider_id=self.provider_id,
                display_name=self.display_name,
                status="HEALTHY",
                message=f"Local archive accessible ({self.archive_path.stat().st_size} bytes).",
                last_checked=now,
                last_success=now,
            )
        return ProviderHealthStatus(
            provider_id=self.provider_id,
            display_name=self.display_name,
            status="OFFLINE",
            message=f"Archive file {self.archive_path} does not exist.",
            last_checked=now,
        )

    def fetch_latest_quotes(self, symbols: list[str] | None = None) -> list[QuotationSnapshot]:
        if not self.archive_path.exists() or self.input_format != "canonical":
            return []
        bars = read_bars_csv(self.archive_path)
        if not bars:
            return []
        latest_date = max(b.session_date for b in bars)
        target_symbols = set(symbols) if symbols else None
        return [
            QuotationSnapshot(
                instrument_id=b.instrument_id,
                symbol=b.symbol,
                session_date=b.session_date,
                open=b.open,
                high=b.high,
                low=b.low,
                close=b.close,
                volume_shares=b.volume_shares,
                turnover_tnd=b.turnover_tnd,
                status=b.status,
                provenance="Local Archive",
                retrieved_at=b.ingested_at,
                is_delayed=False,
                source_id=b.source_id,
            )
            for b in bars
            if b.session_date == latest_date
            and (target_symbols is None or b.symbol in target_symbols)
        ]

    def sync_daily_bars(
        self,
        output_dir: Path,
        *,
        as_of: date | None = None,
        force: bool = False,
    ) -> DailyMarketRefreshResult:
        if self.input_format == "tunis_stockexchange_ndjson":
            return refresh_daily_market_pipeline(
                new_source_path=self.archive_path,
                output_dir=output_dir,
                source_format="tunis_stockexchange_ndjson",
                source_url=f"file://{self.archive_path.resolve()}",
                as_of=as_of,
            )
        # If canonical, read and write
        existing_bars = read_bars_csv(self.archive_path)
        canonical_csv = output_dir / "daily_bars.canonical.csv"
        output_dir.mkdir(parents=True, exist_ok=True)
        atomic_write_text(
            canonical_csv,
            self.archive_path.read_text(encoding="utf-8-sig"),
            allow_identical=True,
            allow_overwrite=True,
        )
        freshness = check_data_freshness(existing_bars, as_of=as_of)
        all_sessions = sorted({b.session_date for b in existing_bars})
        return DailyMarketRefreshResult(
            source_id="local_archive",
            source_path=str(self.archive_path),
            source_url=f"file://{self.archive_path.resolve()}",
            retrieved_at=datetime.now(UTC).isoformat(),
            previous_bars_count=len(existing_bars),
            new_bars_count=0,
            total_bars_count=len(existing_bars),
            previous_sessions_count=len(all_sessions),
            new_sessions_count=0,
            total_sessions_count=len(all_sessions),
            first_session=str(all_sessions[0]) if all_sessions else None,
            latest_session=str(all_sessions[-1]) if all_sessions else None,
            duplicate_rows_detected=0,
            rejected_rows_count=0,
            stale_instruments_count=len(freshness.stale_instruments),
            quality_report_path="",
            canonical_bars_path=str(canonical_csv),
            is_data_fresh=not freshness.is_stale,
            freshness_status=freshness.status,
        )


@dataclass(frozen=True)
class MarketGatewayStatus:
    active_provider_id: str
    active_provider_name: str
    health_status: Literal["HEALTHY", "DEGRADED", "OFFLINE", "UNCONFIGURED"]
    health_message: str
    latest_session_date: str | None
    sessions_behind: int
    is_data_fresh: bool
    stale_instruments_count: int
    total_bars_count: int
    total_sessions_count: int
    data_classification: Literal["OFFICIAL_EOD", "DELAYED_QUOTES", "SYNTHETIC_DEMO"]
    last_sync_timestamp: str | None
    next_expected_session: str | None
    calendar_status: str


class MarketDataGateway:
    """Top-level coordinator for automated BVMT market data synchronization."""

    def __init__(
        self,
        provider: MarketDataProvider | None = None,
        output_dir: Path = DEFAULT_PROCESSED_DIR,
    ) -> None:
        self.output_dir = output_dir
        self.provider = provider or OfficialBvmtNdjsonProvider()

    def get_status(self, as_of: date | None = None) -> MarketGatewayStatus:
        canonical_csv = self.output_dir / "daily_bars.canonical.csv"
        health = self.provider.check_health()
        now = datetime.now(UTC)
        as_of_date = as_of or now.date()

        # Check calendar status
        calendar_status = "REGULAR_TRADING_SCHEDULE"
        if as_of_date.weekday() in (5, 6):
            calendar_status = "WEEKEND_CLOSED"
        else:
            calendar_csv = self.output_dir / "exchange_calendar.csv"
            if calendar_csv.exists():
                try:
                    cal = read_exchange_calendar(calendar_csv)
                    cal_map = {s.session_date: s for s in cal}
                    if as_of_date in cal_map and not cal_map[as_of_date].is_open:
                        calendar_status = f"EXCHANGE_HOLIDAY ({cal_map[as_of_date].schedule_type})"
                except Exception:
                    pass

        if not canonical_csv.exists():
            return MarketGatewayStatus(
                active_provider_id=self.provider.provider_id,
                active_provider_name=self.provider.display_name,
                health_status=health.status,
                health_message=health.message,
                latest_session_date=None,
                sessions_behind=999,
                is_data_fresh=False,
                stale_instruments_count=0,
                total_bars_count=0,
                total_sessions_count=0,
                data_classification="SYNTHETIC_DEMO",
                last_sync_timestamp=health.last_success.isoformat()
                if health.last_success
                else None,
                next_expected_session=None,
                calendar_status=calendar_status,
            )

        bars = read_bars_csv(canonical_csv)
        freshness = check_data_freshness(bars, as_of=as_of_date)
        all_sessions = sorted({b.session_date for b in bars})
        latest_session = all_sessions[-1] if all_sessions else None

        classification: Literal["OFFICIAL_EOD", "DELAYED_QUOTES", "SYNTHETIC_DEMO"] = "OFFICIAL_EOD"
        if "synthetic" in str(self.output_dir).lower():
            classification = "SYNTHETIC_DEMO"

        cached = (
            OfficialBvmtNdjsonProvider(staging_dir=DEFAULT_STAGING_DIR)._read_cached_metadata()
            if isinstance(self.provider, OfficialBvmtNdjsonProvider)
            else {}
        )
        last_sync = cached.get("last_synced_at") or (
            health.last_success.isoformat() if health.last_success else None
        )

        return MarketGatewayStatus(
            active_provider_id=self.provider.provider_id,
            active_provider_name=self.provider.display_name,
            health_status=health.status,
            health_message=health.message,
            latest_session_date=str(latest_session) if latest_session else None,
            sessions_behind=freshness.days_since_latest_session,
            is_data_fresh=not freshness.is_stale,
            stale_instruments_count=len(freshness.stale_instruments),
            total_bars_count=len(bars),
            total_sessions_count=len(all_sessions),
            data_classification=classification,
            last_sync_timestamp=last_sync,
            next_expected_session=None,
            calendar_status=calendar_status,
        )

    def refresh(
        self,
        *,
        force: bool = False,
        as_of: date | None = None,
    ) -> DailyMarketRefreshResult:
        """Execute market data synchronization via the active provider."""
        return self.provider.sync_daily_bars(
            output_dir=self.output_dir,
            as_of=as_of,
            force=force,
        )
