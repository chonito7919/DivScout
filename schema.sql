-- DivScout Database Schema
-- PostgreSQL 12+
--
-- This schema defines the database structure for storing dividend data
-- extracted from SEC EDGAR XBRL filings with confidence scoring and
-- data quality tracking.

-- ============================================================================
-- Companies Table
-- Stores master company information
-- ============================================================================
CREATE TABLE IF NOT EXISTS companies (
    company_id SERIAL PRIMARY KEY,
    ticker VARCHAR(10) NOT NULL UNIQUE,
    company_name VARCHAR(255),
    cik VARCHAR(10) UNIQUE,
    sector VARCHAR(100),
    industry VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_companies_ticker ON companies(ticker);
CREATE INDEX idx_companies_cik ON companies(cik);
CREATE INDEX idx_companies_active ON companies(is_active);

-- ============================================================================
-- Dividend Events Table
-- Stores individual dividend records with confidence scoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS dividend_events (
    dividend_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,

    -- Dividend dates
    declaration_date DATE,
    ex_dividend_date DATE NOT NULL,
    record_date DATE,
    payment_date DATE,

    -- Dividend details
    amount NUMERIC(10, 4) NOT NULL,
    frequency VARCHAR(20),  -- 'quarterly', 'monthly', 'annual', etc.
    dividend_type VARCHAR(20) DEFAULT 'cash',  -- 'cash', 'stock', 'special'

    -- Fiscal period information
    fiscal_year INTEGER,
    fiscal_quarter INTEGER,  -- 1, 2, 3, 4

    -- Data quality and confidence scoring
    confidence NUMERIC(3, 3) DEFAULT 1.0,  -- 0.0 to 1.0
    needs_review BOOLEAN DEFAULT false,
    confidence_reasons TEXT,  -- Comma-separated reasons for confidence reduction

    -- XBRL metadata
    period_type VARCHAR(20),  -- 'instant', 'quarterly', 'semi_annual', 'annual'
    period_days INTEGER,

    -- Review workflow
    review_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'approved', 'deleted', 'reviewed'
    review_notes TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP,

    -- Audit trail
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Ensure uniqueness: one dividend per company per ex-dividend date
    CONSTRAINT unique_dividend_per_date UNIQUE (company_id, ex_dividend_date)
);

CREATE INDEX idx_dividend_company ON dividend_events(company_id);
CREATE INDEX idx_dividend_ex_date ON dividend_events(ex_dividend_date);
CREATE INDEX idx_dividend_confidence ON dividend_events(confidence);
CREATE INDEX idx_dividend_needs_review ON dividend_events(needs_review);
CREATE INDEX idx_dividend_review_status ON dividend_events(review_status);
CREATE INDEX idx_dividend_fiscal_year ON dividend_events(fiscal_year);

-- ============================================================================
-- Data Collection Log
-- Tracks all scraping attempts for auditing and monitoring
-- ============================================================================
CREATE TABLE IF NOT EXISTS data_collection_log (
    log_id SERIAL PRIMARY KEY,
    company_id INTEGER REFERENCES companies(company_id) ON DELETE SET NULL,
    ticker VARCHAR(10),
    data_type VARCHAR(20),  -- 'xbrl', '8-K', '10-K', etc.
    status VARCHAR(20),  -- 'success', 'failed', 'not_available', 'error'
    source_url TEXT,
    error_message TEXT,
    records_inserted INTEGER DEFAULT 0,
    processing_time_seconds INTEGER,
    period_start DATE,
    period_end DATE,
    collection_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_collection_company ON data_collection_log(company_id);
CREATE INDEX idx_collection_ticker ON data_collection_log(ticker);
CREATE INDEX idx_collection_status ON data_collection_log(status);
CREATE INDEX idx_collection_date ON data_collection_log(collection_date);

-- ============================================================================
-- Data Sources
-- Tracks the source of each piece of data for audit trail
-- ============================================================================
CREATE TABLE IF NOT EXISTS data_sources (
    source_id SERIAL PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(company_id) ON DELETE CASCADE,
    source_type VARCHAR(50),  -- 'edgar_filing', 'xbrl_api', 'manual', etc.
    source_url TEXT,
    filing_type VARCHAR(10),  -- '8-K', '10-K', '10-Q', etc.
    filing_date DATE,
    accession_number VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_sources_company ON data_sources(company_id);
CREATE INDEX idx_sources_type ON data_sources(source_type);
CREATE INDEX idx_sources_filing_date ON data_sources(filing_date);

-- ============================================================================
-- Dividend Review Log
-- Tracks manual review actions for compliance and auditing
-- ============================================================================
CREATE TABLE IF NOT EXISTS dividend_review_log (
    review_log_id SERIAL PRIMARY KEY,
    dividend_id INTEGER NOT NULL REFERENCES dividend_events(dividend_id) ON DELETE CASCADE,
    action VARCHAR(20),  -- 'approved', 'deleted', 'reviewed', 'flagged'
    review_notes TEXT,
    reviewed_by VARCHAR(100),
    reviewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_review_dividend ON dividend_review_log(dividend_id);
CREATE INDEX idx_review_date ON dividend_review_log(reviewed_at);

-- ============================================================================
-- Materialized View: Company Dividend Statistics
-- Provides quick access to dividend statistics per company
-- Refresh periodically: REFRESH MATERIALIZED VIEW CONCURRENTLY company_dividend_stats;
-- ============================================================================
CREATE MATERIALIZED VIEW IF NOT EXISTS company_dividend_stats AS
SELECT
    c.company_id,
    c.ticker,
    c.company_name,
    COUNT(de.dividend_id) as total_dividends,
    COUNT(CASE WHEN de.needs_review THEN 1 END) as needs_review_count,
    COUNT(CASE WHEN de.confidence < 0.8 THEN 1 END) as low_confidence_count,
    MIN(de.amount) as min_amount,
    MAX(de.amount) as max_amount,
    AVG(de.amount) as avg_amount,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY de.amount) as median_amount,
    AVG(de.confidence) as avg_confidence,
    MIN(de.ex_dividend_date) as earliest_dividend,
    MAX(de.ex_dividend_date) as latest_dividend,
    COUNT(DISTINCT de.fiscal_year) as years_with_dividends
FROM companies c
LEFT JOIN dividend_events de ON c.company_id = de.company_id
WHERE de.review_status != 'deleted'
GROUP BY c.company_id, c.ticker, c.company_name;

CREATE UNIQUE INDEX idx_company_stats_id ON company_dividend_stats(company_id);
CREATE INDEX idx_company_stats_ticker ON company_dividend_stats(ticker);

-- ============================================================================
-- Trigger: Update timestamp on row modification
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_companies_updated_at BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dividend_events_updated_at BEFORE UPDATE ON dividend_events
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Comments for documentation
-- ============================================================================
COMMENT ON TABLE companies IS 'Master table of companies tracked for dividend data';
COMMENT ON TABLE dividend_events IS 'Individual dividend records with confidence scoring and quality metrics';
COMMENT ON TABLE data_collection_log IS 'Audit trail of all data collection attempts';
COMMENT ON TABLE data_sources IS 'Tracks the origin of data for provenance and verification';
COMMENT ON TABLE dividend_review_log IS 'Audit trail of manual review actions';
COMMENT ON COLUMN dividend_events.confidence IS 'Confidence score from 0.0 to 1.0 based on data quality heuristics';
COMMENT ON COLUMN dividend_events.needs_review IS 'Flag indicating dividend needs manual review (confidence < 0.8)';
COMMENT ON COLUMN dividend_events.review_status IS 'Workflow status: pending, approved, deleted, reviewed';

-- ============================================================================
-- Initial setup complete
-- ============================================================================
-- To refresh the materialized view after data changes:
-- REFRESH MATERIALIZED VIEW CONCURRENTLY company_dividend_stats;
