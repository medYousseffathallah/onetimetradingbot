"""R1: Chronological Portfolio Autopsy, EOD MTM Trajectories & Benchmark Comparisons.

Reads strictly read-only legacy portfolio snapshots/ledger and V2 equity-only canonical
market bars (`data/v2_market/daily_bars.equity_only.csv`). Writes structured empirical
results to `research/experiments-v2/r1_autopsy_results.json`.
"""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from statistics import median
from typing import Any

# Paths
V2_ROOT = Path(r"C:\Users\Thinkcenter\Desktop\BVMT\bvmt-v2")
LEGACY_ROOT = Path(r"C:\Users\Thinkcenter\Desktop\BVMT\bvmt-starter-kit")

# Add legacy src read-only only for challenge_universe registry inspection
sys.path.insert(0, str(LEGACY_ROOT / "src"))
from bvmt.challenge_universe import (  # noqa: E402
    get_challenge_universe,
    resolve_challenge_record,
)

SNAPSHOTS_DIR = LEGACY_ROOT / "data" / "portfolio" / "snapshots"
LEDGER_PATH = LEGACY_ROOT / "data" / "portfolio" / "real_competition_ledger.json"
OPENING_SNAP_PATH = LEGACY_ROOT / "data" / "portfolio" / "real_account_snapshot.json"
EQUITY_BARS_PATH = V2_ROOT / "data" / "v2_market" / "daily_bars.equity_only.csv"
MASTER_PATH = V2_ROOT / "data" / "v2_market" / "instrument_master.csv"
OUTPUT_JSON_PATH = V2_ROOT / "research" / "experiments-v2" / "r1_autopsy_results.json"

D = Decimal
FEE_RATE = D("0.005")  # 0.50% competition fee


def q3(val: Decimal) -> Decimal:
    return val.quantize(D("0.001"), rounding=ROUND_HALF_UP)


def q2(val: Decimal) -> Decimal:
    return val.quantize(D("0.01"), rounding=ROUND_HALF_UP)


def pct_str(val: Decimal, base: Decimal) -> float:
    if base == 0:
        return 0.0
    return round(float((val / base) * D("100")), 4)


def load_market_data() -> tuple[dict[str, dict[str, dict[str, Any]]], list[str], dict[str, str]]:
    """Load equity_only bars mapped by canonical ISIN-joined instrument_id."""
    master_rows = list(csv.DictReader(MASTER_PATH.open(encoding="utf-8")))
    id_to_canonical: dict[str, str] = {}
    id_to_isin: dict[str, str] = {}
    for row in master_rows:
        iid = row["instrument_id"]
        isin = row["isin"]
        id_to_isin[iid] = isin
        rec = resolve_challenge_record(isin) or resolve_challenge_record(iid)
        if rec is not None:
            id_to_canonical[iid] = rec.canonical_instrument_id
        else:
            id_to_canonical[iid] = iid

    bars_by_id: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    all_dates: set[str] = set()
    with EQUITY_BARS_PATH.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cid = id_to_canonical[row["instrument_id"]]
            d = row["session_date"]
            all_dates.add(d)
            bars_by_id[cid][d] = {
                "source_instrument_id": row["instrument_id"],
                "symbol": row["symbol"],
                "session_date": d,
                "open": D(row["open"]),
                "high": D(row["high"]),
                "low": D(row["low"]),
                "close": D(row["close"]),
                "volume_shares": int(row["volume_shares"]),
                "turnover_tnd": D(row["turnover_tnd"]),
                "status": row["status"],
            }
    return dict(bars_by_id), sorted(all_dates), id_to_isin


def map_symbol_to_canonical(symbol: str) -> str:
    rec = resolve_challenge_record(symbol)
    if rec is not None:
        return rec.canonical_instrument_id
    return symbol.strip().upper().replace(" ", "_")


def reconstruct_snapshots() -> dict[str, Any]:
    """Reconstruct all 11 snapshots + opening snapshot + ledger discrepancy."""
    portal_id_map = {
        223375: "BH_BANK",
        223493: "DELICE_HOLDING",
        223529: "UNCONFIRMED_PORTAL_223529",
        223514: "NEW_BODY_LINE",
        223516: "STA",
    }

    opening = json.loads(OPENING_SNAP_PATH.read_text(encoding="utf-8"))
    snap_files = sorted(SNAPSHOTS_DIR.glob("*.json"))
    chronology: list[dict[str, Any]] = []

    for sf in snap_files:
        data = json.loads(sf.read_text(encoding="utf-8"))
        total = D(str(data["portfolio_total_tnd"]))
        cash = D(str(data["available_cash_tnd"]))
        holdings_val = D(str(data["holdings_market_value_tnd"]))
        cash_pct = round(float((cash / total) * D("100")), 2) if total > 0 else 0.0
        invested_pct = round(float((holdings_val / total) * D("100")), 2) if total > 0 else 0.0

        raw_holdings = data.get("holdings", [])
        is_dom_corrupted = any(h.get("symbol") == "VENDRE" for h in raw_holdings)

        parsed_holdings: list[dict[str, Any]] = []
        decoded_corrupted_holdings: list[dict[str, Any]] = []
        open_unrealized_sum = D("0")

        for h in raw_holdings:
            if is_dom_corrupted:
                portal_id = int(h["quantity"])
                actual_qty = int(D(str(h["acquisition_price_tnd"])))
                actual_acq_price = D(str(h["latest_price_tnd"]))
                actual_acq_amt = D(str(h["market_value_tnd"]))
                decoded_corrupted_holdings.append(
                    {
                        "portal_id": portal_id,
                        "mapped_candidate_id": portal_id_map.get(portal_id, f"UNKNOWN_{portal_id}"),
                        "actual_quantity": actual_qty,
                        "actual_acquisition_price_tnd": str(actual_acq_price),
                        "actual_acquisition_amount_tnd": str(actual_acq_amt),
                        "corrupted_dom_qty": h["quantity"],
                        "corrupted_dom_acq_amt": h["acquisition_amount_tnd"],
                        "corrupted_dom_gain": h["gain_tnd"],
                    }
                )
            else:
                gain = D(str(h["gain_tnd"]))
                open_unrealized_sum += gain
                parsed_holdings.append(
                    {
                        "canonical_id": map_symbol_to_canonical(h["symbol"]),
                        "symbol": h["symbol"],
                        "displayed_identifier": h.get("displayed_identifier"),
                        "quantity": int(h["quantity"]),
                        "acquisition_price_tnd": str(h["acquisition_price_tnd"]),
                        "acquisition_amount_tnd": str(h["acquisition_amount_tnd"]),
                        "latest_price_tnd": str(h["latest_price_tnd"]),
                        "market_value_tnd": str(h["market_value_tnd"]),
                        "gain_tnd": str(h["gain_tnd"]),
                        "gain_pct": str(h["gain_pct"]),
                        "weight_pct": round(float((D(str(h["market_value_tnd"])) / total) * D("100")), 3),
                    }
                )

        entry: dict[str, Any] = {
            "filename": sf.name,
            "snapshot_id": data.get("snapshot_id"),
            "retrieved_at": data.get("retrieved_at"),
            "source_url": data.get("source_url"),
            "portfolio_total_tnd": str(total),
            "available_cash_tnd": str(cash),
            "holdings_market_value_tnd": str(holdings_val),
            "cash_drag_pct": cash_pct,
            "invested_pct": invested_pct,
            "holdings_count": len(raw_holdings),
            "competition_rank": data.get("competition_rank"),
            "total_participants": data.get("total_participants"),
            "displayed_overall_performance_pct": data.get("displayed_overall_performance_pct"),
            "movements_page_captured": data.get("movements_page_captured"),
            "is_dom_corrupted": is_dom_corrupted,
            "open_unrealized_sum_tnd": str(q3(open_unrealized_sum)) if not is_dom_corrupted else None,
            "holdings": parsed_holdings,
        }
        if is_dom_corrupted:
            entry["decoded_corrupted_holdings"] = decoded_corrupted_holdings
            entry["corrupted_bogus_pnl_sum_tnd"] = str(
                sum(D(str(h["gain_tnd"])) for h in raw_holdings)
            )
        chronology.append(entry)

    # Ledger discrepancy audit
    ledger = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    ledger_snapshots = [
        {
            "index": idx,
            "snapshot_id": s.get("snapshot_id"),
            "capture_timestamp": s.get("capture_timestamp"),
            "portfolio_total_tnd": s.get("portfolio_total_tnd"),
            "available_cash_tnd": s.get("available_cash_tnd"),
            "holdings_count": len(s.get("holdings", [])),
            "competition_rank": s.get("competition_rank"),
        }
        for idx, s in enumerate(ledger.get("snapshot_history", []))
    ]
    active_holdings = {
        k: {
            "total_shares": v["total_shares"],
            "average_cost_tnd": v["average_cost_tnd"],
            "cost_basis_tnd": v["cost_basis_tnd"],
        }
        for k, v in ledger.get("holdings", {}).items()
    }

    return {
        "opening_snapshot": {
            "snapshot_id": opening["snapshot_id"],
            "provenance": opening["provenance"],
            "portfolio_total_tnd": opening["portfolio_total_tnd"],
            "available_cash_tnd": opening["available_cash_tnd"],
            "cash_drag_pct": round(
                float((D(opening["available_cash_tnd"]) / D(opening["portfolio_total_tnd"])) * 100), 2
            ),
            "competition_rank": opening["competition_rank"],
            "competition_participants": opening["competition_participants"],
            "holdings": opening["holdings"],
        },
        "snapshots_count": len(chronology),
        "chronology": chronology,
        "ledger_discrepancy": {
            "ledger_updated_at": ledger.get("updated_at"),
            "ledger_available_cash_tnd": ledger.get("available_cash_tnd"),
            "ledger_active_holdings_count": len(active_holdings),
            "ledger_active_holdings": active_holdings,
            "account_snapshots_sequence_in_ledger": ledger_snapshots,
            "root_cause": (
                "real_competition_ledger.json ingested Nov 12 ext_1794476128406 (8 holdings, "
                "cash 29,574.190 TND, total 50,093.190 TND, rank 81/14,450) at EVT-00020/21, "
                "then a stale Nov 10 browser_sync_20261110_110702 capture (6 holdings, "
                "cash 38,752.350 TND, total 49,993.430 TND, rank 14,258/14,430) was re-applied "
                "last at EVT-00022/23 without monotonic timestamp guard, reverting the active state "
                "back to Nov 10 and dropping EURO-CYCLES (510 sh) and MPBS (400 sh)."
            ),
        },
    }


def audit_nov9_roundtrip(bars_by_id: dict[str, dict[str, dict[str, Any]]]) -> dict[str, Any]:
    """Audit portal ID 223529 intraday Nov 9 buy+sell and check matching stocks."""
    # Cash flows on Nov 9
    cash_0913 = D("44586.070")
    cash_1204 = D("36939.520")
    cash_1440 = D("41622.790")
    nbl_cost = D("492.450")
    sta_cost = D("2542.650")

    implied_buy_outlay_from_cash = cash_0913 - cash_1204 - nbl_cost - sta_cost  # 4611.450
    dom_shifted_buy_outlay = D("4611.440")
    qty = 35
    dom_avg_cost = D("131.756")
    sale_net_proceeds = cash_1440 - cash_1204  # 4683.270
    realized_gain_from_cash = sale_net_proceeds - implied_buy_outlay_from_cash  # +71.820
    realized_gain_from_dom = sale_net_proceeds - dom_shifted_buy_outlay  # +71.830

    implied_gross_buy_price = q3(implied_buy_outlay_from_cash / (D(qty) * (D("1") + FEE_RATE)))
    implied_gross_sell_price = q3(sale_net_proceeds / (D(qty) * (D("1") - FEE_RATE)))

    # Scan ALL 76 equities on Nov 6 and Nov 9 for price bands matching ~131..135
    candidates: list[dict[str, Any]] = []
    for cid, date_map in sorted(bars_by_id.items()):
        b06 = date_map.get("2026-11-06")
        b09 = date_map.get("2026-11-09")
        prices = []
        for b in (b06, b09):
            if b:
                prices.extend([float(b["low"]), float(b["high"])])
        if prices and min(prices) <= 136.0 and max(prices) >= 130.0:
            candidates.append(
                {
                    "canonical_id": cid,
                    "nov06": {
                        "open": str(b06["open"]),
                        "high": str(b06["high"]),
                        "low": str(b06["low"]),
                        "close": str(b06["close"]),
                        "volume_shares": b06["volume_shares"],
                    }
                    if b06
                    else None,
                    "nov09": {
                        "open": str(b09["open"]),
                        "high": str(b09["high"]),
                        "low": str(b09["low"]),
                        "close": str(b09["close"]),
                        "volume_shares": b09["volume_shares"],
                    }
                    if b09
                    else None,
                }
            )

    icf_traj = {}
    for d in ["2026-11-06", "2026-11-09", "2026-11-10", "2026-11-11", "2026-11-12", "2026-11-18"]:
        b = bars_by_id["ICF"].get(d)
        if b:
            gross_val = D(qty) * b["close"]
            net_liq = q3(gross_val * (D("1") - FEE_RATE))
            icf_traj[d] = {
                "close": str(b["close"]),
                "volume": b["volume_shares"],
                "gross_value_35sh": str(q3(gross_val)),
                "net_liq_value_35sh": str(net_liq),
                "net_pnl_vs_4611_45": str(q3(net_liq - implied_buy_outlay_from_cash)),
            }

    return {
        "portal_id": 223529,
        "quantity": qty,
        "displayed_avg_cost_shifted_tnd": str(dom_avg_cost),
        "dom_shifted_acq_amount_tnd": str(dom_shifted_buy_outlay),
        "cash_reconciled_acq_amount_tnd": str(implied_buy_outlay_from_cash),
        "sale_net_proceeds_tnd": str(sale_net_proceeds),
        "realized_gain_cash_reconciled_tnd": str(realized_gain_from_cash),
        "realized_gain_dom_reconciled_tnd": str(realized_gain_from_dom),
        "implied_gross_buy_price_tnd": str(implied_gross_buy_price),
        "implied_gross_sell_price_tnd": str(implied_gross_sell_price),
        "candidate_equities_in_130_136_band_nov06_nov09": candidates,
        "candidate_label": "UNVERIFIED_CANDIDATE (ICF pending display_histo.aspx sync)",
        "if_icf_held_instead_of_sold_trajectory": icf_traj,
    }


def compute_eod_trajectories(
    bars_by_id: dict[str, dict[str, dict[str, Any]]], dates: list[str]
) -> dict[str, Any]:
    """Track confirmed 8 holdings (ext_1794476128406) & stale 6 holdings through Nov 18."""
    nov_dates = [d for d in dates if d >= "2026-11-06"]

    # Confirmed 8 holdings from sync_20261112_093526.json (ext_1794476128406)
    confirmed_8 = [
        {"id": "BH_BANK", "qty": 30, "acq_amt": D("391.950"), "snap_nov12_price": D("12.910")},
        {"id": "DELICE_HOLDING", "qty": 263, "acq_amt": D("5021.990"), "snap_nov12_price": D("19.000")},
        {"id": "EURO-CYCLES", "qty": 510, "acq_amt": D("4997.360"), "snap_nov12_price": D("9.850")},
        {"id": "MPBS", "qty": 400, "acq_amt": D("4180.800"), "snap_nov12_price": D("10.600")},
        {"id": "NEW_BODY_LINE", "qty": 200, "acq_amt": D("492.450"), "snap_nov12_price": D("2.370")},
        {"id": "SMART_TUNISIE", "qty": 62, "acq_amt": D("1993.920"), "snap_nov12_price": D("32.000")},
        {"id": "STA", "qty": 22, "acq_amt": D("2542.650"), "snap_nov12_price": D("115.000")},
        {"id": "UIB", "qty": 24, "acq_amt": D("876.520"), "snap_nov12_price": D("36.800")},
    ]
    confirmed_cash = D("29574.190")

    # Stale 6 holdings from browser_sync_20261110_110702
    stale_6 = [h for h in confirmed_8 if h["id"] not in {"EURO-CYCLES", "MPBS"}]
    stale_cash = D("38752.350")

    per_holding_eod: dict[str, dict[str, Any]] = {}
    for h in confirmed_8:
        cid = h["id"]
        traj = {}
        for d in nov_dates:
            b = bars_by_id[cid][d]
            mv = q3(D(h["qty"]) * b["close"])
            pnl = q3(mv - h["acq_amt"])
            ret_pct = pct_str(pnl, h["acq_amt"])
            traj[d] = {
                "close": str(b["close"]),
                "volume": b["volume_shares"],
                "market_value_tnd": str(mv),
                "unrealized_pnl_tnd": str(pnl),
                "unrealized_return_pct": ret_pct,
            }
        per_holding_eod[cid] = {
            "qty": h["qty"],
            "acq_amt_tnd": str(h["acq_amt"]),
            "nov12_morning_snap_price": str(h["snap_nov12_price"]),
            "nov12_eod_price": traj["2026-11-12"]["close"],
            "nov18_eod_price": traj["2026-11-18"]["close"],
            "nov12_eod_pnl_tnd": traj["2026-11-12"]["unrealized_pnl_tnd"],
            "nov18_eod_pnl_tnd": traj["2026-11-18"]["unrealized_pnl_tnd"],
            "trajectory": traj,
        }

    confirmed_daily_mtm: list[dict[str, Any]] = []
    stale_daily_mtm: list[dict[str, Any]] = []
    for d in [x for x in nov_dates if x >= "2026-11-12"]:
        c_mv = sum(D(h["qty"]) * bars_by_id[h["id"]][d]["close"] for h in confirmed_8)
        c_total = q3(confirmed_cash + c_mv)
        c_liq = q3(confirmed_cash + c_mv * (D("1") - FEE_RATE))
        c_open_pnl = q3(c_mv - sum(h["acq_amt"] for h in confirmed_8))
        confirmed_daily_mtm.append(
            {
                "session_date": d,
                "holdings_mv_tnd": str(q3(c_mv)),
                "cash_tnd": str(confirmed_cash),
                "total_equity_tnd": str(c_total),
                "return_vs_50k_pct": pct_str(c_total - D("50000"), D("50000")),
                "liquidated_equity_tnd": str(c_liq),
                "liquidated_return_vs_50k_pct": pct_str(c_liq - D("50000"), D("50000")),
                "open_unrealized_pnl_tnd": str(c_open_pnl),
            }
        )

        s_mv = sum(D(h["qty"]) * bars_by_id[h["id"]][d]["close"] for h in stale_6)
        s_total = q3(stale_cash + s_mv)
        stale_daily_mtm.append(
            {
                "session_date": d,
                "holdings_mv_tnd": str(q3(s_mv)),
                "cash_tnd": str(stale_cash),
                "total_equity_tnd": str(s_total),
                "return_vs_50k_pct": pct_str(s_total - D("50000"), D("50000")),
            }
        )

    # Unverified User Screenshot analysis
    amen_traj = {
        d: {
            "close": str(bars_by_id["AMEN_BANK"][d]["close"]),
            "mv_45sh": str(q3(D(45) * bars_by_id["AMEN_BANK"][d]["close"])),
        }
        for d in [x for x in nov_dates if x >= "2026-11-12"]
    }
    unverified_total = D("50647.64")
    unverified_total_gain = unverified_total - D("50000.00")  # +647.64
    unverified_open_gains_sum = D("411.96")
    unverified_gap = unverified_total_gain - unverified_open_gains_sum  # +235.68
    nov9_known_realized = D("71.82")
    residual_after_nov9 = unverified_gap - nov9_known_realized  # +163.86

    return {
        "confirmed_8_holdings_eod": per_holding_eod,
        "confirmed_portfolio_static_from_nov12_mtm": confirmed_daily_mtm,
        "stale_ledger_6_holdings_static_mtm": stale_daily_mtm,
        "unverified_user_screenshot": {
            "provenance_tag": "UNVERIFIED_USER_SCREENSHOT",
            "reported_equity_tnd": "50647.64",
            "reported_return_pct": "+1.30%",
            "computed_return_pct": pct_str(unverified_total_gain, D("50000")),
            "reported_rank": "111 / 14541",
            "reported_holdings_count": 9,
            "reported_new_holding": "AMEN_BANK 45 sh",
            "amen_bank_nov12_nov18_prices": amen_traj,
            "reported_open_gains_sum_tnd": str(unverified_open_gains_sum),
            "reported_total_gain_tnd": str(unverified_total_gain),
            "unexplained_realized_fee_valuation_gap_tnd": str(unverified_gap),
            "known_nov9_realized_gain_tnd": str(nov9_known_realized),
            "residual_unexplained_after_nov9_tnd": str(residual_after_nov9),
        },
    }


def compute_benchmarks(
    bars_by_id: dict[str, dict[str, dict[str, Any]]], dates: list[str]
) -> dict[str, Any]:
    """Compare actual portfolio returns against baselines over identical Nov 7-12 & Nov 7-18 windows."""
    challenge_ids = sorted({r.canonical_instrument_id for r in get_challenge_universe()})
    full_ids = sorted(bars_by_id.keys())

    # Identify index of 2026-11-06, 2026-11-09, 2026-11-12, 2026-11-18
    idx_nov06 = dates.index("2026-11-06")
    idx_nov09 = dates.index("2026-11-09")
    dates_window_20 = dates[idx_nov06 - 20 : idx_nov06 + 1]  # 21 dates -> 20-session momentum

    def ew_return(ids: list[str], start_d: str, end_d: str, entry_mode: str, round_trip_fees: bool) -> dict[str, Any]:
        # Equal weight across all stocks in universe with bars at start_d and end_d
        rets: list[Decimal] = []
        missing = []
        for cid in ids:
            b_start = bars_by_id[cid].get(start_d)
            b_end = bars_by_id[cid].get(end_d)
            if not b_start or not b_end:
                missing.append(cid)
                continue
            p_in = b_start["close"] if entry_mode == "close" else b_start["open"]
            p_out = b_end["close"]
            if round_trip_fees:
                r = (p_out * (D("1") - FEE_RATE)) / (p_in * (D("1") + FEE_RATE)) - D("1")
            else:
                r = (p_out / p_in) - D("1")
            rets.append(r)
        avg_r = sum(rets) / D(len(rets))
        med_r = D(str(median([float(x) for x in rets])))
        return {
            "count_included": len(rets),
            "count_missing": len(missing),
            "gross_or_net": "net_0.5pct_each_way" if round_trip_fees else "gross_no_fees",
            "return_pct": round(float(avg_r * D("100")), 4),
            "median_stock_return_pct": round(float(med_r * D("100")), 4),
        }

    def simple_mom20_portfolio(
        ids: list[str], end_d: str, top_k: int = 5, min_med_turnover: Decimal = D("0")
    ) -> dict[str, Any]:
        """Rank as of 2026-11-06 close using trailing 20s momentum; enter 2026-11-09 open with 0.5% fee + 10% cap."""
        ranked = []
        for cid in ids:
            b_now = bars_by_id[cid].get("2026-11-06")
            b_prev = bars_by_id[cid].get(dates[idx_nov06 - 20])
            if not b_now or not b_prev:
                continue
            # Check trailing 20s median turnover
            turns = [
                bars_by_id[cid][d]["turnover_tnd"]
                for d in dates[idx_nov06 - 19 : idx_nov06 + 1]
                if d in bars_by_id[cid]
            ]
            if len(turns) < 20:
                continue
            med_turn = Decimal(str(median([float(t) for t in turns])))
            if med_turn < min_med_turnover:
                continue
            mom20 = (b_now["close"] / b_prev["close"]) - D("1")
            ranked.append((mom20, cid, med_turn))
        ranked.sort(reverse=True)
        picks = ranked[:top_k]

        # Simulate 50,000 TND capital, 10% max weight (5,000 TND) per stock, 10% volume cap at Nov 9 open
        cash = D("50000.000")
        sleeve_budget = D("5000.000")
        positions = []
        for mom20, cid, med_turn in picks:
            b_entry = bars_by_id[cid]["2026-11-09"]
            if b_entry["status"] != "traded" or b_entry["volume_shares"] <= 0:
                positions.append({"id": cid, "mom20_pct": round(float(mom20 * 100), 2), "shares": 0, "reason": "untraded_nov09"})
                continue
            p_in = b_entry["open"]
            max_by_cash = int(sleeve_budget / (p_in * (D("1") + FEE_RATE)))
            max_by_vol = int(b_entry["volume_shares"] * 0.10)
            shares = min(max_by_cash, max_by_vol)
            if shares <= 0:
                positions.append({"id": cid, "mom20_pct": round(float(mom20 * 100), 2), "shares": 0, "reason": "vol_cap_zero"})
                continue
            gross = D(shares) * p_in
            fee = q3(gross * FEE_RATE)
            cash -= gross + fee
            p_out = bars_by_id[cid][end_d]["close"]
            mv_end = D(shares) * p_out
            liq_end = q3(mv_end * (D("1") - FEE_RATE))
            positions.append(
                {
                    "id": cid,
                    "mom20_pct": round(float(mom20 * 100), 2),
                    "shares": shares,
                    "entry_open": str(p_in),
                    "end_close": str(p_out),
                    "mv_end_tnd": str(q3(mv_end)),
                    "liq_end_tnd": str(liq_end),
                }
            )
        total_mv = sum(D(p["mv_end_tnd"]) for p in positions if "mv_end_tnd" in p)
        total_liq = sum(D(p["liq_end_tnd"]) for p in positions if "liq_end_tnd" in p)
        eq_mtm = cash + total_mv
        eq_liq = cash + total_liq
        return {
            "picks": positions,
            "cash_remaining_tnd": str(q3(cash)),
            "equity_mtm_tnd": str(q3(eq_mtm)),
            "return_mtm_pct": pct_str(eq_mtm - D("50000"), D("50000")),
            "equity_liq_tnd": str(q3(eq_liq)),
            "return_liq_pct": pct_str(eq_liq - D("50000"), D("50000")),
        }

    # Buy & Hold Nov 7 Initial (BH_BANK 30 sh + 49,608.050 cash)
    def bh_portfolio(holdings: list[tuple[str, int]], cash: Decimal, end_d: str) -> dict[str, Any]:
        mv = sum(D(qty) * bars_by_id[cid][end_d]["close"] for cid, qty in holdings)
        eq = q3(cash + mv)
        return {
            "equity_tnd": str(eq),
            "return_vs_50k_pct": pct_str(eq - D("50000"), D("50000")),
        }

    nov7_holdings = [("BH_BANK", 30)]
    nov7_cash = D("49608.050")

    nov9_morning_holdings = [("BH_BANK", 30), ("DELICE_HOLDING", 263)]
    nov9_morning_cash = D("44586.070")

    nov9_eod_holdings = [("BH_BANK", 30), ("DELICE_HOLDING", 263), ("NEW_BODY_LINE", 200), ("STA", 22)]
    nov9_eod_cash = D("41622.790")

    # Confirmed account trajectories
    mtm_res = compute_eod_trajectories(bars_by_id, dates)["confirmed_portfolio_static_from_nov12_mtm"]
    nov12_eod_confirmed = next(x for x in mtm_res if x["session_date"] == "2026-11-12")
    nov18_eod_confirmed = next(x for x in mtm_res if x["session_date"] == "2026-11-18")

    windows = {}
    for label, end_d in [("Nov7_to_Nov12", "2026-11-12"), ("Nov7_to_Nov18", "2026-11-18")]:
        windows[label] = {
            "cash_baseline_pct": 0.0,
            "tunindex": "UNAVAILABLE (no point-in-time TUNINDEX CSV exists in local archive)",
            "ew_challenge_42_eod_nov06_gross": ew_return(challenge_ids, "2026-11-06", end_d, "close", False),
            "ew_challenge_42_open_nov09_net": ew_return(challenge_ids, "2026-11-09", end_d, "open", True),
            "ew_full_bvmt_75_isin_eod_nov06_gross": ew_return(full_ids, "2026-11-06", end_d, "close", False),
            "ew_full_bvmt_75_isin_open_nov09_net": ew_return(full_ids, "2026-11-09", end_d, "open", True),
            "simple_mom20_challenge_top5_unfiltered": simple_mom20_portfolio(challenge_ids, end_d, 5, D("0")),
            "simple_mom20_challenge_top5_liq5k": simple_mom20_portfolio(challenge_ids, end_d, 5, D("5000")),
            "simple_mom20_full_top5_liq5k": simple_mom20_portfolio(full_ids, end_d, 5, D("5000")),
            "buy_and_hold_nov7_initial": bh_portfolio(nov7_holdings, nov7_cash, end_d),
            "buy_and_hold_nov9_0913_holdings": bh_portfolio(nov9_morning_holdings, nov9_morning_cash, end_d),
            "buy_and_hold_nov9_1440_holdings": bh_portfolio(nov9_eod_holdings, nov9_eod_cash, end_d),
        }

    # Add actual account numbers into windows
    windows["Nov7_to_Nov12"]["actual_confirmed_nov12_morning_snap"] = {
        "equity_tnd": "50093.190",
        "return_vs_50k_pct": pct_str(D("50093.190") - D("50000"), D("50000")),
        "return_vs_nov7_snap_pct": pct_str(D("50093.190") - D("50000.750"), D("50000.750")),
    }
    windows["Nov7_to_Nov12"]["actual_confirmed_nov12_eod_mtm"] = nov12_eod_confirmed
    windows["Nov7_to_Nov18"]["actual_confirmed_nov12_static_through_nov18_eod"] = nov18_eod_confirmed
    windows["Nov7_to_Nov18"]["unverified_user_screenshot"] = {
        "status": "UNVERIFIED_USER_SCREENSHOT",
        "equity_tnd": "50647.64",
        "return_vs_50k_pct": 1.2953,
        "displayed_return_pct": "+1.30%",
        "rank": "111 / 14541",
    }

    return windows


def main() -> None:
    bars_by_id, dates, id_to_isin = load_market_data()
    results = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "data_sources": {
            "equity_bars": str(EQUITY_BARS_PATH),
            "equity_rows": 15080,
            "unique_token_ids": 76,
            "unique_isins": len(set(id_to_isin.values())),
            "sessions_count": len(dates),
            "first_session": dates[0],
            "last_session": dates[-1],
            "snapshots_dir": str(SNAPSHOTS_DIR),
            "ledger_path": str(LEDGER_PATH),
        },
        "snapshot_reconstruction": reconstruct_snapshots(),
        "nov9_roundtrip_223529": audit_nov9_roundtrip(bars_by_id),
        "eod_trajectories": compute_eod_trajectories(bars_by_id, dates),
        "benchmark_comparisons": compute_benchmarks(bars_by_id, dates),
    }

    OUTPUT_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Wrote {OUTPUT_JSON_PATH}")

    # Print concise executive verification summary
    sr = results["snapshot_reconstruction"]
    print("\n--- SNAPSHOT CHRONOLOGY ---")
    for s in sr["chronology"]:
        print(
            f"{s['filename']} | {s['retrieved_at']} | eq={s['portfolio_total_tnd']} | "
            f"cash={s['available_cash_tnd']} ({s['cash_drag_pct']}%) | n={s['holdings_count']} | "
            f"rank={s['competition_rank']} | dom_corrupt={s['is_dom_corrupted']}"
        )

    print("\n--- NOV 9 ROUNDTRIP ---")
    rt = results["nov9_roundtrip_223529"]
    print("Buy:", rt["cash_reconciled_acq_amount_tnd"], "Sell:", rt["sale_net_proceeds_tnd"], "Gain:", rt["realized_gain_cash_reconciled_tnd"])
    print("Candidates in 130-136 band:", [c["canonical_id"] for c in rt["candidate_equities_in_130_136_band_nov06_nov09"]])

    print("\n--- CONFIRMED STATIC NOV 12 -> NOV 18 MTM ---")
    for row in results["eod_trajectories"]["confirmed_portfolio_static_from_nov12_mtm"]:
        print(row["session_date"], "eq=", row["total_equity_tnd"], "ret%=", row["return_vs_50k_pct"], "liq_ret%=", row["liquidated_return_vs_50k_pct"])

    print("\n--- BENCHMARK SUMMARY ---")
    for wname, wdata in results["benchmark_comparisons"].items():
        print(f"[{wname}]")
        print("  EW Challenge 42 (Nov6 EOD gross):", wdata["ew_challenge_42_eod_nov06_gross"]["return_pct"])
        print("  EW Challenge 42 (Nov9 Open net):", wdata["ew_challenge_42_open_nov09_net"]["return_pct"])
        print("  EW Full BVMT 75 (Nov6 EOD gross):", wdata["ew_full_bvmt_75_isin_eod_nov06_gross"]["return_pct"])
        print("  EW Full BVMT 75 (Nov9 Open net):", wdata["ew_full_bvmt_75_isin_open_nov09_net"]["return_pct"])
        print("  Simple Mom20 Chal Top5 liq5k MTM:", wdata["simple_mom20_challenge_top5_liq5k"]["return_mtm_pct"], "picks:", [p["id"] for p in wdata["simple_mom20_challenge_top5_liq5k"]["picks"]])
        print("  B&H Nov7 initial:", wdata["buy_and_hold_nov7_initial"]["return_vs_50k_pct"])
        print("  B&H Nov9 14:40:", wdata["buy_and_hold_nov9_1440_holdings"]["return_vs_50k_pct"])


if __name__ == "__main__":
    main()
