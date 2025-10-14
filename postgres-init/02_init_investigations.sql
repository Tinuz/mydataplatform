-- ============================================================================
-- Investigation Management Schema
-- ============================================================================
-- Purpose: Track strafrechtelijke onderzoeken with strict data isolation
-- Created: 13 oktober 2025
-- ============================================================================

-- Database creation (if needed)
CREATE DATABASE IF NOT EXISTS investigations;

-- Connect to investigations database
\c investigations;

-- ============================================================================
-- Table: investigations
-- ============================================================================
-- Stores metadata about each strafrechtelijk onderzoek
CREATE TABLE IF NOT EXISTS investigations (
    investigation_id VARCHAR(20) PRIMARY KEY,  -- Format: OND-2025-001234
    name VARCHAR(255) NOT NULL,
    description TEXT,
    start_date DATE NOT NULL,
    end_date DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active' 
        CHECK (status IN ('active', 'archived', 'closed')),
    lead_investigator VARCHAR(100),
    team_members TEXT[],  -- Array of team member names
    retention_until DATE,  -- Data retention policy
    metadata JSONB DEFAULT '{}',  -- Flexible additional data
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_by VARCHAR(100),
    updated_by VARCHAR(100)
);

-- Indexes for investigations
CREATE INDEX IF NOT EXISTS idx_inv_status ON investigations(status);
CREATE INDEX IF NOT EXISTS idx_inv_start_date ON investigations(start_date);
CREATE INDEX IF NOT EXISTS idx_inv_lead ON investigations(lead_investigator);
CREATE INDEX IF NOT EXISTS idx_inv_retention ON investigations(retention_until);

-- ============================================================================
-- Table: data_sources
-- ============================================================================
-- Tracks all uploaded files and their processing status
CREATE TABLE IF NOT EXISTS data_sources (
    source_id VARCHAR(30) PRIMARY KEY,  -- Format: SRC-2025-001234-001
    investigation_id VARCHAR(20) NOT NULL REFERENCES investigations(investigation_id) ON DELETE CASCADE,
    source_type VARCHAR(50) NOT NULL,  -- bank, telecom, forensic_image, social_media
    provider VARCHAR(100),             -- ING Bank, KPN, NFI, etc.
    file_name VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,           -- S3/MinIO path
    file_size_bytes BIGINT,
    file_hash VARCHAR(64),             -- SHA256 for integrity
    received_date DATE NOT NULL,
    uploaded_by VARCHAR(100),
    processing_status VARCHAR(20) DEFAULT 'pending' 
        CHECK (processing_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')),
    processing_started_at TIMESTAMP,
    processing_completed_at TIMESTAMP,
    processor_pipeline VARCHAR(100),   -- Name of Dagster pipeline
    error_message TEXT,                -- If processing failed
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for data_sources
CREATE INDEX IF NOT EXISTS idx_source_inv ON data_sources(investigation_id);
CREATE INDEX IF NOT EXISTS idx_source_status ON data_sources(processing_status);
CREATE INDEX IF NOT EXISTS idx_source_type ON data_sources(source_type);
CREATE INDEX IF NOT EXISTS idx_source_provider ON data_sources(provider);
CREATE INDEX IF NOT EXISTS idx_source_received ON data_sources(received_date);

-- ============================================================================
-- Table: processed_records
-- ============================================================================
-- Index/search layer for processed data (full data in Parquet)
CREATE TABLE IF NOT EXISTS processed_records (
    record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id VARCHAR(20) NOT NULL REFERENCES investigations(investigation_id) ON DELETE CASCADE,
    source_id VARCHAR(30) NOT NULL REFERENCES data_sources(source_id) ON DELETE CASCADE,
    record_type VARCHAR(50) NOT NULL,  -- transaction, call_record, message, file_metadata
    record_date DATE,                  -- Transaction/call/event date
    parquet_path TEXT NOT NULL,        -- Path to full record in Parquet
    summary JSONB DEFAULT '{}',        -- Key fields for quick search
    indexed_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for processed_records
CREATE INDEX IF NOT EXISTS idx_record_inv ON processed_records(investigation_id);
CREATE INDEX IF NOT EXISTS idx_record_source ON processed_records(source_id);
CREATE INDEX IF NOT EXISTS idx_record_type ON processed_records(record_type);
CREATE INDEX IF NOT EXISTS idx_record_date ON processed_records(record_date);
CREATE INDEX IF NOT EXISTS idx_record_summary ON processed_records USING GIN(summary);  -- JSONB search

-- ============================================================================
-- Table: audit_log
-- ============================================================================
-- Complete audit trail for compliance and security
CREATE TABLE IF NOT EXISTS audit_log (
    log_id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    action VARCHAR(50) NOT NULL,  -- upload, view, download, delete, update, query
    investigation_id VARCHAR(20),
    resource_type VARCHAR(50),    -- investigation, file, record, query
    resource_id TEXT,
    ip_address INET,
    user_agent TEXT,
    request_path TEXT,
    status_code INTEGER,
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    timestamp TIMESTAMP DEFAULT NOW()
);

-- Indexes for audit_log
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_inv ON audit_log(investigation_id);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_log(resource_type, resource_id);

-- ============================================================================
-- Table: user_permissions
-- ============================================================================
-- Role-based access control per investigation
CREATE TABLE IF NOT EXISTS user_permissions (
    permission_id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    investigation_id VARCHAR(20) NOT NULL REFERENCES investigations(investigation_id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL CHECK (role IN ('lead', 'member', 'analyst', 'auditor', 'viewer')),
    granted_by VARCHAR(100),
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    UNIQUE(user_id, investigation_id)
);

-- Indexes for user_permissions
CREATE INDEX IF NOT EXISTS idx_perm_user ON user_permissions(user_id);
CREATE INDEX IF NOT EXISTS idx_perm_inv ON user_permissions(investigation_id);
CREATE INDEX IF NOT EXISTS idx_perm_role ON user_permissions(role);

-- ============================================================================
-- Views for convenience
-- ============================================================================

-- View: Investigation summary with file counts
CREATE OR REPLACE VIEW investigation_summary AS
SELECT 
    i.investigation_id,
    i.name,
    i.status,
    i.start_date,
    i.lead_investigator,
    COUNT(DISTINCT ds.source_id) as total_files,
    COUNT(DISTINCT ds.source_id) FILTER (WHERE ds.processing_status = 'completed') as processed_files,
    COUNT(DISTINCT ds.source_id) FILTER (WHERE ds.processing_status = 'failed') as failed_files,
    COUNT(DISTINCT pr.record_id) as total_records,
    SUM(ds.file_size_bytes) as total_storage_bytes,
    MAX(ds.received_date) as last_file_received,
    i.created_at,
    i.updated_at
FROM investigations i
LEFT JOIN data_sources ds ON i.investigation_id = ds.investigation_id
LEFT JOIN processed_records pr ON i.investigation_id = pr.investigation_id
GROUP BY i.investigation_id, i.name, i.status, i.start_date, i.lead_investigator, i.created_at, i.updated_at;

-- View: Processing status overview
CREATE OR REPLACE VIEW processing_status_overview AS
SELECT 
    ds.investigation_id,
    ds.source_type,
    ds.processing_status,
    COUNT(*) as count,
    SUM(ds.file_size_bytes) as total_bytes,
    AVG(EXTRACT(EPOCH FROM (ds.processing_completed_at - ds.processing_started_at))) as avg_processing_seconds
FROM data_sources ds
GROUP BY ds.investigation_id, ds.source_type, ds.processing_status;

-- ============================================================================
-- Functions
-- ============================================================================

-- Function: Generate next investigation_id
CREATE OR REPLACE FUNCTION generate_investigation_id(year INTEGER)
RETURNS VARCHAR(20) AS $$
DECLARE
    next_number INTEGER;
    new_id VARCHAR(20);
BEGIN
    -- Find highest number for given year
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(investigation_id FROM 10 FOR 6) AS INTEGER)
    ), 0) + 1
    INTO next_number
    FROM investigations
    WHERE investigation_id LIKE 'OND-' || year || '-%';
    
    -- Format: OND-2025-001234
    new_id := 'OND-' || year || '-' || LPAD(next_number::TEXT, 6, '0');
    
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Generate next source_id for investigation
CREATE OR REPLACE FUNCTION generate_source_id(inv_id VARCHAR(20))
RETURNS VARCHAR(30) AS $$
DECLARE
    next_number INTEGER;
    new_id VARCHAR(30);
BEGIN
    -- Find highest source number for investigation
    SELECT COALESCE(MAX(
        CAST(SUBSTRING(source_id FROM 21) AS INTEGER)
    ), 0) + 1
    INTO next_number
    FROM data_sources
    WHERE investigation_id = inv_id;
    
    -- Format: SRC-2025-001234-001
    new_id := 'SRC-' || SUBSTRING(inv_id FROM 5) || '-' || LPAD(next_number::TEXT, 3, '0');
    
    RETURN new_id;
END;
$$ LANGUAGE plpgsql;

-- Function: Auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for auto-updating updated_at
CREATE TRIGGER update_investigations_updated_at
    BEFORE UPDATE ON investigations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_data_sources_updated_at
    BEFORE UPDATE ON data_sources
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- Seed Data (for testing)
-- ============================================================================

-- Insert example investigation
INSERT INTO investigations (investigation_id, name, description, start_date, status, lead_investigator)
VALUES (
    'OND-2025-000001',
    'Operatie Voorbeeld',
    'Test onderzoek voor platform development',
    '2025-01-15',
    'active',
    'J. van der Berg'
) ON CONFLICT (investigation_id) DO NOTHING;

-- Grant permissions to test user
INSERT INTO user_permissions (user_id, investigation_id, role, granted_by)
VALUES (
    'test_user',
    'OND-2025-000001',
    'lead',
    'system'
) ON CONFLICT (user_id, investigation_id) DO NOTHING;

-- ============================================================================
-- Grants (adjust based on your user setup)
-- ============================================================================

-- Grant permissions to superset user (if exists)
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = 'superset') THEN
        GRANT SELECT ON ALL TABLES IN SCHEMA public TO superset;
        GRANT SELECT ON investigation_summary TO superset;
        GRANT SELECT ON processing_status_overview TO superset;
    END IF;
END
$$;

-- ============================================================================
-- Comments for documentation
-- ============================================================================

COMMENT ON TABLE investigations IS 'Strafrechtelijke onderzoeken met metadata en status';
COMMENT ON TABLE data_sources IS 'Uploaded bestanden per onderzoek met processing status';
COMMENT ON TABLE processed_records IS 'Index laag voor snelle search over verwerkte data';
COMMENT ON TABLE audit_log IS 'Complete audit trail voor compliance';
COMMENT ON TABLE user_permissions IS 'Role-based access control per onderzoek';

COMMENT ON COLUMN investigations.investigation_id IS 'Uniek onderzoek ID (format: OND-YYYY-NNNNNN)';
COMMENT ON COLUMN investigations.retention_until IS 'Data wordt verwijderd na deze datum';
COMMENT ON COLUMN data_sources.file_hash IS 'SHA256 hash voor file integrity check';
COMMENT ON COLUMN data_sources.processor_pipeline IS 'Naam van Dagster pipeline die file verwerkt';
COMMENT ON COLUMN processed_records.summary IS 'JSONB met key fields voor quick search';
COMMENT ON COLUMN processed_records.parquet_path IS 'MinIO path naar complete record in Parquet format';

-- ============================================================================
-- Success message
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Investigation Management Schema created successfully!';
    RAISE NOTICE '📊 Tables: investigations, data_sources, processed_records, audit_log, user_permissions';
    RAISE NOTICE '👁️  Views: investigation_summary, processing_status_overview';
    RAISE NOTICE '🔧 Functions: generate_investigation_id(), generate_source_id()';
END
$$;
