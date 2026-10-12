-- Supabase Database Schema for Digital Risk Protection (Sentinel)
-- Migrated from Django to PostgreSQL (Supabase)

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================
-- Table: brands
-- ============================================================
-- Brand model:
-- - id: BigAutoField PK
-- - brand_name: CharField(max_length=100), unique case-insensitive
-- - official_accounts: TextField()
-- - official_urls: TextField(blank=True, default="")
-- - created_at: DateTimeField(auto_now_add=True)
-- ============================================================
CREATE TABLE IF NOT EXISTS brands (
  id BIGSERIAL PRIMARY KEY,
  brand_name VARCHAR(100) NOT NULL,
  official_accounts TEXT NOT NULL DEFAULT '',
  official_urls TEXT NOT NULL DEFAULT '',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  CONSTRAINT unique_brand_name_case_insensitive UNIQUE (LOWER(brand_name))
);

-- Index for case-insensitive searches
CREATE INDEX IF NOT EXISTS idx_brands_lower_name ON brands (LOWER(brand_name));

-- ============================================================
-- Table: official_apps
-- ============================================================
-- OfficialAppAsset model:
-- - id: BigAutoField PK
-- - brand: ForeignKey(Brand, on_delete=CASCADE, related_name="official_apps")
-- - app_name: CharField(max_length=120)
-- - publisher: CharField(max_length=120, blank=True)
-- - package_id: CharField(max_length=180, blank=True)
-- - listing_url: URLField(max_length=500, blank=True)
-- - created_at: DateTimeField(auto_now_add=True)
-- ============================================================
CREATE TABLE IF NOT EXISTS official_apps (
  id BIGSERIAL PRIMARY KEY,
  brand_id BIGINT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  app_name VARCHAR(120) NOT NULL,
  publisher VARCHAR(120) DEFAULT '',
  package_id VARCHAR(180) DEFAULT '',
  listing_url VARCHAR(500) DEFAULT '',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Index for brand lookups
CREATE INDEX IF NOT EXISTS idx_official_apps_brand_id ON official_apps (brand_id);
CREATE INDEX IF NOT EXISTS idx_official_apps_package_id ON official_apps (package_id);

-- ============================================================
-- Table: monitoring_results
-- ============================================================
-- MonitoringResult model:
-- - id: BigAutoField PK
-- - brand: ForeignKey(Brand, on_delete=CASCADE, related_name="monitoring_results")
-- - asset_type: CharField(max_length=8, choices=[social, app], default=social)
-- - candidate_username: CharField(max_length=30)
-- - candidate_display_name: CharField(max_length=160, blank=True, default="")
-- - candidate_description: TextField(blank=True, default="")
-- - publisher: CharField(max_length=160, blank=True, default="")
-- - package_id: CharField(max_length=180, blank=True, default="")
-- - listing_url: URLField(max_length=500, blank=True, default="")
-- - source: CharField(max_length=80, default="manual", blank=True)
-- - similarity_score: PositiveSmallIntegerField(null=True, blank=True)
-- - risk_score: PositiveSmallIntegerField(null=True, blank=True)
-- - confidence_score: PositiveSmallIntegerField(null=True, blank=True)
-- - detected_signals: JSONField(blank=True, default=list)
-- - evidence: JSONField(blank=True, default=list)
-- - risk_status: CharField(max_length=12, choices=[official, high, possible, low])
-- - review_status: CharField(max_length=12, choices=[pending, under_review, reviewed], default=pending)
-- - explanation: CharField(max_length=255)
-- - created_at: DateTimeField(auto_now_add=True)
-- ============================================================
CREATE TABLE IF NOT EXISTS monitoring_results (
  id BIGSERIAL PRIMARY KEY,
  brand_id BIGINT NOT NULL REFERENCES brands(id) ON DELETE CASCADE,
  asset_type VARCHAR(8) NOT NULL DEFAULT 'social',
  candidate_username VARCHAR(30) NOT NULL,
  candidate_display_name VARCHAR(160) DEFAULT '',
  candidate_description TEXT DEFAULT '',
  publisher VARCHAR(160) DEFAULT '',
  package_id VARCHAR(180) DEFAULT '',
  listing_url VARCHAR(500) DEFAULT '',
  source VARCHAR(80) DEFAULT 'manual',
  similarity_score SMALLINT,
  risk_score SMALLINT,
  confidence_score SMALLINT,
  detected_signals JSONB DEFAULT '[]'::jsonb,
  evidence JSONB DEFAULT '[]'::jsonb,
  risk_status VARCHAR(12) NOT NULL DEFAULT 'low',
  review_status VARCHAR(12) NOT NULL DEFAULT 'pending',
  explanation VARCHAR(255) DEFAULT '',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Check constraints for asset_type
ALTER TABLE monitoring_results ADD CONSTRAINT chk_asset_type CHECK (asset_type IN ('social', 'app'));

-- Check constraints for risk_status
ALTER TABLE monitoring_results ADD CONSTRAINT chk_risk_status CHECK (risk_status IN ('official', 'high', 'possible', 'low'));

-- Check constraints for review_status
ALTER TABLE monitoring_results ADD CONSTRAINT chk_review_status CHECK (review_status IN ('pending', 'under_review', 'reviewed'));

-- Index for brand lookups
CREATE INDEX IF NOT EXISTS idx_monitoring_results_brand_id ON monitoring_results (brand_id);
CREATE INDEX IF NOT EXISTS idx_monitoring_results_risk_status ON monitoring_results (risk_status);
CREATE INDEX IF NOT EXISTS idx_monitoring_results_review_status ON monitoring_results (review_status);
CREATE INDEX IF NOT EXISTS idx_monitoring_results_created_at ON monitoring_results (created_at DESC);

-- ============================================================
-- View: recent_results (for dashboard overview)
-- ============================================================
CREATE OR REPLACE VIEW recent_results AS
SELECT mr.*, b.brand_name
FROM monitoring_results mr
JOIN brands b ON mr.brand_id = b.id
ORDER BY mr.created_at DESC
LIMIT 6;

-- ============================================================
-- View: brand_stats (for dashboard statistics)
-- ============================================================
CREATE OR REPLACE VIEW brand_stats AS
SELECT 
  b.id,
  b.brand_name,
  b.official_accounts,
  b.official_urls,
  b.created_at,
  COALESCE(mr.result_count, 0) AS checks_saved
FROM brands b
LEFT JOIN (
  SELECT brand_id, COUNT(*) AS result_count
  FROM monitoring_results
  GROUP BY brand_id
) mr ON b.id = mr.brand_id;

-- ============================================================
-- Row-level security (optional - enable based on your auth needs)
-- ==========================================================--
-- Uncomment and configure if using Supabase auth:
--
-- ALTER TABLE brands ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow public read access" ON brands FOR ALL USING (true);
-- ALTER TABLE official_apps ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow public read access" ON official_apps FOR ALL USING (true);
-- ALTER TABLE monitoring_results ENABLE ROW LEVEL SECURITY;
-- CREATE POLICY "Allow public read access" ON monitoring_results FOR ALL USING (true);