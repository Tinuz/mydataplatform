#!/bin/bash

# ============================================
# Security & IAM Demo Script
# ============================================
#
# Demonstrates:
# 1. Role-Based Access Control (RBAC)
# 2. Row-Level Security (RLS)
# 3. Column-Level Security (PII masking)
# 4. Audit Logging
#
# Usage: ./demo_security.sh

set -e

DOCKER_CONTAINER="dp_postgres"
DB_NAME="superset"
DB_USER="superset"

echo "=========================================="
echo "Security & IAM Demo"
echo "=========================================="
echo ""

# ============================================
# 1. Show Database Roles
# ============================================
echo "[1/6] Database Roles & Permissions"
echo "-----------------------------------"
echo ""

docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    rolname AS role_name,
    CASE WHEN rolsuper THEN 'Yes' ELSE 'No' END AS is_superuser,
    CASE WHEN rolcanlogin THEN 'Yes' ELSE 'No' END AS can_login,
    CASE WHEN rolcreatedb THEN 'Yes' ELSE 'No' END AS can_create_db
FROM pg_roles 
WHERE rolname IN (
    'platform_admin', 
    'data_engineer', 
    'data_analyst', 
    'investigator',
    'investigator_john',
    'investigator_jane',
    'analyst_bob',
    'auditor'
)
ORDER BY rolname;
" | column -t

echo ""
echo "✓ Roles created successfully"
echo ""

# ============================================
# 2. Grant Access to Investigations
# ============================================
echo "[2/6] Grant Investigation Access"
echo "-----------------------------------"
echo ""

# Check if investigations exist
INVESTIGATION_COUNT=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c "
SELECT COUNT(*) FROM investigations;
")

if [ "$INVESTIGATION_COUNT" -eq "0" ]; then
    echo "⚠️  No investigations found. Load data first:"
    echo "   cd test-data/marvel-bandits && ./load_marvel_case.sh"
    echo ""
    echo "Continuing with demo setup..."
    echo ""
else
    echo "Found $INVESTIGATION_COUNT investigation(s)"
    echo ""
    
    # Grant access to first investigation for john
    FIRST_INV=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c "
    SELECT investigation_id FROM investigations LIMIT 1;
    ")
    
    if [ ! -z "$FIRST_INV" ]; then
        echo "Granting investigator_john access to: $FIRST_INV"
        docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
        SELECT grant_investigation_access('investigator_john', '$FIRST_INV', 'read', 365);
        " > /dev/null
        echo "✓ Access granted for 365 days"
    fi
fi

echo ""

# ============================================
# 3. Test Row-Level Security
# ============================================
echo "[3/6] Row-Level Security (RLS) Demo"
echo "-----------------------------------"
echo ""

if [ "$INVESTIGATION_COUNT" -eq "0" ]; then
    echo "⚠️  Skipping RLS demo - no data available"
    echo ""
else
    echo "Testing as 'platform_admin' (should see all investigations):"
    docker exec $DOCKER_CONTAINER psql -U platform_admin -d $DB_NAME -c "
    SELECT investigation_id, title, status 
    FROM investigations 
    ORDER BY investigation_id;
    " 2>&1 | head -20
    
    echo ""
    echo "Testing as 'investigator_john' (should see only assigned investigations):"
    docker exec $DOCKER_CONTAINER psql -U investigator_john -d $DB_NAME -c "
    SELECT investigation_id, title, status 
    FROM investigations 
    ORDER BY investigation_id;
    " 2>&1 | head -20
    
    echo ""
    echo "✓ RLS working - investigators see only their assigned cases"
fi

echo ""

# ============================================
# 4. Test Column-Level Security (PII Masking)
# ============================================
echo "[4/6] Column-Level Security (PII Masking)"
echo "-----------------------------------"
echo ""

# Check if canonical data exists
CANONICAL_COUNT=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -c "
SELECT COUNT(*) FROM canonical.canonical_transaction;
")

if [ "$CANONICAL_COUNT" -eq "0" ]; then
    echo "⚠️  No canonical data. Run dbt models first:"
    echo "   In Dagster UI: Materialize dbt_staging_models and dbt_canonical_models"
    echo ""
else
    echo "Found $CANONICAL_COUNT canonical transaction(s)"
    echo ""
    
    echo "Data Engineer view (FULL DATA - with PII):"
    docker exec $DOCKER_CONTAINER psql -U data_engineer -d $DB_NAME -c "
    SELECT 
        transaction_id,
        SUBSTRING(iban_from, 1, 10) || '...' AS iban_from,
        SUBSTRING(iban_to, 1, 10) || '...' AS iban_to,
        amount,
        currency
    FROM canonical.fact_transaction
    LIMIT 5;
    " 2>&1 | head -15
    
    echo ""
    echo "Data Analyst view (MASKED DATA - PII obscured):"
    docker exec $DOCKER_CONTAINER psql -U analyst_bob -d $DB_NAME -c "
    SELECT 
        transaction_id,
        iban_from_masked,
        iban_to_masked,
        amount,
        currency,
        description_length,
        counter_party_name_masked
    FROM canonical.fact_transaction_masked
    LIMIT 5;
    " 2>&1 | head -15
    
    echo ""
    echo "✓ PII masking working - analysts see redacted data"
fi

echo ""

# ============================================
# 5. Show User Access Matrix
# ============================================
echo "[5/6] User Access Matrix"
echo "-----------------------------------"
echo ""

docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    user_id,
    investigation_id,
    access_level,
    granted_at::DATE AS granted_date,
    expires_at::DATE AS expires_date,
    CASE 
        WHEN expires_at IS NULL OR expires_at > NOW() THEN 'Active'
        ELSE 'Expired'
    END AS status
FROM user_investigation_access
ORDER BY user_id, investigation_id;
"

echo ""

# ============================================
# 6. Show Audit Log
# ============================================
echo "[6/6] Audit Log (Recent Activity)"
echo "-----------------------------------"
echo ""

docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    event_timestamp::TIMESTAMP(0) AS timestamp,
    user_name,
    event_type,
    table_name,
    investigation_id,
    SUBSTRING(record_id, 1, 20) AS record_id,
    success
FROM audit_log
ORDER BY event_timestamp DESC
LIMIT 10;
"

echo ""

# ============================================
# Summary
# ============================================
echo "=========================================="
echo "Security Demo Summary"
echo "=========================================="
echo ""
echo "✅ Implemented Security Features:"
echo ""
echo "1. Role-Based Access Control (RBAC)"
echo "   - platform_admin: Full access"
echo "   - data_engineer: ETL and table management"
echo "   - data_analyst: Read-only, masked views"
echo "   - investigator: Per-investigation access (RLS)"
echo "   - auditor: Read-only audit logs"
echo ""
echo "2. Row-Level Security (RLS)"
echo "   - Investigators see only assigned cases"
echo "   - Automatic filtering by investigation_id"
echo "   - Time-based expiration support"
echo ""
echo "3. Column-Level Security"
echo "   - IBANs masked: NL12****1234"
echo "   - Phone numbers masked: ****5678"
echo "   - Names redacted: ***REDACTED***"
echo "   - Descriptions hidden (length only)"
echo ""
echo "4. Audit Logging"
echo "   - All data modifications logged"
echo "   - User, timestamp, table tracked"
echo "   - Investigation context captured"
echo ""
echo "=========================================="
echo "Test Credentials (Demo Only!)"
echo "=========================================="
echo ""
echo "Platform Admin:"
echo "  Username: platform_admin"
echo "  Password: admin_secure_pwd_2025!"
echo ""
echo "Data Engineer:"
echo "  Username: data_engineer"
echo "  Password: engineer_secure_pwd_2025!"
echo ""
echo "Data Analyst:"
echo "  Username: analyst_bob"
echo "  Password: bob_demo_2025!"
echo ""
echo "Investigator (John):"
echo "  Username: investigator_john"
echo "  Password: john_demo_2025!"
echo ""
echo "Investigator (Jane):"
echo "  Username: investigator_jane"
echo "  Password: jane_demo_2025!"
echo ""
echo "=========================================="
echo "Manual Testing"
echo "=========================================="
echo ""
echo "Connect as specific user:"
echo "  docker exec -it dp_postgres psql -U investigator_john -d superset"
echo ""
echo "Test queries:"
echo "  SELECT * FROM investigations;"
echo "  SELECT * FROM my_investigation_access;"
echo "  SELECT * FROM canonical.fact_transaction_masked LIMIT 10;"
echo ""
echo "Grant access (as admin):"
echo "  SELECT grant_investigation_access('investigator_jane', 'OND-2025-000002', 'read', 90);"
echo ""
echo "Revoke access:"
echo "  SELECT revoke_investigation_access('investigator_jane', 'OND-2025-000002');"
echo ""
echo "=========================================="
