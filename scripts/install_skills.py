"""Copy this repository's reviewed local skills to an agent's project directory.

No network, external installers, deletion, or overwriting differing content.
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {"codex": ".agents/skills", "cursor": ".agents/skills", "claude": ".claude/skills"}


def file_manifest(folder: Path) -> dict[str, str]:
    manifest: dict[str, str] = {}
    for item in sorted(folder.rglob("*")):
        if item.is_symlink():
            raise ValueError(f"Refusing a symlink in a skill: {item}")
        if item.is_file():
            manifest[item.relative_to(folder).as_posix()] = hashlib.sha256(
                item.read_bytes()
            ).hexdigest()
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, choices=sorted(TARGETS))
    parser.add_argument("--project", type=Path, default=ROOT)
    args = parser.parse_args()
    project = args.project.resolve()
    destination = project / TARGETS[args.target]
    if not destination.resolve().is_relative_to(project):
        raise ValueError("Destination escapes the project directory")
    for ancestor in (destination, destination.parent):
        if ancestor.is_symlink():
            raise ValueError("Refusing symlinked installation directories")
    sources = sorted(entry.parent for entry in (ROOT / "skills").glob("*/SKILL.md"))
    if not sources:
        raise ValueError("No local skills to install")
    # Preflight every destination before writing anything.
    for source in sources:
        expected = file_manifest(source)
        target = destination / source.name
        if target.is_symlink():
            raise ValueError(f"Refusing a symlink target: {target}")
        if target.exists() and (not target.is_dir() or file_manifest(target) != expected):
            raise ValueError(f"Existing skill differs; review manually before replacing: {target}")
    destination.mkdir(parents=True, exist_ok=True)
    copied = 0
    for source in sources:
        target = destination / source.name
        if not target.exists():
            shutil.copytree(source, target)
            copied += 1
    print(
        f"{len(sources)} skills available in {destination}; {copied} newly copied; no network used."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
