#!/bin/bash

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🔐 Assign Realm Roles to Keycloak Users${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Authenticate
echo -e "${YELLOW}Authenticating with Keycloak...${NC}"
docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password admin \
  > /dev/null 2>&1
echo -e "${GREEN}✅ Authenticated${NC}"
echo ""

# Function to assign role to user
assign_role() {
    local username=$1
    local role=$2
    
    # Get user ID
    USER_ID=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get users \
      -r data-platform \
      -q username=$username \
      2>/dev/null | jq -r '.[0].id')
    
    if [ "$USER_ID" == "null" ] || [ -z "$USER_ID" ]; then
        echo -e "${RED}   ✗ User not found: $username${NC}"
        return 1
    fi
    
    # Assign realm role
    docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh add-roles \
      -r data-platform \
      --uusername $username \
      --rolename $role \
      > /dev/null 2>&1
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}   ✓ Assigned '$role' to $username${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Role '$role' already assigned to $username (or error)${NC}"
    fi
}

# Assign roles to users
echo -e "${BLUE}Assigning roles to users...${NC}"
echo ""

echo -e "${BLUE}admin.user:${NC}"
assign_role "admin.user" "platform_admin"

echo ""
echo -e "${BLUE}john.engineer:${NC}"
assign_role "john.engineer" "data_engineer"

echo ""
echo -e "${BLUE}bob.analyst:${NC}"
assign_role "bob.analyst" "data_analyst"

echo ""
echo -e "${BLUE}jane.investigator:${NC}"
assign_role "jane.investigator" "investigator"

echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  ✅ Role Assignment Completed${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${BLUE}Verification: Get new token and check roles${NC}"
echo ""
echo -e "curl -X POST http://localhost:8085/realms/data-platform/protocol/openid-connect/token \\"
echo -e "  -d \"client_id=data-platform-api\" \\"
echo -e "  -d \"client_secret=api_client_secret_2025\" \\"
echo -e "  -d \"grant_type=password\" \\"
echo -e "  -d \"username=john.engineer\" \\"
echo -e "  -d \"password=Engineer2025!\" | jq -r '.access_token' | cut -d'.' -f2 | base64 -d 2>/dev/null | jq '.realm_access.roles'"
echo ""
