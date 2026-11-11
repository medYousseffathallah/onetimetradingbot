"""Alternate original full-batch validation and immutable-proof reuse on identical rows.

This isolates validation CPU work, not full API or disk-cold latency. No account
files, network, scores or source mutations. Run after the whole-route audit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import time
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from bvmt import data
from bvmt.perf_cache import invalidate_all_caches


def reference_validate(bars: list[data.DailyBar]) -> list[data.DailyBar]:
    # Exact pre-reuse validate_bars algorithm: preserved in starting data.py copy.
    result = list(bars)
    if not result:
        raise ValueError("Dataset is empty")
    seen = set()
    for bar in result:
        data.validate_bar(bar)
        key = (bar.instrument_id, bar.session_date)
        if key in seen:
            raise ValueError(f"Duplicate instrument/session: {key}")
        seen.add(key)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pairs", type=int, default=7)
    parser.add_argument(
        "--bars",
        type=Path,
        default=Path("data/processed/bvmt_official_2026/daily_bars.canonical.csv"),
    )
    parser.add_argument(
        "--output", type=Path, default=Path("artifacts/m14/cold-reuse/paired-validation.json")
    )
    args = parser.parse_args()
    if args.pairs < 5:
        parser.error("at least five alternating pairs required")
    before_sha = hashlib.sha256(args.bars.read_bytes()).hexdigest()
    rows = data.read_bars_csv(args.bars)
    assert reference_validate(rows) == data.validate_bars(rows)
    measurements: dict[str, list[float]] = {"reference": [], "reuse": []}
    for pair in range(args.pairs):
        for kind in ("reference", "reuse") if pair % 2 == 0 else ("reuse", "reference"):
            invalidate_all_caches()
            validate = reference_validate if kind == "reference" else data.validate_bars
            started = time.perf_counter()
            for _ in range(3):
                validate(rows)
            measurements[kind].append(round((time.perf_counter() - started) * 1000, 3))
    calls = {}
    for name, function in (("reference", reference_validate), ("reuse", data.validate_bars)):
        invalidate_all_caches()
        with patch.object(data, "validate_bar", wraps=data.validate_bar) as checked:
            for _ in range(3):
                function(rows)
            calls[name] = checked.call_count
    unchanged = before_sha == hashlib.sha256(args.bars.read_bytes()).hexdigest()
    reference_ms = statistics.median(measurements["reference"])
    reuse_ms = statistics.median(measurements["reuse"])
    result = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "rows": len(rows),
        "source_sha256": before_sha,
        "source_unchanged": unchanged,
        "pairs": args.pairs,
        "order": "AB then BA alternating; three validation boundaries per sample",
        "scope": "validation CPU only, already parsed rows; not whole API speedup; background load uncontrolled",
        "samples_ms": measurements,
        "median_ms": {"reference": reference_ms, "reuse": reuse_ms},
        "validation_calls_three_boundaries": calls,
        "median_reduction_pct": round((1 - reuse_ms / reference_ms) * 100, 2),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                key: result[key]
                for key in [
                    "rows",
                    "median_ms",
                    "median_reduction_pct",
                    "validation_calls_three_boundaries",
                    "source_unchanged",
                ]
            }
        )
    )
    return 0 if unchanged and reuse_ms < reference_ms and calls["reuse"] == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
