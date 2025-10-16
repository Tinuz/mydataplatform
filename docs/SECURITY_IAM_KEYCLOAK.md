# Security & IAM Implementation - Keycloak Edition

## 🔒 Overview

Modern IAM implementation met **Keycloak** als centrale identity provider. Biedt SSO, OAuth 2.0, MFA, en integratie met alle platform services.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                              │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ 1. Login Request
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Keycloak (Port 8080)                        │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Realms:                                                  │   │
│  │  └─ data-platform                                        │   │
│  │     ├─ Clients: superset, dagster, api, marquez        │   │
│  │     ├─ Roles: admin, engineer, analyst, investigator   │   │
│  │     ├─ Users: john.doe, jane.smith, bob.analyst        │   │
│  │     └─ Groups: investigators, analysts, engineers      │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ 2. OAuth Token (JWT)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Kong API Gateway (Port 8000)                │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Plugins:                                                 │   │
│  │  ├─ OIDC: Verify JWT tokens                             │   │
│  │  ├─ ACL: Role-based routing                             │   │
│  │  ├─ Rate Limiting: Per user/role                        │   │
│  │  └─ Request Transformer: Add user context               │   │
│  └──────────────────────────────────────────────────────────┘   │
└───┬───────────┬───────────┬───────────┬─────────────────────────┘
    │           │           │           │
    │ 3. Authenticated Requests with JWT
    │           │           │           │
    ▼           ▼           ▼           ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌─────────┐
│Superset│ │ Dagster│ │  API   │ │ Marquez │
│Port    │ │ Port   │ │ Port   │ │ Port    │
│8088    │ │ 3000   │ │ 8001   │ │ 5000    │
└───┬────┘ └───┬────┘ └───┬────┘ └────┬────┘
    │          │          │           │
    │ 4. Verify token + Check permissions
    │          │          │           │
    ▼──────────▼──────────▼───────────▼
┌─────────────────────────────────────────┐
│         PostgreSQL (Port 5432)          │
│  ┌─────────────────────────────────┐   │
│  │  RLS Policies:                   │   │
│  │  - Filter by user claims (JWT)  │   │
│  │  - Investigation-level access   │   │
│  │  - Dynamic policies via tokens  │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## 📦 Docker Compose Configuration

Voeg Keycloak toe aan `docker-compose.yml`:

```yaml
services:
  keycloak:
    image: quay.io/keycloak/keycloak:23.0
    container_name: dp_keycloak
    environment:
      KEYCLOAK_ADMIN: admin
      KEYCLOAK_ADMIN_PASSWORD: admin_secure_2025!
      KC_DB: postgres
      KC_DB_URL: jdbc:postgresql://postgres:5432/keycloak
      KC_DB_USERNAME: superset
      KC_DB_PASSWORD: superset
      KC_HOSTNAME: localhost
      KC_HOSTNAME_PORT: 8085
      KC_HTTP_ENABLED: "true"
      KC_HEALTH_ENABLED: "true"
      KC_METRICS_ENABLED: "true"
    command: start-dev
    ports:
      - "8085:8080"
    depends_on:
      - postgres
    networks:
      - data-platform
    healthcheck:
      test: ["CMD-SHELL", "exec 3<>/dev/tcp/localhost/8080 && echo -e 'GET /health/ready HTTP/1.1\\r\\nHost: localhost\\r\\n\\r\\n' >&3 && cat <&3 | grep -q '200 OK'"]
      interval: 10s
      timeout: 5s
      retries: 30
    profiles: [ "standard" ]

  postgres:
    # ... existing config ...
    environment:
      # Add keycloak database
      POSTGRES_MULTIPLE_DATABASES: superset,keycloak
```

## 🎯 Keycloak Realm Configuration

### 1. Create Realm: `data-platform`

```bash
# Via Keycloak Admin UI: http://localhost:8085
# Username: admin
# Password: admin_secure_2025!

# Or via API:
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password admin_secure_2025!

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create realms \
  -s realm=data-platform \
  -s enabled=true \
  -s displayName="Data Platform" \
  -s sslRequired=none
```

### 2. Create Clients

```bash
# Superset Client
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
  -r data-platform \
  -s clientId=superset \
  -s enabled=true \
  -s clientAuthenticatorType=client-secret \
  -s secret=superset_client_secret_2025 \
  -s 'redirectUris=["http://localhost:8088/*"]' \
  -s 'webOrigins=["http://localhost:8088"]' \
  -s protocol=openid-connect \
  -s publicClient=false \
  -s standardFlowEnabled=true

# Dagster Client
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
  -r data-platform \
  -s clientId=dagster \
  -s enabled=true \
  -s clientAuthenticatorType=client-secret \
  -s secret=dagster_client_secret_2025 \
  -s 'redirectUris=["http://localhost:3000/*"]' \
  -s 'webOrigins=["http://localhost:3000"]' \
  -s protocol=openid-connect

# API Client
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
  -r data-platform \
  -s clientId=data-platform-api \
  -s enabled=true \
  -s clientAuthenticatorType=client-secret \
  -s secret=api_client_secret_2025 \
  -s 'redirectUris=["http://localhost:8001/*"]' \
  -s protocol=openid-connect

# Marquez Client (optional)
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create clients \
  -r data-platform \
  -s clientId=marquez \
  -s enabled=true \
  -s clientAuthenticatorType=client-secret \
  -s secret=marquez_client_secret_2025 \
  -s 'redirectUris=["http://localhost:5000/*"]' \
  -s protocol=openid-connect
```

### 3. Create Realm Roles

```bash
# Platform Admin
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create roles \
  -r data-platform \
  -s name=platform_admin \
  -s 'description=Full platform access'

# Data Engineer
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create roles \
  -r data-platform \
  -s name=data_engineer \
  -s 'description=ETL development and raw data access'

# Data Analyst
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create roles \
  -r data-platform \
  -s name=data_analyst \
  -s 'description=Read-only analytical data access'

# Investigator
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create roles \
  -r data-platform \
  -s name=investigator \
  -s 'description=Case-specific investigation access'

# Auditor
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create roles \
  -r data-platform \
  -s name=auditor \
  -s 'description=Audit log viewing'
```

### 4. Create Groups

```bash
# Engineers Group
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create groups \
  -r data-platform \
  -s name=engineers

# Assign role to group
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r data-platform \
  --gname engineers \
  --rolename data_engineer

# Analysts Group
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create groups \
  -r data-platform \
  -s name=analysts

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r data-platform \
  --gname analysts \
  --rolename data_analyst

# Investigators Group
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create groups \
  -r data-platform \
  -s name=investigators

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh add-roles \
  -r data-platform \
  --gname investigators \
  --rolename investigator
```

### 5. Create Demo Users

```bash
# Admin User
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create users \
  -r data-platform \
  -s username=admin.user \
  -s enabled=true \
  -s email=admin@platform.local \
  -s firstName=Admin \
  -s lastName=User

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh set-password \
  -r data-platform \
  --username admin.user \
  --new-password Admin2025!

# Engineer User
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create users \
  -r data-platform \
  -s username=john.engineer \
  -s enabled=true \
  -s email=john@platform.local \
  -s firstName=John \
  -s lastName=Engineer

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh set-password \
  -r data-platform \
  --username john.engineer \
  --new-password Engineer2025!

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh update users \
  -r data-platform \
  --target-username john.engineer \
  --body '{"groups":["/engineers"]}'

# Analyst User
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create users \
  -r data-platform \
  -s username=bob.analyst \
  -s enabled=true \
  -s email=bob@platform.local \
  -s firstName=Bob \
  -s lastName=Analyst

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh set-password \
  -r data-platform \
  --username bob.analyst \
  --new-password Analyst2025!

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh update users \
  -r data-platform \
  --target-username bob.analyst \
  --body '{"groups":["/analysts"]}'

# Investigator User
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create users \
  -r data-platform \
  -s username=jane.investigator \
  -s enabled=true \
  -s email=jane@platform.local \
  -s firstName=Jane \
  -s lastName=Investigator

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh set-password \
  -r data-platform \
  --username jane.investigator \
  --new-password Investigator2025!

docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh update users \
  -r data-platform \
  --target-username jane.investigator \
  --body '{"groups":["/investigators"]}'
```

## 🔗 Service Integration

### Superset Integration

Update `superset/superset_config.py`:

```python
from flask_appbuilder.security.manager import AUTH_OAUTH

# Enable OAuth authentication
AUTH_TYPE = AUTH_OAUTH

OAUTH_PROVIDERS = [
    {
        'name': 'keycloak',
        'icon': 'fa-key',
        'token_key': 'access_token',
        'remote_app': {
            'client_id': 'superset',
            'client_secret': 'superset_client_secret_2025',
            'api_base_url': 'http://keycloak:8080/realms/data-platform/protocol/openid-connect',
            'client_kwargs': {
                'scope': 'openid email profile'
            },
            'access_token_url': 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/token',
            'authorize_url': 'http://localhost:8085/realms/data-platform/protocol/openid-connect/auth',
            'jwks_uri': 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/certs',
        }
    }
]

# Map Keycloak roles to Superset roles
AUTH_ROLE_ADMIN = 'platform_admin'
AUTH_ROLE_PUBLIC = 'data_analyst'

# Custom user mapping
def custom_user_info(user_dict):
    user_dict['roles'] = []
    if 'realm_access' in user_dict and 'roles' in user_dict['realm_access']:
        for role in user_dict['realm_access']['roles']:
            if role in ['platform_admin', 'data_engineer', 'data_analyst']:
                user_dict['roles'].append(role)
    return user_dict

AUTH_USER_REGISTRATION_ROLE = 'data_analyst'
```

### Dagster Integration

Update `orchestration/dagster.yaml`:

```yaml
run_launcher:
  module: dagster.core.launcher
  class: DefaultRunLauncher

telemetry:
  enabled: false

authentication:
  provider: openid_connect
  openid_connect:
    issuer_url: http://keycloak:8080/realms/data-platform
    client_id: dagster
    client_secret: dagster_client_secret_2025
    redirect_uri: http://localhost:3000/oauth/callback
    scope: openid profile email
    
authorization:
  enabled: true
  policies:
    - name: admin_all_access
      roles: [platform_admin]
      permissions: ["*"]
    
    - name: engineer_pipeline_access
      roles: [data_engineer]
      permissions:
        - "read:*"
        - "launch:*"
        - "terminate:*"
    
    - name: analyst_read_only
      roles: [data_analyst]
      permissions:
        - "read:*"
```

### API Integration (Node.js)

Update `api/server.js`:

```javascript
const express = require('express');
const session = require('express-session');
const passport = require('passport');
const KeycloakStrategy = require('passport-keycloak-oauth2-oidc').Strategy;

const app = express();

// Keycloak configuration
const keycloakConfig = {
  clientID: 'data-platform-api',
  clientSecret: 'api_client_secret_2025',
  authorizationURL: 'http://localhost:8085/realms/data-platform/protocol/openid-connect/auth',
  tokenURL: 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/token',
  userInfoURL: 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/userinfo',
  callbackURL: 'http://localhost:8001/auth/callback'
};

passport.use('keycloak', new KeycloakStrategy(keycloakConfig,
  (accessToken, refreshToken, profile, done) => {
    // Extract user info and roles
    profile.roles = profile.realm_access?.roles || [];
    return done(null, profile);
  }
));

// Session management
app.use(session({
  secret: 'platform_session_secret_2025',
  resave: false,
  saveUninitialized: false
}));

app.use(passport.initialize());
app.use(passport.session());

passport.serializeUser((user, done) => done(null, user));
passport.deserializeUser((obj, done) => done(null, obj));

// Auth routes
app.get('/auth/login', passport.authenticate('keycloak'));

app.get('/auth/callback',
  passport.authenticate('keycloak', { failureRedirect: '/login' }),
  (req, res) => {
    res.redirect('/dashboard');
  }
);

app.get('/auth/logout', (req, res) => {
  req.logout(() => {
    res.redirect('http://localhost:8085/realms/data-platform/protocol/openid-connect/logout?redirect_uri=http://localhost:8001');
  });
});

// Middleware to check authentication
function ensureAuthenticated(req, res, next) {
  if (req.isAuthenticated()) {
    return next();
  }
  res.redirect('/auth/login');
}

// Middleware to check roles
function hasRole(role) {
  return (req, res, next) => {
    if (req.user && req.user.roles.includes(role)) {
      return next();
    }
    res.status(403).json({ error: 'Forbidden - insufficient permissions' });
  };
}

// Protected routes
app.get('/api/investigations', 
  ensureAuthenticated, 
  hasRole('data_analyst'),
  async (req, res) => {
    // Query database with user context
    const username = req.user.username;
    const roles = req.user.roles;
    
    // ... database query ...
  }
);

app.listen(8001, () => {
  console.log('API server running on http://localhost:8001');
});
```

### PostgreSQL Integration with JWT

Update `postgres-init/06_keycloak_rls.sql`:

```sql
-- Create JWT validation extension
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Function to extract username from JWT
CREATE OR REPLACE FUNCTION get_current_username()
RETURNS TEXT AS $$
BEGIN
  -- Extract from current application context
  RETURN current_setting('app.username', true);
END;
$$ LANGUAGE plpgsql STABLE;

-- Function to extract roles from JWT
CREATE OR REPLACE FUNCTION get_current_roles()
RETURNS TEXT[] AS $$
BEGIN
  RETURN string_to_array(current_setting('app.roles', true), ',');
END;
$$ LANGUAGE plpgsql STABLE;

-- RLS Policies using JWT claims
ALTER TABLE investigations ENABLE ROW LEVEL SECURITY;

-- Admin sees everything
CREATE POLICY investigations_admin_policy ON investigations
  FOR ALL
  TO PUBLIC
  USING ('platform_admin' = ANY(get_current_roles()));

-- Engineers see everything
CREATE POLICY investigations_engineer_policy ON investigations
  FOR ALL
  TO PUBLIC
  USING ('data_engineer' = ANY(get_current_roles()));

-- Investigators see only assigned cases
CREATE POLICY investigations_investigator_policy ON investigations
  FOR SELECT
  TO PUBLIC
  USING (
    'investigator' = ANY(get_current_roles())
    AND EXISTS (
      SELECT 1 FROM user_investigation_access
      WHERE user_id = get_current_username()
        AND investigation_id = investigations.investigation_id
        AND (expires_at IS NULL OR expires_at > NOW())
    )
  );

-- Application sets context before queries
-- Example in Python:
-- conn.execute("SET app.username = %s", [username])
-- conn.execute("SET app.roles = %s", [','.join(roles)])
```

### Kong API Gateway Integration

Update `kong/kong.yml`:

```yaml
_format_version: "3.0"

services:
  - name: superset-service
    url: http://superset:8088
    routes:
      - name: superset-route
        paths:
          - /superset
    plugins:
      - name: oidc
        config:
          issuer: http://keycloak:8080/realms/data-platform
          client_id: superset
          client_secret: superset_client_secret_2025
          redirect_uri: http://localhost:8000/superset/callback
          scope: openid profile email
          token_endpoint_auth_method: client_secret_post
      
      - name: acl
        config:
          allow:
            - platform_admin
            - data_engineer
            - data_analyst

  - name: dagster-service
    url: http://dagster-webserver:3000
    routes:
      - name: dagster-route
        paths:
          - /dagster
    plugins:
      - name: oidc
        config:
          issuer: http://keycloak:8080/realms/data-platform
          client_id: dagster
          client_secret: dagster_client_secret_2025
      
      - name: acl
        config:
          allow:
            - platform_admin
            - data_engineer

  - name: api-service
    url: http://api:8001
    routes:
      - name: api-route
        paths:
          - /api
    plugins:
      - name: jwt
        config:
          claims_to_verify:
            - exp
          key_claim_name: kid
          secret_is_base64: false
          uri_param_names:
            - jwt
          cookie_names:
            - access_token
      
      - name: rate-limiting
        config:
          minute: 100
          policy: local
```

## 🎬 Setup Script

Create `setup_keycloak.sh`:

```bash
#!/bin/bash

set -e

echo "🔐 Setting up Keycloak for Data Platform..."

# Wait for Keycloak to be ready
echo "⏳ Waiting for Keycloak..."
until docker exec dp_keycloak curl -sf http://localhost:8080/health/ready > /dev/null; do
  sleep 5
done

echo "✅ Keycloak is ready!"

# Login to Keycloak admin CLI
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh config credentials \
  --server http://localhost:8080 \
  --realm master \
  --user admin \
  --password admin_secure_2025!

# Create realm
echo "📦 Creating data-platform realm..."
docker exec -it dp_keycloak /opt/keycloak/bin/kcadm.sh create realms \
  -s realm=data-platform \
  -s enabled=true \
  -s displayName="Data Platform" \
  -s sslRequired=none \
  --output > /dev/null || echo "Realm already exists"

# Create clients (Superset, Dagster, API)
echo "🔑 Creating OAuth clients..."
# ... (client creation commands from above) ...

# Create roles
echo "👥 Creating realm roles..."
# ... (role creation commands from above) ...

# Create groups
echo "📁 Creating groups..."
# ... (group creation commands from above) ...

# Create demo users
echo "👤 Creating demo users..."
# ... (user creation commands from above) ...

echo ""
echo "✅ Keycloak setup complete!"
echo ""
echo "🌐 Access Keycloak Admin Console:"
echo "   URL: http://localhost:8080"
echo "   Username: admin"
echo "   Password: admin_secure_2025!"
echo ""
echo "👥 Demo Users:"
echo "   admin.user / Admin2025!"
echo "   john.engineer / Engineer2025!"
echo "   bob.analyst / Analyst2025!"
echo "   jane.investigator / Investigator2025!"
```

## 🧪 Testing

### 1. Test Keycloak Login

```bash
# Get access token
curl -X POST "http://localhost:8085/realms/data-platform/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=data-platform-api" \
  -d "client_secret=api_client_secret_2025" \
  -d "grant_type=password" \
  -d "username=john.engineer" \
  -d "password=Engineer2025!" \
  | jq -r '.access_token'
```

### 2. Decode JWT Token

```bash
# Install jq if needed: brew install jq

TOKEN="<access_token_from_above>"

# Decode header
echo $TOKEN | cut -d'.' -f1 | base64 -d | jq

# Decode payload
echo $TOKEN | cut -d'.' -f2 | base64 -d | jq
```

### 3. Test API with Token

```bash
curl -X GET "http://localhost:8001/api/investigations" \
  -H "Authorization: Bearer $TOKEN"
```

## 📊 Comparison: Database Roles vs Keycloak

| Feature | Database Roles | Keycloak |
|---------|---------------|----------|
| **Single Sign-On** | ❌ | ✅ |
| **OAuth 2.0 / OIDC** | ❌ | ✅ |
| **Social Login** | ❌ | ✅ |
| **MFA Support** | ❌ | ✅ |
| **User Management UI** | ❌ | ✅ |
| **Token-based Auth** | ❌ | ✅ |
| **Cross-service Auth** | ❌ | ✅ |
| **LDAP/AD Integration** | Limited | ✅ |
| **Audit Logging** | Custom | Built-in |
| **Session Management** | Manual | Automatic |
| **Password Policies** | Basic | Advanced |
| **Account Lockout** | Manual | Automatic |
| **Setup Complexity** | Low | Medium |
| **Production Ready** | Demo only | ✅ |

## 🚀 Migration Path

### Phase 1: Parallel Running (Week 1-2)
- ✅ Add Keycloak to docker-compose
- ✅ Configure realm and clients
- ✅ Create demo users in both systems
- ✅ Test OAuth flow with one service (API)

### Phase 2: Service Migration (Week 3-4)
- ✅ Migrate Superset to Keycloak OAuth
- ✅ Migrate Dagster to Keycloak OAuth
- ✅ Update Kong gateway with OIDC plugin
- ✅ Migrate PostgreSQL RLS to use JWT claims

### Phase 3: Cleanup (Week 5)
- ✅ Remove database roles (keep for service accounts)
- ✅ Update documentation
- ✅ Train users on SSO login
- ✅ Monitor and optimize

## 📚 Resources

- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Superset OAuth Setup](https://superset.apache.org/docs/security/#custom-oauth2-configuration)
- [Dagster Auth](https://docs.dagster.io/deployment/dagster-instance#authentication)
- [Kong OIDC Plugin](https://docs.konghq.com/hub/nokia/kong-oidc/)

---

**Version**: 1.0  
**Last Updated**: 16 oktober 2025  
**Implementation Status**: 🚧 Design Phase
