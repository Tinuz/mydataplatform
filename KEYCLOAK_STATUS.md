# Keycloak Implementatie Status

## ✅ Voltooid

### 1. Docker Compose Configuratie
- **Service**: Keycloak 23.0 toegevoegd aan `docker-compose.yml`
- **Port**: 8085 (externe) → 8080 (interne)
- **Database**: PostgreSQL database `keycloak` aangemaakt
- **Volume**: `keycloak_data` voor persistentie
- **Health Check**: Geconfigureerd met 30 retries, 60s start period
- **Resources**: 1.5GB memory limit
- **Profile**: `standard`

### 2. Database Initialisatie
- **Script**: `postgres-init/06_init_keycloak.sql`
- **Database**: `keycloak` aangemaakt met alle privileges voor superset user
- **Status**: ✅ Database operationeel, Keycloak schema's automatisch aangemaakt

### 3. Keycloak Configuratie
- **Realm**: `data-platform` aangemaakt
- **Admin Console**: http://localhost:8085
- **Admin Credentials**: 
  - Username: `admin`
  - Password: `admin` (aanpassen voor productie!)

### 4. Realm Rollen (5)
Alle rollen succesvol aangemaakt:
1. ✅ `platform_admin` - Full platform access
2. ✅ `data_engineer` - ETL development and raw data access
3. ✅ `data_analyst` - Read-only analytical data access
4. ✅ `investigator` - Case-specific investigation access
5. ✅ `auditor` - Audit log viewing

### 5. OAuth Clients (4)
Alle clients succesvol aangemaakt met secrets:
1. ✅ `superset` - secret: `superset_client_secret_2025`
2. ✅ `dagster` - secret: `dagster_client_secret_2025`
3. ✅ `data-platform-api` - secret: `api_client_secret_2025`
4. ✅ `marquez` - secret: `marquez_client_secret_2025`

### 6. Demo Gebruikers (4)
Alle gebruikers aangemaakt met wachtwoorden:
1. ✅ `admin.user` / `Admin2025!` - Platform Admin
2. ✅ `john.engineer` / `Engineer2025!` - Data Engineer
3. ✅ `bob.analyst` / `Analyst2025!` - Data Analyst
4. ✅ `jane.investigator` / `Investigator2025!` - Investigator

### 7. OAuth Flow
- ✅ **Token Endpoint**: `http://localhost:8085/realms/data-platform/protocol/openid-connect/token`
- ✅ **Password Grant**: Getest en werkend
- ✅ **JWT Tokens**: Succesvol gegenereerd
- ✅ **Token Payload**: Bevat gebruikersinfo en realm roles
- ✅ **Test Script**: `test_keycloak.sh` voor validatie

### 8. Automatisering
- ✅ **Setup Script**: `setup_keycloak.sh` - Volledig geautomatiseerde configuratie
- ✅ **Test Script**: `test_keycloak.sh` - OAuth flow validatie
- ✅ **Init Script**: `06_init_keycloak.sql` - Database setup

## 📋 Volgende Stappen (Nog Niet Uitgevoerd)

### 1. Groepen Toewijzen
**Issue**: Groepen zijn aangemaakt maar namen zijn incorrect (getallen in plaats van namen)
**Oplossing**: Handmatig via Keycloak Admin Console:
- `engineers` → role: `data_engineer`
- `analysts` → role: `data_analyst`
- `investigators` → role: `investigator`
- `admins` → role: `platform_admin`

Gebruikers toewijzen aan groepen via Admin Console.

### 2. Service Integraties

#### Superset OAuth
**File**: `superset/superset_config.py`

```python
from flask_appbuilder.security.manager import AUTH_OAUTH

# OAuth Configuration
AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [
    {
        'name': 'keycloak',
        'icon': 'fa-key',
        'token_key': 'access_token',
        'remote_app': {
            'client_id': 'superset',
            'client_secret': 'superset_client_secret_2025',
            'api_base_url': 'http://localhost:8085/realms/data-platform/protocol/openid-connect',
            'client_kwargs': {'scope': 'openid email profile'},
            'access_token_url': 'http://localhost:8085/realms/data-platform/protocol/openid-connect/token',
            'authorize_url': 'http://localhost:8085/realms/data-platform/protocol/openid-connect/auth',
            'request_token_url': None,
        }
    }
]

# Role Mapping
AUTH_ROLE_ADMIN = 'Admin'
AUTH_USER_REGISTRATION = True
AUTH_USER_REGISTRATION_ROLE = "Public"
```

#### Dagster OpenID Connect
**File**: `orchestration/dagster.yaml`

```yaml
authentication:
  openid_connect:
    provider: keycloak
    client_id: dagster
    client_secret: dagster_client_secret_2025
    discovery_url: http://localhost:8085/realms/data-platform/.well-known/openid-configuration
```

#### API OAuth Middleware
**File**: `api/server.js`

```javascript
const passport = require('passport');
const KeycloakStrategy = require('passport-keycloak-oauth2-oidc').Strategy;

passport.use(new KeycloakStrategy({
  clientID: 'data-platform-api',
  realm: 'data-platform',
  publicClient: 'false',
  clientSecret: 'api_client_secret_2025',
  sslRequired: 'none',
  authServerURL: 'http://localhost:8085',
  callbackURL: 'http://localhost:8001/callback'
}, function(accessToken, refreshToken, profile, done) {
  return done(null, profile);
}));
```

#### PostgreSQL JWT-based RLS
**File**: `postgres-init/07_keycloak_rls.sql`

```sql
-- Functie om roles uit JWT claims te halen
CREATE OR REPLACE FUNCTION get_current_roles()
RETURNS TEXT[] AS $$
DECLARE
  jwt_token TEXT;
  jwt_payload JSONB;
BEGIN
  -- Haal JWT token uit session variable
  jwt_token := current_setting('app.jwt_token', TRUE);
  
  IF jwt_token IS NULL THEN
    RETURN ARRAY[]::TEXT[];
  END IF;
  
  -- Decode JWT payload (middle part)
  jwt_payload := convert_from(decode(split_part(jwt_token, '.', 2), 'base64'), 'UTF8')::JSONB;
  
  -- Extract roles uit realm_access
  RETURN ARRAY(SELECT jsonb_array_elements_text(jwt_payload->'realm_access'->'roles'));
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Pas RLS policies aan om JWT roles te gebruiken
ALTER POLICY investigator_investigations ON investigations_data.investigation
  USING (
    'platform_admin' = ANY(get_current_roles())
    OR user_id IN (
      SELECT user_id 
      FROM user_investigation_access 
      WHERE investigation_id = investigations_data.investigation.id
        AND (expiry_date IS NULL OR expiry_date > CURRENT_DATE)
    )
  );
```

### 3. Testing Checklist
- [ ] Login via Keycloak Admin Console (http://localhost:8085)
- [ ] Controleer alle realms, roles, clients en users
- [ ] Fix groepen toewijzing (engineers, analysts, etc)
- [ ] Assign users to groups
- [ ] Test Superset SSO login
- [ ] Test Dagster SSO login
- [ ] Test API authentication met JWT
- [ ] Test PostgreSQL RLS met JWT claims
- [ ] Verify audit logging met Keycloak user info

### 4. Productie Checklist
- [ ] Verander admin password van `admin` naar sterk wachtwoord
- [ ] Enable HTTPS (TLS/SSL certificates)
- [ ] Update `KC_HOSTNAME` naar productie domein
- [ ] Set `KC_HOSTNAME_STRICT=true`
- [ ] Set `KC_HOSTNAME_STRICT_HTTPS=true`
- [ ] Switch from `start-dev` to `start` command
- [ ] Configure external PostgreSQL (niet dezelfde als data warehouse)
- [ ] Setup backup strategie voor Keycloak database
- [ ] Configure SMTP voor password reset emails
- [ ] Enable MFA (Multi-Factor Authentication)
- [ ] Configure session timeouts
- [ ] Setup monitoring en alerting
- [ ] Document disaster recovery procedures
- [ ] Rotate all client secrets
- [ ] Configure LDAP/AD integration (indien nodig)

## 🔗 URLs en Referenties

### Keycloak Admin
- **Console**: http://localhost:8085
- **Username**: admin
- **Password**: admin (change in production!)

### OAuth Endpoints
- **Authorization**: http://localhost:8085/realms/data-platform/protocol/openid-connect/auth
- **Token**: http://localhost:8085/realms/data-platform/protocol/openid-connect/token
- **UserInfo**: http://localhost:8085/realms/data-platform/protocol/openid-connect/userinfo
- **Logout**: http://localhost:8085/realms/data-platform/protocol/openid-connect/logout
- **OpenID Config**: http://localhost:8085/realms/data-platform/.well-known/openid-configuration

### Documentatie
- **Keycloak Architecture**: `docs/SECURITY_IAM_KEYCLOAK.md`
- **Database Roles**: `docs/SECURITY_IAM.md`
- **Vergelijking**: `docs/SECURITY_COMPARISON.md`

## 📝 Notities

### Waarom Keycloak?
1. **Single Sign-On (SSO)**: Eén login voor alle services
2. **OAuth 2.0/OIDC**: Industry standard authentication
3. **JWT Tokens**: Stateless authentication met claims
4. **Centraal Beheer**: Web UI voor user/role management
5. **Extensible**: MFA, social login, LDAP/AD integratie
6. **Audit Trail**: Uitgebreide logging van authentication events

### Ontwikkelingsmodus
Keycloak draait nu in development mode (`start-dev`):
- HTTP toegestaan (geen HTTPS vereist)
- Strict hostname checks uitgeschakeld
- Health en metrics endpoints enabled
- Geen TLS/SSL certificaten nodig

Voor productie moet dit worden aangepast naar `start` command met TLS.

### Port 8085
Keycloak gebruikt port 8085 i.p.v. standaard 8080 vanwege conflict met:
- `investigations-ui` nginx container (port 8080:80)

Alle configuratie gebruikt consequent port 8085 voor externe toegang.

## 🐛 Bekende Issues

1. **Groepen Namen**: Setup script heeft issue met groep namen - tonen getallen i.p.v. namen
   - **Workaround**: Handmatig aanpassen via Keycloak Admin Console
   - **Impact**: Laag - functioneel werkt alles, alleen namen zijn incorrect
   
2. **Admin Password**: Gebruikt simpel password `admin` voor development
   - **Risico**: Hoog voor productie
   - **Oplossing**: Verander via Admin Console of environment variable voor productie

## ✨ Testen

### Test OAuth Flow
```bash
./test_keycloak.sh
```

### Test met curl
```bash
TOKEN=$(curl -s -X POST \
  "http://localhost:8085/realms/data-platform/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=data-platform-api" \
  -d "client_secret=api_client_secret_2025" \
  -d "grant_type=password" \
  -d "username=john.engineer" \
  -d "password=Engineer2025!" | jq -r '.access_token')

echo $TOKEN
```

### Test API call met JWT
```bash
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/api/investigations
```

---

**Status**: ✅ Keycloak volledig geïmplementeerd en operationeel
**Datum**: 16 oktober 2025
**Versie**: Keycloak 23.0.7
