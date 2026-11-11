"""Verify M14 local design artifacts and isolated current Next.js rendering.

No actual account session is opened. Dashboard API calls use disposable synthetic
fixtures through TestClient; browsers cannot reach external network destinations.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import socket
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VIEWS = {
    "overview.html": ["overview", "portfolio", "performance", "health"],
    "research.html": ["screener", "stock", "decision", "planner"],
}


def summary(values: list[float]) -> dict[str, Any]:
    return {
        "samples_ms": values,
        "n": len(values),
        "p50_ms": round(statistics.median(values), 2),
        "p95_ms": sorted(values)[math.ceil(0.95 * len(values)) - 1],
    }


def prototypes(browser: Any, output: Path) -> dict[str, Any]:
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    errors: list[str] = []
    external: list[str] = []
    page.on("pageerror", lambda error: errors.append(str(error)))

    def offline(route: Any) -> None:
        if urlsplit(route.request.url).scheme in {"file", "data"}:
            route.continue_()
        else:
            external.append(urlsplit(route.request.url).netloc)
            route.abort()

    page.route("**/*", offline)
    pages = []
    for filename, views in VIEWS.items():
        for view in views:
            page.goto((ROOT / "docs/prototypes/m14" / filename).as_uri() + "#" + view)
            page.locator(f"#{view}.active").wait_for()
            assert page.locator(".navlink").count() == 8
            assert page.get_by_text("DESIGN SANDBOX", exact=True).is_visible()
            overflow = page.evaluate("document.documentElement.scrollWidth > innerWidth")
            assert not overflow, (filename, view, "desktop overflow")
            pages.append({"view": view, "desktop_overflow": overflow})
        page.screenshot(
            path=str(output / filename.replace(".html", "-desktop.png")), full_page=True
        )

    page.goto((ROOT / "docs/prototypes/m14/overview.html").as_uri())
    page.locator('[data-open-dialog="sync-preview"]').first.click()
    assert page.locator("#sync-preview").is_visible()
    assert page.locator("#sync-preview button:not([disabled])").count() == 1
    page.locator("#sync-preview [data-close-dialog]").click()
    page.get_by_role("button", name="90D", exact=True).click()
    assert page.locator("[data-chart-period]").inner_text().startswith("90D")
    page.screenshot(path=str(output / "overview-desktop.png"), full_page=True)

    page.goto((ROOT / "docs/prototypes/m14/research.html").as_uri())
    page.locator("#stock-search").fill("not-a-security")
    assert page.locator("#result-count").inner_text().startswith("0 ")
    assert page.locator("#no-results").is_visible()
    page.locator("#stock-search").fill("")
    page.locator("#coverage-filter").select_option(index=1)
    assert int(page.locator("#result-count").inner_text().split()[0]) > 0
    page.goto((ROOT / "docs/prototypes/m14/research.html").as_uri() + "#stock")
    page.locator("#evidence-scenario").select_option("empty")
    assert page.locator("[data-quote]").first.inner_text() == "Unavailable"
    assert (
        page.locator("#research-chart-line").evaluate("el=>getComputedStyle(el).visibility")
        == "hidden"
    )
    page.locator("[data-evidence-tab]").nth(1).click()
    assert page.locator("[data-evidence-tab].active").count() == 1
    page.locator("#evidence-scenario").select_option("stale")
    page.screenshot(path=str(output / "research-desktop.png"), full_page=True)
    page.goto((ROOT / "docs/prototypes/m14/research.html").as_uri() + "#decision")
    page.locator("#research-note").fill("Verify dated issuer evidence before any decision.")
    page.locator("#save-note").click()
    assert "page only" in page.locator("#note-status").inner_text()
    page.reload()
    assert page.locator("#research-note").input_value() == ""
    page.goto((ROOT / "docs/prototypes/m14/research.html").as_uri() + "#planner")
    page.locator("#limit-input").fill("23.456")
    page.locator("#review-calculation").click()
    assert "23.456" in page.locator("#limit-output").inner_text()
    assert page.locator("#planner button[disabled]").count() > 0
    for filename, views in VIEWS.items():
        page.set_viewport_size({"width": 390, "height": 844})
        for view in views:
            page.goto((ROOT / "docs/prototypes/m14" / filename).as_uri() + "#" + view)
            assert not page.evaluate("document.documentElement.scrollWidth > innerWidth"), (
                view,
                "mobile overflow",
            )
        page.goto((ROOT / "docs/prototypes/m14" / filename).as_uri() + "#" + views[0])
        page.screenshot(path=str(output / filename.replace(".html", "-mobile.png")), full_page=True)
    page.goto((ROOT / "docs/prototypes/m14/wireframes.html").as_uri())
    assert page.locator("svg").count() == 8
    page.screenshot(path=str(output / "wireframes.png"), full_page=True)
    page.close()
    assert not errors, errors
    assert not external, external
    return {
        "status": "PASS",
        "views": pages,
        "runtime_errors": errors,
        "external_requests": external,
        "interaction_checks": 14,
        "responsive_widths": [1440, 390],
    }


def dashboard(browser: Any, build: Path, output: Path) -> dict[str, Any]:
    from fastapi.testclient import TestClient

    sys.path.insert(0, str(ROOT / "tests"))
    from test_api import service as service_fixture

    from bvmt.api import create_app

    cwd = Path.cwd()
    with tempfile.TemporaryDirectory(prefix="browser-fixtures-", dir=output.parent) as directory:
        runtime = Path(directory)
        try:
            os.chdir(runtime)
            # Dataset discovery also inspects its documented relative demo fallback.
            shutil.copytree(ROOT / "tests/fixtures", runtime / "tests/fixtures")
            dataset = runtime / "data/processed/bvmt_official_2026"
            dataset.mkdir(parents=True)
            for name, target in [
                ("daily_bars.csv", "daily_bars.canonical.csv"),
                ("exchange_calendar.csv", "exchange_calendar.csv"),
                ("instrument_master.csv", "instrument_master.csv"),
            ]:
                shutil.copy2(ROOT / "tests/fixtures" / name, dataset / target)
            service = service_fixture.__wrapped__(runtime)
            app = create_app(
                service,
                paper_bars_path=dataset / "daily_bars.canonical.csv",
                paper_calendar_path=dataset / "exchange_calendar.csv",
                paper_instruments_path=dataset / "instrument_master.csv",
                paper_journal_path=runtime / "paper.json",
            )
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            with (output.parent / "next-preview.log").open("w", encoding="utf-8") as log:
                started = time.perf_counter()
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
                    cwd=build,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                try:
                    deadline = time.monotonic() + 40
                    while time.monotonic() < deadline:
                        if server.poll() is not None:
                            raise RuntimeError(
                                "Isolated Next server exited; inspect next-preview.log"
                            )
                        try:
                            with urllib.request.urlopen(base, timeout=1):
                                break
                        except OSError:
                            time.sleep(0.2)
                    else:
                        raise TimeoutError("Isolated Next listener unavailable")
                    startup_ms = round((time.perf_counter() - started) * 1000, 2)
                    errors: list[str] = []
                    statuses: list[dict[str, Any]] = []
                    external: list[str] = []
                    writes: list[str] = []
                    page = browser.new_page(viewport={"width": 1440, "height": 1000})
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    with TestClient(app) as client:

                        def intercept(route: Any) -> None:
                            url = urlsplit(route.request.url)
                            if url.path.startswith("/api/"):
                                if route.request.method != "GET":
                                    writes.append(url.path)
                                    route.fulfill(status=403, body="Audit blocks all writes")
                                    return
                                response = client.get(
                                    url.path + ("?" + url.query if url.query else "")
                                )
                                statuses.append({"path": url.path, "status": response.status_code})
                                body = response.content
                                if url.path == "/api/sync/pairing-token":
                                    data = response.json()
                                    data["pairing_token"] = "fixture-token-not-active"
                                    body = json.dumps(data).encode()
                                route.fulfill(
                                    status=response.status_code,
                                    body=body,
                                    content_type="application/json",
                                    headers={"Access-Control-Allow-Origin": "*"},
                                )
                            elif url.hostname in {"127.0.0.1", "localhost"} and url.port == port:
                                route.continue_()
                            else:
                                external.append(url.netloc)
                                route.abort()

                        page.route("**/*", intercept)
                        routes = [
                            "/",
                            "/portfolio",
                            "/market",
                            "/research",
                            "/planner",
                            "/transactions",
                            "/strategy",
                            "/health",
                            "/daily-summary",
                        ]
                        rows = []
                        for path in routes:
                            began = time.perf_counter()
                            response = page.goto(base + path, wait_until="networkidle")
                            page.locator("main").wait_for()
                            cold = round((time.perf_counter() - began) * 1000, 2)
                            warm = []
                            for _ in range(3):
                                began = time.perf_counter()
                                page.reload(wait_until="networkidle")
                                warm.append(round((time.perf_counter() - began) * 1000, 2))
                            rows.append(
                                {
                                    "route": path,
                                    "http_status": response.status,
                                    "cold_visit_ms": cold,
                                    "warm_reload": summary(warm),
                                }
                            )
                            if path in {"/", "/planner"}:
                                page.screenshot(
                                    path=str(
                                        output
                                        / (
                                            "dashboard-home.png"
                                            if path == "/"
                                            else "dashboard-planner.png"
                                        )
                                    ),
                                    full_page=True,
                                )
                        navigation = []
                        for path in [
                            "/portfolio",
                            "/market",
                            "/planner",
                            "/strategy",
                            "/health",
                            "/",
                        ]:
                            began = time.perf_counter()
                            page.locator(f'aside a[href="{path}"]').first.click()
                            page.wait_for_url(base + path)
                            # Allow scheduled client effects to start before checking idle.
                            page.wait_for_timeout(550)
                            page.wait_for_load_state("networkidle")
                            navigation.append(
                                {
                                    "route": path,
                                    "settled_ms": round((time.perf_counter() - began) * 1000, 2),
                                }
                            )
                    page.close()
                    return {
                        "status": "PASS"
                        if not errors
                        and not writes
                        and not external
                        and all(row["http_status"] == 200 for row in rows)
                        and all(row["status"] == 200 for row in statuses)
                        else "FAIL",
                        "scope": "isolated production Next build; synthetic in-process API fixture interception; not real account or end-to-end API/network timings",
                        "settled_definition": "networkidle includes 500ms quiet; SPA navigation adds 550ms for scheduled effects",
                        "startup_listener_and_first_html_ms": startup_ms,
                        "routes": rows,
                        "sidebar_navigation": navigation,
                        "runtime_errors": errors,
                        "api_statuses": statuses,
                        "external_requests": external,
                        "blocked_write_requests": writes,
                    }
                finally:
                    server.terminate()
                    try:
                        server.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait(timeout=10)
        finally:
            os.chdir(cwd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-dashboard", action="store_true")
    parser.add_argument("--build", type=Path, default=ROOT / "artifacts/m14/frontend-preview")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "artifacts/m14/screenshots")
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel="chrome", headless=True)
        try:
            result = {
                "recorded_at": datetime.now(UTC).isoformat(),
                "browser": browser.version,
                "prototypes": prototypes(browser, output),
            }
            if not args.skip_dashboard:
                result["dashboard"] = dashboard(browser, args.build.resolve(), output)
        finally:
            browser.close()
    (output.parent / "browser-results.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(
        json.dumps(
            {key: value.get("status") for key, value in result.items() if isinstance(value, dict)}
        )
    )
    return (
        0
        if all(
            value.get("status") == "PASS" for value in result.values() if isinstance(value, dict)
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
