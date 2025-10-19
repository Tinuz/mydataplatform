#!/bin/bash

# Update Dagster OAuth Client for OIDC Integration
# This script updates the Dagster client in Keycloak with correct redirect URIs

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Dagster OIDC Integration Setup${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Keycloak is running
if ! docker ps | grep -q dp_keycloak; then
    echo -e "${RED}ERROR: Keycloak container is not running${NC}"
    echo "Start it with: docker-compose --profile standard up -d keycloak"
    exit 1
fi

echo -e "${BLUE}[1/4]${NC} Authenticating with Keycloak..."
# Wait for Keycloak to be ready by attempting authentication
MAX_ATTEMPTS=30
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh config credentials \
      --server http://localhost:8080 \
      --realm master \
      --user admin \
      --password admin \
      --client admin-cli \
      > /dev/null 2>&1; then
        echo -e "${GREEN}   ✓ Connected to Keycloak${NC}"
        break
    fi
    
    ATTEMPT=$((ATTEMPT + 1))
    if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
        echo -e "${RED}   ✗ Failed to authenticate with Keycloak${NC}"
        exit 1
    fi
    
    echo -ne "${YELLOW}   ⏳ Waiting for Keycloak... (attempt $ATTEMPT/$MAX_ATTEMPTS)\r${NC}"
    sleep 2
done
echo ""

# Get Dagster client ID
echo -e "${BLUE}[2/4]${NC} Finding Dagster client..."
CLIENT_UUID=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get clients -r data-platform --fields id,clientId 2>/dev/null | \
  grep -B1 '"clientId" : "dagster"' | grep '"id"' | cut -d'"' -f4)

if [ -z "$CLIENT_UUID" ]; then
    echo -e "${RED}   ✗ Dagster client not found${NC}"
    echo "   Run ./setup_keycloak.sh first to create the client"
    exit 1
fi

echo -e "${GREEN}   ✓ Found Dagster client (ID: ${CLIENT_UUID:0:8}...)${NC}"
echo ""

# Update client with correct redirect URIs for OIDC
echo -e "${BLUE}[3/4]${NC} Updating Dagster client configuration..."

docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh update clients/$CLIENT_UUID \
  -r data-platform \
  -s 'redirectUris=["http://localhost:3000/*","http://localhost:3000/oauth2/callback","http://127.0.0.1:3000/*","http://127.0.0.1:3000/oauth2/callback","http://localhost:4180/oauth2/callback","http://127.0.0.1:4180/oauth2/callback"]' \
  -s 'webOrigins=["http://localhost:3000","http://127.0.0.1:3000","http://localhost:4180","http://127.0.0.1:4180","*"]' \
  -s standardFlowEnabled=true \
  -s directAccessGrantsEnabled=true \
  -s serviceAccountsEnabled=false \
  -s publicClient=false \
  -s 'attributes={"post.logout.redirect.uris":"http://localhost:3000/*++http://localhost:4180/*"}'

if [ $? -eq 0 ]; then
    echo -e "${GREEN}   ✓ Client updated successfully${NC}"
else
    echo -e "${RED}   ✗ Failed to update client${NC}"
    exit 1
fi
echo ""

# Verify the update
echo -e "${BLUE}[4/4]${NC} Verifying configuration..."
echo ""
echo -e "${GREEN}Dagster OIDC Configuration:${NC}"
docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get clients/$CLIENT_UUID \
  -r data-platform \
  --fields clientId,redirectUris,webOrigins,standardFlowEnabled,directAccessGrantsEnabled 2>/dev/null | \
  grep -E '(clientId|redirectUris|webOrigins|standardFlowEnabled|directAccessGrantsEnabled)'

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ Dagster OIDC Setup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Next steps:"
echo "1. Restart Dagster to apply the configuration:"
echo "   docker-compose --profile standard restart dagster"
echo ""
echo "2. Access Dagster UI:"
echo "   http://localhost:3000"
echo ""
echo "3. You will be redirected to Keycloak for authentication"
echo ""
echo "4. Login with any demo user:"
echo "   - admin.user / Admin2025!"
echo "   - john.engineer / Engineer2025!"
echo "   - bob.analyst / Analyst2025!"
echo "   - jane.investigator / Investigator2025!"
