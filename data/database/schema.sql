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
