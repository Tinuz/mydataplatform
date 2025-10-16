-- ==============================================================================
-- JWT-Based Row-Level Security for Keycloak Integration
-- ==============================================================================
-- 
-- Purpose: Extend RLS policies to work with JWT tokens from Keycloak
--
-- Features:
--   - Decode JWT tokens and extract claims
--   - Map Keycloak realm roles to database permissions
--   - Hybrid mode: Support both database users AND JWT authentication
--   - Investigation access based on JWT user claims
--
-- Usage:
--   1. Application sets JWT token: SET app.jwt_token = 'eyJhbG...';
--   2. RLS policies automatically use JWT claims for authorization
--   3. Falls back to current_user if no JWT token is set
--
-- Security:
--   - JWT signature verification should be done at application level
--   - This script only decodes and uses the claims
--   - For production: Add JWT signature verification in PostgreSQL
-- ==============================================================================

-- ============================================
-- 1. JWT UTILITY FUNCTIONS
-- ============================================

-- Function to decode JWT payload (middle part of token)
CREATE OR REPLACE FUNCTION decode_jwt_payload(jwt_token TEXT)
RETURNS JSONB AS $$
DECLARE
  parts TEXT[];
  payload TEXT;
  padding TEXT := '';
BEGIN
  -- JWT format: header.payload.signature
  parts := string_to_array(jwt_token, '.');
  
  IF array_length(parts, 1) != 3 THEN
    RAISE EXCEPTION 'Invalid JWT token format';
  END IF;
  
  -- Get payload (middle part)
  payload := parts[2];
  
  -- Add base64 padding if needed
  CASE mod(length(payload), 4)
    WHEN 2 THEN padding := '==';
    WHEN 3 THEN padding := '=';
    ELSE padding := '';
  END CASE;
  
  -- Decode base64 and convert to JSONB
  RETURN convert_from(decode(payload || padding, 'base64'), 'UTF8')::JSONB;
EXCEPTION
  WHEN OTHERS THEN
    RAISE WARNING 'Failed to decode JWT: %', SQLERRM;
    RETURN '{}'::JSONB;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION decode_jwt_payload(TEXT) IS 
  'Decodes JWT token payload and returns as JSONB. Does NOT verify signature.';

-- Function to extract realm roles from JWT
CREATE OR REPLACE FUNCTION get_jwt_roles()
RETURNS TEXT[] AS $$
DECLARE
  jwt_token TEXT;
  jwt_payload JSONB;
  roles TEXT[];
BEGIN
  -- Get JWT token from session variable
  jwt_token := current_setting('app.jwt_token', TRUE);
  
  IF jwt_token IS NULL OR jwt_token = '' THEN
    -- No JWT token set, return empty array
    RETURN ARRAY[]::TEXT[];
  END IF;
  
  -- Decode JWT payload
  jwt_payload := decode_jwt_payload(jwt_token);
  
  -- Extract realm_access.roles array
  IF jwt_payload ? 'realm_access' AND jwt_payload->'realm_access' ? 'roles' THEN
    SELECT ARRAY(
      SELECT jsonb_array_elements_text(jwt_payload->'realm_access'->'roles')
    ) INTO roles;
    RETURN roles;
  END IF;
  
  RETURN ARRAY[]::TEXT[];
EXCEPTION
  WHEN OTHERS THEN
    RAISE WARNING 'Failed to extract roles from JWT: %', SQLERRM;
    RETURN ARRAY[]::TEXT[];
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION get_jwt_roles() IS 
  'Extracts realm roles from JWT token stored in app.jwt_token session variable';

-- Function to get username from JWT (preferred_username or sub)
CREATE OR REPLACE FUNCTION get_jwt_username()
RETURNS TEXT AS $$
DECLARE
  jwt_token TEXT;
  jwt_payload JSONB;
BEGIN
  jwt_token := current_setting('app.jwt_token', TRUE);
  
  IF jwt_token IS NULL OR jwt_token = '' THEN
    RETURN NULL;
  END IF;
  
  jwt_payload := decode_jwt_payload(jwt_token);
  
  -- Try preferred_username first, fallback to sub (user ID)
  IF jwt_payload ? 'preferred_username' THEN
    RETURN jwt_payload->>'preferred_username';
  ELSIF jwt_payload ? 'sub' THEN
    RETURN jwt_payload->>'sub';
  END IF;
  
  RETURN NULL;
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION get_jwt_username() IS 
  'Returns username from JWT token (preferred_username or sub claim)';

-- Function to get user email from JWT
CREATE OR REPLACE FUNCTION get_jwt_email()
RETURNS TEXT AS $$
DECLARE
  jwt_token TEXT;
  jwt_payload JSONB;
BEGIN
  jwt_token := current_setting('app.jwt_token', TRUE);
  
  IF jwt_token IS NULL OR jwt_token = '' THEN
    RETURN NULL;
  END IF;
  
  jwt_payload := decode_jwt_payload(jwt_token);
  
  RETURN jwt_payload->>'email';
EXCEPTION
  WHEN OTHERS THEN
    RETURN NULL;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

-- ============================================
-- 2. AUTHORIZATION HELPER FUNCTIONS
-- ============================================

-- Check if current session has a specific role (JWT or database role)
CREATE OR REPLACE FUNCTION has_role(role_name TEXT)
RETURNS BOOLEAN AS $$
DECLARE
  jwt_roles TEXT[];
BEGIN
  -- First check JWT roles
  jwt_roles := get_jwt_roles();
  
  IF role_name = ANY(jwt_roles) THEN
    RETURN TRUE;
  END IF;
  
  -- Fallback to database role check
  RETURN pg_has_role(current_user, role_name, 'member');
EXCEPTION
  WHEN OTHERS THEN
    RETURN FALSE;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION has_role(TEXT) IS 
  'Check if current user has role via JWT or database role membership';

-- Get effective user identifier (JWT username or database user)
CREATE OR REPLACE FUNCTION get_effective_user()
RETURNS TEXT AS $$
DECLARE
  jwt_user TEXT;
BEGIN
  jwt_user := get_jwt_username();
  
  IF jwt_user IS NOT NULL THEN
    RETURN jwt_user;
  END IF;
  
  RETURN current_user;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER STABLE;

COMMENT ON FUNCTION get_effective_user() IS 
  'Returns effective username from JWT or falls back to database current_user';

-- ============================================
-- 3. UPDATE RLS POLICIES FOR JWT SUPPORT
-- ============================================

-- Drop existing investigator policies and recreate with JWT support

-- Investigations table
DROP POLICY IF EXISTS investigator_access_policy ON investigations;
CREATE POLICY investigator_jwt_access_policy ON investigations
    FOR SELECT
    TO investigator, PUBLIC  -- PUBLIC allows JWT users without db role
    USING (
        -- Platform admins and data engineers see everything
        has_role('platform_admin') 
        OR has_role('data_engineer')
        -- Investigators see only assigned investigations
        OR (
            has_role('investigator')
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
        )
    );

-- Raw transactions
DROP POLICY IF EXISTS investigator_transaction_policy ON raw_transactions;
CREATE POLICY investigator_jwt_transaction_policy ON raw_transactions
    FOR SELECT
    TO investigator, PUBLIC
    USING (
        has_role('platform_admin') 
        OR has_role('data_engineer')
        OR (
            has_role('investigator')
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
        )
    );

-- Raw calls
DROP POLICY IF EXISTS investigator_call_policy ON raw_calls;
CREATE POLICY investigator_jwt_call_policy ON raw_calls
    FOR SELECT
    TO investigator, PUBLIC
    USING (
        has_role('platform_admin') 
        OR has_role('data_engineer')
        OR (
            has_role('investigator')
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
        )
    );

-- Raw messages
DROP POLICY IF EXISTS investigator_message_policy ON raw_messages;
CREATE POLICY investigator_jwt_message_policy ON raw_messages
    FOR SELECT
    TO investigator, PUBLIC
    USING (
        has_role('platform_admin') 
        OR has_role('data_engineer')
        OR (
            has_role('investigator')
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
        )
    );

-- Canonical transactions
DROP POLICY IF EXISTS investigator_canonical_tx_policy ON canonical.canonical_transaction;
CREATE POLICY investigator_jwt_canonical_tx_policy ON canonical.canonical_transaction
    FOR SELECT
    TO investigator, PUBLIC
    USING (
        has_role('platform_admin') 
        OR has_role('data_engineer')
        OR has_role('data_analyst')  -- Analysts can see all canonical data
        OR (
            has_role('investigator')
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
        )
    );

-- Canonical communications
DROP POLICY IF EXISTS investigator_canonical_comm_policy ON canonical.canonical_communication;
CREATE POLICY investigator_jwt_canonical_comm_policy ON canonical.canonical_communication
    FOR SELECT
    TO investigator, PUBLIC
    USING (
        has_role('platform_admin') 
        OR has_role('data_engineer')
        OR has_role('data_analyst')
        OR (
            has_role('investigator')
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
                  AND (expires_at IS NULL OR expires_at > NOW())
            )
        )
    );

-- Update admin policies to use JWT as well
DROP POLICY IF EXISTS admin_access_all ON investigations;
CREATE POLICY admin_jwt_access_all ON investigations
    FOR ALL
    TO platform_admin, data_engineer, PUBLIC
    USING (has_role('platform_admin') OR has_role('data_engineer'));

DROP POLICY IF EXISTS admin_transaction_access ON raw_transactions;
CREATE POLICY admin_jwt_transaction_access ON raw_transactions
    FOR ALL
    TO platform_admin, data_engineer, PUBLIC
    USING (has_role('platform_admin') OR has_role('data_engineer'));

-- ============================================
-- 4. GRANT NECESSARY PERMISSIONS
-- ============================================

-- Grant execute on JWT functions to all users
GRANT EXECUTE ON FUNCTION decode_jwt_payload(TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_jwt_roles() TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_jwt_username() TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_jwt_email() TO PUBLIC;
GRANT EXECUTE ON FUNCTION has_role(TEXT) TO PUBLIC;
GRANT EXECUTE ON FUNCTION get_effective_user() TO PUBLIC;

-- Grant select on user_investigation_access to check permissions
GRANT SELECT ON user_investigation_access TO PUBLIC;

-- ============================================
-- 5. EXAMPLE USAGE & TESTING
-- ============================================

-- Example: Set JWT token in application
-- SET app.jwt_token = 'eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...';

-- Example: Test JWT decoding
-- SELECT get_jwt_username();
-- SELECT get_jwt_roles();
-- SELECT has_role('data_engineer');

-- Example: Query with JWT context
-- SET app.jwt_token = '...token...';
-- SELECT * FROM investigations;  -- Will use JWT roles for RLS

-- ============================================
-- 6. MONITORING & AUDIT
-- ============================================

-- Add JWT user tracking to audit log
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS jwt_username TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS jwt_email TEXT;

-- Update audit trigger to capture JWT info
CREATE OR REPLACE FUNCTION audit_trigger_func()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO audit_log (
        table_name,
        operation,
        user_name,
        jwt_username,
        jwt_email,
        changed_at,
        old_values,
        new_values
    ) VALUES (
        TG_TABLE_NAME,
        TG_OP,
        current_user,
        get_jwt_username(),
        get_jwt_email(),
        NOW(),
        CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN row_to_json(OLD) ELSE NULL END,
        CASE WHEN TG_OP IN ('INSERT', 'UPDATE') THEN row_to_json(NEW) ELSE NULL END
    );
    RETURN COALESCE(NEW, OLD);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- 7. INFO & DOCUMENTATION
-- ============================================

DO $$
BEGIN
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'JWT-Based RLS Configuration Completed';
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'Features:';
  RAISE NOTICE '  ✓ JWT token decoding (decode_jwt_payload)';
  RAISE NOTICE '  ✓ Realm role extraction (get_jwt_roles)';
  RAISE NOTICE '  ✓ Username from JWT (get_jwt_username)';
  RAISE NOTICE '  ✓ Hybrid role checking (has_role) - JWT + DB roles';
  RAISE NOTICE '  ✓ Updated RLS policies for all tables';
  RAISE NOTICE '  ✓ Audit logging with JWT user tracking';
  RAISE NOTICE '';
  RAISE NOTICE 'Usage in Application:';
  RAISE NOTICE '  1. Get JWT token from Keycloak OAuth flow';
  RAISE NOTICE '  2. Set session variable: SET app.jwt_token = ''token...'';';
  RAISE NOTICE '  3. Execute queries - RLS uses JWT claims automatically';
  RAISE NOTICE '';
  RAISE NOTICE 'Supported Roles (from Keycloak):';
  RAISE NOTICE '  - platform_admin: Full access';
  RAISE NOTICE '  - data_engineer: Full access to all data';
  RAISE NOTICE '  - data_analyst: Read canonical data (PII masked)';
  RAISE NOTICE '  - investigator: Access assigned investigations';
  RAISE NOTICE '  - auditor: Read audit logs';
  RAISE NOTICE '';
  RAISE NOTICE 'Testing:';
  RAISE NOTICE '  SELECT get_jwt_roles();';
  RAISE NOTICE '  SELECT get_jwt_username();';
  RAISE NOTICE '  SELECT has_role(''data_engineer'');';
  RAISE NOTICE '=================================================================';
END $$;
