"""Resolve an actual dependency lock when absent, then perform locked synchronization.

Network access is required on the first run. No lockfile is fabricated offline.
"""

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    if sys.version_info[:2] not in {(3, 12), (3, 13)}:
        print("Use Python 3.12 or 3.13 for this starter.", file=sys.stderr)
        return 1
    uv = shutil.which("uv")
    if uv is None:
        print(
            "uv is missing. Install it using the official instructions in README.md.",
            file=sys.stderr,
        )
        return 1
    if not (ROOT / "uv.lock").is_file():
        print(
            "No lockfile supplied. Resolving a real uv.lock; network access is required.",
            flush=True,
        )
        result = subprocess.run([uv, "lock", "--python", sys.executable], cwd=ROOT, check=False)
        if result.returncode:
            print(
                "Resolution failed; no success claimed. Use scripts/smoke_check.py offline.",
                file=sys.stderr,
            )
            return result.returncode
    return subprocess.run(
        [uv, "sync", "--locked", "--group", "dev", "--python", sys.executable],
        cwd=ROOT,
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
