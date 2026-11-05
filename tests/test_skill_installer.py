import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("target", ["codex", "cursor", "claude"])
def test_skill_copy_is_offline_idempotent_and_refuses_changes(tmp_path, target):
    command = [
        sys.executable,
        str(ROOT / "scripts/install_skills.py"),
        "--target",
        target,
        "--project",
        str(tmp_path),
    ]
    first = subprocess.run(command, capture_output=True, text=True, check=False)
    assert first.returncode == 0, first.stderr
    destination = ".claude/skills" if target == "claude" else ".agents/skills"
    entries = list((tmp_path / destination).glob("*/SKILL.md"))
    assert len(entries) == 10
    second = subprocess.run(command, capture_output=True, text=True, check=False)
    assert second.returncode == 0 and "0 newly copied" in second.stdout
    entries[0].write_text("local changes")
    third = subprocess.run(command, capture_output=True, text=True, check=False)
    assert third.returncode != 0 and "Existing skill differs" in third.stderr
    assert entries[0].read_text() == "local changes"
