#!/bin/bash

# Grant Investigation Access
# This script adds investigation access for a user

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

# Check if required arguments are provided
if [ "$#" -lt 3 ]; then
    error "Usage: $0 <user_id> <investigation_id> <access_level> [granted_by] [expires_days]"
    echo ""
    echo "Arguments:"
    echo "  user_id           - Keycloak username (e.g., jane.investigator)"
    echo "  investigation_id  - Investigation ID (e.g., OND-2025-000001)"
    echo "  access_level      - read or write"
    echo "  granted_by        - (Optional) Username who grants access (default: admin.user)"
    echo "  expires_days      - (Optional) Days until access expires (default: permanent)"
    echo ""
    echo "Examples:"
    echo "  # Grant permanent read access"
    echo "  $0 jane.investigator OND-2025-000001 read"
    echo ""
    echo "  # Grant write access that expires in 30 days"
    echo "  $0 jane.investigator OND-2025-000002 write admin.user 30"
    echo ""
    echo "  # Grant read access that expires in 7 days"
    echo "  $0 john.engineer OND-2025-000003 read bob.analyst 7"
    exit 1
fi

USER_ID="$1"
INVESTIGATION_ID="$2"
ACCESS_LEVEL="$3"
GRANTED_BY="${4:-admin.user}"
EXPIRES_DAYS="${5:-}"

# Validate access level
if [[ "$ACCESS_LEVEL" != "read" && "$ACCESS_LEVEL" != "write" ]]; then
    error "Access level must be 'read' or 'write'"
    exit 1
fi

# Build the SQL command
if [ -z "$EXPIRES_DAYS" ]; then
    # Permanent access
    SQL="INSERT INTO user_investigation_access (user_id, investigation_id, access_level, granted_by, granted_at)
         VALUES ('$USER_ID', '$INVESTIGATION_ID', '$ACCESS_LEVEL', '$GRANTED_BY', NOW())
         ON CONFLICT (user_id, investigation_id) 
         DO UPDATE SET 
             access_level = EXCLUDED.access_level,
             granted_by = EXCLUDED.granted_by,
             granted_at = NOW(),
             expires_at = NULL;"
    
    info "Granting PERMANENT $ACCESS_LEVEL access to $USER_ID for investigation $INVESTIGATION_ID"
else
    # Temporary access
    SQL="INSERT INTO user_investigation_access (user_id, investigation_id, access_level, granted_by, granted_at, expires_at)
         VALUES ('$USER_ID', '$INVESTIGATION_ID', '$ACCESS_LEVEL', '$GRANTED_BY', NOW(), NOW() + INTERVAL '$EXPIRES_DAYS days')
         ON CONFLICT (user_id, investigation_id) 
         DO UPDATE SET 
             access_level = EXCLUDED.access_level,
             granted_by = EXCLUDED.granted_by,
             granted_at = NOW(),
             expires_at = NOW() + INTERVAL '$EXPIRES_DAYS days';"
    
    info "Granting $ACCESS_LEVEL access to $USER_ID for investigation $INVESTIGATION_ID (expires in $EXPIRES_DAYS days)"
fi

# Execute the SQL
docker exec -i dp_postgres psql -U app_user -d superset -c "$SQL"

if [ $? -eq 0 ]; then
    info "Access granted successfully!"
    echo ""
    
    # Show the access details
    docker exec -i dp_postgres psql -U app_user -d superset << EOF
SELECT 
    user_id,
    investigation_id,
    access_level,
    granted_by,
    granted_at,
    expires_at,
    CASE 
        WHEN expires_at IS NULL THEN 'Permanent'
        WHEN expires_at > NOW() THEN 'Active (expires ' || expires_at::date || ')'
        ELSE 'EXPIRED'
    END as status
FROM user_investigation_access
WHERE user_id = '$USER_ID' AND investigation_id = '$INVESTIGATION_ID';
EOF
else
    error "Failed to grant access"
    exit 1
fi
