"""Canonical backend portfolio-state and market-dataset resolution service (Phase 0).

Provides a single deterministic authority (`PortfolioStateService` and
`resolve_canonical_portfolio_context`) used by both the FastAPI layer (`bvmt.api`)
and the Streamlit fallback interface (`bvmt.dashboard`).

Canonical Data-Source Selection Rules:
1. When `portfolio_mode == "REAL_COMPETITION"`:
   - Active ledger path defaults to `data/portfolio/real_competition_ledger.json`.
   - Active market dataset defaults to the latest `VERIFIED IMPORT` canonical bars
     under `data/processed/*/daily_bars.canonical.csv` (e.g. `bvmt_official_2026`
     through `2026-11-06`).
   - Synthetic fixture bars (`tests/fixtures/daily_bars.csv`) are NEVER selected by
     default in `REAL_COMPETITION` mode when a verified dataset exists, and are
     strictly blocked from generating actionable recommendations on a real account.
   - Any browser snapshot in `data/portfolio/snapshots/` whose `retrieved_at`
     timestamp is not yet recorded in `ledger.snapshot_history` is surfaced as
     `pending_browser_snapshot` ("awaiting confirmation") and is never silently
     applied without `confirmed_by_user=True`.
2. When `portfolio_mode == "SYNTHETIC_DEMO"`:
   - Active ledger path defaults to `data/portfolio/ledger.json`.
   - Active market dataset defaults to `tests/fixtures/daily_bars.csv`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from bvmt.browser import (
    CompetitionPortfolioDOMSnapshot,
    load_latest_browser_snapshot,
)
from bvmt.dashboard import (
    DEFAULT_ALERTS_PATH,
    DEFAULT_BARS_PATH,
    DEFAULT_CALENDAR_PATH,
    DEFAULT_COMPETITION_CONFIG,
    DEFAULT_DOC_INDEX_PATH,
    DEFAULT_INSTRUMENTS_PATH,
    DEFAULT_LEDGER_PATH,
    DEFAULT_LLM_CONFIG,
    DEFAULT_REAL_LEDGER_PATH,
    DEFAULT_REAL_SNAPSHOT_PATH,
    DEFAULT_SNAPSHOTS_DIR,
    DashboardAppState,
    apply_confirmed_browser_sync_to_state,
    build_dashboard_state,
    discover_available_bar_datasets,
    evaluate_account_sync_freshness,
    select_default_dataset_index,
)
from bvmt.ledger import (
    CompetitionScreenshotSnapshot,
    ReconciliationReport,
    build_snapshot_from_dom,
)


@dataclass(frozen=True)
class CanonicalDataResolution:
    """Resolved ledger and market dataset paths for a requested portfolio mode."""

    portfolio_mode: str
    ledger_path: Path
    bars_path: Path
    dataset_label: str
    available_datasets: dict[str, Path]


def resolve_canonical_portfolio_context(
    *,
    portfolio_mode: str = "REAL_COMPETITION",
    requested_bars_path: Path | None = None,
    requested_ledger_path: Path | None = None,
    processed_root: Path = Path("data/processed"),
    default_bars_path: Path = DEFAULT_BARS_PATH,
) -> CanonicalDataResolution:
    """Resolve the canonical ledger path and market dataset path according to Phase 0 rules."""
    normalized_mode = "SYNTHETIC_DEMO" if portfolio_mode == "SYNTHETIC_DEMO" else "REAL_COMPETITION"
    datasets = discover_available_bar_datasets(
        processed_root=processed_root,
        default_bars_path=default_bars_path,
    )
    labels = list(datasets.keys())
    default_idx = select_default_dataset_index(labels, portfolio_mode=normalized_mode)
    default_label = (
        labels[default_idx] if labels else f"SYNTHETIC DEMO: {default_bars_path.as_posix()}"
    )

    if requested_bars_path is not None:
        bars_path = requested_bars_path
        matching_label = next(
            (lbl for lbl, p in datasets.items() if p.resolve() == requested_bars_path.resolve()),
            f"CUSTOM: {requested_bars_path.as_posix()}",
        )
    else:
        bars_path = datasets.get(default_label, default_bars_path)
        matching_label = default_label

    if requested_ledger_path is not None:
        ledger_path = requested_ledger_path
    else:
        ledger_path = (
            DEFAULT_REAL_LEDGER_PATH
            if normalized_mode == "REAL_COMPETITION"
            else DEFAULT_LEDGER_PATH
        )

    return CanonicalDataResolution(
        portfolio_mode=normalized_mode,
        ledger_path=ledger_path,
        bars_path=bars_path,
        dataset_label=matching_label,
        available_datasets=datasets,
    )


class PortfolioStateService:
    """Single backend portfolio-state service coordinating ledger, snapshots, and market data."""

    def __init__(
        self,
        *,
        portfolio_mode: str = "REAL_COMPETITION",
        bars_path: Path | None = None,
        ledger_path: Path | None = None,
        alerts_path: Path = DEFAULT_ALERTS_PATH,
        calendar_path: Path = DEFAULT_CALENDAR_PATH,
        instruments_path: Path = DEFAULT_INSTRUMENTS_PATH,
        competition_config_path: Path = DEFAULT_COMPETITION_CONFIG,
        llm_config_path: Path = DEFAULT_LLM_CONFIG,
        doc_index_path: Path = DEFAULT_DOC_INDEX_PATH,
        real_snapshot_path: Path = DEFAULT_REAL_SNAPSHOT_PATH,
        snapshots_dir: Path = DEFAULT_SNAPSHOTS_DIR,
        processed_root: Path = Path("data/processed"),
    ) -> None:
        self.portfolio_mode = portfolio_mode
        self.requested_bars_path = bars_path
        self.requested_ledger_path = ledger_path
        self.alerts_path = alerts_path
        self.calendar_path = calendar_path
        self.instruments_path = instruments_path
        self.competition_config_path = competition_config_path
        self.llm_config_path = llm_config_path
        self.doc_index_path = doc_index_path
        self.real_snapshot_path = real_snapshot_path
        self.snapshots_dir = snapshots_dir
        self.processed_root = processed_root

    def resolve_context(self) -> CanonicalDataResolution:
        return resolve_canonical_portfolio_context(
            portfolio_mode=self.portfolio_mode,
            requested_bars_path=self.requested_bars_path,
            requested_ledger_path=self.requested_ledger_path,
            processed_root=self.processed_root,
        )

    def load_state(
        self,
        *,
        short_lookback: int = 2,
        long_lookback: int = 3,
        min_turnover_tnd: Decimal = Decimal("5000"),
    ) -> DashboardAppState:
        ctx = self.resolve_context()
        return build_dashboard_state(
            ledger_path=ctx.ledger_path,
            alerts_path=self.alerts_path,
            bars_path=ctx.bars_path,
            calendar_path=self.calendar_path,
            instruments_path=self.instruments_path,
            competition_config_path=self.competition_config_path,
            llm_config_path=self.llm_config_path,
            doc_index_path=self.doc_index_path,
            short_lookback=short_lookback,
            long_lookback=long_lookback,
            min_turnover_tnd=min_turnover_tnd,
            portfolio_mode=ctx.portfolio_mode,
            real_snapshot_path=self.real_snapshot_path,
            snapshots_dir=self.snapshots_dir,
        )

    def list_browser_snapshots(self) -> list[tuple[Path, CompetitionPortfolioDOMSnapshot]]:
        """Return all saved browser DOM snapshots sorted newest-first."""
        if not self.snapshots_dir.is_dir():
            return []
        files = sorted(self.snapshots_dir.glob("sync_*.json"), reverse=True)
        out: list[tuple[Path, CompetitionPortfolioDOMSnapshot]] = []
        for path in files:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
                out.append((path, CompetitionPortfolioDOMSnapshot.from_dict(raw)))
            except Exception:
                continue
        return out

    def preview_reconciliation(
        self,
        dom_snap: CompetitionPortfolioDOMSnapshot | None = None,
    ) -> tuple[CompetitionScreenshotSnapshot, ReconciliationReport] | None:
        """Preview reconciliation of a browser DOM snapshot against the current ledger without mutating disk."""
        state = self.load_state()
        target_dom = (
            dom_snap
            or state.pending_browser_snapshot
            or load_latest_browser_snapshot(self.snapshots_dir)
        )
        if target_dom is None:
            return None
        candidate_acct = build_snapshot_from_dom(target_dom)
        comp_acct = candidate_acct.to_competition_account_snapshot(
            as_of=target_dom.retrieved_at.isoformat()
        )
        recon = state.ledger.reconcile_with_snapshot(
            comp_acct,
            evaluated_at=target_dom.retrieved_at,
        )
        return candidate_acct, recon

    def confirm_snapshot(
        self,
        *,
        confirmed_by_user: bool,
        dom_snap: CompetitionPortfolioDOMSnapshot | None = None,
    ) -> tuple[DashboardAppState, ReconciliationReport]:
        """Confirm and persist a browser DOM snapshot to the active real competition ledger."""
        if confirmed_by_user is not True:
            raise ValueError(
                "Explicit user confirmation (confirmed_by_user=True) is required before applying browser sync"
            )
        state = self.load_state()
        target_dom = (
            dom_snap
            or state.pending_browser_snapshot
            or load_latest_browser_snapshot(self.snapshots_dir)
        )
        if target_dom is None:
            raise FileNotFoundError("No browser snapshot available to confirm.")
        recon = apply_confirmed_browser_sync_to_state(
            state,
            target_dom,
            confirmed_by_user=True,
        )
        return state, recon

    def get_freshness_status(self, state: DashboardAppState | None = None) -> dict[str, object]:
        active_state = state or self.load_state()
        return evaluate_account_sync_freshness(
            active_state.account_snapshot,
            active_state.latest_bar_session_str,
        )
