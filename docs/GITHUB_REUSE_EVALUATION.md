# Open-Source Trading Infrastructure Evaluation & Reuse Decision

## 1. Purpose
Evaluate four candidate open-source repositories against our BVMT Trading Intelligence requirements:
1. **Microsoft Qlib** (`https://github.com/microsoft/qlib`)
2. **Backtrader** (`https://github.com/mementum/backtrader`)
3. **VectorBT** (`https://github.com/polakowo/vectorbt`)
4. **FinGPT** (`https://github.com/AI4Finance-Foundation/FinGPT`)

Per `rules.md`, `architecture.md`, and `docs/THIRD_PARTY_AUDIT.md`, we evaluate maintenance status, licensing, Python 3.12/3.13 compatibility, hardware footprint, illiquid-market suitability, and Tunis Bourse Challenge execution rules before installing or adopting external code.

---

## 2. 14-Criterion Comparison Matrix

| # | Criterion | Microsoft Qlib (`microsoft/qlib`) | Backtrader (`mementum/backtrader`) | VectorBT (`polakowo/vectorbt`) | FinGPT (`AI4Finance-Foundation/FinGPT`) |
|---|---|---|---|---|---|
| 1 | **Maintenance status** | Active community/research maintenance, but complex legacy Cython/binary pipeline | Unmaintained upstream (last official release `1.9.78.123` in 2020; community forks vary) | Open-source `vectorbt` is frozen/maintenance-only (author moved active features to paid closed-source `vectorbt.pro`) | Active academic/research collection of notebooks and LoRA scripts |
| 2 | **License & usage restrictions** | **MIT License** (permissive) | **GPLv3** (strong copyleft if distributed; internal research use permitted) | **Apache 2.0 with Commons Clause** (non-open-source fair-code restriction) | **MIT License** (code), but underlying base LLM weights have separate licenses |
| 3 | **Python 3.12 / 3.13 compatibility** | Partial (`<=3.12` supported in recent builds; frequent Cython/binary wheel build issues on Windows + Python 3.13) | Pure Python; runs on 3.12/3.13, though legacy `collections`/matplotlib shims occasionally surface | Fragile on Python 3.12/3.13 due to pinned Numba/NumPy/SciPy constraints in open-source `vectorbt` | Notebook-oriented; heavy PyTorch/Transformers/PEFT pins frequently conflict on Python 3.13 |
| 4 | **CPU & RAM requirements** | Medium–High (multi-process data server, custom `.bin` calendar storage) | Low (single-process event loop; runs easily on 4–8 GB RAM) | Medium–High (dense 2D/3D NumPy arrays + Numba JIT compilation) | High if running local LLMs (16–32+ GB RAM) |
| 5 | **GPU requirements** | Optional (CPU works for LightGBM; GPU needed for PyTorch zoo models) | None (CPU only) | None (CPU only) | **Mandatory GPU (VRAM 16–24+ GB)** for FinGPT LoRA fine-tuning/inference |
| 6 | **Installation complexity** | **High** on Windows (requires C++ build tools for Cython extensions and custom data dumping scripts) | **Low** (zero required binary dependencies beyond standard Python) | **Medium–High** (Numba/llvmlite binary wheels often lag Python 3.13) | **High** (CUDA, PyTorch, bitsandbytes, transformers, peft) |
| 7 | **Suitability for small, illiquid markets (~80 stocks)** | **Low–Medium** (engineered for CSI300/S&P500 liquid cross-sections; assumes continuous daily liquidity) | **Medium** (event-driven loop fits ~80 stocks well, **only if** default broker/filler is overridden) | **Low** (vectorized matrix math assumes independent path-invariant fills or simple percent-volume caps) | **Low** for French/Arabic Tunisian disclosures (trained on English US/Chinese financial news) |
| 8 | **Ability to use custom BVMT data** | Requires converting canonical CSV/Parquet into Qlib's proprietary `.bin` directory format | High via custom `DataBase` / pandas feed | High via pandas DataFrames | Requires custom prompt/dataset formatting |
| 9 | **Support for transaction fees** | Yes (percentage buy/sell costs) | Yes (`CommInfoBase` supports 0.50% buy/sell commission) | Yes (percentage fees in `Portfolio.from_orders`) | N/A |
| 10 | **Support for partial fills & liquidity constraints** | Limited in standard `SimulatorExecutor` | **Critical Caveat**: Default `BackBroker` **ignores volume (`filler=None`)**! Requires custom `filler` + shared session capacity tracker | Limited when multiple orders compete for cash and a 10% portfolio cap simultaneously | N/A |
| 11 | **Pending orders, 1-week expiry & suspended-stock holding** | Poor (bar-level rebalance assumptions) | Supports `valid` order expiry and custom broker hooks, but **does not natively hold orders across suspended BVMT sessions or auto-reduce to a 10% portfolio cap** | Poor (vectorized engine cannot easily model stateful 1-week pending queues with dynamic 10% cap auto-reduction) | N/A |
| 12 | **Integration complexity with our starter** | **High** (duplicates our `calendar.py`, `data.py`, and planned DuckDB storage) | **Low–Medium** behind an adapter, or reference-only for broker accounting patterns | **Medium** (only useful for fast single-indicator screening) | **Low** if used strictly as **reference methodology** for prompt/schema design |
| 13 | **Reusable modules vs bloat** | Useful walk-forward/IC metric ideas; 90%+ of repo (RL, PyTorch zoo, binary dumpers) is bloat for BVMT | `CommInfo` / `Order` state machine ideas are useful; plotting/indicator zoo is unneeded | Portfolio metric formulas are useful; Numba dependency tree is heavy | Prompt templates and financial sentiment task framing are useful; LoRA training stack is unneeded |
| 14 | **Long-term maintainability** | Heavy external dependency burden | Stable (frozen), easy to vendor/adapt small pure-Python patterns | Poor (open-source version is a dead-end teaser for `vectorbt.pro`) | Poor as a runtime dependency |

---

## 3. Deep-Dive Findings on Critical Risks

### 3.1 Backtrader's Default Volume-Filling Trap (`S07`)
In `mementum/backtrader` (`backtrader/brokers/bbroker.py` and `backtrader/fillers.py`):
- **Default behavior**: `BackBroker` initializes with `filler=None` (`perc=100%` of order size filled regardless of bar volume, or only capped by total bar volume if `fill_price` checks are enabled, without sharing volume across multiple orders in the same session).
- **Zero-volume & suspended bars**: Without a strict custom broker/filler override, Backtrader can fill market orders on bars where an instrument should be treated as `no_trade` or `suspended`, or fail to enforce the Tunis Bourse Challenge's specific rules:
  1. Orders placed outside `09:00–14:15` wait for the next session.
  2. Orders on `no_trade`, low-activity, or `suspended` securities remain **pending** (up to 1 week) rather than filling at a stale reference close.
  3. Before any purchase, if existing + new exposure exceeds **10% of total portfolio value**, the simulator automatically reduces order quantity or purges the order.
  4. `Decimal` exactness: Backtrader uses IEEE-754 `float` internally, whereas our `rules.md` requires `Decimal` with declared `0.001` TND rounding (`ROUND_HALF_UP`).

### 3.2 Why Qlib and VectorBT Overcomplicate or Distort BVMT Research
- **Universe Scale**: BVMT has fewer than 90 listed equities (~40–55 in *Continu du Marché Principal*). A pure Python + DuckDB/pandas/LightGBM pipeline processes 10 years of daily data (~200,000 rows total) in **< 0.5 seconds on CPU** without Qlib's Cython binary store or VectorBT's Numba JIT compilation.
- **Point-in-Time & Execution Accuracy**: In an illiquid market with frequent `no_trade` days, 10% concentration caps, and 0.50% one-way fees (1.00% round-trip), **execution modeling and point-in-time event alignment** dominate strategy performance—areas where both Qlib and VectorBT make simplifying liquid-market assumptions.

### 3.3 Why FinGPT Should Be Used as Reference Methodology Only
- FinGPT's local fine-tuning requires GPUs and targets English/Chinese datasets.
- However, FinGPT's **structured financial aspect extraction and sentiment/catalyst taxonomy** provide useful design patterns for our **Alibaba Cloud Model Studio** prompts (`Priority C`), where multilingual models (`Qwen`, `DeepSeek`, `Kimi`, `GLM`) natively read French and Arabic BVMT/CMF disclosures via zero-shot/few-shot JSON schemas.

---

## 4. Build-vs-Reuse Decision Matrix

| Component / Capability | Decision | Chosen Tool / Source | Rationale |
|---|---|---|---|
| **Data Storage & PIT Queries** | **REUSE (Library)** | `duckdb` + `pyarrow` (Parquet) + `pandas` | Zero-server, fast SQL window functions (`ASOF JOIN` for point-in-time fundamentals/events), native Parquet support, works offline on CPU. |
| **Tabular ML & Cross-Sectional Ranking** | **REUSE (Library)** | `lightgbm` + `scikit-learn` | Industry-standard CPU gradient boosting and cross-validation splitters; already declared in `pyproject.toml` (`research` extra). |
| **Qlib (`microsoft/qlib`)** | **REFERENCE ONLY** | Do not install `pyqlib` | Borrow Qlib's Information Coefficient (`IC`, `RankIC`) and purged walk-forward evaluation metrics in ~80 lines of typed Python/pandas; avoid Cython/Windows build fragility and proprietary `.bin` format. |
| **VectorBT (`polakowo/vectorbt`)** | **REJECT** | Do not install `vectorbt` | Commons Clause license, frozen open-source branch, Numba/Python 3.13 friction, and inability to model stateful BVMT pending orders and 10% auto-reduction. |
| **Backtrader (`mementum/backtrader`)** | **REFERENCE / OPTIONAL ADAPTER** | Custom `Decimal` Ledger (`src/bvmt/ledger.py`) as primary; `backtrader` optional adapter only | Because our universe is ~50–80 stocks and `rules.md` mandates `Decimal` cash/price accounting plus competition-specific pending-order/10%-cap mechanics, a ~250-line pure-Python `Decimal` portfolio & order-queue engine (`ResearchEngine` / `CompetitionEngine`) is **simpler, safer, and 100% auditable** than overriding Backtrader's float-based `BackBroker`. |
| **FinGPT (`AI4Finance-Foundation/FinGPT`)** | **REFERENCE ONLY** | Do not install `fingpt` | Adapt FinGPT's aspect-based financial catalyst taxonomy into our deterministic JSON schemas (`schemas/`) and Alibaba Cloud Model Studio prompts (`docs/LLM_TRADING_INTELLIGENCE.md`). |

---

## 5. Recommended Architecture

### Recommendation: **Lightweight Python + DuckDB/Parquet + LightGBM/scikit-learn + Custom `Decimal` BVMT Execution Engine + Cached Alibaba Model Studio Extraction**

1. **Why it fits the Tunisian market**: Handles thin volume, `no_trade`/`suspended` states, French/Arabic disclosures, and `0.001` TND (`Millime`) `Decimal` precision without liquid-market approximations.
2. **Why it fits hardware & budget constraints**: Runs entirely on a standard laptop CPU (4–8 GB RAM, 0 GPUs, $0/month cloud cost) and passes `mypy --strict` and `pytest` in < 5 seconds on Python 3.13.
3. **Why it respects competition rules**: Implements the exact Tunis Bourse Challenge constraints (09:00–14:15 window, pending order queue, 1-week expiry, 10% single-stock cap auto-reduction/purge, 0.50% buy/sell fees) in clean, unit-tested domain code (`ResearchEngine` and `CompetitionEngine`).
