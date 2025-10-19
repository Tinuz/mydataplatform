# 🚀 Modern Data Platform with Enterprise OAuth

Complete data platform met OAuth2/OIDC authentication, Row-Level Security (RLS), data lineage tracking, en comprehensive investigation management.

**Key Features:**
- 🔐 **OAuth2/OIDC** - Centralized authentication via Keycloak
- 🛡️ **Row-Level Security** - JWT-based PostgreSQL RLS policies
- 📊 **Data Orchestration** - Dagster for workflow management
- 📈 **Data Lineage** - OpenLineage integration via Marquez
- 🎨 **Visualization** - Apache Superset dashboards
- 🚪 **API Gateway** - Kong with OAuth protection
- 🔍 **Investigation Management** - Case-based data access control

---

## 📑 Table of Contents

1. [Quick Start](#-quick-start)
2. [Services Overview](#-services-overview)
3. [Authentication & Security](#-authentication--security)
   - [OAuth2/OIDC Setup](#oauth2oidc-setup)
   - [Demo Users & Roles](#demo-users--roles)
   - [JWT-Based RLS](#jwt-based-row-level-security)
4. [Protecting Services with OAuth](#-protecting-services-with-oauth)
   - [Dagster Example (Complete Guide)](#example-dagster-ui-protection)
   - [Applying to Other Services](#applying-oauth-to-other-services)
5. [Investigation Management](#-investigation-management)
6. [Development Guide](#-development-guide)
7. [Production Deployment](#-production-deployment)
8. [Troubleshooting](#-troubleshooting)

---

## ⚡ Quick Start

### 1. Start the Platform

```bash
# Start all services (recommended for development)
docker-compose --profile standard up -d

# Wait for services to be ready (~2 minutes)
```

### 2. Initialize Authentication

```bash
# Setup Keycloak with users, roles, and OAuth clients
./scripts/setup_keycloak.sh

# This creates:
# - data-platform realm
# - 5 demo users with different roles
# - OAuth clients for all services
# - JWT token configuration
# - RLS policies in PostgreSQL
```

### 3. Access Services

| Service | URL | Credentials | OAuth Protected |
|---------|-----|-------------|-----------------|
| **Dagster UI** (OAuth) | http://localhost:4180 | jane.investigator / Investigator2025! | ✅ Yes |
| **Dagster UI** (Direct) | http://localhost:3000 | - | ❌ No |
| **Keycloak Admin** | http://localhost:8085 | admin / admin | ❌ No |
| **Superset** | http://localhost:8088 | admin / admin | ❌ No |
| **Marquez Web** | http://localhost:3001 | - | ❌ No |
| **Kong Gateway** | http://localhost:8000 | - | ⚙️ Configurable |
| **Investigations UI** | http://localhost:8080 | - | ❌ No |

**🔐 First OAuth Login:**
1. Go to http://localhost:4180
2. Click "Sign in with OpenID Connect"
3. Login with: **jane.investigator** / **Investigator2025!**
4. You'll be redirected to Dagster UI

---

## 📊 Services Overview

### Core Services

| Service | Port | Description | Profile |
|---------|------|-------------|---------|
| **PostgreSQL** | 5432 | Primary database with RLS | standard |
| **Keycloak** | 8085 | IAM & OAuth provider | standard |
| **oauth2-proxy** | 4180 | OAuth reverse proxy | standard |
| **Dagster** | 3000 | Orchestration & workflows | standard |
| **Superset** | 8088 | BI & visualization | standard |
| **Marquez** | 5000 | Data lineage API | standard |
| **Marquez Web** | 3001 | Lineage UI | standard |
| **MinIO** | 9000-9001 | S3-compatible storage | standard |
| **Kong** | 8000-8001 | API Gateway | standard |
| **Konga** | 1337 | Kong Admin UI | standard |
| **Cell API** | 3100 | Cell tower data API | standard |
| **Swagger UI** | 8082 | API documentation | standard |
| **Investigations API** | 8090 | Investigation management | standard |
| **Investigations UI** | 8080 | Investigation dashboard | standard |

### Additional Services

| Service | Port | Profile | Description |
|---------|------|---------|-------------|
| **Kafka** | 9092 | streaming | Event streaming |
| **Iceberg REST** | 8181 | streaming | Iceberg catalog |
| **Amundsen** | 5005 | amundsen | Data catalog |
| **Neo4j** | 7474, 7687 | amundsen | Graph database |
| **Elasticsearch** | 9200 | amundsen | Search engine |

---

## 🔐 Authentication & Security

### Architecture Overview

```
┌─────────────┐
│   Browser   │
└──────┬──────┘
       │ 1. Access http://localhost:4180
       ▼
┌─────────────────┐
│  oauth2-proxy   │ ← Reverse Proxy
│   Port: 4180    │
└──────┬──────────┘
       │ 2. Not authenticated? Redirect to Keycloak
       ▼
┌─────────────────┐
│    Keycloak     │ ← Identity Provider
│   Port: 8085    │
└──────┬──────────┘
       │ 3. User logs in
       │ 4. OAuth callback with authorization code
       ▼
┌─────────────────┐
│  oauth2-proxy   │
└──────┬──────────┘
       │ 5. Exchange code for tokens
       │ 6. Set session cookie
       │ 7. Proxy authenticated requests
       ▼
┌─────────────────┐
│  Dagster UI     │ ← Protected Application
│   Port: 3000    │
└─────────────────┘
```

### OAuth2/OIDC Setup

The platform uses **Keycloak** as the OAuth2/OIDC identity provider:

**Key Components:**
- **Keycloak Realm**: `data-platform`
- **OAuth Clients**: Pre-configured for each service
- **JWT Tokens**: Include user roles and investigation access
- **Session Management**: Via oauth2-proxy cookies

**Configuration Location:**
- Keycloak: `docker-compose.yml` (keycloak service)
- oauth2-proxy: `docker-compose.yml` (oauth2-proxy service)
- Setup script: `scripts/setup_keycloak.sh`

### Demo Users & Roles

| Username | Password | Roles | Access Level |
|----------|----------|-------|--------------|
| **admin.user** | Admin2025! | platform_admin | Full access to everything |
| **john.engineer** | Engineer2025! | data_engineer | ETL, raw data, create tables |
| **bob.analyst** | Analyst2025! | data_analyst | Read-only canonical data (PII masked) |
| **jane.investigator** | Investigator2025! | investigator | Assigned investigations only |
| **john.auditor** | Auditor2025! | auditor | Audit logs, read-only |

### Keycloak Realm Roles

**Available Roles:**

1. **platform_admin**
   - Full database access
   - Can modify configuration
   - Sees all investigations and PII data
   - Superuser privileges

2. **data_engineer**
   - ETL development and raw data access
   - Can create/modify tables
   - Sees all investigations
   - No PII restrictions

3. **data_analyst**
   - Read-only access to canonical data
   - PII data is automatically masked
   - Cannot see raw data
   - No investigation restrictions

4. **investigator**
   - Access to assigned investigations only
   - Must be granted explicit access via `user_investigation_access` table
   - Sees only data for assigned cases
   - PII visible for assigned investigations

5. **auditor**
   - Read-only access to audit logs
   - Cannot modify any data
   - Track user actions and data access

### JWT-Based Row-Level Security

**How it works:**

1. **User Authentication**
   ```
   User → Keycloak Login → JWT Token (includes roles + investigation access)
   ```

2. **Token Structure**
   ```json
   {
     "sub": "jane.investigator",
     "realm_access": {
       "roles": ["investigator"]
     },
     "investigation_access": ["case-001", "case-002"],
     "exp": 1698234567
   }
   ```

3. **PostgreSQL RLS Policies**
   ```sql
   -- Example: Investigation access policy
   CREATE POLICY investigation_access_policy ON investigations
   FOR SELECT
   USING (
     -- Admin sees everything
     current_setting('app.role', true) = 'platform_admin'
     OR
     -- Investigator sees assigned cases only
     (current_setting('app.role', true) = 'investigator'
      AND investigation_id = ANY(string_to_array(
        current_setting('app.investigation_access', true), ','
      )))
   );
   ```

4. **JWT Token Usage**
   ```python
   # Example: Python application
   import psycopg2
   import jwt
   
   # Get JWT from Keycloak
   token = get_keycloak_token(username, password)
   decoded = jwt.decode(token, verify=False)
   
   # Set session variables for RLS
   conn = psycopg2.connect(...)
   cursor = conn.cursor()
   cursor.execute(f"SET app.role = '{decoded['realm_access']['roles'][0]}'")
   cursor.execute(f"SET app.investigation_access = '{','.join(decoded['investigation_access'])}'")
   
   # Now RLS policies apply automatically
   cursor.execute("SELECT * FROM investigations")
   ```

**PostgreSQL Helper Functions:**

```sql
-- Decode JWT token
SELECT decode_jwt_token('eyJhbGciOi...');

-- Extract roles from JWT
SELECT extract_jwt_roles('eyJhbGciOi...');

-- Extract investigation access from JWT
SELECT extract_jwt_investigation_access('eyJhbGciOi...');

-- Set session from JWT (one command)
SELECT set_jwt_session('eyJhbGciOi...');
```

### Testing RLS

```bash
# Test JWT token generation and RLS enforcement
./scripts/tests/test_jwt_rls.sh

# Output shows:
# - Token generation for each user
# - RLS filtering per role
# - Investigation access enforcement
# - PII masking for analysts
```

---

## 🔒 Protecting Services with OAuth

### Example: Dagster UI Protection

**Complete step-by-step guide to protect any web service with OAuth2/OIDC.**

#### Step 1: Create OAuth Client in Keycloak

```bash
# Edit scripts/setup_keycloak.sh and add:
docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
  -r data-platform \
  -s clientId=dagster \
  -s secret=dagster_client_secret_2025 \
  -s 'redirectUris=["http://localhost:4180/oauth2/callback","http://localhost:3000/*"]' \
  -s 'webOrigins=["http://localhost:4180","http://localhost:3000"]' \
  -s publicClient=false \
  -s standardFlowEnabled=true \
  -s directAccessGrantsEnabled=true
```

Or use the update script:
```bash
./scripts/update_dagster_oidc.sh
```

#### Step 2: Add oauth2-proxy to docker-compose.yml

```yaml
services:
  oauth2-proxy:
    image: quay.io/oauth2-proxy/oauth2-proxy:v7.6.0
    container_name: dp_oauth2_proxy
    ports:
      - "4180:4180"
    environment:
      # Provider Configuration
      OAUTH2_PROXY_PROVIDER: oidc
      OAUTH2_PROXY_OIDC_ISSUER_URL: http://keycloak:8080/realms/data-platform
      OAUTH2_PROXY_CLIENT_ID: dagster
      OAUTH2_PROXY_CLIENT_SECRET: dagster_client_secret_2025
      
      # Redirect Configuration
      OAUTH2_PROXY_REDIRECT_URL: http://localhost:4180/oauth2/callback
      
      # Upstream Service (what to protect)
      OAUTH2_PROXY_UPSTREAMS: http://dagster:3000
      
      # Cookie Configuration
      OAUTH2_PROXY_COOKIE_SECRET: eOWvPEmrVmW24wemknp83rAKWiE6PkVd  # 32 bytes
      OAUTH2_PROXY_COOKIE_NAME: _oauth2_proxy_dagster
      OAUTH2_PROXY_COOKIE_EXPIRE: 24h
      OAUTH2_PROXY_COOKIE_REFRESH: 1h
      
      # Email Configuration
      OAUTH2_PROXY_EMAIL_DOMAINS: "*"
      OAUTH2_PROXY_INSECURE_OIDC_ALLOW_UNVERIFIED_EMAIL: "true"
      
      # Security Settings (Development)
      OAUTH2_PROXY_SKIP_PROVIDER_CA_VERIFY: "true"
      OAUTH2_PROXY_SSL_INSECURE_SKIP_VERIFY: "true"
      OAUTH2_PROXY_INSECURE_OIDC_SKIP_ISSUER_VERIFICATION: "true"
      
      # Pass tokens to upstream
      OAUTH2_PROXY_PASS_ACCESS_TOKEN: "true"
      OAUTH2_PROXY_PASS_USER_HEADERS: "true"
      OAUTH2_PROXY_SET_XAUTHREQUEST: "true"
      
    depends_on:
      keycloak:
        condition: service_healthy
      dagster:
        condition: service_started
    networks:
      - default
    profiles: [ "standard" ]
```

#### Step 3: Start and Test

```bash
# Start oauth2-proxy
docker-compose --profile standard up -d oauth2-proxy

# Test access
open http://localhost:4180

# You'll be redirected to Keycloak login
# After login, you'll see Dagster UI
```

#### Step 4: Verify OAuth Flow

```bash
# Check oauth2-proxy logs
docker logs dp_oauth2_proxy --tail 50

# Should see:
# - OIDC Discovery successful
# - OAuthProxy configured for Client ID: dagster
# - Cookie settings configured
# - Upstream mapping: / => http://dagster:3000
```

### Key Configuration Points

**1. Cookie Secret**
Must be exactly 16, 24, or 32 bytes:
```bash
# Generate 32-byte secret
python3 -c "import secrets; print(secrets.token_urlsafe(32)[:32])"
```

**2. Redirect URIs**
Must match in both Keycloak AND oauth2-proxy:
- Keycloak client: `http://localhost:4180/oauth2/callback`
- oauth2-proxy: `OAUTH2_PROXY_REDIRECT_URL=http://localhost:4180/oauth2/callback`

**3. OIDC Issuer**
Use internal Docker network name:
```
OAUTH2_PROXY_OIDC_ISSUER_URL: http://keycloak:8080/realms/data-platform
```
NOT: `http://localhost:8085/realms/data-platform`

**4. Development Flags**
For development only (remove in production):
```yaml
OAUTH2_PROXY_INSECURE_OIDC_SKIP_ISSUER_VERIFICATION: "true"
OAUTH2_PROXY_INSECURE_OIDC_ALLOW_UNVERIFIED_EMAIL: "true"
OAUTH2_PROXY_SKIP_PROVIDER_CA_VERIFY: "true"
```

### Applying OAuth to Other Services

**Template for any service:**

1. **Create Keycloak Client**
   ```bash
   docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
     -r data-platform \
     -s clientId=<SERVICE_NAME> \
     -s secret=<SERVICE_SECRET> \
     -s 'redirectUris=["http://localhost:<PORT>/oauth2/callback"]' \
     -s standardFlowEnabled=true
   ```

2. **Add oauth2-proxy instance**
   ```yaml
   <service>-oauth:
     image: quay.io/oauth2-proxy/oauth2-proxy:v7.6.0
     ports:
       - "<EXTERNAL_PORT>:4180"
     environment:
       OAUTH2_PROXY_CLIENT_ID: <SERVICE_NAME>
       OAUTH2_PROXY_CLIENT_SECRET: <SERVICE_SECRET>
       OAUTH2_PROXY_UPSTREAMS: http://<SERVICE_NAME>:<INTERNAL_PORT>
       OAUTH2_PROXY_REDIRECT_URL: http://localhost:<EXTERNAL_PORT>/oauth2/callback
       # ... rest of config same as Dagster example
   ```

3. **Test**
   ```bash
   docker-compose up -d <service>-oauth
   open http://localhost:<EXTERNAL_PORT>
   ```

**Services Ready for OAuth Protection:**
- ✅ **Dagster** - Already protected (port 4180)
- ⚙️ **Superset** - Port 8088 (can protect with oauth2-proxy on port 8189)
- ⚙️ **Marquez Web** - Port 3001 (can protect on port 3101)
- ⚙️ **Konga** - Port 1337 (can protect on port 1338)
- ⚙️ **Investigations UI** - Port 8080 (can protect on port 8081)


---

## 🔍 Investigation Management

### Granting Investigation Access

```bash
# Grant access to jane.investigator for case-001
./scripts/grant_investigation_access.sh jane.investigator case-001

# Grant access to multiple investigations
./scripts/grant_investigation_access.sh jane.investigator case-002
./scripts/grant_investigation_access.sh john.auditor case-001
```

### Listing Investigation Access

```bash
# List all investigation access
./scripts/list_investigation_access.sh

# Output:
# username          | investigation_id | granted_at
# ------------------+------------------+------------
# jane.investigator | case-001        | 2025-01-15
# jane.investigator | case-002        | 2025-01-15
```

### Revoking Investigation Access

```bash
# Revoke access
./scripts/revoke_investigation_access.sh jane.investigator case-001
```

### How RLS Enforces Investigation Access

1. **User logs in** → Keycloak generates JWT with `investigation_access` claim
2. **Application receives JWT** → Extracts investigation IDs from token
3. **PostgreSQL session configured** → `SET app.investigation_access = 'case-001,case-002'`
4. **RLS policies apply** → User only sees data for assigned investigations

**Example Query Flow:**

```sql
-- Jane logs in, JWT contains investigation_access: ["case-001", "case-002"]
SET app.role = 'investigator';
SET app.investigation_access = 'case-001,case-002';

-- Query sees only assigned investigations
SELECT * FROM investigations;

-- Result: Only case-001 and case-002 rows returned
-- RLS policy filters automatically
```

---

## �� Development Guide

### Starting the Platform

**Tiny Profile (MinIO + Postgres only):**
```bash
docker-compose --profile tiny up -d
```

**Standard Profile (Full platform - 15 services):**
```bash
docker-compose --profile standard up -d
```

**Streaming Profile (Add Kafka ecosystem):**
```bash
docker-compose --profile streaming up -d
```

**All Services:**
```bash
docker-compose --profile tiny --profile standard --profile streaming up -d
```

### Database Access

**PostgreSQL (Application DB):**
```bash
# psql access
docker exec -it dp_postgres psql -U postgres -d data_platform

# Connect from host
psql postgresql://postgres:postgres@localhost:5432/data_platform
```

**Trino (Query Engine):**
```bash
# Trino CLI
docker exec -it dp_trino trino

# Show catalogs and schemas
trino> SHOW CATALOGS;
trino> SHOW SCHEMAS FROM minio;
trino> SHOW TABLES FROM minio.bronze;
```

### Running ETL Pipelines

```bash
# Manual trigger via Dagster Web UI
open http://localhost:4180  # OAuth-protected
# Or direct: http://localhost:3000

# Run ETL script directly
docker exec -it dp_etl python pipeline.py
```

### Testing Authentication

```bash
# Test Keycloak setup
./scripts/tests/test_keycloak.sh

# Test JWT token generation and RLS
./scripts/tests/test_jwt_rls.sh

# Test security demo (roles + RLS)
./scripts/demo_security.sh
```

### Accessing Services

| Service | URL | Authentication |
|---------|-----|----------------|
| **Dagster (OAuth)** | http://localhost:4180 | Keycloak SSO |
| **Dagster (Direct)** | http://localhost:3000 | None |
| **Keycloak** | http://localhost:8085 | admin/admin |
| **Superset** | http://localhost:8088 | admin/admin |
| **Marquez Web** | http://localhost:3001 | None |
| **Kong Admin** | http://localhost:8001 | None |
| **Konga** | http://localhost:1337 | None |
| **Swagger UI** | http://localhost:8082 | None |
| **MinIO Console** | http://localhost:9001 | minioadmin/minioadmin |

### Environment Variables

All configuration in `.env.example`:

```bash
# Copy and customize
cp .env.example .env
nano .env

# Restart services
docker-compose --profile standard down
docker-compose --profile standard up -d
```

### Logs and Debugging

```bash
# View logs for specific service
docker logs dp_keycloak --tail 100 -f
docker logs dp_oauth2_proxy --tail 50 -f
docker logs dp_dagster --tail 100 -f

# View all service logs
docker-compose logs -f

# Check service health
docker-compose ps
```

---

## 🚀 Production Deployment

### Security Checklist

**Before deploying to production:**

- [ ] **Change all default passwords** in `.env` file
- [ ] **Generate new secrets**:
  ```bash
  # OAuth cookie secret (32 bytes)
  python3 -c "import secrets; print(secrets.token_urlsafe(32)[:32])"
  
  # Keycloak client secrets
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  
  # Database passwords
  python3 -c "import secrets; print(secrets.token_urlsafe(24))"
  ```

- [ ] **Enable SSL/TLS**:
  - Get SSL certificates (Let's Encrypt, corporate CA)
  - Configure NGINX/Traefik reverse proxy
  - Update all `http://` URLs to `https://`
  - Update Keycloak redirect URIs with HTTPS

- [ ] **Harden oauth2-proxy**:
  - Remove `INSECURE_*` flags
  - Set `OAUTH2_PROXY_COOKIE_SECURE: "true"`
  - Enable `OAUTH2_PROXY_COOKIE_SAMESITE: "lax"`
  - Configure proper CA certificates

- [ ] **Secure Keycloak**:
  - Change admin password
  - Enable HTTPS for Keycloak
  - Configure proper SMTP for email verification
  - Set up backup for Keycloak realm configuration

- [ ] **Database Security**:
  - Use separate credentials per service
  - Enable SSL for PostgreSQL connections
  - Restrict database access by IP
  - Regular backups with encryption

- [ ] **Network Segmentation**:
  - Internal services on private network
  - Expose only reverse proxy publicly
  - Use firewall rules for service isolation
  - Enable Docker network encryption

- [ ] **Monitoring & Logging**:
  - Set up centralized logging (ELK, Loki)
  - Configure alerts for authentication failures
  - Monitor oauth2-proxy sessions
  - Track database access patterns

- [ ] **RLS Production Settings**:
  - Review all RLS policies
  - Test with production-like data volume
  - Monitor query performance
  - Set up audit logging for sensitive tables

### Environment-Specific Configuration

**Development:**
```yaml
# .env.development
OAUTH2_PROXY_INSECURE_OIDC_SKIP_ISSUER_VERIFICATION=true
OAUTH2_PROXY_COOKIE_SECURE=false
KEYCLOAK_HOSTNAME=localhost
```

**Staging:**
```yaml
# .env.staging
OAUTH2_PROXY_INSECURE_OIDC_SKIP_ISSUER_VERIFICATION=false
OAUTH2_PROXY_COOKIE_SECURE=true
KEYCLOAK_HOSTNAME=keycloak.staging.example.com
```

**Production:**
```yaml
# .env.production
OAUTH2_PROXY_INSECURE_OIDC_SKIP_ISSUER_VERIFICATION=false
OAUTH2_PROXY_COOKIE_SECURE=true
OAUTH2_PROXY_COOKIE_HTTPONLY=true
OAUTH2_PROXY_COOKIE_SAMESITE=strict
KEYCLOAK_HOSTNAME=keycloak.example.com
SSL_ENABLED=true
```

---

## 🔧 Troubleshooting

### OAuth Issues

**Problem: "Invalid redirect URI"**
```bash
# Check Keycloak client configuration
docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get clients/<CLIENT_UUID> -r data-platform

# Update redirect URIs
./scripts/update_dagster_oidc.sh
```

**Problem: "OIDC discovery failed"**
```bash
# Check Keycloak is accessible from oauth2-proxy container
docker exec dp_oauth2_proxy curl http://keycloak:8080/realms/data-platform/.well-known/openid-configuration

# If fails, check docker network
docker network inspect data-platform_default
```

**Problem: "Cookie secret invalid"**
```bash
# Must be exactly 16, 24, or 32 bytes
# Generate new secret:
python3 -c "import secrets; print(secrets.token_urlsafe(32)[:32])"

# Update docker-compose.yml and restart
docker-compose up -d oauth2-proxy
```

**Problem: "Issuer verification failed"**
```bash
# For development, add to docker-compose.yml:
OAUTH2_PROXY_INSECURE_OIDC_SKIP_ISSUER_VERIFICATION: "true"

# For production, fix issuer URL to use public hostname
OAUTH2_PROXY_OIDC_ISSUER_URL: https://keycloak.example.com/realms/data-platform
```

### Keycloak Issues

**Problem: Keycloak won't start**
```bash
# Check logs
docker logs dp_keycloak --tail 100

# Common causes:
# - Port 8085 already in use
# - Database connection failed
# - Invalid configuration

# Restart with fresh state
docker-compose down
docker volume rm dp_keycloak_data
docker-compose --profile standard up -d keycloak
```

**Problem: Can't login with demo users**
```bash
# Reinitialize Keycloak
./scripts/setup_keycloak.sh

# Check user exists
docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get users -r data-platform --fields username,email
```

### Database Connection Issues

**Problem: "Connection refused" to PostgreSQL**
```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Check from host
psql postgresql://postgres:postgres@localhost:5432/data_platform

# Check from Trino container
docker exec -it dp_trino psql -h postgres -U postgres -d data_platform
```

**Problem: RLS not working**
```bash
# Check session variables are set
SET app.role = 'investigator';
SET app.investigation_access = 'case-001';

# Verify RLS policies exist
SELECT * FROM pg_policies WHERE tablename = 'investigations';

# Test with specific user
./scripts/tests/test_jwt_rls.sh
```

### Service-Specific Issues

**Problem: Dagster won't start**
```bash
# Check logs
docker logs dp_dagster --tail 100

# Common issues:
# - Database not initialized
# - Port 3000 in use
# - Python dependencies missing

# Rebuild if needed
docker-compose build dagster
docker-compose up -d dagster
```

**Problem: Swagger UI shows blank page**
```bash
# Check openapi.yaml exists
docker exec dp_swagger-ui ls -la /openapi.yaml

# Check volume mount
docker inspect dp_swagger-ui | grep -A 10 Mounts

# Should see: ./api/openapi.yaml:/openapi.yaml:ro
```

### Cleanup and Reset

**Full platform reset:**
```bash
# Stop everything
docker-compose --profile standard down

# Remove volumes (WARNING: deletes all data)
docker volume rm dp_postgres_data dp_minio_data dp_keycloak_data

# Restart
docker-compose --profile standard up -d

# Reinitialize authentication
./scripts/setup_keycloak.sh
```

**Quick cleanup (keep data):**
```bash
./scripts/tests/quick_cleanup.sh
```

**Investigation data cleanup:**
```bash
./scripts/tests/cleanup_platform.sh
```

---

## 📚 Additional Documentation

- **Scripts Reference**: See `scripts/README.md` for detailed script usage
- **Cleanup Summary**: See `CLEANUP_SUMMARY.md` for recent project cleanup details
- **Environment Variables**: See `.env.example` for all configuration options
- **Original Documentation**: Backup in `.backup/` directory

---

## 🤝 Contributing

**For new engineers:**

1. Read this README thoroughly
2. Start with tiny profile: `docker-compose --profile tiny up -d`
3. Test authentication: `./scripts/tests/test_keycloak.sh`
4. Explore services via web UIs
5. Review script documentation: `scripts/README.md`
6. Check `.env.example` for configuration options

**Project Structure:**
```
.
├── api/                    # REST API service
├── etl/                    # ETL pipelines (Python)
├── kong/                   # API Gateway config
├── marquez/                # Data lineage config
├── postgres-init/          # Database initialization
├── superset/               # BI tool config
├── trino/                  # Query engine config
├── scripts/                # Management scripts
│   ├── setup/              # Setup scripts
│   └── tests/              # Test scripts
├── docker-compose.yml      # Infrastructure definition
├── .env.example            # Configuration template
└── README.md               # This file
```

---

**Built with ❤️ for data platform engineering**

