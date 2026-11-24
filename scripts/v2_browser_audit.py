"""Isolated V2 Next.js production UI browser audit across all 9 destinations (1440px & 390px)."""

from __future__ import annotations

import argparse
import hashlib
import json
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SCREENS = (
    ("/", "v2-overview", "Investment Overview"),
    ("/portfolio", "v2-portfolio", "Portfolio Manager"),
    ("/discovery", "v2-discovery", "Opportunity Discovery"),
    ("/stocks/EURO-CYCLES", "v2-stock-research", "EURO-CYCLES"),
    ("/decisions", "v2-decisions", "Investment Decision Workspace"),
    ("/positions/EURO-CYCLES", "v2-position", "EURO-CYCLES"),
    ("/attribution", "v2-attribution", "Performance & Attribution"),
    ("/research-lab", "v2-research-lab", "Research Lab"),
    ("/health", "v2-health", "Data & Account Health"),
)


def _protected_hashes() -> dict[str, str]:
    base = ROOT.parent / "bvmt-starter-kit"
    result: dict[str, str] = {}
    for pattern in ("data/portfolio/**/*.json", "configs/*.json"):
        for p in sorted(base.glob(pattern)):
            if p.is_file():
                result[p.relative_to(base).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
    return result


def audit(app_dir: Path, out_dir: Path, artifact_dir: Path | None) -> dict[str, Any]:
    sys.path.insert(0, str(ROOT / "src"))
    from fastapi.testclient import TestClient
    from playwright.sync_api import sync_playwright

    from bvmt_v2.api import create_v2_app

    build_id_path = app_dir / ".next/BUILD_ID"
    if not build_id_path.is_file():
        raise FileNotFoundError(f"Missing Next.js build at {build_id_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    initial_hashes = _protected_hashes()
    result: dict[str, Any] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "build_id": build_id_path.read_text(encoding="utf-8").strip(),
        "checks": [],
        "screenshots": [],
        "api_statuses": [],
        "runtime_errors": [],
        "external_attempts": [],
    }

    app = create_v2_app()
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    log_path = out_dir.parent / "browser-audit-next.log"

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
                raise TimeoutError("Next V2 server failed to bind")

            with TestClient(
                app, base_url="http://127.0.0.1", client=("127.0.0.1", 50000)
            ) as client:
                with sync_playwright() as p:
                    browser = p.chromium.launch(channel="chrome", headless=True)
                    try:
                        page = browser.new_page(viewport={"width": 1440, "height": 1000})
                        page.on("pageerror", lambda e: result["runtime_errors"].append(str(e)))
                        page.on(
                            "console",
                            lambda msg: (
                                result["runtime_errors"].append(msg.text)
                                if msg.type == "error"
                                else None
                            ),
                        )

                        def handle_route(route: Any) -> None:
                            url = urlsplit(route.request.url)
                            if url.path.startswith("/api/v2/"):
                                path_q = url.path + (f"?{url.query}" if url.query else "")
                                method = route.request.method
                                headers = {"Host": "127.0.0.1"}
                                if method == "GET":
                                    resp = client.get(path_q, headers=headers)
                                elif method == "POST":
                                    resp = client.post(
                                        path_q,
                                        content=route.request.post_data_buffer or b"{}",
                                        headers={
                                            **headers,
                                            "Content-Type": "application/json",
                                        },
                                    )
                                else:
                                    route.abort()
                                    return
                                result["api_statuses"].append(
                                    {"path": path_q, "method": method, "status": resp.status_code}
                                )
                                route.fulfill(
                                    status=resp.status_code,
                                    body=resp.content,
                                    content_type=resp.headers.get(
                                        "content-type", "application/json"
                                    ),
                                )
                            elif url.hostname == "127.0.0.1" and url.port == port:
                                route.continue_()
                            else:
                                result["external_attempts"].append(url.netloc)
                                route.abort()

                        page.route("**/*", handle_route)

                        def settle() -> None:
                            page.wait_for_load_state("networkidle")
                            page.wait_for_timeout(200)

                        def visit(path: str) -> None:
                            resp = page.goto(base + path, wait_until="networkidle")
                            assert resp is not None and resp.status == 200
                            page.locator("main").wait_for()
                            settle()

                        def capture(filename: str) -> None:
                            target = out_dir / filename
                            page.screenshot(path=str(target), full_page=True)
                            result["screenshots"].append(str(target.relative_to(ROOT)))
                            if artifact_dir is not None and filename in {
                                "v2-overview-desktop.png",
                                "v2-portfolio-desktop.png",
                                "v2-discovery-desktop.png",
                                "v2-stock-research-desktop.png",
                                "v2-decisions-desktop.png",
                                "v2-position-desktop.png",
                                "v2-attribution-desktop.png",
                                "v2-research-lab-desktop.png",
                                "v2-health-desktop.png",
                                "v2-overview-mobile.png",
                                "v2-position-mobile.png",
                            }:
                                artifact_dir.mkdir(parents=True, exist_ok=True)
                                (artifact_dir / filename).write_bytes(target.read_bytes())

                        def check(name: str, fn: Callable[[], None]) -> None:
                            try:
                                fn()
                                result["checks"].append({"name": name, "status": "PASS"})
                            except Exception as exc:
                                result["checks"].append(
                                    {"name": name, "status": "FAIL", "error": str(exc)[:1000]}
                                )
                                try:
                                    capture(f"failure-{len(result['checks'])}.png")
                                except Exception:
                                    pass

                        for width, height, label in ((1440, 1000, "desktop"), (390, 844, "mobile")):
                            page.set_viewport_size({"width": width, "height": height})
                            for path, shot_name, heading in SCREENS:

                                def _run(
                                    p_arg: str = path,
                                    s_arg: str = shot_name,
                                    h_arg: str = heading,
                                    lbl: str = label,
                                    w: int = width,
                                ) -> None:
                                    visit(p_arg)
                                    assert page.get_by_role(
                                        "heading", name=h_arg, exact=False
                                    ).first.is_visible()
                                    overflow = page.evaluate(
                                        "document.documentElement.scrollWidth > innerWidth"
                                    )
                                    assert not overflow, f"Overflow on {p_arg} at {w}px"
                                    capture(f"{s_arg}-{lbl}.png")

                                check(f"{label} {path}", _run)

                        page.set_viewport_size({"width": 1440, "height": 1000})

                        def discovery_scope_switch() -> None:
                            visit("/discovery")
                            page.get_by_role("button", name="Full BVMT Research").click()
                            settle()
                            assert page.get_by_text("RESTRICTED", exact=False).first.is_visible()

                        check("discovery challenge vs full bvmt scope", discovery_scope_switch)

                        def decision_buy_scenarios() -> None:
                            visit("/decisions?instrument=MONOPRIX")
                            assert page.get_by_text(
                                "RESTRICTED_CHALLENGE", exact=False
                            ).first.is_visible()
                            assert page.get_by_role(
                                "button", name="Blocked: Outside Challenge Universe"
                            ).is_disabled()
                            visit("/decisions?instrument=EURO-CYCLES")
                            page.get_by_role("button", name="Run Dry-Run BUY Scenario").click()
                            settle()
                            assert page.get_by_text(
                                "UNVERIFIED_COMPETITION_RULES", exact=False
                            ).first.is_visible()

                        check("decisions non-challenge buy blocked", decision_buy_scenarios)

                        def position_worksheets() -> None:
                            visit("/positions/EURO-CYCLES")
                            page.get_by_role("button", name="Run Protection Scenario").click()
                            settle()
                            page.get_by_role("button", name="Simulate Manual Sale").click()
                            settle()
                            assert page.get_by_text("is_executed", exact=False).first.is_visible()

                        check("position protection and sell scenario", position_worksheets)

                        def demo_mode_switch() -> None:
                            visit("/?mode=SYNTHETIC_DEMO")
                            assert page.get_by_text("SYNTHETIC DEMO MODE", exact=False).is_visible()
                            visit("/positions/EURO-CYCLES?mode=SYNTHETIC_DEMO")
                            assert page.get_by_role(
                                "heading", name="EURO-CYCLES", exact=False
                            ).is_visible()

                        check("synthetic demo mode switching", demo_mode_switch)

                        browser.close()
                    finally:
                        pass
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)

    final_hashes = _protected_hashes()
    result["protected_files_unchanged"] = initial_hashes == final_hashes
    result["status"] = (
        "PASS"
        if (
            all(c["status"] == "PASS" for c in result["checks"])
            and not result["runtime_errors"]
            and not result["external_attempts"]
            and result["protected_files_unchanged"]
        )
        else "FAIL"
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app", type=Path, default=ROOT / "apps/terminal-v2")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/v2/browser-results.json")
    parser.add_argument(
        "--copy-artifacts",
        type=Path,
        default=Path(
            r"C:\Users\Thinkcenter\.gemini\antigravity\brain\f52abe73-b91c-4cc5-ad93-809e6f7ae9fe"
        ),
    )
    args = parser.parse_args()
    res = audit(
        args.app.resolve(), args.output.resolve().parent / "screenshots", args.copy_artifacts
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": res["status"],
                "checks": len(res["checks"]),
                "failed": [c for c in res["checks"] if c["status"] == "FAIL"],
                "runtime_errors": res["runtime_errors"],
                "external_attempts": res["external_attempts"],
                "protected_files_unchanged": res["protected_files_unchanged"],
                "screenshots": len(res["screenshots"]),
            }
        )
    )
    return 0 if res["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
