import json
from collections.abc import Sequence
from pathlib import Path

import pytest

from bvmt.cli import main
from bvmt.data import aware_timestamp
from bvmt.llm import (
    DashScopeOpenAICompatibleTransport,
    LLMQuotaExhaustedOrForbiddenError,
    LLMRateLimitError,
    _classify_and_raise_http_error,
    chunk_financial_document,
    embed_chunks_with_sidecar,
    evaluate_dry_run,
    execute_structured_extraction,
    load_document_index,
    load_llm_budget_config,
    load_usage_ledger,
    record_usage_tokens,
    save_document_index,
    search_document_index,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "configs/llm_budget.example.json"
NOW = aware_timestamp("2026-11-05T18:30:00+01:00")


class MockLLMTransport:
    def __init__(self, response_json: dict[str, object] | None = None) -> None:
        self.calls = 0
        self.embedding_calls = 0
        self.response_json = response_json or {
            "evidence": [
                {
                    "locator": "Paragraph 1",
                    "original_text": "Le Conseil d'Administration propose un dividende de 1,200 TND par action.",
                    "source_id": "cmf_doc_1",
                }
            ],
            "verified_metrics": [{"current_value": "1.200", "metric_name": "dividend"}],
        }

    def create_chat_completion(
        self,
        *,
        base_url: str,
        api_key: str,
        api_model_id: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int,
        temperature: float,
        timeout_seconds: float,
    ) -> tuple[dict[str, object], int, int, int]:
        self.calls += 1
        return self.response_json, 120, 80, 200

    def create_embeddings(
        self,
        *,
        base_url: str,
        api_key: str,
        api_model_id: str,
        texts: Sequence[str],
        timeout_seconds: float,
    ) -> tuple[list[list[float]], int]:
        self.embedding_calls += 1
        vectors: list[list[float]] = []
        for idx, t in enumerate(texts):
            if "dividende" in t.lower():
                vectors.append([0.9, 0.1, 0.0, float(idx) * 0.01])
            else:
                vectors.append([0.1, 0.9, 0.0, float(idx) * 0.01])
        return vectors, 50 * len(texts)


def test_load_25_model_inventory_and_offline_default():
    cfg = load_llm_budget_config(CONFIG_PATH)
    assert len(cfg.models) == 25
    assert cfg.network_enabled is False
    assert cfg.console_free_quota_only_verified is True

    # Priority 0 embedding model uses full 1,000,000 allowance since Stop on Exhaustion is enabled
    emb = cfg.models["qwen3.7-text-embedding"]
    assert emb.modality == "embedding"
    assert emb.hard_limit == 1000000
    assert emb.safety_reserve == 0
    assert emb.enabled is True

    # Excluded image/video/tts models have hard_limit == 0 and enabled is False
    assert cfg.models["qwen-image-2.1-pro"].enabled is False
    assert cfg.models["qwen-image-2.1-pro"].hard_limit == 0
    assert cfg.models["wan3.0-video-prime"].enabled is False


def test_dry_run_permits_local_budget_but_blocks_live_network_by_default(tmp_path):
    cfg = load_llm_budget_config(CONFIG_PATH)
    report = evaluate_dry_run(
        cfg,
        model_label="qwen3.7-text-embedding",
        role="document_chunk_embedding_pilot",
        prompt_version="v1",
        text_payload="Indicateurs d'activité du 3ème trimestre 2026: PNB en hausse de 8,4%.",
        now=NOW,
        ledger_override_path=tmp_path / "ledger.json",
        cache_override_dir=tmp_path / "cache",
    )
    assert report.permitted_for_local_budget_and_expiry is True
    assert report.permitted_for_live_network_call is False
    assert "config_network_enabled_is_false" in report.blockers
    assert "console_free_quota_only_not_verified" not in report.blockers
    assert report.remaining_budget_before == 1000000


def test_expiration_and_safety_buffer_rejection(tmp_path):
    cfg = load_llm_budget_config(CONFIG_PATH)
    # qwen3.7-text-embedding expires 2026-11-08T00:00:00Z, cutoff is 2026-11-07T12:00:00Z
    after_cutoff = aware_timestamp("2026-11-07T13:00:00+00:00")
    report = evaluate_dry_run(
        cfg,
        model_label="qwen3.7-text-embedding",
        role="document_chunk_embedding_pilot",
        prompt_version="v1",
        text_payload="Test text",
        now=after_cutoff,
        ledger_override_path=tmp_path / "ledger.json",
        cache_override_dir=tmp_path / "cache",
    )
    assert report.permitted_for_local_budget_and_expiry is False
    assert any("model_allowance_expired" in b for b in report.blockers)


def test_independent_model_budget_exhaustion_rejection(tmp_path):
    cfg = load_llm_budget_config(CONFIG_PATH)
    ledger_path = tmp_path / "ledger.json"
    record_usage_tokens(ledger_path, "qwen3.8-2.4t-a95b", 998000, updated_at=NOW)

    # Exhausted on qwen3.8-2.4t-a95b (needs 4000 max completion tokens + input tokens > 2000 remaining)
    rep_qwen = evaluate_dry_run(
        cfg,
        model_label="qwen3.8-2.4t-a95b",
        role="financial_statement_analyst",
        prompt_version="v1",
        text_payload="États financiers annuels 2025",
        now=NOW,
        ledger_override_path=ledger_path,
        cache_override_dir=tmp_path / "cache",
    )
    assert rep_qwen.permitted_for_local_budget_and_expiry is False
    assert any("local_token_budget_exceeded" in b for b in rep_qwen.blockers)

    # Independent pool: deepseek-v4-pro-0813 still has full 1,000,000 remaining
    rep_ds = evaluate_dry_run(
        cfg,
        model_label="deepseek-v4-pro-0813",
        role="independent_research_critic",
        prompt_version="v1",
        text_payload="États financiers annuels 2025",
        now=NOW,
        ledger_override_path=ledger_path,
        cache_override_dir=tmp_path / "cache",
    )
    assert rep_ds.permitted_for_local_budget_and_expiry is True
    assert rep_ds.remaining_budget_before == 1000000


def test_mocked_extraction_caching_and_verbatim_quote_guard(tmp_path):
    cfg = load_llm_budget_config(CONFIG_PATH)
    ledger_path = tmp_path / "ledger.json"
    cache_dir = tmp_path / "cache"
    doc_text = (
        "Communiqué BVMT: Le Conseil d'Administration propose un dividende de 1,200 TND par action."
    )
    transport = MockLLMTransport()

    # Offline default blocks when allow_mock_transport=False
    with pytest.raises(ValueError, match="offline default"):
        execute_structured_extraction(
            cfg,
            model_label="qwen3.8-2.4t-a95b",
            role="financial_statement_analyst",
            prompt_version="v1",
            system_prompt="Extract JSON.",
            source_document_id="cmf_doc_1",
            document_text=doc_text,
            now=NOW,
            transport=transport,
            allow_mock_transport=False,
            ledger_override_path=ledger_path,
            cache_override_dir=cache_dir,
        )

    # First mocked execution succeeds and writes cache + ledger
    payload1, cached1, charged1 = execute_structured_extraction(
        cfg,
        model_label="qwen3.8-2.4t-a95b",
        role="financial_statement_analyst",
        prompt_version="v1",
        system_prompt="Extract JSON.",
        source_document_id="cmf_doc_1",
        document_text=doc_text,
        now=NOW,
        transport=transport,
        allow_mock_transport=True,
        ledger_override_path=ledger_path,
        cache_override_dir=cache_dir,
    )
    assert cached1 is False
    assert charged1 > 0
    assert transport.calls == 1

    # Second call with identical inputs hits local cache (0 tokens charged, 0 transport calls)
    payload2, cached2, charged2 = execute_structured_extraction(
        cfg,
        model_label="qwen3.8-2.4t-a95b",
        role="financial_statement_analyst",
        prompt_version="v1",
        system_prompt="Extract JSON.",
        source_document_id="cmf_doc_1",
        document_text=doc_text,
        now=NOW,
        transport=transport,
        allow_mock_transport=False,  # Even with live disabled, cache serves offline!
        ledger_override_path=ledger_path,
        cache_override_dir=cache_dir,
    )
    assert cached2 is True
    assert charged2 == 0
    assert payload2 == payload1
    assert transport.calls == 1

    # Hallucinated quote not in source document is rejected
    bad_transport = MockLLMTransport(
        response_json={
            "evidence": [
                {
                    "locator": "P1",
                    "original_text": "Fabricated quote not in document",
                    "source_id": "cmf_doc_2",
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="not found verbatim"):
        execute_structured_extraction(
            cfg,
            model_label="qwen3.8-2.4t-a95b",
            role="financial_statement_analyst",
            prompt_version="v1",
            system_prompt="Extract JSON.",
            source_document_id="cmf_doc_2",
            document_text=doc_text,
            now=NOW,
            transport=bad_transport,
            allow_mock_transport=True,
            ledger_override_path=ledger_path,
            cache_override_dir=cache_dir,
        )


def test_document_index_embedding_sidecar_and_post_expiry_bm25_fallback(tmp_path):
    cfg = load_llm_budget_config(CONFIG_PATH)
    ledger_path = tmp_path / "ledger.json"
    index_path = tmp_path / "document_chunks.json"
    sidecar_path = tmp_path / "chunk_embeddings_qwen3_7.json"

    c1 = chunk_financial_document(
        source_document_id="cmf_biat_2026q1",
        instrument_ids=["TN0001000010"],
        published_at=aware_timestamp("2026-04-20T15:00:00+01:00"),
        ingested_at=aware_timestamp("2026-04-20T16:00:00+01:00"),
        language="fr",
        text="Le Conseil d'Administration propose la distribution d'un dividende de 1,200 TND par action.\n\nLe produit net bancaire (PNB) progresse de 9,2% au premier trimestre.",
        max_chunk_chars=120,
    )
    c_future = chunk_financial_document(
        source_document_id="cmf_future_2026q3",
        instrument_ids=["TN0001000010"],
        published_at=aware_timestamp("2026-10-20T15:00:00+01:00"),
        ingested_at=aware_timestamp("2026-10-20T16:00:00+01:00"),
        language="fr",
        text="Dividende exceptionnel annoncé en octobre 2026.",
        max_chunk_chars=200,
    )
    all_chunks = c1 + c_future
    save_document_index(all_chunks, index_path)
    loaded_chunks = load_document_index(index_path)
    assert len(loaded_chunks) == 3

    transport = MockLLMTransport()
    sidecar = embed_chunks_with_sidecar(
        cfg,
        loaded_chunks,
        now=NOW,
        sidecar_path=sidecar_path,
        transport=transport,
        allow_mock_transport=True,
        ledger_override_path=ledger_path,
    )
    assert len(sidecar) == 3
    assert transport.embedding_calls == 1
    assert load_usage_ledger(ledger_path)["qwen3.7-text-embedding"] > 0

    # Cutoff in May 2026 excludes the October 2026 future document!
    cutoff_may = aware_timestamp("2026-05-01T17:00:00+01:00")

    # 1. Search using precomputed canonical query vector + sidecar
    vec_hits = search_document_index(
        loaded_chunks,
        cutoff=cutoff_may,
        precomputed_query_vector=[0.95, 0.05, 0.0, 0.0],
        embedding_sidecar=sidecar,
        top_k=5,
    )
    assert len(vec_hits) == 2
    assert vec_hits[0].method == "cosine_embedding_sidecar"
    assert "dividende" in vec_hits[0].chunk_text.lower()
    assert all(h.source_document_id != "cmf_future_2026q3" for h in vec_hits)

    # 2. Search after embedding allowance expires (no query vector / no sidecar) -> automatic BM25 fallback
    bm25_hits = search_document_index(
        loaded_chunks,
        cutoff=cutoff_may,
        query_text="distribution dividende action",
        top_k=5,
    )
    assert len(bm25_hits) == 1
    assert bm25_hits[0].method == "bm25_lexical_fallback"
    assert "dividende" in bm25_hits[0].chunk_text.lower()


def test_cli_llm_dry_run_command(capsys):
    code = main(
        [
            "llm-dry-run",
            "--model",
            "qwen3.7-text-embedding",
            "--role",
            "document_chunk_embedding_pilot",
            "--now",
            "2026-11-05T18:30:00+01:00",
        ]
    )
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["model_label"] == "qwen3.7-text-embedding"
    assert payload["permitted_for_local_budget_and_expiry"] is True
    assert payload["permitted_for_live_network_call"] is False


def test_dashscope_transport_error_classification_and_url_guard():
    transport = DashScopeOpenAICompatibleTransport()

    # Untrusted URL is blocked before any network socket is opened
    with pytest.raises(ValueError, match="untrusted URL"):
        transport._post_json(
            url="https://evil.example.com/v1/chat/completions",
            api_key="sk-test",
            payload={},
            timeout_seconds=5.0,
            model_id="qwen3.8-2.4t-a95b",
        )

    # Rate limit (429 / Throttling) raises LLMRateLimitError
    with pytest.raises(LLMRateLimitError, match="rate limit"):
        _classify_and_raise_http_error(
            429, '{"error":{"code":"Throttling.RateQuota"}}', "qwen3.8-2.4t-a95b"
        )

    # Free quota exhaustion (403 / FreeQuota) raises LLMQuotaExhaustedOrForbiddenError
    with pytest.raises(LLMQuotaExhaustedOrForbiddenError, match="free quota exhausted"):
        _classify_and_raise_http_error(
            403,
            '{"error":{"code":"FreeQuotaExhausted","message":"Stop on exhaustion triggered"}}',
            "qwen3.7-text-embedding",
        )
