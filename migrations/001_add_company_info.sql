-- Migration: Add company description and website fields
-- Date: 2025-10-06

ALTER TABLE companies
ADD COLUMN IF NOT EXISTS description TEXT,
ADD COLUMN IF NOT EXISTS description_source VARCHAR(500),
ADD COLUMN IF NOT EXISTS description_license VARCHAR(50) DEFAULT 'CC BY-SA 3.0',
ADD COLUMN IF NOT EXISTS website VARCHAR(500),
ADD COLUMN IF NOT EXISTS info_updated_at TIMESTAMP;

-- Index for quick lookups
CREATE INDEX IF NOT EXISTS idx_companies_info_updated ON companies(info_updated_at);

COMMENT ON COLUMN companies.description IS 'First paragraph from Wikipedia article';
COMMENT ON COLUMN companies.description_source IS 'Wikipedia article URL';
COMMENT ON COLUMN companies.description_license IS 'License for description (CC BY-SA 3.0)';
COMMENT ON COLUMN companies.website IS 'Official company website from SEC filings';
COMMENT ON COLUMN companies.info_updated_at IS 'Last time description/website was updated';
