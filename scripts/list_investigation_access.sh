#!/bin/bash

# List Investigation Access
# This script shows investigation access for users

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

header() {
    echo -e "${BLUE}$1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

USER_ID="${1:-}"

if [ -z "$USER_ID" ]; then
    # Show all access
    header "All Investigation Access"
    header "========================="
    echo ""
    
    docker exec -i dp_postgres psql -U app_user -d superset << 'EOF'
SELECT 
    user_id,
    investigation_id,
    i.name as investigation_name,
    access_level,
    granted_by,
    granted_at::date as granted,
    CASE 
        WHEN expires_at IS NULL THEN 'Permanent'
        WHEN expires_at > NOW() THEN expires_at::date || ' (' || EXTRACT(DAY FROM expires_at - NOW())::int || ' days)'
        ELSE 'EXPIRED (' || expires_at::date || ')'
    END as expires
FROM user_investigation_access uia
LEFT JOIN investigations i ON uia.investigation_id = i.investigation_id
ORDER BY user_id, investigation_id;
EOF

    echo ""
    info "To see access for a specific user: $0 <username>"
    
else
    # Show access for specific user
    header "Investigation Access for: $USER_ID"
    header "=================================="
    echo ""
    
    # Check if user has any access
    COUNT=$(docker exec dp_postgres psql -U app_user -d superset -tAc "SELECT COUNT(*) FROM user_investigation_access WHERE user_id = '$USER_ID';")
    
    if [ "$COUNT" -eq "0" ]; then
        warn "User $USER_ID has no investigation access"
        exit 0
    fi
    
    docker exec -i dp_postgres psql -U app_user -d superset << EOF
SELECT 
    uia.investigation_id,
    i.name as investigation_name,
    i.status as inv_status,
    uia.access_level,
    uia.granted_by,
    uia.granted_at::date as granted,
    CASE 
        WHEN uia.expires_at IS NULL THEN 'Permanent'
        WHEN uia.expires_at > NOW() THEN uia.expires_at::date || ' (' || EXTRACT(DAY FROM uia.expires_at - NOW())::int || ' days left)'
        ELSE 'EXPIRED (' || uia.expires_at::date || ')'
    END as expires,
    CASE 
        WHEN uia.expires_at IS NULL OR uia.expires_at > NOW() THEN '✓ ACTIVE'
        ELSE '✗ EXPIRED'
    END as status
FROM user_investigation_access uia
LEFT JOIN investigations i ON uia.investigation_id = i.investigation_id
WHERE user_id = '$USER_ID'
ORDER BY 
    CASE WHEN uia.expires_at IS NULL OR uia.expires_at > NOW() THEN 0 ELSE 1 END,
    uia.investigation_id;
EOF

    echo ""
    info "Total access entries: $COUNT"
    
    # Show summary
    ACTIVE=$(docker exec dp_postgres psql -U app_user -d superset -tAc "SELECT COUNT(*) FROM user_investigation_access WHERE user_id = '$USER_ID' AND (expires_at IS NULL OR expires_at > NOW());")
    EXPIRED=$(docker exec dp_postgres psql -U app_user -d superset -tAc "SELECT COUNT(*) FROM user_investigation_access WHERE user_id = '$USER_ID' AND expires_at IS NOT NULL AND expires_at <= NOW();")
    
    info "Active: $ACTIVE | Expired: $EXPIRED"
    
    # Test RLS for this user
    echo ""
    header "RLS Test: What can $USER_ID see?"
    header "=================================="
    
    # Get JWT token for user
    # Note: This assumes we know the password pattern
    PASSWORD=""
    case "$USER_ID" in
        "admin.user") PASSWORD="Admin2025!" ;;
        "john.engineer") PASSWORD="Engineer2025!" ;;
        "bob.analyst") PASSWORD="Analyst2025!" ;;
        "jane.investigator") PASSWORD="Investigator2025!" ;;
        *) 
            warn "Unknown demo user, cannot test RLS"
            exit 0
            ;;
    esac
    
    TOKEN=$(curl -s -X POST http://localhost:8085/realms/data-platform/protocol/openid-connect/token \
      -d "client_id=data-platform-api" \
      -d "client_secret=api_client_secret_2025" \
      -d "grant_type=password" \
      -d "username=$USER_ID" \
      -d "password=$PASSWORD" | jq -r '.access_token')
    
    if [ "$TOKEN" != "null" ] && [ -n "$TOKEN" ]; then
        docker exec -i dp_postgres psql -U app_user -d superset << EOF
SET app.jwt_token = '$TOKEN';

SELECT 
    investigation_id,
    name,
    status,
    created_at::date as created
FROM investigations
ORDER BY investigation_id;
EOF
    else
        warn "Could not get JWT token for $USER_ID"
    fi
fi
