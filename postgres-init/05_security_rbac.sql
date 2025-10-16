-- ============================================
-- Security & IAM Implementation
-- Role-Based Access Control (RBAC)
-- ============================================
--
-- Purpose: Implement security layers for investigation data platform
-- 
-- Security Layers:
--   1. Database Users & Roles
--   2. Row-Level Security (RLS) per investigation
--   3. Column-Level Security (PII masking)
--   4. Audit Logging
--
-- Roles:
--   - platform_admin: Full access to all data and configuration
--   - data_engineer: Can create/modify tables, run ETL jobs
--   - data_analyst: Read access to canonical data (PII masked)
--   - investigator: Full access to assigned investigations only
--   - auditor: Read-only access to audit logs

-- ============================================
-- 1. CREATE DATABASE ROLES
-- ============================================

-- Platform Admin: Full superuser access
CREATE ROLE platform_admin WITH LOGIN PASSWORD 'admin_secure_pwd_2025!';
GRANT ALL PRIVILEGES ON DATABASE superset TO platform_admin;

-- Data Engineer: Can create tables, run ETL, access raw data
CREATE ROLE data_engineer WITH LOGIN PASSWORD 'engineer_secure_pwd_2025!';
GRANT CONNECT ON DATABASE superset TO data_engineer;

-- Data Analyst: Read access to canonical data, PII masked
CREATE ROLE data_analyst WITH LOGIN PASSWORD 'analyst_secure_pwd_2025!';
GRANT CONNECT ON DATABASE superset TO data_analyst;

-- Investigator: Access to specific investigations only (via RLS)
CREATE ROLE investigator WITH LOGIN PASSWORD 'investigator_secure_pwd_2025!';
GRANT CONNECT ON DATABASE superset TO investigator;

-- Auditor: Read-only access to audit logs
CREATE ROLE auditor WITH LOGIN PASSWORD 'auditor_secure_pwd_2025!';
GRANT CONNECT ON DATABASE superset TO auditor;

-- ============================================
-- 2. SCHEMA PERMISSIONS
-- ============================================

-- Grant schema usage
GRANT USAGE ON SCHEMA public TO data_engineer, data_analyst, investigator, auditor;
GRANT USAGE ON SCHEMA canonical TO data_engineer, data_analyst, investigator;

-- Data Engineer: Can create objects
GRANT CREATE ON SCHEMA public TO data_engineer;
GRANT CREATE ON SCHEMA canonical TO data_engineer;

-- ============================================
-- 3. TABLE PERMISSIONS
-- ============================================

-- Data Engineer: Full access to all tables
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO data_engineer;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA canonical TO data_engineer;

-- Data Analyst: Read-only on canonical tables
GRANT SELECT ON ALL TABLES IN SCHEMA canonical TO data_analyst;

-- Investigator: Read-only on raw and canonical (RLS will filter)
GRANT SELECT ON raw_transactions, raw_calls, raw_messages TO investigator;
GRANT SELECT ON ALL TABLES IN SCHEMA canonical TO investigator;

-- Auditor: Read-only on audit tables
GRANT SELECT ON investigations, data_sources, processed_records TO auditor;

-- Apply to future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA public 
    GRANT ALL ON TABLES TO data_engineer;

ALTER DEFAULT PRIVILEGES IN SCHEMA canonical 
    GRANT ALL ON TABLES TO data_engineer;

ALTER DEFAULT PRIVILEGES IN SCHEMA canonical 
    GRANT SELECT ON TABLES TO data_analyst, investigator;

-- ============================================
-- 4. ROW-LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on investigation-related tables
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_calls ENABLE ROW LEVEL SECURITY;
ALTER TABLE raw_messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE canonical.canonical_transaction ENABLE ROW LEVEL SECURITY;
ALTER TABLE canonical.canonical_communication ENABLE ROW LEVEL SECURITY;

-- Create user-investigation mapping table
CREATE TABLE IF NOT EXISTS user_investigation_access (
    user_id VARCHAR(100) NOT NULL,
    investigation_id VARCHAR(50) NOT NULL,
    access_level VARCHAR(20) NOT NULL DEFAULT 'read', -- read, write, admin
    granted_by VARCHAR(100),
    granted_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    PRIMARY KEY (user_id, investigation_id),
    CONSTRAINT fk_investigation FOREIGN KEY (investigation_id) 
        REFERENCES investigations(investigation_id) ON DELETE CASCADE
);

COMMENT ON TABLE user_investigation_access IS 
    'Maps users to investigations they can access. Used for RLS policies.';

-- RLS Policy: Investigators can only see their assigned investigations
CREATE POLICY investigator_access_policy ON investigations
    FOR SELECT
    TO investigator
    USING (
        investigation_id IN (
            SELECT investigation_id 
            FROM user_investigation_access 
            WHERE user_id = current_user 
              AND (expires_at IS NULL OR expires_at > NOW())
        )
    );

-- RLS Policy: Investigators can only see transactions from their investigations
CREATE POLICY investigator_transaction_policy ON raw_transactions
    FOR SELECT
    TO investigator
    USING (
        investigation_id IN (
            SELECT investigation_id 
            FROM user_investigation_access 
            WHERE user_id = current_user
              AND (expires_at IS NULL OR expires_at > NOW())
        )
    );

-- RLS Policy: Same for calls
CREATE POLICY investigator_call_policy ON raw_calls
    FOR SELECT
    TO investigator
    USING (
        investigation_id IN (
            SELECT investigation_id 
            FROM user_investigation_access 
            WHERE user_id = current_user
              AND (expires_at IS NULL OR expires_at > NOW())
        )
    );

-- RLS Policy: Same for messages
CREATE POLICY investigator_message_policy ON raw_messages
    FOR SELECT
    TO investigator
    USING (
        investigation_id IN (
            SELECT investigation_id 
            FROM user_investigation_access 
            WHERE user_id = current_user
              AND (expires_at IS NULL OR expires_at > NOW())
        )
    );

-- RLS Policy: Canonical transactions
CREATE POLICY investigator_canonical_tx_policy ON canonical.canonical_transaction
    FOR SELECT
    TO investigator
    USING (
        investigation_id IN (
            SELECT investigation_id 
            FROM user_investigation_access 
            WHERE user_id = current_user
              AND (expires_at IS NULL OR expires_at > NOW())
        )
    );

-- RLS Policy: Canonical communications
CREATE POLICY investigator_canonical_comm_policy ON canonical.canonical_communication
    FOR SELECT
    TO investigator
    USING (
        investigation_id IN (
            SELECT investigation_id 
            FROM user_investigation_access 
            WHERE user_id = current_user
              AND (expires_at IS NULL OR expires_at > NOW())
        )
    );

-- Admin and Data Engineer bypass RLS
CREATE POLICY admin_access_all ON investigations
    FOR ALL
    TO platform_admin, data_engineer
    USING (true);

CREATE POLICY admin_transaction_access ON raw_transactions
    FOR ALL
    TO platform_admin, data_engineer
    USING (true);

CREATE POLICY admin_call_access ON raw_calls
    FOR ALL
    TO platform_admin, data_engineer
    USING (true);

CREATE POLICY admin_message_access ON raw_messages
    FOR ALL
    TO platform_admin, data_engineer
    USING (true);

CREATE POLICY admin_canonical_tx_access ON canonical.canonical_transaction
    FOR ALL
    TO platform_admin, data_engineer
    USING (true);

CREATE POLICY admin_canonical_comm_access ON canonical.canonical_communication
    FOR ALL
    TO platform_admin, data_engineer
    USING (true);

-- ============================================
-- 5. COLUMN-LEVEL SECURITY (PII Masking)
-- ============================================

-- Create masked views for analysts (PII fields obscured)
CREATE OR REPLACE VIEW canonical.fact_transaction_masked AS
SELECT
    transaction_id,
    investigation_id,
    source_id,
    transaction_date,
    transaction_timestamp,
    posted_date,
    -- Mask IBANs (show only first 4 and last 4 chars)
    CASE 
        WHEN iban_from IS NOT NULL THEN 
            SUBSTRING(iban_from, 1, 4) || '****' || SUBSTRING(iban_from, LENGTH(iban_from)-3, 4)
        ELSE NULL
    END AS iban_from_masked,
    CASE 
        WHEN iban_to IS NOT NULL THEN 
            SUBSTRING(iban_to, 1, 4) || '****' || SUBSTRING(iban_to, LENGTH(iban_to)-3, 4)
        ELSE NULL
    END AS iban_to_masked,
    account_key_from,
    account_key_to,
    amount,
    currency,
    transaction_type,
    category,
    -- Redact description (show only length)
    LENGTH(description) AS description_length,
    -- Mask counter party name
    CASE 
        WHEN counter_party_name IS NOT NULL THEN '***REDACTED***'
        ELSE NULL
    END AS counter_party_name_masked,
    reference,
    is_suspicious,
    risk_score,
    tags,
    created_at,
    updated_at
FROM canonical.fact_transaction;

COMMENT ON VIEW canonical.fact_transaction_masked IS
    'Masked view of transactions for data analysts. IBANs and names are obscured.';

-- Grant access to masked view
GRANT SELECT ON canonical.fact_transaction_masked TO data_analyst;

-- Similar masked view for communications
CREATE OR REPLACE VIEW canonical.fact_call_masked AS
SELECT
    call_id,
    investigation_id,
    source_id,
    call_date,
    call_date_only,
    call_time,
    -- Mask phone numbers (show only last 4 digits)
    '****' || SUBSTRING(caller_number, LENGTH(caller_number)-3, 4) AS caller_number_masked,
    '****' || SUBSTRING(called_number, LENGTH(called_number)-3, 4) AS called_number_masked,
    caller_phone_key,
    called_phone_key,
    duration_seconds,
    duration_minutes,
    call_type,
    call_direction,
    is_suspicious,
    risk_score,
    tags,
    created_at,
    updated_at
FROM canonical.fact_call;

GRANT SELECT ON canonical.fact_call_masked TO data_analyst;

-- ============================================
-- 6. AUDIT LOGGING
-- ============================================

-- Create audit log table
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id BIGSERIAL PRIMARY KEY,
    event_timestamp TIMESTAMP DEFAULT NOW(),
    user_name VARCHAR(100),
    user_role VARCHAR(50),
    event_type VARCHAR(50), -- SELECT, INSERT, UPDATE, DELETE, LOGIN
    table_name VARCHAR(100),
    investigation_id VARCHAR(50),
    record_id VARCHAR(100),
    query_text TEXT,
    ip_address INET,
    success BOOLEAN DEFAULT true,
    error_message TEXT
);

CREATE INDEX idx_audit_log_timestamp ON audit_log(event_timestamp DESC);
CREATE INDEX idx_audit_log_user ON audit_log(user_name);
CREATE INDEX idx_audit_log_investigation ON audit_log(investigation_id);

COMMENT ON TABLE audit_log IS
    'Audit trail of all data access and modifications in the platform';

-- Grant auditor read access
GRANT SELECT ON audit_log TO auditor, platform_admin;

-- Function to log SELECT queries on sensitive tables
CREATE OR REPLACE FUNCTION log_data_access()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        user_name,
        user_role,
        event_type,
        table_name,
        investigation_id,
        record_id
    ) VALUES (
        current_user,
        current_setting('role', true),
        TG_OP,
        TG_TABLE_NAME,
        COALESCE(NEW.investigation_id, OLD.investigation_id),
        COALESCE(NEW.transaction_id::TEXT, NEW.call_id::TEXT, NEW.message_id::TEXT, 
                 OLD.transaction_id::TEXT, OLD.call_id::TEXT, OLD.message_id::TEXT)
    );
    
    IF TG_OP = 'DELETE' THEN
        RETURN OLD;
    ELSE
        RETURN NEW;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Create triggers for audit logging (INSERT, UPDATE, DELETE)
-- Note: PostgreSQL doesn't support SELECT triggers, so we log DML only

CREATE TRIGGER audit_raw_transactions
AFTER INSERT OR UPDATE OR DELETE ON raw_transactions
FOR EACH ROW EXECUTE FUNCTION log_data_access();

CREATE TRIGGER audit_raw_calls
AFTER INSERT OR UPDATE OR DELETE ON raw_calls
FOR EACH ROW EXECUTE FUNCTION log_data_access();

CREATE TRIGGER audit_raw_messages
AFTER INSERT OR UPDATE OR DELETE ON raw_messages
FOR EACH ROW EXECUTE FUNCTION log_data_access();

CREATE TRIGGER audit_canonical_transactions
AFTER INSERT OR UPDATE OR DELETE ON canonical.canonical_transaction
FOR EACH ROW EXECUTE FUNCTION log_data_access();

CREATE TRIGGER audit_canonical_communications
AFTER INSERT OR UPDATE OR DELETE ON canonical.canonical_communication
FOR EACH ROW EXECUTE FUNCTION log_data_access();

-- ============================================
-- 7. HELPER FUNCTIONS FOR IAM MANAGEMENT
-- ============================================

-- Grant investigation access to a user
CREATE OR REPLACE FUNCTION grant_investigation_access(
    p_user_id VARCHAR,
    p_investigation_id VARCHAR,
    p_access_level VARCHAR DEFAULT 'read',
    p_expires_days INTEGER DEFAULT NULL
)
RETURNS VOID AS $$
BEGIN
    INSERT INTO user_investigation_access (
        user_id,
        investigation_id,
        access_level,
        granted_by,
        expires_at
    ) VALUES (
        p_user_id,
        p_investigation_id,
        p_access_level,
        current_user,
        CASE 
            WHEN p_expires_days IS NOT NULL 
            THEN NOW() + (p_expires_days || ' days')::INTERVAL
            ELSE NULL
        END
    )
    ON CONFLICT (user_id, investigation_id) 
    DO UPDATE SET
        access_level = EXCLUDED.access_level,
        granted_by = current_user,
        granted_at = NOW(),
        expires_at = EXCLUDED.expires_at;
        
    -- Log the grant
    INSERT INTO audit_log (
        user_name,
        event_type,
        investigation_id,
        query_text
    ) VALUES (
        current_user,
        'GRANT_ACCESS',
        p_investigation_id,
        format('Granted %s access to user %s', p_access_level, p_user_id)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Revoke investigation access
CREATE OR REPLACE FUNCTION revoke_investigation_access(
    p_user_id VARCHAR,
    p_investigation_id VARCHAR
)
RETURNS VOID AS $$
BEGIN
    DELETE FROM user_investigation_access
    WHERE user_id = p_user_id
      AND investigation_id = p_investigation_id;
      
    -- Log the revocation
    INSERT INTO audit_log (
        user_name,
        event_type,
        investigation_id,
        query_text
    ) VALUES (
        current_user,
        'REVOKE_ACCESS',
        p_investigation_id,
        format('Revoked access from user %s', p_user_id)
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- View to check current user's access
CREATE OR REPLACE VIEW my_investigation_access AS
SELECT 
    i.investigation_id,
    i.title,
    i.status,
    uia.access_level,
    uia.granted_at,
    uia.expires_at,
    CASE 
        WHEN uia.expires_at IS NULL THEN true
        WHEN uia.expires_at > NOW() THEN true
        ELSE false
    END AS is_active
FROM investigations i
JOIN user_investigation_access uia ON i.investigation_id = uia.investigation_id
WHERE uia.user_id = current_user;

-- Grant access to own view
GRANT SELECT ON my_investigation_access TO investigator, data_analyst;

-- ============================================
-- 8. DEMO DATA: Create sample users and access
-- ============================================

-- Sample investigator users
-- In production, these would be LDAP/SSO users
CREATE ROLE investigator_john WITH LOGIN PASSWORD 'john_demo_2025!' IN ROLE investigator;
CREATE ROLE investigator_jane WITH LOGIN PASSWORD 'jane_demo_2025!' IN ROLE investigator;
CREATE ROLE analyst_bob WITH LOGIN PASSWORD 'bob_demo_2025!' IN ROLE data_analyst;

COMMENT ON ROLE investigator_john IS 'Demo investigator - assigned to OND-2025-000001';
COMMENT ON ROLE investigator_jane IS 'Demo investigator - assigned to OND-2025-000002';
COMMENT ON ROLE analyst_bob IS 'Demo analyst - read-only access to masked data';

-- Grant access to specific investigations (will be populated after data load)
-- Example usage:
-- SELECT grant_investigation_access('investigator_john', 'OND-2025-000001', 'read', 365);
-- SELECT grant_investigation_access('investigator_jane', 'OND-2025-000002', 'read', 365);

-- ============================================
-- SUMMARY & TESTING
-- ============================================

-- View all roles
SELECT rolname, rolcanlogin, rolsuper FROM pg_roles WHERE rolname LIKE '%investigat%' OR rolname LIKE '%analyst%' OR rolname LIKE '%engineer%';

-- Test RLS (as investigator)
-- SET ROLE investigator_john;
-- SELECT * FROM investigations;  -- Should see only assigned investigations
-- RESET ROLE;

-- Test masked views (as analyst)
-- SET ROLE analyst_bob;
-- SELECT * FROM canonical.fact_transaction_masked LIMIT 10;
-- RESET ROLE;

-- View audit log
-- SELECT * FROM audit_log ORDER BY event_timestamp DESC LIMIT 20;

COMMIT;
