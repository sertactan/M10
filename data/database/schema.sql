PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS security_master (
    security_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    name TEXT NOT NULL,
    exchange TEXT NOT NULL,
    market TEXT NOT NULL DEFAULT 'US',
    cik TEXT,
    sector TEXT,
    industry TEXT,
    ipo_date TEXT,
    delisted_date TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    primary_exchange_mic TEXT,
    security_type TEXT,
    currency TEXT,
    locale TEXT,
    composite_figi TEXT,
    share_class_figi TEXT,
    source_priority INTEGER NOT NULL DEFAULT 99,
    first_seen TEXT,
    last_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_security_ticker ON security_master(ticker);
CREATE INDEX IF NOT EXISTS idx_security_exchange ON security_master(exchange);

CREATE TABLE IF NOT EXISTS ticker_aliases (
    alias TEXT NOT NULL,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    valid_from TEXT NOT NULL DEFAULT '',
    valid_to TEXT,
    source TEXT NOT NULL DEFAULT 'UNKNOWN',
    event_type TEXT NOT NULL DEFAULT 'alias',
    availability_date TEXT,
    ingested_at TEXT,
    PRIMARY KEY(alias, security_id, valid_from)
);

CREATE TABLE IF NOT EXISTS universe_snapshot_membership (
    snapshot_date TEXT NOT NULL,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    ticker TEXT NOT NULL,
    exchange TEXT NOT NULL,
    exchange_mic TEXT NOT NULL,
    security_type TEXT,
    source TEXT NOT NULL,
    availability_date TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY(snapshot_date, security_id, ticker, source)
);
CREATE INDEX IF NOT EXISTS idx_universe_snapshot_date
ON universe_snapshot_membership(snapshot_date, exchange, ticker);

CREATE TABLE IF NOT EXISTS universe_sync_runs (
    sync_id TEXT PRIMARY KEY,
    as_of_date TEXT NOT NULL,
    source_mode TEXT NOT NULL,
    active_loaded INTEGER NOT NULL DEFAULT 0,
    delisted_loaded INTEGER NOT NULL DEFAULT 0,
    sec_enriched INTEGER NOT NULL DEFAULT 0,
    finnhub_validated INTEGER NOT NULL DEFAULT 0,
    ticker_events_loaded INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    message TEXT
);

CREATE TABLE IF NOT EXISTS price_daily (
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    trade_date TEXT NOT NULL,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    adjusted_close REAL NOT NULL,
    volume REAL NOT NULL,
    vwap REAL,
    market_cap REAL,
    provider TEXT NOT NULL,
    availability_date TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    source_url TEXT,
    PRIMARY KEY(security_id, trade_date, provider, availability_date)
);
CREATE INDEX IF NOT EXISTS idx_price_pit
ON price_daily(security_id, trade_date, availability_date);

CREATE TABLE IF NOT EXISTS corporate_actions (
    action_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    action_type TEXT NOT NULL,
    ex_date TEXT NOT NULL,
    effective_date TEXT,
    ratio REAL,
    cash_amount REAL,
    new_ticker TEXT,
    provider TEXT NOT NULL,
    availability_date TEXT NOT NULL,
    ingested_at TEXT NOT NULL,
    raw_json TEXT
);

CREATE TABLE IF NOT EXISTS filings (
    filing_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    form_type TEXT NOT NULL,
    period_date TEXT,
    filing_date TEXT NOT NULL,
    availability_date TEXT NOT NULL,
    accession_number TEXT,
    source_url TEXT,
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_filings_pit
ON filings(security_id, availability_date);

CREATE TABLE IF NOT EXISTS financial_facts (
    fact_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    fact_key TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    fiscal_period TEXT,
    fiscal_year INTEGER,
    period_date TEXT,
    filing_date TEXT,
    availability_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    source TEXT NOT NULL,
    source_url TEXT,
    ingested_at TEXT NOT NULL,
    raw_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_facts_pit
ON financial_facts(security_id, fact_key, period_date, availability_date);

CREATE TABLE IF NOT EXISTS market_observations (
    observation_id TEXT PRIMARY KEY,
    market TEXT NOT NULL,
    metric TEXT NOT NULL,
    value REAL,
    text_value TEXT,
    period_date TEXT,
    availability_date TEXT NOT NULL,
    provider TEXT NOT NULL,
    ingested_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_market_pit
ON market_observations(market, metric, availability_date);

CREATE TABLE IF NOT EXISTS provider_state (
    provider TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    last_success_at TEXT,
    last_attempt_at TEXT,
    message TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS analysis_runs (
    analysis_id TEXT PRIMARY KEY,
    ticker TEXT NOT NULL,
    security_id TEXT NOT NULL,
    analysis_date TEXT NOT NULL,
    mode TEXT NOT NULL,
    model_version TEXT NOT NULL,
    data_snapshot_hash TEXT NOT NULL,
    model_config_hash TEXT NOT NULL,
    score REAL,
    route TEXT,
    destination TEXT,
    prediction TEXT,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_scores (
    analysis_id TEXT NOT NULL REFERENCES analysis_runs(analysis_id),
    factor_key TEXT NOT NULL,
    factor_value REAL,
    availability TEXT NOT NULL DEFAULT 'AVAILABLE',
    evidence_json TEXT,
    PRIMARY KEY(analysis_id, factor_key)
);

CREATE TABLE IF NOT EXISTS backtest_results (
    analysis_id TEXT PRIMARY KEY REFERENCES analysis_runs(analysis_id),
    entry_price REAL,
    return_1m REAL,
    return_3m REAL,
    return_6m REAL,
    return_12m REAL,
    max_gain_12m REAL,
    max_drawdown_12m REAL,
    result_class TEXT,
    outcome_status TEXT NOT NULL
);


-- Phase 2: provider-isolated historical price metadata.
CREATE TABLE IF NOT EXISTS price_series_registry (
    series_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    source TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    row_count INTEGER NOT NULL,
    quality_status TEXT NOT NULL,
    adjustment_status TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    parquet_root TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(security_id, source, source_symbol)
);
CREATE INDEX IF NOT EXISTS idx_price_series_lookup
ON price_series_registry(security_id, source, start_date, end_date);

CREATE TABLE IF NOT EXISTS canonical_price_selection (
    selection_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    purpose TEXT NOT NULL,
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    source TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    reason TEXT NOT NULL,
    selected_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_price_selection_window
ON canonical_price_selection(security_id, purpose, start_date, end_date, selected_at);

CREATE TABLE IF NOT EXISTS price_validation_results (
    validation_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    start_date TEXT NOT NULL,
    end_date TEXT NOT NULL,
    source_a TEXT NOT NULL,
    source_b TEXT NOT NULL,
    overlap_rows INTEGER NOT NULL,
    median_abs_pct_diff REAL,
    max_abs_pct_diff REAL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS split_events_source (
    event_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    source TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    execution_date TEXT NOT NULL,
    split_from REAL NOT NULL,
    split_to REAL NOT NULL,
    retrieved_at TEXT NOT NULL,
    quality_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_split_events_source
ON split_events_source(security_id, source, execution_date);

CREATE TABLE IF NOT EXISTS dividend_events_source (
    event_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    source TEXT NOT NULL,
    source_symbol TEXT NOT NULL,
    ex_date TEXT NOT NULL,
    cash_amount REAL NOT NULL,
    currency TEXT,
    declaration_date TEXT,
    record_date TEXT,
    pay_date TEXT,
    retrieved_at TEXT NOT NULL,
    quality_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_dividend_events_source
ON dividend_events_source(security_id, source, ex_date);
