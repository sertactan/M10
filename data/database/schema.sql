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
    listing_key TEXT,
    country TEXT,
    country_code TEXT,
    isin TEXT,
    asset_type TEXT,
    aliases TEXT,
    source_scope TEXT NOT NULL DEFAULT 'CANONICAL',
    redistribution_status TEXT,
    source_priority INTEGER NOT NULL DEFAULT 99,
    first_seen TEXT,
    last_seen TEXT
);
CREATE INDEX IF NOT EXISTS idx_security_ticker ON security_master(ticker);
CREATE INDEX IF NOT EXISTS idx_security_exchange ON security_master(exchange);
CREATE INDEX IF NOT EXISTS idx_security_market ON security_master(market);
CREATE INDEX IF NOT EXISTS idx_security_country_code ON security_master(country_code);
CREATE INDEX IF NOT EXISTS idx_security_isin ON security_master(isin);
CREATE INDEX IF NOT EXISTS idx_security_listing_key ON security_master(listing_key);

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


-- Phase 3: provider-isolated fundamental data.
CREATE TABLE IF NOT EXISTS filing_records_source (
    filing_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    source TEXT NOT NULL,
    cik TEXT,
    form_type TEXT NOT NULL,
    period_end TEXT,
    filing_date TEXT NOT NULL,
    accepted_at TEXT,
    accession_number TEXT,
    source_document TEXT,
    primary_document TEXT,
    is_amendment INTEGER NOT NULL DEFAULT 0,
    retrieved_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_filing_records_pit
ON filing_records_source(security_id, source, accepted_at, filing_date);

CREATE TABLE IF NOT EXISTS fundamental_facts_source (
    fact_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    metric_name TEXT NOT NULL,
    provider_metric_name TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT NOT NULL,
    period_kind TEXT NOT NULL,
    filing_date TEXT,
    accepted_at TEXT,
    available_at TEXT NOT NULL,
    source TEXT NOT NULL,
    source_document TEXT NOT NULL,
    accession_number TEXT,
    retrieved_at TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    validation_status TEXT NOT NULL,
    family TEXT NOT NULL,
    form_type TEXT,
    fiscal_year INTEGER,
    fiscal_period TEXT,
    taxonomy TEXT,
    frame TEXT,
    statement_type TEXT,
    is_amendment INTEGER NOT NULL DEFAULT 0,
    raw_payload_hash TEXT
);
CREATE INDEX IF NOT EXISTS idx_fundamental_facts_pit
ON fundamental_facts_source(
    security_id, metric_name, period_end, period_kind, available_at, source
);
CREATE INDEX IF NOT EXISTS idx_fundamental_accession
ON fundamental_facts_source(security_id, accession_number, source);

CREATE TABLE IF NOT EXISTS fundamental_estimates_source (
    estimate_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    metric_name TEXT NOT NULL,
    period_end TEXT NOT NULL,
    value REAL NOT NULL,
    unit TEXT,
    low REAL,
    high REAL,
    analyst_count INTEGER,
    source TEXT NOT NULL,
    source_document TEXT NOT NULL,
    available_at TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    validation_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_estimates_pit
ON fundamental_estimates_source(security_id, metric_name, period_end, available_at, source);

CREATE TABLE IF NOT EXISTS company_kpi_guidance_source (
    record_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    metric_name TEXT NOT NULL,
    period_end TEXT,
    value REAL,
    value_low REAL,
    value_high REAL,
    unit TEXT,
    text_value TEXT,
    source TEXT NOT NULL,
    source_document TEXT NOT NULL,
    accession_number TEXT,
    available_at TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    validation_status TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_company_kpi_guidance_pit
ON company_kpi_guidance_source(security_id, metric_name, period_end, available_at, source);

CREATE TABLE IF NOT EXISTS fundamental_validation_results (
    validation_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    metric_name TEXT NOT NULL,
    period_end TEXT NOT NULL,
    period_kind TEXT NOT NULL,
    unit TEXT NOT NULL,
    sec_fact_id TEXT NOT NULL REFERENCES fundamental_facts_source(fact_id),
    secondary_fact_id TEXT NOT NULL REFERENCES fundamental_facts_source(fact_id),
    secondary_source TEXT NOT NULL,
    relative_difference REAL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fundamental_validation
ON fundamental_validation_results(security_id, metric_name, period_end, secondary_source, created_at);

CREATE TABLE IF NOT EXISTS fundamental_sync_runs (
    sync_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    ticker TEXT NOT NULL,
    provider_mode TEXT NOT NULL,
    filings_loaded INTEGER NOT NULL DEFAULT 0,
    facts_loaded INTEGER NOT NULL DEFAULT 0,
    estimates_loaded INTEGER NOT NULL DEFAULT 0,
    kpis_loaded INTEGER NOT NULL DEFAULT 0,
    validations_run INTEGER NOT NULL DEFAULT 0,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    message TEXT
);


-- Phase 4: canonical model-feature materialization.
CREATE TABLE IF NOT EXISTS canonical_model_features (
    feature_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    feature_key TEXT NOT NULL,
    value REAL,
    feature_as_of TEXT NOT NULL,
    available_at TEXT NOT NULL,
    source_phase TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    computation_version TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_canonical_model_features_pit
ON canonical_model_features(security_id,feature_key,feature_as_of,available_at);
CREATE INDEX IF NOT EXISTS idx_canonical_model_features_source
ON canonical_model_features(source_phase,source_ref);


-- Phase 6: canonical historical backtest labels/evaluation.
-- Feature/model scoring remains physically/logically separate from future outcome labels.
CREATE TABLE IF NOT EXISTS forward_outcomes (
    observation_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    as_of_date_requested TEXT NOT NULL,
    anchor_session TEXT,
    anchor_lag_calendar_days INTEGER,
    entry_adjusted_close REAL,
    horizon_sessions_available INTEGER NOT NULL,
    fm252 REAL,
    max_multiple_observed REAL,
    outcome_class TEXT,
    time_to_2x_sessions INTEGER,
    time_to_3x_sessions INTEGER,
    time_to_5x_sessions INTEGER,
    time_to_7x_sessions INTEGER,
    time_to_10x_sessions INTEGER,
    outcome_status TEXT NOT NULL,
    diagnostics_json TEXT NOT NULL DEFAULT '{}',
    outcome_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forward_outcomes_security_date
ON forward_outcomes(security_id,as_of_date_requested,outcome_status);

CREATE TABLE IF NOT EXISTS backtest_predictions (
    observation_id TEXT NOT NULL,
    model_version TEXT NOT NULL,
    score REAL,
    precision_confirmed INTEGER,
    status TEXT NOT NULL,
    score_hash TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(observation_id,model_version)
);

CREATE TABLE IF NOT EXISTS backtest_run_manifest (
    run_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    s15_spec_version TEXT NOT NULL,
    backtest_spec_version TEXT NOT NULL,
    feature_version TEXT,
    match_version TEXT,
    universe_version TEXT,
    price_data_version TEXT,
    fundamental_data_version TEXT,
    winner_count INTEGER,
    control_count INTEGER,
    censored_count INTEGER,
    match_quality_distribution TEXT,
    date_min TEXT,
    date_max TEXT,
    git_commit TEXT,
    random_seed INTEGER NOT NULL DEFAULT 0,
    dataset_hash TEXT,
    status TEXT NOT NULL
);


-- Phase 8: validated forecast calibration profiles.
-- Probability calibration is allowed only from unbiased market-prevalence /
-- walk-forward backtest evidence. This table stores validated upstream outputs;
-- it does not define or fit a probability formula.
CREATE TABLE IF NOT EXISTS forecast_calibration_profiles (
    calibration_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES backtest_run_manifest(run_id),
    model_version TEXT NOT NULL,
    horizon_months INTEGER NOT NULL,
    dataset_kind TEXT NOT NULL,
    calibration_method TEXT NOT NULL,
    calibration_cutoff TEXT NOT NULL,
    sample_size INTEGER NOT NULL,
    bull_return_pct REAL NOT NULL,
    base_return_pct REAL NOT NULL,
    bear_return_pct REAL NOT NULL,
    probability_positive_return_pct REAL NOT NULL,
    probability_2x_plus_pct REAL NOT NULL,
    probability_5x_plus_pct REAL NOT NULL,
    probability_10x_plus_pct REAL NOT NULL,
    confidence_pct REAL NOT NULL,
    risk TEXT NOT NULL,
    evidence_json TEXT NOT NULL DEFAULT '{}',
    evidence_hash TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forecast_calibration_lookup
ON forecast_calibration_profiles(
    model_version,horizon_months,dataset_kind,calibration_cutoff,status
);

-- Phase 8: reproducible forward forecast run records.
CREATE TABLE IF NOT EXISTS forecast_runs (
    analysis_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    ticker TEXT NOT NULL,
    analysis_date TEXT NOT NULL,
    horizon_months INTEGER NOT NULL,
    v12_model_version TEXT NOT NULL,
    v14_model_version TEXT NOT NULL,
    v12_score REAL,
    v14_score REAL,
    v12_route TEXT,
    v14_route TEXT,
    v12_destination TEXT,
    v14_destination TEXT,
    calibration_id TEXT NOT NULL REFERENCES forecast_calibration_profiles(calibration_id),
    calibration_cutoff TEXT NOT NULL,
    calibration_sample_size INTEGER NOT NULL,
    calibration_evidence_hash TEXT NOT NULL,
    data_snapshot_hash TEXT NOT NULL,
    model_config_hash TEXT NOT NULL,
    forecast_payload_json TEXT NOT NULL,
    forecast_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_forecast_runs_security_date
ON forecast_runs(security_id,analysis_date);


-- Data Fabric V2 Phase 1: persistent provider health and circuit breaker.
CREATE TABLE IF NOT EXISTS provider_health_state (
    provider TEXT PRIMARY KEY,
    circuit_state TEXT NOT NULL DEFAULT 'CLOSED',
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    cooldown_seconds INTEGER NOT NULL DEFAULT 60,
    opened_at TEXT,
    last_attempt_at TEXT,
    last_success_at TEXT,
    availability_score REAL NOT NULL DEFAULT 100.0,
    freshness_score REAL NOT NULL DEFAULT 100.0,
    data_quality_score REAL NOT NULL DEFAULT 80.0,
    latency_score REAL NOT NULL DEFAULT 100.0,
    rate_limit_score REAL NOT NULL DEFAULT 100.0,
    health_score REAL NOT NULL DEFAULT 100.0,
    last_message TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS provider_health_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    latency_ms REAL,
    rate_limited INTEGER NOT NULL DEFAULT 0,
    message TEXT
);
CREATE INDEX IF NOT EXISTS idx_provider_health_events_provider
ON provider_health_events(provider,event_id);


-- Data Fabric V2 Phase 3: persistent background sync queue.
CREATE TABLE IF NOT EXISTS background_sync_tasks (
    task_id TEXT PRIMARY KEY,
    task_type TEXT NOT NULL,
    dedupe_key TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    priority INTEGER NOT NULL DEFAULT 100,
    status TEXT NOT NULL DEFAULT 'PENDING',
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    run_after TEXT NOT NULL,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    started_at TEXT,
    completed_at TEXT,
    UNIQUE(task_type,dedupe_key)
);
CREATE INDEX IF NOT EXISTS idx_background_sync_ready
ON background_sync_tasks(status,run_after,priority,created_at);


-- S16 Phase 3: point-in-time historical evidence archives.
CREATE TABLE IF NOT EXISTS s16_short_interest_source (
    record_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    ticker TEXT NOT NULL,
    settlement_date TEXT NOT NULL,
    short_interest REAL NOT NULL,
    avg_daily_volume REAL,
    float_shares REAL,
    days_to_cover REAL,
    available_at TEXT NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_s16_short_interest_pit
ON s16_short_interest_source(security_id,available_at,settlement_date,source);

CREATE TABLE IF NOT EXISTS s16_attention_source (
    record_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    ticker TEXT NOT NULL,
    channel TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    available_at TEXT NOT NULL,
    mentions REAL NOT NULL,
    unique_authors REAL,
    sentiment REAL,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_s16_attention_pit
ON s16_attention_source(security_id,channel,observed_at,available_at,source);

CREATE TABLE IF NOT EXISTS s16_feature_evidence_source (
    record_id TEXT PRIMARY KEY,
    security_id TEXT NOT NULL REFERENCES security_master(security_id),
    ticker TEXT NOT NULL,
    feature_key TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    available_at TEXT NOT NULL,
    value REAL NOT NULL,
    source TEXT NOT NULL,
    source_ref TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_s16_feature_evidence_pit
ON s16_feature_evidence_source(security_id,feature_key,observed_at,available_at,source);
