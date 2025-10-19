#!/bin/bash

# Revoke Investigation Access
# This script removes investigation access for a user

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
if [ "$#" -lt 2 ]; then
    error "Usage: $0 <user_id> <investigation_id>"
    echo ""
    echo "Arguments:"
    echo "  user_id           - Keycloak username (e.g., jane.investigator)"
    echo "  investigation_id  - Investigation ID (e.g., OND-2025-000001)"
    echo ""
    echo "Examples:"
    echo "  # Revoke access"
    echo "  $0 jane.investigator OND-2025-000001"
    echo ""
    echo "  # Revoke all access for a user"
    echo "  $0 jane.investigator ALL"
    exit 1
fi

USER_ID="$1"
INVESTIGATION_ID="$2"

# Build the SQL command
if [ "$INVESTIGATION_ID" == "ALL" ]; then
    info "Revoking ALL investigation access for $USER_ID"
    
    # First show what will be deleted
    echo ""
    info "Current access for $USER_ID:"
    docker exec -i dp_postgres psql -U app_user -d superset << EOF
SELECT investigation_id, access_level, granted_at, expires_at
FROM user_investigation_access
WHERE user_id = '$USER_ID';
EOF
    
    echo ""
    warn "This will remove ALL access entries for $USER_ID"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        info "Operation cancelled"
        exit 0
    fi
    
    SQL="DELETE FROM user_investigation_access WHERE user_id = '$USER_ID';"
else
    info "Revoking access to $INVESTIGATION_ID for $USER_ID"
    
    # First show what will be deleted
    echo ""
    info "Current access:"
    docker exec -i dp_postgres psql -U app_user -d superset << EOF
SELECT user_id, investigation_id, access_level, granted_by, granted_at, expires_at
FROM user_investigation_access
WHERE user_id = '$USER_ID' AND investigation_id = '$INVESTIGATION_ID';
EOF
    
    SQL="DELETE FROM user_investigation_access WHERE user_id = '$USER_ID' AND investigation_id = '$INVESTIGATION_ID';"
fi

# Execute the SQL
docker exec -i dp_postgres psql -U app_user -d superset -c "$SQL"

if [ $? -eq 0 ]; then
    info "Access revoked successfully!"
    echo ""
    
    # Show remaining access for this user
    info "Remaining access for $USER_ID:"
    docker exec -i dp_postgres psql -U app_user -d superset << EOF
SELECT 
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
WHERE user_id = '$USER_ID'
ORDER BY investigation_id;
EOF
else
    error "Failed to revoke access"
    exit 1
fi
