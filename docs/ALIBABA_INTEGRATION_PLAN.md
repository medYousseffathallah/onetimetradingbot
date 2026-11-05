# Alibaba Cloud Model Studio (DashScope) Integration Plan — Complete 25-Model Inventory

## 1. Overview & Non-Goals
This document specifies the minimal, zero-cost-risk provider abstraction for **Alibaba Cloud Model Studio (DashScope)** (`src/bvmt/llm.py`, planned after approval), covering the **complete 25-model allowance inventory** across Text LLMs (10), Embeddings (1), Multimodal (2), Image (3), Video (1), and Speech/Audio (8).
- **Default state**: `offline_only` (`network_enabled: false`).
- **Transport**: Standard HTTPS (`httpx` or `urllib.request`) against Alibaba Cloud's OpenAI-compatible endpoints (`/compatible-mode/v1/chat/completions` and `/compatible-mode/v1/embeddings`)—**no vendor SDK (`dashscope`) required** for core text, multimodal, or embedding operations.
- **Core discipline**: Expiring free credits must **never** dictate unnecessary infrastructure. Models without a verified quantitative research use case (e.g., image generation and video generation) are explicitly marked `disabled_in_trading_pipeline: true`.

---

## 2. Complete 25-Model Allowance Inventory, Ranking & Disposition

All allowances are **independent per-model pools** (not a shared pool). Below is the complete inventory ranked by **Expiration Urgency**, **Trading Research Usefulness**, **Quota Unit Type**, and **Offline Replacement Feasibility**:

| Priority Rank | Console Label | Modality | Allowance & Unit Type | Expiration Date (UTC) | Effective Local Cutoff (-12h Buffer) | Trading Usefulness | Offline Replacement Feasibility | Pipeline Disposition |
|---:|---|---|---|---|---|---|---|---|
| **P0 (Immediate: 3 days)** | `qwen3.7-text-embedding` | **Embeddings** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-08** | `2026-11-07T12:00:00Z` | **High** (Batch-index historical CMF/BVMT French/Arabic disclosure chunks into local Parquet) | **High** (DuckDB Full-Text Search BM25 + SQL metadata filters work with zero embeddings) | **PILOT 1 (Immediate)**: Batch-embed historical CMF/BVMT corpus before Nov 8; freeze index. |
| **P1 (Urgent: 6 days)** | `qwen3.8-2.4t-a95b` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-11** | `2026-11-10T12:00:00Z` | **Highest** (Role 1 Financial Statement Analyst & Role 3 Critic on dense CMF filings) | **High** (Cached JSON extractions in `data/processed/llm_extractions/` persist permanently) | **PILOT 2 (Urgent)**: Primary Role 1/3 extractor on 20-doc benchmark + historical corpus. |
| **P1 (Urgent: 7 days)** | `deepseek-v4-pro-0813` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-12** | `2026-11-11T12:00:00Z` | **Highest** (Role 3 Independent Research Critic cross-checking Qwen extractions) | **High** (Cached JSON critic reviews persist permanently) | **PILOT 2 (Urgent)**: Cross-family Role 3 Critic on Role 1/2 extractions before Nov 12. |
| **P2 (11 days)** | `qwen3.8-27b` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-16** | `2026-11-15T12:00:00Z` | **High** (Role 2 Corporate Event Analyst on BVMT communiqués) | **High** (Cached JSON events + regex templates) | **Active (Tier 2)**: Role 2 event extraction through Nov 15. |
| **P2 (11 days)** | `kimi-k3` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-16** | `2026-11-15T12:00:00Z` | **High** (Long-context French/Arabic annual reports & prospectuses) | **High** (Cached JSON extractions) | **Active (Tier 2)**: Long-report extraction through Nov 15. |
| **P3 (17–25 days)** | `glm-5.3` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-22** | `2026-11-21T12:00:00Z` | **Medium–High** (Role 2 event extraction backup) | **High** | **Active (Tier 3)**: Late-November filings. |
| **P3 (19 days)** | `qwen3.8-flash` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-24** | `2026-11-23T12:00:00Z` | **Medium–High** (Fast triage & Role 2 extraction) | **High** | **Active (Tier 3)**: Fast structured extraction. |
| **P3 (20 days)** | `qwen-mt-image-2.0` | **Image (OCR/Translation)** | `100` image units (Hard cap: `100` images) | **2026-11-25** | `2026-11-24T12:00:00Z` | **Low–Medium** (Optional translation/OCR of scanned Arabic/French image tables if needed) | **High** (`pypdf`/`pdfplumber` handles native PDFs; manual entry for rare scans) | **Optional Benchmark Only**: Disabled by default; test only if scanned image filings are encountered. |
| **P3 (25 days)** | `qwen3.8-max-0902` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-11-30** | `2026-11-29T12:00:00Z` | **High** (Flagship Role 3 Critic & Role 1 Analyst after Nov 12) | **High** (Cached JSON extractions) | **Active (Tier 3)**: Primary Critic for late November. |
| **P4 (Dec 2026 – Feb 2027)** | `deepseek-v4.1-flash` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-12-12** | `2026-12-11T12:00:00Z` | **High** (December competition disclosures) | **High** | **Active (Tier 4 Reserve)**. |
| **P4 (Dec 2026)** | `qwen3.8-omni-flash` | **Multimodal** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2026-12-16** | `2026-12-15T12:00:00Z` | **Medium** (Candidate for scanned PDF table extraction — **must pass OCR accuracy benchmark first**) | **High** (Native PDF text parsers + manual review) | **Benchmark-Gated Optional**: Test on 5 scanned CMF financial tables before trusting. |
| **P4 (Jan–Feb 2027)** | `deepseek-v4.1-flash-1017` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2027-01-16** | `2027-01-15T12:00:00Z` | **High** (January 2027 Q4 activity indicators) | **High** | **Active (Tier 4 Reserve)**. |
| **P4 (Feb 2027)** | `kimi-k3.1-pro` | **Text LLM** | `1,000,000` tokens (Hard cap: `1,000,000`) | **2027-02-01** | `2027-01-31T12:00:00Z` | **High** (Final LLM reserve through Jan 31, 2027) | **High** | **Active (Tier 4 Reserve)**. |
| **P5 (Optional Audio)** | `qwen-audio-3.1-asr-flash-filetrans`<br>`qwen-audio-3.1-asr-flash`<br>`qwen-audio-3.1-asr-flash-message`<br>`qwen-audio-3.1-asr-flash-streaming`<br>`qwen3.8-livetranslate-flash-realtime` | **Speech (ASR / Translation)** | `1,000,000` allowance each | **2026-12-15** to **2026-12-20** | `-12h` buffer | **Low (Optional)** (Transcribing recorded CEO/broker interviews or AGM webcasts if audio files are downloaded) | **High** (Written CMF/BVMT communiqués are the primary statutory source) | **Optional / Disabled by Default**: Do not build streaming audio pipelines; use `filetrans` offline only if an official AGM/analyst audio recording is obtained. |
| **P6 (Excluded)** | `qwen3.8-omni-flash-realtime`<br>`qwen-audio-3.1-tts-plus` (`10K`)<br>`qwen-audio-3.1-tts-flash` (`1M`)<br>`qwen-audio-3.1-tts-next` (`1M`)<br>`qwen-image-2.1-pro` (`10 units`)<br>`qwen-image-2.1-turbo` (`10 units`)<br>`wan3.0-video-prime` (`30 units`) | **Realtime Omni / TTS / Image Gen / Video Gen** | Tokens / Characters / Image & Video units | **2026-11-20** to **2026-12-31** | N/A | **None (`0`)** (Synthetic image/video generation and text-to-speech add zero value to quantitative BVMT research) | N/A | **EXCLUDED (`enabled: false`)**: Explicitly blocked in `configs/llm_budget.example.json` to prevent accidental invocation or billing. |

---

## 3. Priority Analysis: `qwen3.7-text-embedding` (Expires November 8, 2026) & Local Document Search

### 3.1 Can Embeddings Improve Tunisian Financial Research?
Yes, with strict boundaries:
- **Where embeddings help**: Semantic cross-lingual retrieval across French/Arabic CMF filings and BVMT announcements (e.g., querying *"hausse du coût du risque bancaire / provisions sur créances"* or *"augmentation de capital par incorporation de réserves"* across 200+ historical PDFs where exact phrasings vary).
- **Where embeddings must NEVER be used**: Computing numerical signals directly from cosine similarity without Role 1/2 structured extraction, or retrieving chunks published *after* a backtest's `decision_cutoff` (point-in-time leakage).

### 3.2 Persistent Local Document & Chunk Index Design (`data/processed/document_index/`)
To avoid introducing a vector database server (explicitly a non-goal in `goal.md`), we store the document index in **two flat Parquet/JSON tables queryable via DuckDB and NumPy**:

1. **`document_chunks.parquet` (Permanent, Model-Independent Text & Metadata)**:
   - `chunk_id`: `SHA256(source_document_id + ":" + str(chunk_index) + ":" + chunk_sha256)`
   - `source_document_id`: Safe ID referencing `data/raw/<source_id>/<doc_sha256>.bin`
   - `instrument_ids`: Array of mapped `instrument_id`s from `InstrumentRecord`
   - `published_at`: UTC-aware publication timestamp (`None` if unknown — excluded from point-in-time retrieval unless verified)
   - `ingested_at`: UTC-aware ingestion timestamp
   - `language`: `fr` | `ar` | `en`
   - `section_locator`: Page / heading locator
   - `chunk_text`: Normalized UTF-8 text (e.g., 400–600 tokens per chunk)
   - `chunk_sha256`: SHA-256 of `chunk_text`
2. **`chunk_embeddings_<model_slug>.parquet` (Model-Specific Vector Sidecar)**:
   - `chunk_id`: Foreign key to `document_chunks.parquet`
   - `embedding_model_id`: `"qwen3.7-text-embedding"`
   - `embedding_dim`: Integer dimension (e.g., `1024` or `1536`)
   - `vector`: `FLOAT[D]` L2-normalized embedding vector

### 3.3 Why Embedding Spaces Are Incompatible Across Models — and How Search Works After November 8, 2026
**Critical Technical Constraint**:
Vector embeddings from `qwen3.7-text-embedding` live in a model-specific vector space. Once `qwen3.7-text-embedding` expires on **November 8, 2026**:
- You **cannot** embed a new user query (or a new December 2026 document) using a different embedding model (e.g., a local HuggingFace model) and compute cosine similarity against the `qwen3.7-text-embedding` vectors—different models have orthogonal/incompatible latent spaces.

**Our 3-Part Post-Expiration Search Architecture (Zero Re-Embedding Required)**:
1. **Pre-Compute a Taxonomy of Canonical Research Queries Before Nov 8**:
   - During the Nov 5–7 pilot, in addition to embedding the historical CMF/BVMT document chunks (~100,000–300,000 tokens), we also embed a fixed catalog of **~50 canonical financial research query templates** (`canonical_query_embeddings.parquet`, consuming < 2,000 tokens total)—covering dividends, capital increases, revenue growth, margin compression, debt/financing, tax/regulation, auditor qualifications, and litigation.
   - Because both the historical chunks and the 50 canonical research queries are embedded by `qwen3.7-text-embedding` before Nov 8, **document-to-document similarity** and **canonical-topic retrieval** remain 100% functional offline forever via a 5-line NumPy dot product.
2. **Primary Ad-Hoc Search via DuckDB Full-Text Search (`fts` BM25) + SQL Point-in-Time Filters**:
   - For arbitrary ad-hoc text queries or newly ingested post-Nov-8 documents, `document_chunks.parquet` is indexed by **DuckDB's built-in BM25 Full-Text Search** plus exact SQL filters (`WHERE instrument_id = ? AND published_at <= ?`).
   - On financial disclosures (where specific terms like `dividende`, `PNB`, `résultat net`, `détachement`, `souscription`, or ISINs appear explicitly), **BM25 lexical search + SQL metadata filtering** is deterministic, requires zero API tokens, and works seamlessly across old and new documents alike.
3. **Clean Sidecar Separation**:
   - Because `chunk_embeddings_qwen3_7.parquet` is stored as a separate sidecar keyed by `chunk_id`, `document_chunks.parquet` remains the single source of truth regardless of whether vector similarity or BM25 is used.

---

## 4. Multimodal (`qwen3.8-omni-flash`) & Speech (`qwen-audio-3.1-*`) Evaluation

### 4.1 Multimodal (`qwen3.8-omni-flash`, Expires Dec 16, 2026)
- **Potential Use**: Some older Tunisian company filings on `cmf.tn` are published as **scanned image PDFs** (where standard text extractors return empty strings) or contain complex multi-column French financial tables.
- **Strict Safeguard**: Do **not** assume `qwen3.8-omni-flash` performs error-free OCR on French/Arabic accounting tables (`12 345,600` vs `12 345 600` or negative parentheses `(1 250)`).
- **Verification Gate**: `qwen3.8-omni-flash` is gated behind **Benchmark Subset E (Scanned Table OCR Benchmark)** in `docs/LLM_BENCHMARK_PLAN.md`: it must achieve **100% cell-level numeric and sign accuracy** on 5 rendered images of known BVMT/CMF financial tables before being allowed to extract any scanned PDF. Even then, all multimodal extractions require `validation_status: "needs_human_review"`.

### 4.2 Speech/Audio (`qwen-audio-3.1-*`, Expires Dec 15–20, 2026) & Image/Video Exclusions
- **Speech ASR (`qwen-audio-3.1-asr-flash-filetrans`)**: Kept as **optional/disabled by default**. Only used offline if a recorded AGM or management interview audio file is manually downloaded into `data/raw/`. No real-time streaming audio (`-streaming`, `-realtime`) or TTS (`-tts-*`) will be built.
- **Image Generation (`qwen-image-2.1-*`) & Video Generation (`wan3.0-video-prime`)**: **Permanently excluded (`enabled: false`)**. Generating synthetic images or videos has zero relevance to BVMT equity research and carries high unit-billing risk if free quotas are exceeded.

---

## 5. Console "Stop on Exhaustion / Free Quota Only" Update & Defense-in-Depth Controls

### 5.1 Console Free-Quota Protection Status & Endpoint Coverage Verification
1. **Console Toggle Enabled (2026-11-05)**:
   - The user confirmed enabling **"Stop on Exhaustion / Free Quota Only"** in the Alibaba Cloud Model Studio Console (`console_free_quota_only_verified: true` in `configs/llm_budget.example.json`).
   - Because Alibaba Cloud's server-side billing gate now automatically stops requests when a model's free quota reaches `0`, we have **removed the artificial 15% (`150,000`-token) local safety reserve** and raised the local `hard_limit` to the **full `1,000,000` tokens** (`safety_reserve: 0`) for all active research models, while raising `max_input_chars` to `80,000` and `max_completion_tokens` to `4,000` so full multi-page Tunisian financial filings and annual report sections can be processed without artificial truncation.
   - Furthermore, when the DashScope API returns exact `usage.total_tokens` in the response, the local ledger charges the **actual API-reported tokens** rather than the pre-call upper-bound estimate.
2. **Does "Stop on Exhaustion / Free Quota Only" Apply to All Models and Endpoints? (Important Verification Notes)**:
   - **OpenAI-Compatible Endpoints (`/compatible-mode/v1/chat/completions` & `/compatible-mode/v1/embeddings`)**: Yes — Alibaba Cloud Model Studio shares the same underlying workspace quota pool and "Free Quota Only" circuit breaker across both native DashScope endpoints and `/compatible-mode/v1` endpoints, **provided** you call the exact `api_model_id` string associated with the free-quota grant in the same region (`dashscope-intl.aliyuncs.com` vs `dashscope-us.aliyuncs.com`).
   - **Critical Edge Cases Requiring Local Protection (Why We Retain Basic Local Guards)**:
     - **Model ID Mismatch Risk**: If a request accidentally specifies a model alias or snapshot ID that is *not* part of the free-tier grant (for example, calling a commercial pay-as-you-go variant whose name differs by a date suffix), the console's free-quota toggle for the free model will **not** cover the ungranted model ID, or will immediately reject it. Therefore, `api_model_id_verified` remains a per-model check in `configs/llm_budget.example.json`.
     - **Expiration Date vs. Exhaustion**: In Alibaba Cloud Model Studio, "Stop on Exhaustion" prevents over-quota billing *while the free quota voucher is active*, but once the calendar **Expiration Date** (`expires_at`) passes, the free voucher disappears. Depending on workspace billing settings, calling a model *after* its voucher expires can either fail or fall back to pay-as-you-go. Therefore, we strictly retain the **local `-12h` UTC expiration cutoff (`effective_cutoff_utc`)** in `evaluate_dry_run` so the system never calls a model after its free window expires.
     - **Non-Research Modalities (`qwen-image-2.1-*`, `wan3.0-video-prime`, `qwen-audio-3.1-tts-*`)**: Kept `enabled: false` and `hard_limit: 0` locally so they can never be called accidentally.

### 5.2 Retained Basic Protections & Live HTTP Transport (`DashScopeOpenAICompatibleTransport`)
1. **Standard-Library Live HTTPS Client (`DashScopeOpenAICompatibleTransport` in `src/bvmt/llm.py`)**:
   - Fully implemented using Python's standard `urllib.request` against `/compatible-mode/v1/chat/completions` and `/compatible-mode/v1/embeddings` (zero external SDK bloat).
   - Remains **offline by default** (`network_enabled: false`) until explicitly authorized.
   - Enforces **explicit Rate-Limit (`LLMRateLimitError` on HTTP `429` / `Throttling`)** and **Free-Quota Exhaustion (`LLMQuotaExhaustedOrForbiddenError` on HTTP `402`/`403` / `FreeQuota` / `QuotaExhausted`)** classification with `max_retries: 0` (never hammered in retry loops).
2. **Retained Local Safeguards**:
   - Offline-by-default lock (`network_enabled: false` and `BVMT_ALLOW_LIVE_LLM=1` required).
   - Content-addressed local cache (`data/processed/llm_cache/`) so identical document extractions never consume tokens twice.
   - Independent per-model usage ledger (`data/processed/llm_usage_ledger.json`) with full `1,000,000`-token ceiling.
   - Strict UTC expiration cutoff (`expires_at - 12 hours`).
   - Post-response JSON schema + verbatim substring grounding check (`verify_verbatim_evidence_quotes`).
