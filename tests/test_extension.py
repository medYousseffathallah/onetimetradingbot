"""Unit test suite for BVMT Browser Companion extension (P0 Bug Fix).

Verifies:
- Manifest V3 structure and permissions.
- "scripting" permission presence.
- Safe execution context and defensive guards in popup.js.
- Zero extension-only API usage in content.js.
- Narrow host permissions (no broad <all_urls>).
"""

from __future__ import annotations

import json
from pathlib import Path

EXTENSION_DIR = Path("extension")


def test_manifest_v3_structure() -> None:
    manifest_path = EXTENSION_DIR / "manifest.json"
    assert manifest_path.is_file(), "manifest.json must exist in extension directory"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["manifest_version"] == 3
    assert manifest["name"] == "BVMT Intelligence Companion"

    # Strict permission audit
    perms = set(manifest.get("permissions", []))
    assert "scripting" in perms, (
        "Manifest must declare 'scripting' permission for chrome.scripting API"
    )
    assert "activeTab" in perms, "Manifest must declare 'activeTab' permission"
    assert "storage" in perms, "Manifest must declare 'storage' permission"
    assert "<all_urls>" not in perms, "Manifest must not declare broad <all_urls> in permissions"

    # Narrow host permissions
    host_perms = set(manifest.get("host_permissions", []))
    assert "<all_urls>" not in host_perms, "Broad permissions (<all_urls>) are strictly forbidden"
    assert "*://*/*" not in host_perms
    assert any("tunisbourse-challenge.com" in h for h in host_perms)
    assert any("localhost" in h or "127.0.0.1" in h for h in host_perms)

    # Action popup files existence
    assert "action" in manifest
    popup_html = manifest["action"].get("default_popup")
    assert popup_html == "popup.html"
    assert (EXTENSION_DIR / popup_html).is_file()


def test_extension_files_integrity() -> None:
    for filename in [
        "manifest.json",
        "popup.html",
        "popup.js",
        "content.js",
        "styles.css",
        "background.js",
    ]:
        path = EXTENSION_DIR / filename
        assert path.is_file(), f"Extension bundle file {filename} is missing"
        assert path.stat().st_size > 20, (
            f"Extension bundle file {filename} is empty or suspiciously small"
        )


def test_popup_scripting_guard() -> None:
    popup_js = (EXTENSION_DIR / "popup.js").read_text(encoding="utf-8")

    # 1. Guard against undefined chrome.scripting.executeScript
    assert (
        "chrome?.scripting?.executeScript" in popup_js
        or "chrome.scripting && chrome.scripting.executeScript" in popup_js
    ), "popup.js must defensively check for chrome.scripting.executeScript presence"

    # 2. Guard against missing active tab or invalid tab ID
    assert "targetTab.id" in popup_js or "tab.id" in popup_js
    assert "isAllowedChallengeUrl" in popup_js, "popup.js must validate authorized challenge URLs"

    # 3. Guard against restricted chrome:// and extension:// URLs
    assert "chrome://" in popup_js
    assert "chrome-extension://" in popup_js


def test_content_script_no_extension_apis() -> None:
    content_js = (EXTENSION_DIR / "content.js").read_text(encoding="utf-8")

    # content.js runs in web page context; it must NEVER invoke extension APIs
    assert "chrome.runtime" not in content_js
    assert "chrome.tabs" not in content_js
    assert "chrome.storage" not in content_js
    assert "chrome.scripting" not in content_js
    assert "browser." not in content_js
