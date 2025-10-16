# Keycloak OAuth + JWT-Based RLS Implementation

Complete implementatie van enterprise-grade authentication en authorization voor het Data Platform.

## 🎯 Wat is er gebouwd?

### 1. **Keycloak Identity Provider**
- OAuth 2.0 / OpenID Connect server
- Centraal beheer van users, roles en clients
- Single Sign-On (SSO) voor alle services
- **URL**: http://localhost:8085
- **Admin**: admin / admin

### 2. **JWT-Based Row-Level Security**
- PostgreSQL functies om JWT tokens te decoderen
- Automatische role extraction uit Keycloak tokens
- RLS policies gebruiken JWT claims voor authorization
- Hybride mode: ondersteunt zowel JWT als database roles

### 3. **Demo Scripts**
- **setup_keycloak.sh**: Automatische Keycloak configuratie
- **assign_keycloak_roles.sh**: Realm roles toewijzen aan users
- **test_keycloak.sh**: OAuth flow testen
- **test_jwt_rls.sh**: JWT + RLS functionaliteit testen
- **demo_keycloak_jwt_rls.py**: End-to-end Python demo

## 🚀 Quick Start

### Stap 1: Start Keycloak
```bash
docker-compose --profile standard up -d keycloak
```

### Stap 2: Configureer Keycloak (eerste keer)
```bash
./setup_keycloak.sh
./assign_keycloak_roles.sh
```

### Stap 3: Test de setup
```bash
# Test OAuth flow
./test_keycloak.sh

# Test JWT + RLS
./test_jwt_rls.sh

# Run end-to-end demo
python3 demo_keycloak_jwt_rls.py
```

## 👥 Demo Gebruikers

| Username | Password | Role | Rechten |
|----------|----------|------|---------|
| admin.user | Admin2025! | platform_admin | Volledige toegang tot alles |
| john.engineer | Engineer2025! | data_engineer | ETL, raw data, create tables |
| bob.analyst | Analyst2025! | data_analyst | Read-only canonical data (PII masked) |
| jane.investigator | Investigator2025! | investigator | Alleen toegewezen onderzoeken |

## 🔐 OAuth Clients

| Client ID | Secret | Redirect URI | Gebruik |
|-----------|--------|--------------|---------|
| superset | superset_client_secret_2025 | http://localhost:8088/* | Superset SSO |
| dagster | dagster_client_secret_2025 | http://localhost:3000/* | Dagster SSO |
| data-platform-api | api_client_secret_2025 | http://localhost:8001/* | API OAuth |
| marquez | marquez_client_secret_2025 | http://localhost:5000/* | Marquez SSO |

## 📋 Realm Roles

De volgende realm roles zijn aangemaakt en mappen 1-op-1 naar database permissions:

1. **platform_admin**
   - Volledige toegang tot alle data
   - Kan configuratie wijzigen
   - Ziet alle onderzoeken en PII data

2. **data_engineer**
   - ETL development en raw data toegang
   - Kan tabellen aanmaken en wijzigen
   - Ziet alle onderzoeken

3. **data_analyst**
   - Read-only toegang tot canonical data
   - PII data is gemaskeerd
   - Ziet geen raw data

4. **investigator**
   - Toegang tot specifieke onderzoeken alleen
   - Moet expliciet toegang krijgen via `user_investigation_access`
   - Ziet alleen data van toegewezen onderzoeken

5. **auditor**
   - Read-only toegang tot audit logs
   - Kan geen data wijzigen

## 🔧 PostgreSQL JWT Functies

### Beschikbare Functies

```sql
-- Decode JWT payload
SELECT decode_jwt_payload('eyJhbG...');

-- Get username uit JWT
SELECT get_jwt_username();

-- Get email uit JWT
SELECT get_jwt_email();

-- Get alle roles uit JWT
SELECT get_jwt_roles();

-- Check of user een role heeft
SELECT has_role('data_engineer');

-- Get effective username (JWT of database user)
SELECT get_effective_user();
```

### Gebruik in Applicatie

```python
import psycopg2

# 1. Get JWT token van Keycloak
token = get_keycloak_token(username, password)
access_token = token['access_token']

# 2. Connect naar PostgreSQL
conn = psycopg2.connect(**pg_config)
cur = conn.cursor()

# 3. Set JWT token in session
cur.execute("SET app.jwt_token = %s;", (access_token,))

# 4. Execute queries - RLS gebruikt automatisch JWT claims
cur.execute("SELECT * FROM investigations;")
# Resultaten zijn gefilterd op basis van JWT roles!
```

## 🛡️ RLS Policies

Alle RLS policies ondersteunen nu JWT authentication:

### Investigations Table
```sql
-- Users zien alleen onderzoeken waar ze toegang toe hebben
CREATE POLICY investigator_jwt_access_policy ON investigations
    FOR SELECT
    USING (
        has_role('platform_admin')  -- Admins zien alles
        OR has_role('data_engineer')  -- Engineers zien alles
        OR (
            has_role('investigator')  -- Investigators zien alleen toegewezen
            AND investigation_id IN (
                SELECT investigation_id 
                FROM user_investigation_access 
                WHERE user_id = get_effective_user()
            )
        )
    );
```

### Transacties, Calls, Messages
- Admins en Engineers: Zien alles
- Investigators: Alleen van toegewezen onderzoeken
- Analysts: Geen toegang tot raw data

### Canonical Data
- Admins, Engineers, Analysts: Zien alle data
- Analysts: PII is gemaskeerd (via views)
- Investigators: Alleen van toegewezen onderzoeken

## 📊 Flow Diagram

```
┌─────────────┐     OAuth 2.0      ┌──────────────┐
│             │◄──────────────────►│              │
│  Frontend   │   1. Authenticate  │  Keycloak    │
│ Application │   2. Get JWT Token │   :8085      │
│             │                     │              │
└──────┬──────┘                     └──────────────┘
       │                                   │
       │ 3. Include JWT                    │ JWT contains:
       │    in requests                    │ - username
       │                                   │ - email  
       ▼                                   │ - realm_access.roles
┌─────────────┐                           │
│             │  4. SET app.jwt_token     │
│  Backend    │     = 'eyJhbG...'         │
│    API      │                            │
│             │                            │
└──────┬──────┘                           │
       │                                   │
       │ 5. Execute SQL                   │
       │    queries                        │
       ▼                                   ▼
┌─────────────────────────────────────────┐
│         PostgreSQL :5432                │
│                                          │
│  ┌────────────────────────────────┐   │
│  │  JWT Functions                  │   │
│  │  - decode_jwt_payload()         │   │
│  │  - get_jwt_roles()              │   │
│  │  - has_role()                   │   │
│  └────────────────────────────────┘   │
│                                          │
│  ┌────────────────────────────────┐   │
│  │  RLS Policies                   │   │
│  │  - Use has_role() to check      │   │
│  │  - Filter rows per user         │   │
│  │  - Automatic based on JWT       │   │
│  └────────────────────────────────┘   │
│                                          │
│  6. Return filtered data                │
└─────────────────────────────────────────┘
```

## 🔍 Testing & Validation

### Test 1: OAuth Flow
```bash
./test_keycloak.sh
```
Expected: JWT token met user claims en roles

### Test 2: JWT Decoding
```bash
./test_jwt_rls.sh
```
Expected: Roles worden correct geëxtraheerd uit JWT

### Test 3: End-to-End
```bash
python3 demo_keycloak_jwt_rls.py
```
Expected: 
- Admin/Engineer zien alle data
- Analyst ziet canonical data (PII masked)
- Investigator ziet alleen toegewezen onderzoeken

### Test 4: Manual SQL Test
```bash
docker exec -i dp_postgres psql -U superset -d superset <<EOF
-- Get token (gebruik output van test_keycloak.sh)
SET app.jwt_token = 'eyJhbGci...';

-- Check wie je bent
SELECT 
  get_jwt_username() as user,
  get_jwt_roles() as roles,
  has_role('data_engineer') as is_engineer;

-- Query data (RLS filtering happens automatically)
SELECT * FROM investigations;
EOF
```

## 📁 File Structure

```
data-platform/
├── docker-compose.yml              # Keycloak service op port 8085
├── postgres-init/
│   ├── 05_security_rbac.sql       # Database roles en basis RLS
│   ├── 06_init_keycloak.sql       # Keycloak database setup
│   └── 07_jwt_rls.sql             # JWT functies en RLS policies
├── setup_keycloak.sh               # Keycloak configuratie script
├── assign_keycloak_roles.sh        # Assign roles aan users
├── test_keycloak.sh                # Test OAuth flow
├── test_jwt_rls.sh                 # Test JWT + RLS
├── demo_keycloak_jwt_rls.py        # End-to-end Python demo
├── docs/
│   ├── SECURITY_IAM.md            # Database roles documentatie
│   ├── SECURITY_IAM_KEYCLOAK.md   # Keycloak implementatie guide
│   └── SECURITY_COMPARISON.md      # Vergelijking beide approaches
└── KEYCLOAK_STATUS.md              # Implementatie status
```

## 🔗 Keycloak Endpoints

### Admin Console
- **URL**: http://localhost:8085
- **Realm**: master → data-platform

### OAuth Endpoints
- **Authorization**: http://localhost:8085/realms/data-platform/protocol/openid-connect/auth
- **Token**: http://localhost:8085/realms/data-platform/protocol/openid-connect/token
- **UserInfo**: http://localhost:8085/realms/data-platform/protocol/openid-connect/userinfo
- **Logout**: http://localhost:8085/realms/data-platform/protocol/openid-connect/logout
- **OpenID Config**: http://localhost:8085/realms/data-platform/.well-known/openid-configuration

## ⚙️ Volgende Stappen

### 1. Superset OAuth Integratie
**File**: `superset/superset_config.py`
```python
AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [{
    'name': 'keycloak',
    'remote_app': {
        'client_id': 'superset',
        'client_secret': 'superset_client_secret_2025',
        'api_base_url': 'http://localhost:8085/realms/data-platform/protocol/openid-connect',
        # ...
    }
}]
```

### 2. Dagster OIDC Integratie
**File**: `orchestration/dagster.yaml`
```yaml
authentication:
  openid_connect:
    provider: keycloak
    client_id: dagster
    client_secret: dagster_client_secret_2025
    discovery_url: http://localhost:8085/realms/data-platform/.well-known/openid-configuration
```

### 3. API OAuth Middleware
**File**: `api/server.js`
```javascript
const KeycloakStrategy = require('passport-keycloak-oauth2-oidc').Strategy;

passport.use(new KeycloakStrategy({
  clientID: 'data-platform-api',
  clientSecret: 'api_client_secret_2025',
  authServerURL: 'http://localhost:8085',
  realm: 'data-platform'
}, ...));
```

### 4. Investigation Access Management
Maak users toegang geven tot specifieke onderzoeken:
```sql
-- Grant access to jane.investigator for investigation OND-2025-000001
INSERT INTO user_investigation_access (user_id, investigation_id, access_level)
VALUES ('jane.investigator', 'OND-2025-000001', 'read');

-- Now jane can see this investigation when querying with JWT
```

## 🐛 Troubleshooting

### Token niet geaccepteerd
```bash
# Check of Keycloak draait
docker-compose ps keycloak

# Check Keycloak logs
docker logs dp_keycloak

# Test token endpoint
curl http://localhost:8085/realms/data-platform/protocol/openid-connect/token \
  -d "client_id=data-platform-api" \
  -d "client_secret=api_client_secret_2025" \
  -d "grant_type=password" \
  -d "username=john.engineer" \
  -d "password=Engineer2025!"
```

### Roles niet in JWT
```bash
# Check user roles via Keycloak Admin Console
# Of via API:
docker exec dp_keycloak /opt/keycloak/bin/kcadm.sh get users \
  -r data-platform \
  -q username=john.engineer

# Re-assign roles
./assign_keycloak_roles.sh
```

### RLS geeft geen resultaten
```bash
# Check of user access heeft
SELECT * FROM user_investigation_access WHERE user_id = 'jane.investigator';

# Check RLS policies
\d+ investigations

# Test zonder RLS (als admin)
SET ROLE platform_admin;
SELECT * FROM investigations;
```

## 📚 Referenties

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [OAuth 2.0 Specification](https://oauth.net/2/)
- [PostgreSQL RLS](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [JWT.io](https://jwt.io/) - Decode en inspect JWT tokens

## ✅ Status

| Component | Status | Details |
|-----------|--------|---------|
| Keycloak Service | ✅ | Running op port 8085 |
| Realm Setup | ✅ | data-platform realm met 5 roles |
| OAuth Clients | ✅ | 4 clients configured |
| Demo Users | ✅ | 4 users met roles |
| JWT Functions | ✅ | 6 PostgreSQL functies |
| RLS Policies | ✅ | Updated voor JWT support |
| Testing Scripts | ✅ | OAuth, JWT, RLS, End-to-end |
| Superset SSO | ⏳ | Configuration ready, not integrated |
| Dagster SSO | ⏳ | Configuration ready, not integrated |
| API OAuth | ⏳ | Configuration ready, not integrated |

---

**Last Updated**: 16 oktober 2025  
**Keycloak Version**: 23.0.7  
**PostgreSQL Version**: 16
