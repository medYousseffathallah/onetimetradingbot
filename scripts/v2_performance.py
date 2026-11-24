"""Offline V2 API & Next.js page cold/warm latency profiler."""

from __future__ import annotations

import hashlib
import json
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
API_PATHS = (
    "/api/v2/overview",
    "/api/v2/portfolio",
    "/api/v2/discovery?universe=TUNIS_BOURSE_CHALLENGE&horizon=5_10",
    "/api/v2/positions/EURO-CYCLES",
    "/api/v2/attribution",
    "/api/v2/research-lab?horizon=10",
)
PAGE_PATHS = (
    "/",
    "/portfolio",
    "/discovery",
    "/positions/EURO-CYCLES",
    "/attribution",
    "/research-lab",
)


def _protected_hashes() -> dict[str, str]:
    base = ROOT.parent / "bvmt-starter-kit"
    return {
        p.relative_to(base).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for pattern in ("data/portfolio/**/*.json", "configs/*.json")
        for p in sorted(base.glob(pattern))
        if p.is_file()
    }


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright

    from bvmt_v2.api import create_v2_app

    initial_hashes = _protected_hashes()
    api_samples: dict[str, dict[str, list[float]]] = {
        p: {"cold": [], "warm": []} for p in API_PATHS
    }
    page_samples: dict[str, dict[str, list[float]]] = {
        p: {"cold": [], "warm": []} for p in PAGE_PATHS
    }
    errors: list[str] = []
    external: list[str] = []

    for path in API_PATHS:
        for _ in range(5):
            # Cold sample: fresh FastAPI app instance clears lru_cache
            with TestClient(
                create_v2_app(), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)
            ) as cold_client:
                t0 = time.perf_counter()
                r1 = cold_client.get(path, headers={"Host": "127.0.0.1"})
                api_samples[path]["cold"].append(round(1000 * (time.perf_counter() - t0), 3))
                assert r1.status_code == 200, r1.text

                # Warm sample: reuse populated lru_cache on same app
                t1 = time.perf_counter()
                r2 = cold_client.get(path, headers={"Host": "127.0.0.1"})
                api_samples[path]["warm"].append(round(1000 * (time.perf_counter() - t1), 3))
                assert r2.status_code == 200, r2.text

    app_dir = ROOT / "apps/terminal-v2"
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log_path = ROOT / "artifacts/v2/performance-next.log"

    with log_path.open("w", encoding="utf-8") as log_file:
        server = subprocess.Popen(
            [
                "node",
                str(app_dir / "node_modules/next/dist/bin/next"),
                "start",
                "-H",
                "127.0.0.1",
                "-p",
                str(port),
            ],
            cwd=app_dir,
            stdout=log_file,
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
                raise TimeoutError("Next V2 server unavailable")

            with TestClient(
                create_v2_app(), base_url="http://127.0.0.1", client=("127.0.0.1", 50000)
            ) as api_client:

                def attach_router(target_page: Any) -> None:
                    def route_handler(route: Any) -> None:
                        url = urlsplit(route.request.url)
                        if url.path.startswith("/api/v2/"):
                            path_q = url.path + (f"?{url.query}" if url.query else "")
                            resp = api_client.get(path_q, headers={"Host": "127.0.0.1"})
                            route.fulfill(
                                status=resp.status_code,
                                body=resp.content,
                                content_type="application/json",
                            )
                        elif url.hostname == "127.0.0.1" and url.port == port:
                            route.continue_()
                        else:
                            external.append(url.netloc)
                            route.abort()

                    target_page.on("pageerror", lambda e: errors.append(str(e)))
                    target_page.route("**/*", route_handler)

                with sync_playwright() as p:
                    browser = p.chromium.launch(channel="chrome", headless=True)
                    warm_context = browser.new_context(viewport={"width": 1440, "height": 1000})
                    warm_page = warm_context.new_page()
                    warm_page.set_default_timeout(45000)
                    attach_router(warm_page)
                    try:
                        # Prime Next.js server & lru_cache once before timing warm vs cold browser contexts
                        warm_page.goto(base + "/", wait_until="networkidle")
                        for path in PAGE_PATHS:
                            for _ in range(5):
                                cold_ctx = browser.new_context(
                                    viewport={"width": 1440, "height": 1000}
                                )
                                try:
                                    cold_page = cold_ctx.new_page()
                                    cold_page.set_default_timeout(45000)
                                    attach_router(cold_page)
                                    t0 = time.perf_counter()
                                    resp = cold_page.goto(base + path, wait_until="networkidle")
                                    assert resp is not None and resp.status == 200
                                    cold_page.wait_for_load_state("networkidle")
                                    page_samples[path]["cold"].append(
                                        round(1000 * (time.perf_counter() - t0), 3)
                                    )
                                finally:
                                    cold_ctx.close()

                                t1 = time.perf_counter()
                                resp_w = warm_page.goto(base + path, wait_until="networkidle")
                                assert resp_w is not None and resp_w.status == 200
                                warm_page.wait_for_load_state("networkidle")
                                page_samples[path]["warm"].append(
                                    round(1000 * (time.perf_counter() - t1), 3)
                                )
                    finally:
                        warm_context.close()
                        browser.close()
        finally:
            server.terminate()
            server.wait(timeout=10)

    final_hashes = _protected_hashes()
    assert initial_hashes == final_hashes
    assert not errors and not external

    out = {
        "recorded_at_utc": datetime.now(UTC).isoformat(),
        "samples": 5,
        "api_samples_ms": api_samples,
        "page_samples_ms": page_samples,
        "api_medians_ms": {
            k: {c: round(median(v), 3) for c, v in s.items()} for k, s in api_samples.items()
        },
        "page_medians_ms": {
            k: {c: round(median(v), 3) for c, v in s.items()} for k, s in page_samples.items()
        },
        "protected_files_unchanged": True,
        "runtime_errors": errors,
        "external_attempts": external,
    }
    out_path = ROOT / "artifacts/v2/performance.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "api_medians_ms": out["api_medians_ms"],
                "page_medians_ms": out["page_medians_ms"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
