"""Measure M14 offline API latency in an isolated disposable working directory.

Run from the repository root with its existing environment. This uses FastAPI's
in-process TestClient, not a TCP server or a browser. Account responses are never
printed or saved. Source files are hashed before/after and all writable runtime
paths are under a temporary copy. No dependency installation or network access.
"""

from __future__ import annotations

import argparse
import cProfile
import hashlib
import json
import math
import os
import platform
import pstats
import shutil
import socket
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DATASET = Path("data/processed/bvmt_official_2026")
ROUTES = (
    "/api/health",
    "/api/overview",
    "/api/holdings",
    "/api/snapshots",
    "/api/transactions",
    "/api/orders/pending",
    "/api/market-status",
    "/api/rankings",
    "/api/market-research",
    "/api/research?include_strategy_comparison=false",
    "/api/research",
    "/api/strategy-lab",
    "/api/paper-trading",
    "/api/session/summary",
    "/api/trade-plans?universe=TUNIS_BOURSE_CHALLENGE",
    "/api/holding-periods?universe=TUNIS_BOURSE_CHALLENGE",
    "/api/trading-intelligence",
    "/api/sync/preview",
    "/api/glossary",
    "/api/challenge-universe",
    "/api/market-data/status",
)


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _protected_hashes() -> dict[str, str]:
    paths = [*ROOT.glob("src/bvmt/*.py"), *ROOT.glob("data/portfolio/**/*.json")]
    paths.extend((ROOT / DATASET).glob("*.csv"))
    paths.extend((ROOT / "configs").glob("*.json"))
    return {path.relative_to(ROOT).as_posix(): _sha(path) for path in paths}


def _copy_runtime(destination: Path) -> None:
    """Copy only runtime inputs, never browser profiles, cookies, env or tokens."""
    groups = (
        (ROOT / DATASET).glob("*.csv"),
        (ROOT / DATASET).glob("*.json"),
        (ROOT / "data/portfolio").rglob("*.json"),
        (ROOT / "configs").glob("*.json"),
        (ROOT / "tests/fixtures").glob("*.csv"),
    )
    paths = [path for group in groups for path in group]
    for name in ("strategy_experiments_2026.json", "backtest_audit_2026.json", "doc_index.json"):
        path = ROOT / "artifacts" / name
        if path.is_file():
            paths.append(path)
    for source in paths:
        # Jobs may carry browser/session diagnostics; the audit needs none of them.
        if source.name in {"sync_jobs.json"}:
            continue
        target = destination / source.relative_to(ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def _duration(call: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = call()
    return result, round((time.perf_counter() - started) * 1000, 3)


def _summary(samples: list[float]) -> dict[str, Any]:
    ordered = sorted(samples)
    return {
        "samples_ms": samples,
        "sample_count": len(samples),
        "p50_ms": round(statistics.median(samples), 3),
        "p95_ms": ordered[math.ceil(0.95 * len(ordered)) - 1],
        "percentile_method": "nearest_rank",
    }


def _profile_rows(profile: cProfile.Profile) -> list[dict[str, Any]]:
    stats = pstats.Stats(profile)
    selected = sorted(stats.stats.items(), key=lambda item: item[1][3], reverse=True)
    rows = []
    for (filename, line, function), (primitive, total, own, cumulative, _callers) in selected:
        if "bvmt" not in filename or len(rows) >= 20:
            continue
        rows.append(
            {
                "file": Path(filename).name,
                "line": line,
                "function": function,
                "primitive_calls": primitive,
                "total_calls": total,
                "own_ms": round(own * 1000, 3),
                "cumulative_ms": round(cumulative * 1000, 3),
            }
        )
    return rows


def _measure(working: Path, samples: int) -> dict[str, Any]:
    os.chdir(working)
    sys.path.insert(0, str(ROOT / "src"))
    started = time.perf_counter()
    from fastapi.testclient import TestClient

    from bvmt.api import create_app
    from bvmt.perf_cache import get_cache_generation, invalidate_all_caches
    from bvmt.portfolio_service import PortfolioStateService

    import_ms = round((time.perf_counter() - started) * 1000, 3)
    service = PortfolioStateService(
        portfolio_mode="REAL_COMPETITION",
        bars_path=working / DATASET / "daily_bars.canonical.csv",
        ledger_path=working / "data/portfolio/real_competition_ledger.json",
        alerts_path=working / "data/portfolio/m14_alerts.json",
        calendar_path=working / DATASET / "exchange_calendar.csv",
        instruments_path=working / DATASET / "instrument_master.csv",
        competition_config_path=working / "configs/competition.json",
        llm_config_path=working / "configs/llm_budget.example.json",
        doc_index_path=working / "artifacts/doc_index.json",
        real_snapshot_path=working / "data/portfolio/real_account_snapshot.json",
        snapshots_dir=working / "data/portfolio/snapshots",
        processed_root=working / "data/processed",
    )
    app, create_ms = _duration(
        lambda: create_app(
            service,
            strategy_registry_path=working / "artifacts/strategy_experiments_2026.json",
            paper_journal_path=working / "artifacts/m14_paper_journal.json",
            paper_bars_path=working / DATASET / "daily_bars.canonical.csv",
            paper_calendar_path=working / DATASET / "exchange_calendar.csv",
            paper_instruments_path=working / DATASET / "instrument_master.csv",
        )
    )
    invalidate_all_caches()
    state, cold_state_ms = _duration(service.load_state)
    warm_state = [_duration(service.load_state)[1] for _ in range(samples)]
    endpoints: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for route in ROUTES:
            invalidate_all_caches()
            response, cold_ms = _duration(lambda route=route: client.get(route))
            statuses = [response.status_code]
            warm = []
            for _ in range(samples):
                response, elapsed = _duration(lambda route=route: client.get(route))
                warm.append(elapsed)
                statuses.append(response.status_code)
            row = {
                "route": route,
                "statuses": statuses,
                "payload_bytes": len(response.content),
                "cold_ms": cold_ms,
                "cold_definition": "registered application caches cleared; OS file cache retained",
                "warm": _summary(warm),
                "warm_p95_target_ms": 500,
                "verdict": "PASS"
                if max(statuses) == min(statuses) == 200 and max(warm) < 500
                else "FAIL",
            }
            endpoints.append(row)
            print(
                json.dumps({key: row[key] for key in ("route", "cold_ms", "verdict")}), flush=True
            )

    # Controlled cache invalidation probes mutate disposable copies only.
    invalidate_all_caches()
    first = service.load_state()
    cached = service.load_state()
    ledger = service.resolve_context().ledger_path
    ledger_raw = json.loads(ledger.read_text(encoding="utf-8"))
    ledger_raw["updated_at"] = "2099-01-01T00:00:00+00:00"  # fixture-only metadata mutation
    ledger.write_text(json.dumps(ledger_raw), encoding="utf-8")
    changed = service.load_state()
    snapshot_paths = sorted(service.snapshots_dir.glob("sync_*.json"))
    if not snapshot_paths:
        raise ValueError("Cache probe requires a copied snapshot")
    duplicate = service.snapshots_dir / "sync_m14_cache_probe.json"
    duplicate.write_bytes(snapshot_paths[-1].read_bytes())
    after_snapshot = service.load_state()
    generation_before = get_cache_generation()
    invalidate_all_caches()
    regenerated = service.load_state()
    cache_checks = {
        "warm_identity_reused": first is cached,
        "ledger_content_change_invalidates": changed is not cached,
        "snapshot_directory_change_invalidates": after_snapshot is not changed,
        "explicit_generation_change_invalidates": (
            get_cache_generation() > generation_before and regenerated is not after_snapshot
        ),
    }

    profile = cProfile.Profile()
    invalidate_all_caches()
    profile.enable()
    service.load_state()
    profile.disable()
    return {
        "import_api_and_testclient_ms": import_ms,
        "create_app_ms": create_ms,
        "state_cold_ms": cold_state_ms,
        "state_warm": _summary(warm_state),
        "state_cold_profile": _profile_rows(profile),
        "endpoints": endpoints,
        "cache_checks": cache_checks,
        "timestamps": {
            "market_session": state.latest_bar_session_str,
            "decision_cutoff": state.recommendations.decision_cutoff,
            "quote_kind": "EOD; no measured intraday quote",
            "freshness_scope": "relative to dataset decision cutoff, not wall-clock trading freshness",
            "account_values_recorded": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, default=8)
    parser.add_argument("--output", type=Path, default=Path("artifacts/m14/performance.json"))
    args = parser.parse_args()
    if args.samples < 3:
        parser.error("at least 3 warm samples are required")
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    initial_cwd = Path.cwd()
    previous_allow_live = os.environ.get("BVMT_ALLOW_LIVE_LLM")
    os.environ["BVMT_ALLOW_LIVE_LLM"] = "0"
    source_hashes = _protected_hashes()
    network_attempts = 0
    internal_loopback_connections = 0
    original_connect = socket.socket.connect

    def deny_network(*_args: Any, **_kwargs: Any) -> Any:
        nonlocal network_attempts
        network_attempts += 1
        raise AssertionError("Network disabled by M14 audit harness")

    def guarded_connect(sock: socket.socket, address: Any) -> Any:
        nonlocal internal_loopback_connections
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1", "localhost"}:
            # Windows asyncio implements its wake-up socketpair using loopback.
            internal_loopback_connections += 1
            return original_connect(sock, address)
        return deny_network()

    try:
        with tempfile.TemporaryDirectory(
            prefix="performance-runtime-", dir=output.parent
        ) as runtime:
            working = Path(runtime)
            _copy_runtime(working)
            try:
                with (
                    patch("socket.socket.connect", new=guarded_connect),
                    patch("urllib.request.urlopen", side_effect=deny_network),
                ):
                    measurements = _measure(working, args.samples)
            finally:
                # Leave the runtime before Windows attempts to remove its CWD.
                os.chdir(initial_cwd)
    finally:
        os.chdir(initial_cwd)
        if previous_allow_live is None:
            os.environ.pop("BVMT_ALLOW_LIVE_LLM", None)
        else:
            os.environ["BVMT_ALLOW_LIVE_LLM"] = previous_allow_live
    changed = [path for path, sha in source_hashes.items() if _sha(ROOT / path) != sha]
    result = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "scope": "FastAPI in-process TestClient; not TCP, browser or Next.js",
        "cold_process_samples": 1,
        "warm_samples_per_route": args.samples,
        "system": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logical_processors": os.cpu_count(),
        },
        "network_attempts_blocked": network_attempts,
        "internal_loopback_connections": internal_loopback_connections,
        "source_files_hashed": len(source_hashes),
        "source_files_changed": changed,
        "disposable_runtime_copy": True,
        **measurements,
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    passed = (
        not changed
        and network_attempts == 0
        and all(measurements["cache_checks"].values())
        and all(row["verdict"] == "PASS" for row in measurements["endpoints"])
    )
    print(json.dumps({"output": str(output), "verdict": "PASS" if passed else "FAIL"}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
