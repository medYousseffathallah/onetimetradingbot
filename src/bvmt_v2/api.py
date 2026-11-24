"""Start locally with uvicorn bvmt_v2.api:create_v2_app --factory --host 127.0.0.1."""

from __future__ import annotations

import json
import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .backtester import EXIT_POLICIES, FAMILIES, Backtester, PhaseSensitivity
from .contracts import (
    Horizon,
    ManualTradeScenario,
    Mode,
    ModelExperiment,
    PerformanceAttribution,
    PositionDecision,
    StockAssessment,
    Universe,
    money,
    pv,
)
from .market_data import MarketData, load_market, synthetic_market
from .portfolio_engine import PortfolioBook, load_portfolio, read_signal_journal
from .research_engine import ResearchContext, ResearchEngine

HOST = r"(?:127\.0\.0\.1|localhost)(?::[0-9]{1,5})?"
ORIGIN = rf"https?://{HOST}"


class ScenarioInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    instrument_id: str = Field(min_length=1)
    quantity: Annotated[int, Field(gt=0)]
    limit_price_tnd: str
    mode: Mode | None = None

    @field_validator("limit_price_tnd")
    @classmethod
    def positive_decimal_string(cls, value: str) -> str:
        try:
            amount = money(Decimal(value))
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("Expected a finite TND decimal string") from exc
        if amount <= 0:
            raise ValueError("A positive TND price is required")
        return format(amount, "f")


def create_v2_app(
    *,
    market: MarketData | None = None,
    demo_market: MarketData | None = None,
    portfolio_dir: Path | None = None,
    autopsy_path: Path | None = None,
) -> FastAPI:
    app = FastAPI(
        title="BVMT Trading Intelligence V2",
        version="2.0.0",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=ORIGIN,
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.middleware("http")
    async def local_only(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        origin = request.headers.get("origin")
        if (
            request.client is None
            or request.client.host not in {"127.0.0.1", "localhost", "::1"}
            or not re.fullmatch(HOST, request.headers.get("host", ""), re.IGNORECASE)
            or (origin is not None and not re.fullmatch(ORIGIN, origin, re.IGNORECASE))
        ):
            return JSONResponse({"detail": "Loopback access required"}, status_code=403)
        return await call_next(request)

    @lru_cache(maxsize=2)
    def data(mode: Mode) -> MarketData:
        if mode == "SYNTHETIC_DEMO":
            return demo_market if demo_market is not None else synthetic_market()
        return market if market is not None else load_market()

    def book(mode: Mode) -> PortfolioBook:
        try:
            return load_portfolio(
                data(mode), mode, portfolio_dir=portfolio_dir, autopsy_path=autopsy_path
            )
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(503, "Portfolio source unavailable or invalid") from exc

    def research(mode: Mode) -> ResearchEngine:
        portfolio = book(mode)
        snapshot = portfolio.eod_mark_portfolio
        equity = snapshot.equity_tnd.value
        weights = {
            h.instrument_id: h.quantity * v / equity
            for h in snapshot.holdings
            if equity and equity > 0 and (v := h.eod_reference_close_tnd.value) is not None
        }
        return ResearchEngine(
            data(mode),
            datetime.now(UTC),
            ResearchContext(tuple(h.instrument_id for h in portfolio.current.holdings), weights),
        )

    def identify(mode: Mode, identifier: str) -> str:
        try:
            return data(mode).resolve(identifier)
        except KeyError as exc:
            raise HTTPException(404, "Unknown equity instrument") from exc

    def _competition_blockers_count() -> int:
        cfg_path = Path(__file__).resolve().parents[2] / "configs/competition.json"
        if not cfg_path.is_file():
            return 0
        raw = json.loads(cfg_path.read_text(encoding="utf-8"))
        fields = raw.get("fields") or {}
        blockers = 0
        for item in fields.values():
            if not isinstance(item, dict):
                continue
            if item.get("value") is None:
                blockers += 1
            if item.get("status") != "verified":
                blockers += 1
            for req in ("source", "evidence_locator", "reviewed_by", "reviewed_at"):
                if not item.get(req):
                    blockers += 1
        return blockers

    @app.get("/api/v2/health")
    def health(mode: Mode = "REAL_COMPETITION") -> dict[str, object]:
        m = data(mode)
        pub_count = sum(
            1
            for series in m.bars.values()
            for bar in series
            if bar.provenance.source_publication_time is not None
        )
        return {
            "mode": mode,
            "status": "ok",
            "execution_enabled": False,
            "automatic_submission_enabled": False,
            "llm_live_enabled": False,
            "rules_blocker_count": _competition_blockers_count(),
            "latest_session": m.sessions[-1] if m.sessions else None,
            "session_count": len(m.sessions),
            "equity_instruments": len(m.instruments),
            "challenge_members": sum(i.challenge_member for i in m.instruments.values()),
            "rejected_non_equity_count": m.rejected_non_equity_count,
            "published_at_present_count": pub_count,
        }

    @app.get("/api/v2/overview")
    def overview(mode: Mode = "REAL_COMPETITION") -> dict[str, object]:
        p = book(mode)
        m = data(mode)
        return {
            **health(mode),
            "account_state_conflict": p.account_state_conflict,
            "current": p.current,
            "equity_by_source": {k: s.equity_tnd for k, s in p.snapshots().items()},
            "latest_market_session": m.sessions[-1] if m.sessions else None,
            "market_instruments": len(m.instruments),
            "challenge_members": sum(i.challenge_member for i in m.instruments.values()),
            "rejected_non_equity_count": m.rejected_non_equity_count,
        }

    @app.get("/api/v2/portfolio")
    def portfolio(mode: Mode = "REAL_COMPETITION") -> dict[str, object]:
        p = book(mode)
        return {
            **health(mode),
            "account_state_conflict": p.account_state_conflict,
            "current": p.current,
            "snapshots": p.snapshots(),
            "rejected_captures": p.rejected_captures,
        }

    @app.get("/api/v2/positions/{instrument_id}")
    def position(instrument_id: str, mode: Mode = "REAL_COMPETITION") -> PositionDecision:
        try:
            return book(mode).position(identify(mode, instrument_id))
        except KeyError as exc:
            raise HTTPException(404, "No holding for this instrument") from exc

    @app.get("/api/v2/discovery")
    def discovery(
        universe: Universe = "TUNIS_BOURSE_CHALLENGE",
        horizon: Horizon = "5_10",
        mode: Mode = "REAL_COMPETITION",
    ) -> dict[str, object]:
        return {
            "mode": mode,
            "universe": universe,
            "horizon": horizon,
            "candidates": research(mode).discover(universe, horizon),
        }

    @app.get("/api/v2/stocks/{instrument_id}")
    def stock(
        instrument_id: str, horizon: Horizon = "5_10", mode: Mode = "REAL_COMPETITION"
    ) -> StockAssessment:
        key = identify(mode, instrument_id)
        return research(mode).candidate(key, horizon).assessment

    @app.get("/api/v2/stocks/{instrument_id}/bars")
    def stock_bars(
        instrument_id: str,
        mode: Mode = "REAL_COMPETITION",
        limit: Annotated[int, Query(ge=1, le=250)] = 60,
    ) -> dict[str, object]:
        m = data(mode)
        key = identify(mode, instrument_id)
        series = m.bars.get(key, ())
        return {
            "mode": mode,
            "instrument": m.instruments[key],
            "bars": series[-limit:],
        }

    def scenario(
        side: Literal["BUY", "SELL", "PROTECTION"], payload: ScenarioInput, query_mode: Mode | None
    ) -> ManualTradeScenario:
        if query_mode and payload.mode and query_mode != payload.mode:
            raise HTTPException(422, "Conflicting account modes")
        mode = query_mode or payload.mode or "REAL_COMPETITION"
        try:
            key = data(mode).resolve(payload.instrument_id)
        except KeyError:
            key = payload.instrument_id
        try:
            return book(mode).scenario(
                side, key, payload.quantity, Decimal(payload.limit_price_tnd)
            )
        except InvalidOperation as exc:
            raise HTTPException(422, "Scenario exceeds supported Decimal precision") from exc

    @app.post("/api/v2/decisions/buy-scenario")
    def buy(payload: ScenarioInput, mode: Mode | None = None) -> ManualTradeScenario:
        return scenario("BUY", payload, mode)

    @app.post("/api/v2/positions/sell-scenario")
    def sell(payload: ScenarioInput, mode: Mode | None = None) -> ManualTradeScenario:
        return scenario("SELL", payload, mode)

    @app.post("/api/v2/positions/protection-scenario")
    def protect(payload: ScenarioInput, mode: Mode | None = None) -> ManualTradeScenario:
        return scenario("PROTECTION", payload, mode)

    @app.get("/api/v2/attribution")
    def attribution(mode: Mode = "REAL_COMPETITION") -> PerformanceAttribution:
        return book(mode).attribution

    @lru_cache(maxsize=2)
    def simulator(mode: Mode) -> Backtester:
        return Backtester.from_market(data(mode))

    @lru_cache(maxsize=6)
    def lab(
        mode: Mode, horizon: int
    ) -> tuple[tuple[ModelExperiment, ...], dict[str, PhaseSensitivity]]:
        tester = simulator(mode)
        experiments = tuple(tester.run(family, horizon) for family in FAMILIES)
        phases = {}
        for family in FAMILIES:
            cadence = 20 if family == "LEGACY-G-APPROX" else horizon
            if len(tester.sessions) >= 61 + cadence + horizon:
                phases[family] = tester.phase_sensitivity(family, horizon)
        return experiments, phases

    @app.get("/api/v2/research-lab")
    def research_lab(
        mode: Mode = "REAL_COMPETITION", horizon: int = 10, exit_instrument_id: str | None = None
    ) -> dict[str, object]:
        if horizon not in (5, 10, 20):
            raise HTTPException(422, "Supported experiment horizons are 5, 10 and 20 sessions")
        enough = len(data(mode).sessions) >= 62 + horizon
        experiments, phases = lab(mode, horizon) if enough else ((), {})
        exit_key = identify(mode, exit_instrument_id) if exit_instrument_id is not None else None
        return {
            "mode": mode,
            "classification": "RETROSPECTIVE_EXPLORATORY"
            if mode == "REAL_COMPETITION"
            else "SYNTHETIC_DEMO",
            "families": FAMILIES,
            "exit_policies": EXIT_POLICIES,
            "signal_journal": read_signal_journal() if mode == "REAL_COMPETITION" else (),
            "experiments": experiments,
            "phase_sensitivity": phases,
            "exit_instrument_id": exit_key,
            "exit_policy_comparison": simulator(mode).compare_exit_policies(exit_key, horizon)
            if exit_key and enough
            else {},
            "limitations": ("Insufficient sessions for all phase offsets",)
            if len(phases) != len(FAMILIES)
            else (),
            "tunindex": pv(
                None,
                "RATIO",
                "UNAVAILABLE",
                "local_archive",
                datetime.now(UTC),
                "No local TUNINDEX series",
            ),
        }

    return app
