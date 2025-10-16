#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BLUE}  🔐 Data Platform - Keycloak Setup${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# Check if Keycloak container is running
if ! docker ps | grep -q dp_keycloak; then
    echo -e "${RED}❌ Keycloak container is not running!${NC}"
    echo -e "${YELLOW}💡 Start it with: docker-compose up -d keycloak${NC}"
    exit 1
fi

# Wait for Keycloak to be ready by trying to authenticate
echo -e "${YELLOW}⏳ Waiting for Keycloak to be ready...${NC}"
MAX_RETRIES=30
RETRY_COUNT=0

until docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password admin \
  > /dev/null 2>&1; do
  RETRY_COUNT=$((RETRY_COUNT + 1))
  if [ $RETRY_COUNT -ge $MAX_RETRIES ]; then
    echo -e "${RED}❌ Keycloak did not become ready in time${NC}"
    exit 1
  fi
  echo -e "${YELLOW}   Attempt $RETRY_COUNT/$MAX_RETRIES...${NC}"
  sleep 5
done

echo -e "${GREEN}✅ Keycloak is ready and authenticated!${NC}"
echo ""

# Create realm
echo -e "${BLUE}[2/7]${NC} Creating 'data-platform' realm..."
if docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get realms/data-platform > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Realm already exists, skipping...${NC}"
else
    docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create realms \
      -s realm=data-platform \
      -s enabled=true \
      -s displayName="Data Platform" \
      -s sslRequired=none \
      -s registrationAllowed=false \
      -s resetPasswordAllowed=true \
      -s editUsernameAllowed=false \
      > /dev/null 2>&1
    echo -e "${GREEN}✅ Realm created${NC}"
fi
echo ""

# Create realm roles
echo -e "${BLUE}[3/7]${NC} Creating realm roles..."
ROLES=("platform_admin:Full platform access" \
       "data_engineer:ETL development and raw data access" \
       "data_analyst:Read-only analytical data access" \
       "investigator:Case-specific investigation access" \
       "auditor:Audit log viewing")

for role_def in "${ROLES[@]}"; do
    IFS=':' read -r role desc <<< "$role_def"
    if docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get roles/$role -r data-platform > /dev/null 2>&1; then
        echo -e "${YELLOW}   ⚠️  Role '$role' already exists${NC}"
    else
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create roles \
          -r data-platform \
          -s name=$role \
          -s "description=$desc" \
          > /dev/null 2>&1
        echo -e "${GREEN}   ✓ Created role: $role${NC}"
    fi
done
echo ""

# Create groups
echo -e "${BLUE}[4/7]${NC} Creating groups..."
GROUPS=("engineers:data_engineer" \
        "analysts:data_analyst" \
        "investigators:investigator" \
        "admins:platform_admin")

for group_def in "${GROUPS[@]}"; do
    IFS=':' read -r group role <<< "$group_def"
    
    # Check if group exists
    GROUP_ID=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get groups -r data-platform --fields id,name 2>/dev/null | grep -B1 "\"name\" : \"$group\"" | grep "\"id\"" | cut -d'"' -f4 || echo "")
    
    if [ -z "$GROUP_ID" ]; then
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create groups \
          -r data-platform \
          -s name=$group \
          > /dev/null 2>&1
        
        # Get the newly created group ID
        GROUP_ID=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get groups -r data-platform --fields id,name 2>/dev/null | grep -B1 "\"name\" : \"$group\"" | grep "\"id\"" | cut -d'"' -f4)
        
        echo -e "${GREEN}   ✓ Created group: $group${NC}"
    else
        echo -e "${YELLOW}   ⚠️  Group '$group' already exists${NC}"
    fi
    
    # Assign role to group
    if [ -n "$GROUP_ID" ]; then
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh add-roles \
          -r data-platform \
          --gid "$GROUP_ID" \
          --rolename $role \
          > /dev/null 2>&1 || true
        echo -e "${GREEN}   ✓ Assigned role '$role' to group '$group'${NC}"
    fi
done
echo ""

# Create OAuth clients
echo -e "${BLUE}[5/7]${NC} Creating OAuth clients..."
CLIENTS=("superset:superset_client_secret_2025:http://localhost:8088/*" \
         "dagster:dagster_client_secret_2025:http://localhost:3000/*" \
         "data-platform-api:api_client_secret_2025:http://localhost:8001/*" \
         "marquez:marquez_client_secret_2025:http://localhost:5000/*")

for client_def in "${CLIENTS[@]}"; do
    IFS=':' read -r client_id client_secret redirect_uri <<< "$client_def"
    
    if docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get clients -r data-platform --fields clientId 2>/dev/null | grep -q "\"$client_id\""; then
        echo -e "${YELLOW}   ⚠️  Client '$client_id' already exists${NC}"
    else
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
          -r data-platform \
          -s clientId=$client_id \
          -s enabled=true \
          -s clientAuthenticatorType=client-secret \
          -s secret=$client_secret \
          -s "redirectUris=[\"$redirect_uri\"]" \
          -s "webOrigins=[\"${redirect_uri%/*}\"]" \
          -s protocol=openid-connect \
          -s publicClient=false \
          -s standardFlowEnabled=true \
          -s directAccessGrantsEnabled=true \
          > /dev/null 2>&1
        echo -e "${GREEN}   ✓ Created client: $client_id${NC}"
    fi
done
echo ""

# Create demo users
echo -e "${BLUE}[6/7]${NC} Creating demo users..."
USERS=("admin.user:Admin2025!:admin@platform.local:Admin:User:admins" \
       "john.engineer:Engineer2025!:john@platform.local:John:Engineer:engineers" \
       "bob.analyst:Analyst2025!:bob@platform.local:Bob:Analyst:analysts" \
       "jane.investigator:Investigator2025!:jane@platform.local:Jane:Investigator:investigators")

for user_def in "${USERS[@]}"; do
    IFS=':' read -r username password email first_name last_name group <<< "$user_def"
    
    # Check if user exists
    if docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get users -r data-platform -q username=$username 2>/dev/null | grep -q "\"username\" : \"$username\""; then
        echo -e "${YELLOW}   ⚠️  User '$username' already exists${NC}"
    else
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create users \
          -r data-platform \
          -s username=$username \
          -s enabled=true \
          -s email=$email \
          -s firstName=$first_name \
          -s lastName=$last_name \
          > /dev/null 2>&1
        
        # Set password
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh set-password \
          -r data-platform \
          --username $username \
          --new-password $password \
          > /dev/null 2>&1
        
        echo -e "${GREEN}   ✓ Created user: $username${NC}"
    fi
    
    # Get group ID
    GROUP_ID=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get groups -r data-platform --fields id,name 2>/dev/null | grep -B1 "\"name\" : \"$group\"" | grep "\"id\"" | cut -d'"' -f4 || echo "")
    
    # Get user ID
    USER_ID=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get users -r data-platform -q username=$username 2>/dev/null | grep "\"id\"" | head -1 | cut -d'"' -f4)
    
    # Add user to group
    if [ -n "$GROUP_ID" ] && [ -n "$USER_ID" ]; then
        docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh update users/$USER_ID/groups/$GROUP_ID \
          -r data-platform \
          -s realm=data-platform \
          -s userId=$USER_ID \
          -s groupId=$GROUP_ID \
          -n > /dev/null 2>&1 || true
        echo -e "${GREEN}   ✓ Added '$username' to group '$group'${NC}"
    fi
done
echo ""

# Summary
echo -e "${BLUE}[7/7]${NC} Verifying setup..."
REALM_CHECK=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get realms/data-platform --fields enabled 2>/dev/null | grep -c "true" || echo "0")
USERS_COUNT=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get users -r data-platform 2>/dev/null | grep -c "\"username\"" || echo "0")
ROLES_COUNT=$(docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get roles -r data-platform 2>/dev/null | grep -c "\"name\"" || echo "0")

echo -e "${GREEN}✅ Setup verification:${NC}"
echo -e "   • Realm active: ${GREEN}✓${NC}"
echo -e "   • Users created: ${GREEN}$USERS_COUNT${NC}"
echo -e "   • Roles created: ${GREEN}$ROLES_COUNT${NC}"
echo ""

echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ Keycloak setup complete!${NC}"
echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}🌐 Access Keycloak Admin Console:${NC}"
echo -e "   URL:      ${BLUE}http://localhost:8085${NC}"
echo -e "   Username: ${GREEN}admin${NC}"
echo -e "   Password: ${GREEN}admin_secure_2025!${NC}"
echo ""
echo -e "${YELLOW}👥 Demo Users:${NC}"
echo -e "   ${GREEN}admin.user${NC} / Admin2025!         (Platform Admin)"
echo -e "   ${GREEN}john.engineer${NC} / Engineer2025!    (Data Engineer)"
echo -e "   ${GREEN}bob.analyst${NC} / Analyst2025!       (Data Analyst)"
echo -e "   ${GREEN}jane.investigator${NC} / Investigator2025! (Investigator)"
echo ""
echo -e "${YELLOW}🔑 OAuth Client Secrets:${NC}"
echo -e "   superset: ${GREEN}superset_client_secret_2025${NC}"
echo -e "   dagster:  ${GREEN}dagster_client_secret_2025${NC}"
echo -e "   api:      ${GREEN}api_client_secret_2025${NC}"
echo -e "   marquez:  ${GREEN}marquez_client_secret_2025${NC}"
echo ""
echo -e "${YELLOW}🧪 Test OAuth Flow:${NC}"
echo -e "   ${BLUE}curl -X POST \"http://localhost:8085/realms/data-platform/protocol/openid-connect/token\" \\${NC}"
echo -e "     ${BLUE}-H \"Content-Type: application/x-www-form-urlencoded\" \\${NC}"
echo -e "     ${BLUE}-d \"client_id=data-platform-api\" \\${NC}"
echo -e "     ${BLUE}-d \"client_secret=api_client_secret_2025\" \\${NC}"
echo -e "     ${BLUE}-d \"grant_type=password\" \\${NC}"
echo -e "     ${BLUE}-d \"username=john.engineer\" \\${NC}"
echo -e "     ${BLUE}-d \"password=Engineer2025!\" | jq -r '.access_token'${NC}"
echo ""
echo -e "${YELLOW}📚 Next Steps:${NC}"
echo -e "   1. Configure Superset OAuth in ${BLUE}superset/superset_config.py${NC}"
echo -e "   2. Configure Dagster auth in ${BLUE}orchestration/dagster.yaml${NC}"
echo -e "   3. Update API with OAuth middleware in ${BLUE}api/server.js${NC}"
echo -e "   4. Update Kong gateway config in ${BLUE}kong/kong.yml${NC}"
echo ""
