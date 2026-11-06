"""Alibaba Cloud Model Studio (DashScope) budget-gated provider, document index, and sidecar embeddings.

Offline by default: never transmits live network requests unless explicitly opted in via
configuration (`network_enabled=True`, `console_free_quota_only_verified=True`,
`api_model_id_verified=True`) AND environment (`BVMT_ALLOW_LIVE_LLM=1`, `DASHSCOPE_API_KEY`).
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from typing import Protocol
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlsplit

from bvmt.data import aware_timestamp
from bvmt.snapshots import (
    atomic_write_text,
    ensure_no_symlink_ancestors,
    validate_safe_id,
)

ALLOWED_BASE_URLS = frozenset(
    {
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    }
)

ALLOWED_ROLES = frozenset(
    {
        "document_chunk_embedding_pilot",
        "financial_statement_analyst",
        "corporate_event_analyst",
        "independent_research_critic",
    }
)

WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿ0-9_]{2,}")


@dataclass(frozen=True)
class ModelAllowanceSpec:
    console_label: str
    api_model_id: str
    api_model_id_verified: bool
    modality: str
    enabled: bool
    quota_unit: str
    initial_allowance: int
    safety_reserve: int
    hard_limit: int
    expires_at: datetime
    effective_cutoff_utc: datetime
    priority_tier: int
    assigned_roles: tuple[str, ...]


@dataclass(frozen=True)
class LLMBudgetConfig:
    schema_version: int
    provider: str
    base_url: str
    api_key_env_var: str
    live_opt_in_env_var: str
    network_enabled: bool
    console_free_quota_only_verified: bool
    cache_dir: str
    ledger_path: str
    expiration_safety_buffer_hours: int
    max_completion_tokens: int
    max_input_chars: int
    max_retries: int
    require_verbatim_quote_check: bool
    temperature: float
    timeout_seconds: float
    models: dict[str, ModelAllowanceSpec]


@dataclass(frozen=True)
class DryRunReport:
    model_label: str
    api_model_id: str
    modality: str
    role: str
    input_chars: int
    estimated_input_tokens: int
    max_completion_tokens: int
    estimated_total_tokens: int
    used_tokens: int
    hard_limit_tokens: int
    remaining_budget_before: int
    remaining_budget_after_estimate: int
    expires_at: str
    effective_cutoff_utc: str
    evaluated_at: str
    cache_key: str
    cached_response_available: bool
    permitted_for_local_budget_and_expiry: bool
    permitted_for_live_network_call: bool
    blockers: list[str]


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    source_document_id: str
    instrument_ids: list[str]
    published_at: str | None
    ingested_at: str
    language: str
    section_locator: str
    chunk_index: int
    chunk_text: str
    chunk_sha256: str


@dataclass(frozen=True)
class ChunkEmbeddingRecord:
    chunk_id: str
    embedding_model_id: str
    embedding_dim: int
    vector: list[float]


@dataclass(frozen=True)
class SearchHit:
    chunk_id: str
    source_document_id: str
    instrument_ids: list[str]
    published_at: str | None
    section_locator: str
    score: float
    method: str
    chunk_text: str


class LLMTransport(Protocol):
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
        """Return (parsed_json_object, prompt_tokens, completion_tokens, total_tokens)."""

    def create_embeddings(
        self,
        *,
        base_url: str,
        api_key: str,
        api_model_id: str,
        texts: Sequence[str],
        timeout_seconds: float,
    ) -> tuple[list[list[float]], int]:
        """Return (vectors, total_tokens)."""


class LLMRateLimitError(RuntimeError):
    """Raised when Alibaba Cloud Model Studio returns HTTP 429 or a rate-limit error code."""


class LLMQuotaExhaustedOrForbiddenError(RuntimeError):
    """Raised when Alibaba Cloud Model Studio blocks a request due to Free Quota exhaustion or 402/403."""


def _classify_and_raise_http_error(status_code: int, body_text: str, model_id: str) -> None:
    lower_body = body_text.lower()
    if (
        status_code == 429
        or "throttling" in lower_body
        or "rate limit" in lower_body
        or "limitrequests" in lower_body
    ):
        raise LLMRateLimitError(
            f"Alibaba Model Studio rate limit (HTTP {status_code}) for '{model_id}'; "
            f"max_retries=0 enforced to protect quota: {body_text[:240]}"
        )
    if (
        status_code in {401, 402, 403}
        or "freetieronly" in lower_body
        or "accessdenied" in lower_body
        or "invalidapikey" in lower_body
        or "freequota" in lower_body
        or "quota" in lower_body
        or "arrearage" in lower_body
        or "exhausted" in lower_body
    ):
        raise LLMQuotaExhaustedOrForbiddenError(
            f"Alibaba Model Studio free quota exhausted or forbidden (HTTP {status_code}) "
            f"for '{model_id}': {body_text[:240]}"
        )
    raise RuntimeError(
        f"Alibaba Model Studio HTTP {status_code} error for '{model_id}': {body_text[:240]}"
    )


class DashScopeOpenAICompatibleTransport:
    """Standard-library HTTPS client for DashScope OpenAI-compatible endpoints (/chat/completions & /embeddings).

    Never invoked unless all local and live-network opt-in gates pass. Enforces zero automatic
    retries and explicit rate-limit (429) and free-quota exhaustion (402/403) error classification.
    """

    def __init__(self, *, region: str | None = None, base_url: str | None = None) -> None:
        self.base_url = resolve_dashscope_base_url(base_url=base_url, region=region)

    def _post_json(
        self,
        *,
        url: str,
        api_key: str,
        payload: dict[str, object],
        timeout_seconds: float,
        model_id: str,
    ) -> dict[str, object]:
        base = url.removesuffix("/chat/completions").removesuffix("/embeddings")
        if base == url or not _trusted_dashscope_url(base):
            raise ValueError(f"Refusing to send request to untrusted URL: '{url}'")
        if not api_key or not api_key.strip():
            raise ValueError("Missing API key for DashScope transport")
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib_request.Request(
            url,
            data=data,
            headers={
                "Authorization": f"Bearer {api_key.strip()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )
        try:
            with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:  # nosec B310
                raw_bytes = resp.read()
        except urllib_error.HTTPError as exc:
            err_body = ""
            try:
                err_body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                err_body = str(exc)
            _classify_and_raise_http_error(exc.code, err_body, model_id)
            raise AssertionError("unreachable") from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"Network transport error for '{model_id}': {exc}") from exc

        decoded = json.loads(raw_bytes.decode("utf-8"))
        if not isinstance(decoded, dict):
            raise ValueError("DashScope response must be a JSON object")
        if decoded.get("error") or decoded.get("code"):
            _classify_and_raise_http_error(400, json.dumps(decoded), model_id)
        return decoded

    def create_chat_completion(
        self,
        *,
        base_url: str | None = None,
        api_key: str,
        api_model_id: str,
        system_prompt: str,
        user_prompt: str,
        max_completion_tokens: int,
        temperature: float,
        timeout_seconds: float,
    ) -> tuple[dict[str, object], int, int, int]:
        url = f"{resolve_dashscope_base_url(base_url=(base_url or self.base_url) if not os.environ.get('DASHSCOPE_REGION') else None)}/chat/completions"
        payload: dict[str, object] = {
            "model": api_model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_completion_tokens,
            "temperature": temperature,
            "response_format": {"type": "json_object"},
        }
        resp = self._post_json(
            url=url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=timeout_seconds,
            model_id=api_model_id,
        )
        choices = resp.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Missing choices in DashScope chat completion response")
        first = choices[0]
        if not isinstance(first, dict) or not isinstance(first.get("message"), dict):
            raise ValueError("Malformed choice message in DashScope response")
        content = first["message"].get("content")
        if isinstance(content, list):
            if any(
                not isinstance(block, dict)
                or block.get("type") != "text"
                or not isinstance(block.get("text"), str)
                for block in content
            ):
                raise ValueError("Unsupported chat content block")
            content = "".join(block["text"] for block in content)
        if not isinstance(content, str) or not content.strip():
            raise ValueError("Missing text content in DashScope response")
        parsed_json = json.loads(content)
        if not isinstance(parsed_json, dict):
            raise ValueError("Extracted model content must be a JSON object")
        usage = resp.get("usage")
        prompt_tok = 0
        comp_tok = 0
        total_tok = 0
        if isinstance(usage, dict):
            prompt_tok = int(str(usage.get("prompt_tokens", 0) or 0))
            comp_tok = int(str(usage.get("completion_tokens", 0) or 0))
            total_tok = int(
                str(
                    usage.get("total_tokens")
                    if usage.get("total_tokens") is not None
                    else prompt_tok + comp_tok
                )
            )
        return parsed_json, prompt_tok, comp_tok, total_tok

    def create_embeddings(
        self,
        *,
        base_url: str | None = None,
        api_key: str,
        api_model_id: str,
        texts: Sequence[str],
        timeout_seconds: float,
        dimensions: int | None = None,
        encoding_format: str = "float",
    ) -> tuple[list[list[float]], int]:
        if encoding_format != "float" or (
            dimensions is not None and (type(dimensions) is not int or dimensions <= 0)
        ):
            raise ValueError("Expected float encoding and positive dimensions")
        url = f"{resolve_dashscope_base_url(base_url=(base_url or self.base_url) if not os.environ.get('DASHSCOPE_REGION') else None)}/embeddings"
        payload: dict[str, object] = {
            "model": api_model_id,
            "input": list(texts),
            "encoding_format": encoding_format,
        }
        if dimensions is not None:
            payload["dimensions"] = dimensions
        resp = self._post_json(
            url=url,
            api_key=api_key,
            payload=payload,
            timeout_seconds=timeout_seconds,
            model_id=api_model_id,
        )
        data_list = resp.get("data")
        if not isinstance(data_list, list) or len(data_list) != len(texts):
            raise ValueError("Malformed or incomplete embedding data in DashScope response")
        vectors: list[list[float]] = []
        for item in data_list:
            if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
                raise ValueError("Missing embedding vector in DashScope response item")
            vector = item["embedding"]
            if not vector or any(
                type(x) not in {int, float} or not math.isfinite(x) for x in vector
            ):
                raise ValueError("Embedding must be a non-empty finite numeric vector")
            if dimensions is not None and len(vector) != dimensions:
                raise ValueError("Unexpected embedding dimensions")
            if vectors and len(vector) != len(vectors[0]):
                raise ValueError("Inconsistent embedding dimensions")
            vectors.append([float(x) for x in vector])
        usage = resp.get("usage")
        total_tok = 0
        if isinstance(usage, dict):
            total_tok = int(str(usage.get("total_tokens", usage.get("prompt_tokens", 0)) or 0))
        return vectors, total_tok

    # Additive names used by provider integrations; original protocol remains intact.
    generate = create_chat_completion
    embed = create_embeddings


def estimate_tokens(text: str) -> int:
    """Conservative upper-bound token estimate for French/Arabic/English financial text."""
    if not text:
        return 0
    utf8_len = len(text.encode("utf-8"))
    return max(1, math.ceil(utf8_len / 2.5))


def _canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_llm_budget_config(path: Path) -> LLMBudgetConfig:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") not in {1, 2}:
        raise ValueError("Unsupported LLM budget config schema_version")
    base_url = str(raw.get("base_url") or "").strip()
    if base_url not in ALLOWED_BASE_URLS:
        raise ValueError(f"Unsupported or untrusted Model Studio base_url: '{base_url}'")
    policy = raw.get("default_policy")
    if not isinstance(policy, dict):
        raise ValueError("Missing default_policy in LLM budget config")
    raw_models = raw.get("models")
    if not isinstance(raw_models, list) or not raw_models:
        raise ValueError("Missing models list in LLM budget config")

    models: dict[str, ModelAllowanceSpec] = {}
    for item in raw_models:
        if not isinstance(item, dict):
            raise ValueError("Each model entry must be an object")
        label = str(item.get("console_label") or "").strip()
        if not label:
            raise ValueError("Model console_label is required")
        raw_initial = item.get("initial_allowance", item.get("initial_allowance_tokens", 0))
        raw_reserve = item.get("safety_reserve", item.get("safety_reserve_tokens", 0))
        raw_hard = item.get("hard_limit", item.get("hard_limit_tokens", 0))
        initial = int(str(raw_initial if raw_initial is not None else 0))
        reserve = int(str(raw_reserve if raw_reserve is not None else 0))
        hard_limit = int(str(raw_hard if raw_hard is not None else 0))
        if initial < 0 or reserve < 0 or hard_limit < 0 or hard_limit > initial - reserve:
            raise ValueError(f"Invalid budget limits for model '{label}'")
        expires_at = aware_timestamp(str(item["expires_at"]))
        cutoff_utc = aware_timestamp(str(item["effective_cutoff_utc"]))
        if cutoff_utc > expires_at:
            raise ValueError(f"effective_cutoff_utc cannot follow expires_at for '{label}'")
        roles = tuple(str(r) for r in item.get("assigned_roles", []))
        models[label] = ModelAllowanceSpec(
            console_label=label,
            api_model_id=str(item.get("api_model_id") or "").strip(),
            api_model_id_verified=bool(item.get("api_model_id_verified", False)),
            modality=str(item.get("modality") or "text").strip(),
            enabled=bool(item.get("enabled", True)),
            quota_unit=str(item.get("quota_unit") or "tokens").strip(),
            initial_allowance=initial,
            safety_reserve=reserve,
            hard_limit=hard_limit,
            expires_at=expires_at,
            effective_cutoff_utc=cutoff_utc,
            priority_tier=int(item.get("priority_tier", 9)),
            assigned_roles=roles,
        )

    return LLMBudgetConfig(
        schema_version=int(raw["schema_version"]),
        provider=str(raw.get("provider") or ""),
        base_url=base_url,
        api_key_env_var=str(raw.get("api_key_env_var") or "DASHSCOPE_API_KEY"),
        live_opt_in_env_var=str(raw.get("live_opt_in_env_var") or "BVMT_ALLOW_LIVE_LLM"),
        network_enabled=bool(raw.get("network_enabled", False)),
        console_free_quota_only_verified=bool(raw.get("console_free_quota_only_verified", False)),
        cache_dir=str(policy.get("cache_dir") or "data/processed/llm_cache"),
        ledger_path=str(policy.get("ledger_path") or "data/processed/llm_usage_ledger.json"),
        expiration_safety_buffer_hours=int(policy.get("expiration_safety_buffer_hours", 12)),
        max_completion_tokens=int(policy.get("max_completion_tokens", 1500)),
        max_input_chars=int(policy.get("max_input_chars", 24000)),
        max_retries=int(policy.get("max_retries", 0)),
        require_verbatim_quote_check=bool(policy.get("require_verbatim_quote_check", True)),
        temperature=float(policy.get("temperature", 0.0)),
        timeout_seconds=float(policy.get("timeout_seconds", 45.0)),
        models=models,
    )


def load_usage_ledger(ledger_path: Path) -> dict[str, int]:
    if not ledger_path.is_file():
        return {}
    raw = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Corrupt LLM usage ledger")
    usage = raw.get("model_usage_tokens", {})
    if not isinstance(usage, dict):
        raise ValueError("Corrupt model_usage_tokens in LLM usage ledger")
    return {str(k): int(v) for k, v in usage.items()}


def record_usage_tokens(
    ledger_path: Path, model_label: str, delta_tokens: int, *, updated_at: datetime
) -> int:
    if delta_tokens < 0:
        raise ValueError("Token usage delta cannot be negative")
    if updated_at.tzinfo is None or updated_at.utcoffset() is None:
        raise ValueError("updated_at must be timezone-aware")
    ensure_no_symlink_ancestors(ledger_path)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    current = load_usage_ledger(ledger_path)
    new_total = current.get(model_label, 0) + delta_tokens
    current[model_label] = new_total
    payload = {
        "model_usage_tokens": dict(sorted(current.items())),
        "schema_version": 1,
        "updated_at": updated_at.isoformat(),
    }
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if ledger_path.exists():
        ledger_path.unlink()
    atomic_write_text(ledger_path, text, allow_identical=True)
    return new_total


def evaluate_dry_run(
    config: LLMBudgetConfig,
    *,
    model_label: str,
    role: str,
    prompt_version: str,
    text_payload: str,
    now: datetime,
    ledger_override_path: Path | None = None,
    cache_override_dir: Path | None = None,
) -> DryRunReport:
    """Evaluate all 7 local budget, expiration, size, role, and live-network gates without calling any API."""
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("Evaluation timestamp 'now' must be timezone-aware")
    if model_label not in config.models:
        raise ValueError(f"Unknown model_label '{model_label}'")
    spec = config.models[model_label]
    ledger_path = ledger_override_path or Path(config.ledger_path)
    cache_dir = cache_override_dir or Path(config.cache_dir)

    usage_map = load_usage_ledger(ledger_path)
    used_tokens = usage_map.get(model_label, 0)

    input_chars = len(text_payload)
    est_input_tokens = estimate_tokens(text_payload)
    max_comp_tokens = 0 if spec.modality == "embedding" else config.max_completion_tokens
    est_total_tokens = est_input_tokens + max_comp_tokens

    cache_key = _canonical_hash(
        {
            "api_model_id": spec.api_model_id,
            "modality": spec.modality,
            "model_label": model_label,
            "payload_sha256": hashlib.sha256(text_payload.encode("utf-8")).hexdigest(),
            "prompt_version": prompt_version,
            "role": role,
        }
    )
    cache_file = cache_dir / f"{cache_key}.json"
    cached_available = cache_file.is_file()

    local_blockers: list[str] = []
    if not spec.enabled:
        local_blockers.append(f"model_disabled:{model_label}")
    if role not in ALLOWED_ROLES:
        local_blockers.append(f"unsupported_role:{role}")
    elif role not in spec.assigned_roles:
        local_blockers.append(f"role_not_assigned_to_model:{role}")
    if input_chars == 0:
        local_blockers.append("empty_input_payload")
    if input_chars > config.max_input_chars:
        local_blockers.append(f"input_exceeds_max_chars:{input_chars}>{config.max_input_chars}")
    if now >= spec.effective_cutoff_utc:
        local_blockers.append(
            f"model_allowance_expired_or_within_safety_buffer:{now.isoformat()}>={spec.effective_cutoff_utc.isoformat()}"
        )
    if used_tokens + est_total_tokens > spec.hard_limit:
        local_blockers.append(
            f"local_token_budget_exceeded:{used_tokens}+{est_total_tokens}>{spec.hard_limit}"
        )

    live_blockers = list(local_blockers)
    if not config.network_enabled:
        live_blockers.append("config_network_enabled_is_false")
    if not config.console_free_quota_only_verified:
        live_blockers.append("console_free_quota_only_not_verified")
    if not spec.api_model_id_verified:
        live_blockers.append("api_model_id_not_verified_in_console")
    if os.environ.get(config.live_opt_in_env_var) != "1":
        live_blockers.append(f"env_{config.live_opt_in_env_var}_not_set_to_1")
    if not os.environ.get(config.api_key_env_var, "").strip():
        live_blockers.append(f"env_{config.api_key_env_var}_missing")

    remaining_before = max(0, spec.hard_limit - used_tokens)
    remaining_after = max(0, spec.hard_limit - (used_tokens + est_total_tokens))

    return DryRunReport(
        model_label=model_label,
        api_model_id=spec.api_model_id,
        modality=spec.modality,
        role=role,
        input_chars=input_chars,
        estimated_input_tokens=est_input_tokens,
        max_completion_tokens=max_comp_tokens,
        estimated_total_tokens=est_total_tokens,
        used_tokens=used_tokens,
        hard_limit_tokens=spec.hard_limit,
        remaining_budget_before=remaining_before,
        remaining_budget_after_estimate=remaining_after,
        expires_at=spec.expires_at.isoformat(),
        effective_cutoff_utc=spec.effective_cutoff_utc.isoformat(),
        evaluated_at=now.isoformat(),
        cache_key=cache_key,
        cached_response_available=cached_available,
        permitted_for_local_budget_and_expiry=(len(local_blockers) == 0),
        permitted_for_live_network_call=(len(live_blockers) == 0),
        blockers=live_blockers,
    )


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def verify_verbatim_evidence_quotes(extracted_payload: dict[str, object], source_text: str) -> None:
    """Ensure every evidence[].original_text quote appears verbatim in source_text."""
    norm_source = _normalize_whitespace(source_text)
    quotes: list[str] = []

    def _collect(obj: object) -> None:
        if isinstance(obj, dict):
            if "original_text" in obj and isinstance(obj["original_text"], str):
                quotes.append(obj["original_text"])
            for val in obj.values():
                _collect(val)
        elif isinstance(obj, list):
            for item in obj:
                _collect(item)

    _collect(extracted_payload)
    if not quotes:
        raise ValueError("Extraction payload contains no verbatim 'original_text' evidence quotes")
    for quote in quotes:
        norm_quote = _normalize_whitespace(quote)
        if not norm_quote or norm_quote not in norm_source:
            raise ValueError(
                f"Evidence quote not found verbatim in source document: '{quote[:80]}'"
            )


def execute_structured_extraction(
    config: LLMBudgetConfig,
    *,
    model_label: str,
    role: str,
    prompt_version: str,
    system_prompt: str,
    source_document_id: str,
    document_text: str,
    now: datetime,
    transport: LLMTransport | None = None,
    allow_mock_transport: bool = False,
    ledger_override_path: Path | None = None,
    cache_override_dir: Path | None = None,
) -> tuple[dict[str, object], bool, int]:
    """Execute or serve from cache a structured JSON extraction with strict budget & quote gates.

    Returns (parsed_json, from_cache, tokens_charged).
    """
    validate_safe_id(source_document_id, "source_document_id")
    wrapped_user_prompt = (
        f"source_document_id: {source_document_id}\n"
        "<UNTRUSTED_SOURCE_DOCUMENT>\n"
        f"{document_text}\n"
        "</UNTRUSTED_SOURCE_DOCUMENT>"
    )
    combined_payload = f"{system_prompt}\n---\n{wrapped_user_prompt}"
    report = evaluate_dry_run(
        config,
        model_label=model_label,
        role=role,
        prompt_version=prompt_version,
        text_payload=combined_payload,
        now=now,
        ledger_override_path=ledger_override_path,
        cache_override_dir=cache_override_dir,
    )
    cache_dir = cache_override_dir or Path(config.cache_dir)
    ledger_path = ledger_override_path or Path(config.ledger_path)
    cache_file = cache_dir / f"{report.cache_key}.json"

    if cache_file.is_file():
        cached_doc = json.loads(cache_file.read_text(encoding="utf-8"))
        payload = cached_doc["response_json"]
        if config.require_verbatim_quote_check and role in {
            "financial_statement_analyst",
            "corporate_event_analyst",
        }:
            verify_verbatim_evidence_quotes(payload, document_text)
        return payload, True, 0

    if not report.permitted_for_local_budget_and_expiry:
        raise ValueError(f"LLM request blocked by local policy: {report.blockers}")

    if not allow_mock_transport and not report.permitted_for_live_network_call:
        raise ValueError(f"Live LLM network call is blocked (offline default): {report.blockers}")

    if transport is None:
        if not allow_mock_transport and report.permitted_for_live_network_call:
            transport = DashScopeOpenAICompatibleTransport()
        else:
            raise ValueError("No LLMTransport provided; live network client is disabled by default")

    api_key = os.environ.get(config.api_key_env_var, "MOCK_KEY" if allow_mock_transport else "")
    spec = config.models[model_label]
    response_json, prompt_tok, comp_tok, total_tok = transport.create_chat_completion(
        base_url=config.base_url,
        api_key=api_key,
        api_model_id=spec.api_model_id,
        system_prompt=system_prompt,
        user_prompt=wrapped_user_prompt,
        max_completion_tokens=config.max_completion_tokens,
        temperature=config.temperature,
        timeout_seconds=config.timeout_seconds,
    )
    reported = max(total_tok, prompt_tok + comp_tok)
    charged = reported if reported > 0 else report.estimated_total_tokens
    record_usage_tokens(ledger_path, model_label, charged, updated_at=now)

    if config.require_verbatim_quote_check and role in {
        "financial_statement_analyst",
        "corporate_event_analyst",
    }:
        verify_verbatim_evidence_quotes(response_json, document_text)

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_record = {
        "cache_key": report.cache_key,
        "charged_tokens": charged,
        "completed_at": now.isoformat(),
        "model_label": model_label,
        "prompt_version": prompt_version,
        "reported_total_tokens": total_tok,
        "response_json": response_json,
        "role": role,
        "source_document_id": source_document_id,
    }
    atomic_write_text(
        cache_file,
        json.dumps(cache_record, indent=2, sort_keys=True, allow_nan=False) + "\n",
        allow_identical=True,
    )
    return response_json, False, charged


def chunk_financial_document(
    *,
    source_document_id: str,
    instrument_ids: Sequence[str],
    published_at: datetime | None,
    ingested_at: datetime,
    language: str,
    text: str,
    max_chunk_chars: int = 1200,
) -> list[DocumentChunk]:
    """Deterministically split a financial disclosure into content-addressed chunks."""
    validate_safe_id(source_document_id, "source_document_id")
    if ingested_at.tzinfo is None or ingested_at.utcoffset() is None:
        raise ValueError("ingested_at must be timezone-aware")
    if published_at is not None:
        if published_at.tzinfo is None or published_at.utcoffset() is None:
            raise ValueError("published_at must be timezone-aware")
        if ingested_at < published_at:
            raise ValueError("ingested_at cannot precede published_at")
    if max_chunk_chars < 100:
        raise ValueError("max_chunk_chars must be >= 100")

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        raise ValueError("Document text is empty")

    raw_chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if not current:
            current = para
        elif len(current) + 2 + len(para) <= max_chunk_chars:
            current = f"{current}\n\n{para}"
        else:
            raw_chunks.append(current)
            current = para
    if current:
        raw_chunks.append(current)

    chunks: list[DocumentChunk] = []
    clean_instruments = sorted({i.strip() for i in instrument_ids if i.strip()})
    pub_iso = published_at.isoformat() if published_at is not None else None
    ing_iso = ingested_at.isoformat()

    for idx, chunk_str in enumerate(raw_chunks):
        c_sha = hashlib.sha256(chunk_str.encode("utf-8")).hexdigest()
        c_id = hashlib.sha256(f"{source_document_id}:{idx}:{c_sha}".encode()).hexdigest()[:24]
        chunks.append(
            DocumentChunk(
                chunk_id=c_id,
                source_document_id=source_document_id,
                instrument_ids=clean_instruments,
                published_at=pub_iso,
                ingested_at=ing_iso,
                language=language.strip() or "fr",
                section_locator=f"chunk_{idx + 1}_of_{len(raw_chunks)}",
                chunk_index=idx,
                chunk_text=chunk_str,
                chunk_sha256=c_sha,
            )
        )
    return chunks


def save_document_index(chunks: Iterable[DocumentChunk], index_path: Path) -> None:
    payload = [
        asdict(c) for c in sorted(chunks, key=lambda x: (x.source_document_id, x.chunk_index))
    ]
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    atomic_write_text(index_path, text, allow_identical=True)


def load_document_index(index_path: Path) -> list[DocumentChunk]:
    raw = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Document index must be a JSON list")
    return [
        DocumentChunk(
            chunk_id=str(item["chunk_id"]),
            source_document_id=str(item["source_document_id"]),
            instrument_ids=[str(x) for x in item.get("instrument_ids", [])],
            published_at=str(item["published_at"]) if item.get("published_at") else None,
            ingested_at=str(item["ingested_at"]),
            language=str(item["language"]),
            section_locator=str(item["section_locator"]),
            chunk_index=int(item["chunk_index"]),
            chunk_text=str(item["chunk_text"]),
            chunk_sha256=str(item["chunk_sha256"]),
        )
        for item in raw
    ]


def save_embedding_sidecar(records: Iterable[ChunkEmbeddingRecord], sidecar_path: Path) -> None:
    payload = [asdict(r) for r in sorted(records, key=lambda x: x.chunk_id)]
    text = json.dumps(payload, indent=2, sort_keys=True, allow_nan=False) + "\n"
    atomic_write_text(sidecar_path, text, allow_identical=True)


def load_embedding_sidecar(sidecar_path: Path) -> dict[str, ChunkEmbeddingRecord]:
    if not sidecar_path.is_file():
        return {}
    raw = json.loads(sidecar_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Embedding sidecar must be a JSON list")
    result: dict[str, ChunkEmbeddingRecord] = {}
    for item in raw:
        rec = ChunkEmbeddingRecord(
            chunk_id=str(item["chunk_id"]),
            embedding_model_id=str(item["embedding_model_id"]),
            embedding_dim=int(item["embedding_dim"]),
            vector=[float(v) for v in item["vector"]],
        )
        result[rec.chunk_id] = rec
    return result


def embed_chunks_with_sidecar(
    config: LLMBudgetConfig,
    chunks: Sequence[DocumentChunk],
    *,
    model_label: str = "qwen3.7-text-embedding",
    now: datetime,
    sidecar_path: Path,
    transport: LLMTransport | None = None,
    allow_mock_transport: bool = False,
    ledger_override_path: Path | None = None,
) -> dict[str, ChunkEmbeddingRecord]:
    """Batch-embed unindexed chunks within the model's budget and persist the vector sidecar."""
    existing = load_embedding_sidecar(sidecar_path)
    missing = [c for c in chunks if c.chunk_id not in existing]
    if not missing:
        return existing

    combined_text = "\n".join(c.chunk_text for c in missing)
    report = evaluate_dry_run(
        config,
        model_label=model_label,
        role="document_chunk_embedding_pilot",
        prompt_version="embedding_v1",
        text_payload=combined_text,
        now=now,
        ledger_override_path=ledger_override_path,
    )
    if not report.permitted_for_local_budget_and_expiry:
        raise ValueError(f"Embedding batch blocked by local policy: {report.blockers}")
    if not allow_mock_transport and not report.permitted_for_live_network_call:
        raise ValueError(f"Live embedding call blocked (offline default): {report.blockers}")
    if transport is None:
        if not allow_mock_transport and report.permitted_for_live_network_call:
            transport = DashScopeOpenAICompatibleTransport()
        else:
            raise ValueError("No LLMTransport provided for embedding batch")

    spec = config.models[model_label]
    api_key = os.environ.get(config.api_key_env_var, "MOCK_KEY" if allow_mock_transport else "")
    vectors, total_tokens = transport.create_embeddings(
        base_url=config.base_url,
        api_key=api_key,
        api_model_id=spec.api_model_id,
        texts=[c.chunk_text for c in missing],
        timeout_seconds=config.timeout_seconds,
    )
    if len(vectors) != len(missing):
        raise ValueError("Embedding count mismatch from transport")

    ledger_path = ledger_override_path or Path(config.ledger_path)
    charged = total_tokens if total_tokens > 0 else report.estimated_total_tokens
    record_usage_tokens(ledger_path, model_label, charged, updated_at=now)

    updated = dict(existing)
    for chunk, vec in zip(missing, vectors, strict=True):
        norm = math.sqrt(sum(v * v for v in vec)) or 1.0
        unit_vec = [round(v / norm, 8) for v in vec]
        updated[chunk.chunk_id] = ChunkEmbeddingRecord(
            chunk_id=chunk.chunk_id,
            embedding_model_id=spec.api_model_id,
            embedding_dim=len(unit_vec),
            vector=unit_vec,
        )
    save_embedding_sidecar(updated.values(), sidecar_path)
    return updated


def _tokenize_bm25(text: str) -> list[str]:
    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def search_document_index(
    chunks: Sequence[DocumentChunk],
    *,
    cutoff: datetime,
    query_text: str | None = None,
    precomputed_query_vector: Sequence[float] | None = None,
    embedding_sidecar: dict[str, ChunkEmbeddingRecord] | None = None,
    instrument_id: str | None = None,
    top_k: int = 5,
) -> list[SearchHit]:
    """Point-in-time local document search with automatic BM25 lexical fallback when embeddings expire.

    Strictly filters out any chunk whose `published_at` is missing or > `cutoff`, or whose
    `ingested_at` > `cutoff`.
    """
    if cutoff.tzinfo is None or cutoff.utcoffset() is None:
        raise ValueError("Search cutoff must be timezone-aware")
    if top_k < 1:
        raise ValueError("top_k must be >= 1")

    eligible: list[DocumentChunk] = []
    for chunk in chunks:
        if chunk.published_at is None:
            continue
        pub_dt = aware_timestamp(chunk.published_at)
        ing_dt = aware_timestamp(chunk.ingested_at)
        if pub_dt <= cutoff and ing_dt <= cutoff:
            if instrument_id is None or instrument_id in chunk.instrument_ids:
                eligible.append(chunk)

    if not eligible:
        return []

    if (
        precomputed_query_vector is not None
        and embedding_sidecar is not None
        and all(c.chunk_id in embedding_sidecar for c in eligible)
    ):
        q_norm = math.sqrt(sum(v * v for v in precomputed_query_vector)) or 1.0
        q_vec = [v / q_norm for v in precomputed_query_vector]
        scored: list[SearchHit] = []
        for chunk in eligible:
            c_vec = embedding_sidecar[chunk.chunk_id].vector
            if len(c_vec) != len(q_vec):
                raise ValueError("Incompatible embedding dimension between query and sidecar")
            sim = float(sum(a * b for a, b in zip(q_vec, c_vec, strict=True)))
            scored.append(
                SearchHit(
                    chunk_id=chunk.chunk_id,
                    source_document_id=chunk.source_document_id,
                    instrument_ids=chunk.instrument_ids,
                    published_at=chunk.published_at,
                    section_locator=chunk.section_locator,
                    score=round(sim, 6),
                    method="cosine_embedding_sidecar",
                    chunk_text=chunk.chunk_text,
                )
            )
        scored.sort(key=lambda h: (-h.score, h.chunk_id))
        return scored[:top_k]

    if not query_text or not query_text.strip():
        raise ValueError("Either query_text or precomputed_query_vector + sidecar is required")

    q_tokens = _tokenize_bm25(query_text)
    if not q_tokens:
        return []

    doc_tokens = [_tokenize_bm25(c.chunk_text) for c in eligible]
    avg_dl = sum(len(t) for t in doc_tokens) / len(eligible) if eligible else 1.0
    n_docs = len(eligible)
    df: Counter[str] = Counter()
    for toks in doc_tokens:
        for term in set(toks):
            df[term] += 1

    k1 = 1.5
    b = 0.75
    bm25_hits: list[SearchHit] = []
    for chunk, toks in zip(eligible, doc_tokens, strict=True):
        tf = Counter(toks)
        dl = len(toks) or 1
        score = 0.0
        for term in q_tokens:
            if tf[term] == 0:
                continue
            term_df = df[term]
            idf = math.log(1.0 + (n_docs - term_df + 0.5) / (term_df + 0.5))
            denom = tf[term] + k1 * (1.0 - b + b * (dl / avg_dl))
            score += idf * ((tf[term] * (k1 + 1.0)) / denom)
        if score > 0.0:
            bm25_hits.append(
                SearchHit(
                    chunk_id=chunk.chunk_id,
                    source_document_id=chunk.source_document_id,
                    instrument_ids=chunk.instrument_ids,
                    published_at=chunk.published_at,
                    section_locator=chunk.section_locator,
                    score=round(score, 6),
                    method="bm25_lexical_fallback",
                    chunk_text=chunk.chunk_text,
                )
            )
    bm25_hits.sort(key=lambda h: (-h.score, h.chunk_id))
    return bm25_hits[:top_k]


REGIONAL_BASE_URLS = {
    "intl": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
    "us": "https://dashscope-us.aliyuncs.com/compatible-mode/v1",
    "cn": "https://dashscope.aliyuncs.com/compatible-mode/v1",
}


def _trusted_dashscope_url(url: str) -> bool:
    parsed = urlsplit(url)
    return (
        parsed.scheme == "https"
        and parsed.username is None
        and parsed.password is None
        and parsed.port in {None, 443}
        and not parsed.query
        and not parsed.fragment
        and parsed.path == "/compatible-mode/v1"
        and (
            url in ALLOWED_BASE_URLS
            or bool(
                re.fullmatch(
                    r"[A-Za-z0-9-]+\.(?:ap-southeast-1|us-east-1|cn-beijing)\.maas\.aliyuncs\.com",
                    parsed.hostname or "",
                )
            )
        )
    )


def resolve_dashscope_base_url(*, base_url: str | None = None, region: str | None = None) -> str:
    """Environment URL > explicit URL > environment/explicit region > intl default.

    Only official regional and workspace HTTPS hosts may receive credentials.
    """
    selected_region = region or os.environ.get("DASHSCOPE_REGION", "intl")
    selected = os.environ.get("DASHSCOPE_BASE_URL") or base_url
    if not selected:
        if selected_region not in REGIONAL_BASE_URLS:
            raise ValueError("DASHSCOPE_REGION must be intl, us or cn")
        selected = REGIONAL_BASE_URLS[selected_region]
    selected = selected.rstrip("/")
    if not _trusted_dashscope_url(selected):
        raise ValueError("Untrusted DashScope base URL")
    return selected


# Documentation evidence is deliberately independent of config verification flags.
DOC_VERIFIED_MODEL_IDS = frozenset(
    {
        "qwen3.7-text-embedding",
        "qwen3.8-2.4t-a95b",
        "deepseek-v4-pro-0813",
        "qwen3.8-flash",
        "kimi-k3",
        "text-embedding-v3",
        "text-embedding-v4",
    }
)


@dataclass(frozen=True)
class ProviderReadinessReport:
    offline_mode_active: bool
    live_env_enabled: bool
    api_key_configured: bool
    resolved_base_url: str
    console_free_quota_only_verified: bool
    active_models: tuple[str, ...]
    expired_models: tuple[str, ...]
    verification_notes: dict[str, str]


class AlibabaModelStudioProvider:
    """Read-only readiness facade; never probes the API or exposes credentials."""

    def __init__(self, config: LLMBudgetConfig) -> None:
        self.config = config

    def check_readiness(self, as_of: date) -> ProviderReadinessReport:
        # Date-only audits use end-of-day UTC: a cutoff later that day is not safely active.
        cutoff = datetime.combine(as_of, time.max, tzinfo=UTC)
        models = tuple(self.config.models.values())
        return ProviderReadinessReport(
            offline_mode_active=not self.config.network_enabled,
            live_env_enabled=os.environ.get(self.config.live_opt_in_env_var) == "1",
            api_key_configured=bool(os.environ.get(self.config.api_key_env_var, "").strip()),
            resolved_base_url=resolve_dashscope_base_url(
                base_url=self.config.base_url if not os.environ.get("DASHSCOPE_REGION") else None
            ),
            console_free_quota_only_verified=self.config.console_free_quota_only_verified,
            active_models=tuple(
                sorted(
                    m.api_model_id for m in models if m.enabled and cutoff < m.effective_cutoff_utc
                )
            ),
            expired_models=tuple(
                sorted(m.api_model_id for m in models if cutoff >= m.effective_cutoff_utc)
            ),
            verification_notes={
                m.api_model_id: "verified_from_docs_requires_controlled_live_test"
                if m.api_model_id in DOC_VERIFIED_MODEL_IDS
                else "offline_only"
                for m in models
            },
        )
