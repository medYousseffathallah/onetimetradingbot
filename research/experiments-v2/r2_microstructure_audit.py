"""R2: Empirical BVMT Microstructure, Capacity, Contamination & Provenance Audit.

Reads strictly read-only legacy artifacts and V2 equity-only canonical market bars.
Writes structured empirical metrics to `research/experiments-v2/r2_microstructure_results.json`.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from statistics import mean, median
from typing import Any

V2_ROOT = Path(r"C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2")
LEGACY_ROOT = Path(r"C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit")

sys.path.insert(0, str(LEGACY_ROOT / "src"))
from bvmt.challenge_universe import get_challenge_universe, resolve_challenge_record  # noqa: E402
from bvmt.rules import competition_blockers  # noqa: E402

EQUITY_BARS_PATH = V2_ROOT / "data" / "v2_market" / "daily_bars.equity_only.csv"
MASTER_PATH = V2_ROOT / "data" / "v2_market" / "instrument_master.csv"
V2_MANIFEST_PATH = V2_ROOT / "data" / "v2_market" / "v2_market_manifest.json"
LEGACY_CANONICAL_PATH = LEGACY_ROOT / "data" / "processed" / "bvmt_official_2026" / "daily_bars.canonical.csv"
LEGACY_REJECTED_PATH = LEGACY_ROOT / "data" / "processed" / "bvmt_official_2026" / "rejected_rows.csv"
COMPETITION_CFG_PATH = LEGACY_ROOT / "configs" / "competition.json"
OUTPUT_JSON_PATH = V2_ROOT / "research" / "experiments-v2" / "r2_microstructure_results.json"


def quantiles(vals: list[float]) -> dict[str, float]:
    if not vals:
        return {}
    s = sorted(vals)
    n = len(s)

    def q(p: float) -> float:
        idx = p * (n - 1)
        lo = int(idx)
        hi = min(lo + 1, n - 1)
        frac = idx - lo
        return round(s[lo] * (1 - frac) + s[hi] * frac, 4)

    return {
        "count": n,
        "min": round(s[0], 4),
        "p10": q(0.10),
        "p25": q(0.25),
        "median": round(median(s), 4),
        "mean": round(mean(s), 4),
        "p75": q(0.75),
        "p90": q(0.90),
        "max": round(s[-1], 4),
    }


def window_stats(rows: list[dict[str, Any]], total_sessions_in_window: int) -> dict[str, Any]:
    obs_count = len(rows)
    traded_rows = [r for r in rows if r["volume_shares"] > 0]
    zero_vol_rows = [r for r in rows if r["volume_shares"] == 0]
    vols = [float(r["volume_shares"]) for r in rows]
    turns = [float(r["turnover_tnd"]) for r in rows]
    traded_turns = [float(r["turnover_tnd"]) for r in traded_rows]

    med_turn = median(turns) if turns else 0.0
    mean_turn = mean(turns) if turns else 0.0
    med_vol = median(vols) if vols else 0.0
    mean_vol = mean(vols) if vols else 0.0

    return {
        "observed_rows": obs_count,
        "traded_days": len(traded_rows),
        "zero_vol_days": len(zero_vol_rows),
        "traded_ratio_vs_window": round(len(traded_rows) / total_sessions_in_window, 4)
        if total_sessions_in_window
        else 0.0,
        "zero_vol_pct_of_observed": round((len(zero_vol_rows) / obs_count) * 100, 2) if obs_count else 100.0,
        "median_daily_volume_shares": round(med_vol, 2),
        "mean_daily_volume_shares": round(mean_vol, 2),
        "median_daily_turnover_tnd": round(med_turn, 2),
        "mean_daily_turnover_tnd": round(mean_turn, 2),
        "median_traded_day_turnover_tnd": round(median(traded_turns), 2) if traded_turns else 0.0,
        "can_absorb_5000_1s_median": (0.10 * med_turn) >= 5000.0,
        "can_absorb_5000_3s_median": (3.0 * 0.10 * med_turn) >= 5000.0,
        "can_absorb_5000_1s_mean": (0.10 * mean_turn) >= 5000.0,
        "can_absorb_5000_3s_mean": (3.0 * 0.10 * mean_turn) >= 5000.0,
        "max_1s_position_10pct_adv_median_tnd": round(0.10 * med_turn, 2),
        "max_3s_position_10pct_adv_median_tnd": round(0.30 * med_turn, 2),
    }


def audit_equities() -> dict[str, Any]:
    master_rows = list(csv.DictReader(MASTER_PATH.open(encoding="utf-8")))
    challenge_by_isin = {r.verified_isin: r for r in get_challenge_universe()}

    token_meta: dict[str, dict[str, Any]] = {}
    isin_to_tokens: dict[str, list[str]] = defaultdict(list)
    for row in master_rows:
        iid = row["instrument_id"]
        isin = row["isin"]
        isin_to_tokens[isin].append(iid)
        chal_rec = challenge_by_isin.get(isin)
        token_meta[iid] = {
            "instrument_id": iid,
            "isin": isin,
            "symbol": row["symbol"],
            "market_segment": row["market_segment"],
            "is_competition_eligible_master": row["is_competition_eligible"] == "True",
            "in_challenge_42": chal_rec is not None,
            "challenge_mode": chal_rec.market_mode if chal_rec else None,
            "challenge_canonical_id": chal_rec.canonical_instrument_id if chal_rec else iid,
        }

    # Load all 15,080 rows
    raw_rows_by_token: dict[str, list[dict[str, Any]]] = defaultdict(list)
    rows_by_isin: dict[str, list[dict[str, Any]]] = defaultdict(list)
    all_dates_set: set[str] = set()
    pub_at_present = 0
    with EQUITY_BARS_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            d = row["session_date"]
            all_dates_set.add(d)
            if row["published_at"].strip():
                pub_at_present += 1
            parsed = {
                "instrument_id": row["instrument_id"],
                "session_date": d,
                "close": float(row["close"]),
                "volume_shares": int(row["volume_shares"]),
                "turnover_tnd": float(row["turnover_tnd"]),
                "status": row["status"],
            }
            iid = row["instrument_id"]
            raw_rows_by_token[iid].append(parsed)
            isin = token_meta[iid]["isin"]
            rows_by_isin[isin].append(parsed)

    all_dates = sorted(all_dates_set)
    last_20_dates = set(all_dates[-20:])
    last_60_dates = set(all_dates[-60:])

    # Per-token (76) and per-ISIN (75) metrics
    token_records: list[dict[str, Any]] = []
    for iid, meta in sorted(token_meta.items()):
        rows_all = raw_rows_by_token[iid]
        rows_60 = [r for r in rows_all if r["session_date"] in last_60_dates]
        rows_20 = [r for r in rows_all if r["session_date"] in last_20_dates]
        token_records.append(
            {
                **meta,
                "full_2026": window_stats(rows_all, len(all_dates)),
                "trailing_60s": window_stats(rows_60, 60),
                "trailing_20s": window_stats(rows_20, 20),
            }
        )

    isin_records: list[dict[str, Any]] = []
    for isin, rows_all in sorted(rows_by_isin.items()):
        tokens = sorted(set(isin_to_tokens[isin]))
        rep_meta = token_meta[tokens[0]]
        chal_rec = challenge_by_isin.get(isin)
        rows_60 = [r for r in rows_all if r["session_date"] in last_60_dates]
        rows_20 = [r for r in rows_all if r["session_date"] in last_20_dates]
        isin_records.append(
            {
                "canonical_id": chal_rec.canonical_instrument_id if chal_rec else rep_meta["instrument_id"],
                "isin": isin,
                "source_tokens": tokens,
                "in_challenge_42": chal_rec is not None,
                "market_segment": rep_meta["market_segment"],
                "challenge_mode": chal_rec.market_mode if chal_rec else None,
                "full_2026": window_stats(rows_all, len(all_dates)),
                "trailing_60s": window_stats(rows_60, 60),
                "trailing_20s": window_stats(rows_20, 20),
            }
        )

    def summarize_group(recs: list[dict[str, Any]], window_key: str) -> dict[str, Any]:
        return {
            "count": len(recs),
            "traded_ratio": quantiles([r[window_key]["traded_ratio_vs_window"] for r in recs]),
            "zero_vol_pct": quantiles([r[window_key]["zero_vol_pct_of_observed"] for r in recs]),
            "median_daily_volume_shares": quantiles([r[window_key]["median_daily_volume_shares"] for r in recs]),
            "median_daily_turnover_tnd": quantiles([r[window_key]["median_daily_turnover_tnd"] for r in recs]),
            "mean_daily_turnover_tnd": quantiles([r[window_key]["mean_daily_turnover_tnd"] for r in recs]),
            "absorb_5000_1s_median_count": sum(1 for r in recs if r[window_key]["can_absorb_5000_1s_median"]),
            "absorb_5000_3s_median_count": sum(1 for r in recs if r[window_key]["can_absorb_5000_3s_median"]),
            "absorb_5000_1s_mean_count": sum(1 for r in recs if r[window_key]["can_absorb_5000_1s_mean"]),
            "absorb_5000_3s_mean_count": sum(1 for r in recs if r[window_key]["can_absorb_5000_3s_mean"]),
        }

    chal_isin = [r for r in isin_records if r["in_challenge_42"]]
    non_chal_isin = [r for r in isin_records if not r["in_challenge_42"]]
    chal_tok = [r for r in token_records if r["in_challenge_42"]]
    non_chal_tok = [r for r in token_records if not r["in_challenge_42"]]

    summary_by_cohort = {}
    for w in ("full_2026", "trailing_60s", "trailing_20s"):
        summary_by_cohort[w] = {
            "isin_all_75": summarize_group(isin_records, w),
            "isin_challenge_42": summarize_group(chal_isin, w),
            "isin_non_challenge_33": summarize_group(non_chal_isin, w),
            "token_all_76": summarize_group(token_records, w),
            "token_challenge_43": summarize_group(chal_tok, w),
            "token_non_challenge_33": summarize_group(non_chal_tok, w),
        }

    # Detailed list of Challenge 42 capacity (20s & full 2026)
    challenge_table = sorted(
        [
            {
                "canonical_id": r["canonical_id"],
                "isin": r["isin"],
                "mode": r["challenge_mode"],
                "full_traded_ratio": r["full_2026"]["traded_ratio_vs_window"],
                "full_zero_vol_pct": r["full_2026"]["zero_vol_pct_of_observed"],
                "full_med_vol": r["full_2026"]["median_daily_volume_shares"],
                "full_med_turn_tnd": r["full_2026"]["median_daily_turnover_tnd"],
                "full_mean_turn_tnd": r["full_2026"]["mean_daily_turnover_tnd"],
                "t20_traded_ratio": r["trailing_20s"]["traded_ratio_vs_window"],
                "t20_zero_vol_pct": r["trailing_20s"]["zero_vol_pct_of_observed"],
                "t20_med_turn_tnd": r["trailing_20s"]["median_daily_turnover_tnd"],
                "t20_mean_turn_tnd": r["trailing_20s"]["mean_daily_turnover_tnd"],
                "t20_1s_med_ok": r["trailing_20s"]["can_absorb_5000_1s_median"],
                "t20_3s_med_ok": r["trailing_20s"]["can_absorb_5000_3s_median"],
                "t20_1s_mean_ok": r["trailing_20s"]["can_absorb_5000_1s_mean"],
                "t20_3s_mean_ok": r["trailing_20s"]["can_absorb_5000_3s_mean"],
            }
            for r in chal_isin
        ],
        key=lambda x: x["t20_med_turn_tnd"],
        reverse=True,
    )

    return {
        "dataset_dimensions": {
            "total_rows": sum(len(v) for v in raw_rows_by_token.values()),
            "unique_tokens": len(token_records),
            "unique_isins": len(isin_records),
            "duplicate_isin_split": {k: v for k, v in isin_to_tokens.items() if len(v) > 1},
            "sessions_count": len(all_dates),
            "first_session": all_dates[0],
            "last_session": all_dates[-1],
            "trailing_60s_start": all_dates[-60],
            "trailing_20s_start": all_dates[-20],
            "published_at_present_count": pub_at_present,
        },
        "summary_by_cohort": summary_by_cohort,
        "challenge_42_capacity_table": challenge_table,
    }


def audit_contamination_and_rejections() -> dict[str, Any]:
    v2_manifest = json.loads(V2_MANIFEST_PATH.read_text(encoding="utf-8"))
    equity_ids = {r["instrument_id"] for r in csv.DictReader(MASTER_PATH.open(encoding="utf-8"))}

    legacy_rows_count = 0
    non_equity_ids: Counter[str] = Counter()
    non_equity_dates: Counter[str] = Counter()
    non_equity_statuses: Counter[str] = Counter()
    with LEGACY_CANONICAL_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            legacy_rows_count += 1
            iid = row["instrument_id"]
            if iid not in equity_ids:
                non_equity_ids[iid] += 1
                non_equity_dates[row["session_date"]] += 1
                non_equity_statuses[row["status"]] += 1

    # Classify excluded IDs heuristically by pattern
    rights_like = [k for k in non_equity_ids if "_DA" in k or "_DS" in k or "DA1" in k or "DS1" in k]
    bond_like = [k for k in non_equity_ids if k not in rights_like]

    rejected_reasons: Counter[str] = Counter()
    rejected_total = 0
    if LEGACY_REJECTED_PATH.exists():
        with LEGACY_REJECTED_PATH.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rejected_total += 1
                rejected_reasons[row.get("reason", "unknown")] += 1

    return {
        "legacy_canonical_total_rows": legacy_rows_count,
        "equity_only_rows": v2_manifest["equity_rows_kept"],
        "excluded_non_equity_rows": sum(non_equity_ids.values()),
        "excluded_non_equity_ids_count": len(non_equity_ids),
        "excluded_pattern_breakdown": {
            "rights_da_ds_ids": len(rights_like),
            "bond_debt_other_ids": len(bond_like),
        },
        "excluded_by_session_date": dict(sorted(non_equity_dates.items())),
        "excluded_by_status": dict(non_equity_statuses),
        "sample_excluded_ids": sorted(non_equity_ids)[:15],
        "rejected_rows_csv_count": rejected_total,
        "rejected_reasons_breakdown": dict(rejected_reasons),
    }


def audit_competition_rules_and_provenance() -> dict[str, Any]:
    cfg = json.loads(COMPETITION_CFG_PATH.read_text(encoding="utf-8"))
    blockers = competition_blockers(cfg)
    fields = cfg.get("fields", {})
    null_value_fields = [k for k, v in fields.items() if v.get("value") is None]
    partial_faq_fields = [k for k, v in fields.items() if v.get("value") is not None]
    return {
        "total_required_fields": len(fields),
        "unverified_fields_count": sum(1 for v in fields.values() if v.get("status") != "verified"),
        "null_value_fields": null_value_fields,
        "partially_populated_unverified_fields": partial_faq_fields,
        "total_attribute_blockers": len(blockers),
        "blockers_list": blockers,
    }


def main() -> None:
    results = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "equity_microstructure": audit_equities(),
        "contamination_and_rejections": audit_contamination_and_rejections(),
        "competition_rules_audit": audit_competition_rules_and_provenance(),
    }
    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON_PATH}")

    em = results["equity_microstructure"]
    print("\n--- DATASET DIMENSIONS ---")
    print(em["dataset_dimensions"])

    for w in ("full_2026", "trailing_60s", "trailing_20s"):
        c = em["summary_by_cohort"][w]
        print(f"\n--- {w} ---")
        for grp in ("isin_all_75", "isin_challenge_42", "isin_non_challenge_33"):
            g = c[grp]
            print(
                f"  {grp}: n={g['count']} | med_traded_ratio={g['traded_ratio']['median']} | "
                f"med_zero_vol%={g['zero_vol_pct']['median']} | med_vol={g['median_daily_volume_shares']['median']} | "
                f"med_turn={g['median_daily_turnover_tnd']['median']} | "
                f"5k_1s(med/mean)={g['absorb_5000_1s_median_count']}/{g['absorb_5000_1s_mean_count']} | "
                f"5k_3s(med/mean)={g['absorb_5000_3s_median_count']}/{g['absorb_5000_3s_mean_count']}"
            )

    cr = results["contamination_and_rejections"]
    print("\n--- CONTAMINATION ---")
    print(
        f"Legacy={cr['legacy_canonical_total_rows']}, Equity={cr['equity_only_rows']}, "
        f"Excluded={cr['excluded_non_equity_rows']} ({cr['excluded_non_equity_ids_count']} IDs), "
        f"Dates={cr['excluded_by_session_date']}, RejectedCSV={cr['rejected_rows_csv_count']} ({cr['rejected_reasons_breakdown']})"
    )

    ra = results["competition_rules_audit"]
    print("\n--- COMPETITION RULES ---")
    print(f"Fields={ra['total_required_fields']}, Unverified={ra['unverified_fields_count']}, Blockers={ra['total_attribute_blockers']}")


if __name__ == "__main__":
    main()
