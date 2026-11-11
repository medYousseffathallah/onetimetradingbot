"""Paired cold API comparison with/without immutable validation proof reuse."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from contextlib import nullcontext
from pathlib import Path
from statistics import median
from unittest.mock import patch
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from m14_perf_audit import DATASET, _copy_runtime, _protected_hashes, _sha  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser", action="store_true")
    args = parser.parse_args()
    from fastapi.testclient import TestClient

    from bvmt import data
    from bvmt.api import create_app
    from bvmt.perf_cache import invalidate_all_caches
    from bvmt.portfolio_service import PortfolioStateService

    output = ROOT / "artifacts/m14-joint/paired-cold-api.json"
    protected = _protected_hashes()
    original_cwd = Path.cwd()
    samples: dict[str, dict[str, list[float]]] = {
        r: {"reference": [], "reuse": []} for r in ("/api/overview", "/api/rankings")
    }
    same_responses = True
    external_attempts = []
    original_connect = socket.socket.connect
    page_result = None

    def guard(sock, address):
        if isinstance(address, tuple) and address[0] in {"127.0.0.1", "::1", "localhost"}:
            return original_connect(sock, address)
        external_attempts.append(str(address))
        raise AssertionError("External network disabled")

    try:
        with tempfile.TemporaryDirectory(dir=output.parent, prefix="paired-api-") as temporary:
            runtime = Path(temporary)
            _copy_runtime(runtime)
            os.chdir(runtime)
            dataset = runtime / DATASET
            service = PortfolioStateService(
                bars_path=dataset / "daily_bars.canonical.csv",
                ledger_path=runtime / "data/portfolio/real_competition_ledger.json",
                real_snapshot_path=runtime / "data/portfolio/real_account_snapshot.json",
                snapshots_dir=runtime / "data/portfolio/snapshots",
                alerts_path=runtime / "data/portfolio/paired-alerts.json",
                calendar_path=dataset / "exchange_calendar.csv",
                instruments_path=dataset / "instrument_master.csv",
                competition_config_path=runtime / "configs/competition.json",
                llm_config_path=runtime / "configs/llm_budget.example.json",
                doc_index_path=runtime / "artifacts/doc_index.json",
                processed_root=runtime / "data/processed",
            )
            with (
                patch("socket.socket.connect", new=guard),
                TestClient(create_app(service)) as client,
            ):
                if args.browser:
                    page_result = measure_pages(client, data, invalidate_all_caches, output.parent)
                for pair in range(5):
                    for route in samples:
                        payloads = []
                        for mode in (
                            ("reference", "reuse") if pair % 2 == 0 else ("reuse", "reference")
                        ):
                            invalidate_all_caches()
                            context = (
                                patch.object(
                                    data._VALIDATED_BAR_ARTIFACTS, "get", return_value=None
                                )
                                if mode == "reference"
                                else nullcontext()
                            )
                            with context:
                                started = time.perf_counter()
                                response = client.get(route)
                                elapsed = (time.perf_counter() - started) * 1000
                            assert response.status_code == 200
                            payloads.append(response.json())
                            samples[route][mode].append(round(elapsed, 3))
                        same_responses = same_responses and payloads[0] == payloads[1]
                    print(f"pair {pair + 1}/5", flush=True)
            os.chdir(original_cwd)
    finally:
        os.chdir(original_cwd)
    changed = [name for name, digest in protected.items() if _sha(ROOT / name) != digest]
    result = {
        "scope": "Alternating five paired application-cache-cold in-process API requests. Same final code/inputs; only validation proof reuse disabled for reference. OS caches retained, not TCP/disk-cold or browser speedup.",
        "samples_ms": samples,
        "summary": {
            route: {
                "reference_median_ms": median(row["reference"]),
                "reuse_median_ms": median(row["reuse"]),
                "median_reduction_pct": round(
                    100 * (1 - median(row["reuse"]) / median(row["reference"])), 2
                ),
            }
            for route, row in samples.items()
        },
        "responses_equal": same_responses,
        "protected_files_changed": changed,
        "external_attempts": len(external_attempts),
        "page_loading": page_result,
    }
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result["summary"]), flush=True)
    return 0 if same_responses and not changed and not external_attempts else 1


def measure_pages(client, data, invalidate, folder):
    """Page timings include real copied-data callbacks, not synthetic responses."""
    from playwright.sync_api import sync_playwright

    samples = {path: {"reference": [], "reuse": []} for path in ("/", "/market")}
    statuses, errors, writes, external = [], [], [], []
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    with (folder / "paired-next.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [
                "node",
                str(ROOT / "frontend/node_modules/next/dist/bin/next"),
                "start",
                "-H",
                "127.0.0.1",
                "-p",
                str(port),
            ],
            cwd=ROOT / "artifacts/m14-joint/frontend-preview",
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                try:
                    with socket.create_connection(("127.0.0.1", port), timeout=1):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise TimeoutError("Isolated Next server did not start")
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                try:
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))

                    def intercept(route):
                        url = urlsplit(route.request.url)
                        if url.path.startswith("/api/"):
                            if route.request.method != "GET":
                                writes.append(url.path)
                                route.fulfill(status=403, body="Writes blocked")
                                return
                            response = client.get(url.path + ("?" + url.query if url.query else ""))
                            statuses.append(response.status_code)
                            route.fulfill(
                                status=response.status_code,
                                body=response.content,
                                content_type="application/json",
                            )
                        elif url.hostname == "127.0.0.1" and url.port == port:
                            route.continue_()
                        else:
                            external.append(url.netloc)
                            route.abort()

                    page.route("**/*", intercept)
                    for path in samples:
                        page.goto(base + path, wait_until="networkidle")
                    for pair in range(5):
                        for path in samples:
                            for mode in (
                                ("reference", "reuse") if pair % 2 == 0 else ("reuse", "reference")
                            ):
                                invalidate()
                                context = (
                                    patch.object(
                                        data._VALIDATED_BAR_ARTIFACTS, "get", return_value=None
                                    )
                                    if mode == "reference"
                                    else nullcontext()
                                )
                                with context:
                                    start = time.perf_counter()
                                    response = page.goto(base + path, wait_until="networkidle")
                                    assert response.status == 200
                                    page.wait_for_timeout(550)
                                    page.wait_for_load_state("networkidle")
                                    samples[path][mode].append(
                                        round((time.perf_counter() - start) * 1000, 3)
                                    )
                        print(f"browser pair {pair + 1}/5", flush=True)
                finally:
                    browser.close()
        finally:
            server.terminate()
            server.wait(timeout=20)
    assert not errors and not writes and not external and all(s == 200 for s in statuses)
    return {
        "scope": "Current production Next build; copied real EOD/account inputs; browser API callbacks via TestClient, not TCP API. Warm JS/OS caches, cold application caches; includes550ms effect allowance. No production account writes.",
        "samples_ms": samples,
        "summary": {
            path: {
                "reference_median_ms": median(v["reference"]),
                "reuse_median_ms": median(v["reuse"]),
                "median_reduction_pct": round(
                    100 * (1 - median(v["reuse"]) / median(v["reference"])), 2
                ),
            }
            for path, v in samples.items()
        },
        "api_responses": len(statuses),
        "runtime_errors": len(errors),
        "external_requests": len(external),
        "write_requests": len(writes),
    }


if __name__ == "__main__":
    raise SystemExit(main())
