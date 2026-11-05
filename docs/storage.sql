-- Planned DuckDB-oriented schema; not an executed migration in the starter.
-- Decimal precision is an engineering choice, not an official exchange tick rule.
CREATE TABLE source_documents (
  document_id VARCHAR PRIMARY KEY, source_id VARCHAR NOT NULL,
  content_sha256 VARCHAR NOT NULL, local_path VARCHAR NOT NULL,
  retrieved_at TIMESTAMPTZ NOT NULL, published_at TIMESTAMPTZ,
  access_permission VARCHAR NOT NULL, parser_version VARCHAR
);
CREATE TABLE instruments (
  instrument_id VARCHAR NOT NULL, symbol VARCHAR NOT NULL, isin VARCHAR,
  valid_from DATE NOT NULL, valid_to DATE, listed_from DATE, listed_to DATE,
  currency VARCHAR NOT NULL, source_document_id VARCHAR NOT NULL,
  PRIMARY KEY (instrument_id, valid_from)
);
CREATE TABLE sessions (
  session_date DATE PRIMARY KEY, is_open BOOLEAN NOT NULL,
  opens_at TIMESTAMPTZ, closes_at TIMESTAMPTZ, source_document_id VARCHAR NOT NULL
);
CREATE TABLE daily_bars (
  instrument_id VARCHAR NOT NULL, session_date DATE NOT NULL,
  revision_id VARCHAR NOT NULL, price_basis VARCHAR NOT NULL,
  open DECIMAL(24,8), high DECIMAL(24,8), low DECIMAL(24,8), close DECIMAL(24,8),
  volume_shares BIGINT, turnover_tnd DECIMAL(24,3), trading_status VARCHAR NOT NULL,
  published_at TIMESTAMPTZ, available_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL, source_document_id VARCHAR NOT NULL,
  PRIMARY KEY (instrument_id, session_date, price_basis, revision_id)
);
CREATE TABLE fundamental_facts (
  instrument_id VARCHAR NOT NULL, metric VARCHAR NOT NULL,
  period_end DATE NOT NULL, numeric_value DECIMAL(30,8), unit VARCHAR NOT NULL,
  published_at TIMESTAMPTZ, available_at TIMESTAMPTZ NOT NULL,
  revision_id VARCHAR NOT NULL, source_document_id VARCHAR NOT NULL,
  PRIMARY KEY (instrument_id, metric, period_end, revision_id)
);
CREATE TABLE corporate_actions (
  action_id VARCHAR PRIMARY KEY, instrument_id VARCHAR NOT NULL,
  action_type VARCHAR NOT NULL, announcement_at TIMESTAMPTZ,
  ex_date DATE, payment_date DATE, payload_json VARCHAR NOT NULL,
  source_document_id VARCHAR NOT NULL
);
CREATE TABLE events (
  event_id VARCHAR PRIMARY KEY, source_document_id VARCHAR NOT NULL,
  published_at TIMESTAMPTZ, available_at TIMESTAMPTZ NOT NULL,
  effective_date DATE, policy_stage VARCHAR NOT NULL,
  evidence_json VARCHAR NOT NULL, model_version VARCHAR, human_review_status VARCHAR
);
CREATE TABLE experiments (
  run_id VARCHAR PRIMARY KEY, code_revision VARCHAR, data_manifest_sha256 VARCHAR NOT NULL,
  config_sha256 VARCHAR NOT NULL, profile VARCHAR NOT NULL, started_at TIMESTAMPTZ NOT NULL,
  completed_at TIMESTAMPTZ, status VARCHAR NOT NULL, results_path VARCHAR
);
CREATE TABLE ledger_entries (
  entry_id VARCHAR PRIMARY KEY, run_id VARCHAR NOT NULL, timestamp TIMESTAMPTZ NOT NULL,
  instrument_id VARCHAR, entry_type VARCHAR NOT NULL, quantity BIGINT,
  cash_delta DECIMAL(24,3) NOT NULL, source_event_id VARCHAR NOT NULL
);
CREATE TABLE audit_events (
  audit_id VARCHAR PRIMARY KEY, run_id VARCHAR, timestamp TIMESTAMPTZ NOT NULL,
  actor VARCHAR NOT NULL, action VARCHAR NOT NULL, input_hash VARCHAR, output_hash VARCHAR,
  details_json VARCHAR NOT NULL
);
