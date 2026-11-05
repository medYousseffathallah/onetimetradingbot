"""Run the offline quality gate in the currently active project environment."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    [sys.executable, "-m", "ruff", "format", "--check", "src", "tests", "scripts"],
    [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"],
    [sys.executable, "-m", "mypy", "src/bvmt"],
    [sys.executable, "scripts/validate_skills.py"],
    [sys.executable, "-m", "pytest", "-q"],
]


def main() -> int:
    for command in COMMANDS:
        print("RUN:", " ".join(command), flush=True)
        result = subprocess.run(command, cwd=ROOT, check=False)
        if result.returncode:
            return result.returncode
    print("All offline quality gates passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
