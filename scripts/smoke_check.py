"""Standard-library smoke checks; no installs, network, pytest or market credentials."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src")
    demo = subprocess.run(
        [sys.executable, "-m", "bvmt.cli", "demo"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if demo.returncode:
        print(demo.stderr, file=sys.stderr)
        return demo.returncode
    payload = json.loads(demo.stdout)
    if payload["mode"] != "synthetic_demo" or payload["execution_authorized"] is not False:
        raise ValueError("Synthetic demo safety contract failed")
    rules = subprocess.run(
        [sys.executable, "-m", "bvmt.cli", "rules-check"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if rules.returncode != 2 or json.loads(rules.stdout)["status"] != "blocked":
        raise ValueError("Shipped unverified rules must block readiness")
    skills = subprocess.run([sys.executable, "scripts/validate_skills.py"], cwd=ROOT, check=False)
    if skills.returncode:
        return skills.returncode
    print("Offline smoke checks passed: synthetic demo, blocked rules, and local skills.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
