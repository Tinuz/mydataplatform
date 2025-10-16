# IAM/Security Implementatie - Opties

## 📊 Overzicht

Het platform ondersteunt twee security implementaties:

| Aspect | **Database Roles** (Simple) | **Keycloak** (Enterprise) |
|--------|----------------------------|---------------------------|
| **Status** | ✅ Geïmplementeerd | 📋 Design fase |
| **Complexiteit** | ⭐ Laag | ⭐⭐⭐ Hoog |
| **Setup tijd** | 5 minuten | 1-2 dagen |
| **Production ready** | Demo/POC only | ✅ Enterprise |
| **Single Sign-On** | ❌ | ✅ |
| **OAuth 2.0 / OIDC** | ❌ | ✅ |
| **Social Login** | ❌ | ✅ (GitHub, Google, etc.) |
| **MFA Support** | ❌ | ✅ |
| **User Management UI** | ❌ (SQL only) | ✅ (Web UI) |
| **LDAP/AD Integration** | ❌ | ✅ |
| **Token-based Auth** | ❌ | ✅ (JWT) |
| **Cross-service Auth** | ❌ | ✅ |
| **Audit Logging** | ✅ Custom | ✅ Built-in |
| **Password Policies** | Basic | ✅ Advanced |
| **Session Management** | Manual | ✅ Automatic |
| **Account Lockout** | Manual | ✅ Automatic |

## 🎯 Keuze Matrix

### Use Case: **Demo / POC / Internal Only**
👉 **Kies voor: Database Roles**

**Voordelen**:
- ✅ Direct klaar (al geïmplementeerd)
- ✅ Geen extra containers
- ✅ Simpel te begrijpen
- ✅ RLS en PII masking werkt prima
- ✅ Audit logging aanwezig

**Nadelen**:
- ⚠️ Geen SSO
- ⚠️ Handmatige user management
- ⚠️ Geen MFA
- ⚠️ Niet schaalbaar

**Implementatie**:
```bash
# Al klaar! Alleen activeren:
docker-compose down
docker-compose up -d
./demo_security.sh
```

### Use Case: **Production / External Users / Enterprise**
👉 **Kies voor: Keycloak**

**Voordelen**:
- ✅ Enterprise-grade security
- ✅ SSO voor alle services
- ✅ OAuth 2.0 / OpenID Connect
- ✅ MFA support
- ✅ LDAP/AD integratie mogelijk
- ✅ Social login (GitHub, Google)
- ✅ Web-based user management
- ✅ Token-based (JWT)
- ✅ Session management
- ✅ Password policies

**Nadelen**:
- ⚠️ Extra container (300MB+)
- ⚠️ Complexe setup (1-2 dagen)
- ⚠️ Requires code changes in alle services
- ⚠️ Steiler leer curve

**Implementatie**:
```bash
# 1. Add Keycloak to docker-compose.yml
# 2. Start Keycloak
docker-compose up -d keycloak

# 3. Run setup script
./setup_keycloak.sh

# 4. Configure services (Superset, Dagster, API)
# 5. Update Kong gateway with OIDC plugin
```

## 📁 Bestanden Overzicht

### Database Roles Implementation (Actief)

```
postgres-init/
├── 05_security_rbac.sql          # 5 roles, RLS, PII masking, audit
demo_security.sh                   # Demo script voor testing
docs/
└── SECURITY_IAM.md               # Documentatie
```

**Features**:
- 5 database roles: platform_admin, data_engineer, data_analyst, investigator, auditor
- Row-Level Security (RLS) op 6 tables
- Column-Level Security (PII masking views)
- Audit logging met triggers
- Helper functies voor access management

### Keycloak Implementation (Design)

```
docker-compose.yml                 # + Keycloak service (poort 8085)
setup_keycloak.sh                  # Setup script
docs/
└── SECURITY_IAM_KEYCLOAK.md      # Volledige implementatie guide
```

**Features**:
- Realm: data-platform
- 4 OAuth clients: superset, dagster, api, marquez
- 5 realm roles (matching database roles)
- 4 groups met role mapping
- 4 demo users
- JWT token-based auth
- Web UI voor user management

## 🚀 Migratie Plan (Database Roles → Keycloak)

Als je later wilt upgraden naar Keycloak:

### Phase 1: Parallel Running (Week 1)
```bash
# 1. Start Keycloak
docker-compose up -d keycloak

# 2. Run setup
./setup_keycloak.sh

# 3. Test OAuth flow
curl -X POST "http://localhost:8085/realms/data-platform/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "client_id=data-platform-api" \
  -d "client_secret=api_client_secret_2025" \
  -d "grant_type=password" \
  -d "username=john.engineer" \
  -d "password=Engineer2025!"
```

### Phase 2: Service Migration (Week 2-3)

**API**: Update `api/server.js`
```javascript
// Add passport-keycloak-oauth2-oidc
const KeycloakStrategy = require('passport-keycloak-oauth2-oidc').Strategy;

passport.use('keycloak', new KeycloakStrategy({
  clientID: 'data-platform-api',
  clientSecret: 'api_client_secret_2025',
  authorizationURL: 'http://localhost:8085/realms/data-platform/protocol/openid-connect/auth',
  tokenURL: 'http://keycloak:8080/realms/data-platform/protocol/openid-connect/token',
  // ...
}));
```

**Superset**: Update `superset/superset_config.py`
```python
AUTH_TYPE = AUTH_OAUTH
OAUTH_PROVIDERS = [{
    'name': 'keycloak',
    'remote_app': {
        'client_id': 'superset',
        'client_secret': 'superset_client_secret_2025',
        'authorize_url': 'http://localhost:8085/realms/data-platform/protocol/openid-connect/auth',
        # ...
    }
}]
```

**Dagster**: Update `orchestration/dagster.yaml`
```yaml
authentication:
  provider: openid_connect
  openid_connect:
    issuer_url: http://keycloak:8080/realms/data-platform
    client_id: dagster
    client_secret: dagster_client_secret_2025
```

**PostgreSQL**: Update RLS policies
```sql
-- Use JWT claims instead of database user
CREATE OR REPLACE FUNCTION get_current_username()
RETURNS TEXT AS $$
BEGIN
  RETURN current_setting('app.username', true);
END;
$$ LANGUAGE plpgsql STABLE;

-- Application sets context from JWT
-- conn.execute("SET app.username = %s", [jwt_username])
```

### Phase 3: Cleanup (Week 4)
```bash
# Keep database roles for service accounts only
# All human users now via Keycloak
# Remove direct database access for users
```

## 📋 Checklist voor Productie

### Database Roles (Simple)
- [ ] Change default passwords in `05_security_rbac.sql`
- [ ] Test RLS policies with real data
- [ ] Test PII masking views
- [ ] Review audit log retention
- [ ] Setup SSL/TLS for PostgreSQL
- [ ] Document access request process

### Keycloak (Enterprise)
- [ ] Setup Keycloak in docker-compose
- [ ] Run `./setup_keycloak.sh`
- [ ] Change default admin password
- [ ] Configure password policies
- [ ] Enable MFA for admin users
- [ ] Configure LDAP/AD integration (optional)
- [ ] Setup SSL/TLS certificates
- [ ] Configure Kong gateway OIDC plugin
- [ ] Update all service configs (Superset, Dagster, API)
- [ ] Update PostgreSQL RLS to use JWT
- [ ] Test OAuth flow end-to-end
- [ ] Test SSO across all services
- [ ] Document user onboarding process
- [ ] Setup monitoring and alerting

## 🎓 Learning Resources

### Database Roles
- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL Roles and Privileges](https://www.postgresql.org/docs/current/user-manag.html)
- Docs: `docs/SECURITY_IAM.md`

### Keycloak
- [Keycloak Documentation](https://www.keycloak.org/documentation)
- [Keycloak Getting Started](https://www.keycloak.org/getting-started/getting-started-docker)
- [OAuth 2.0 and OpenID Connect](https://oauth.net/2/)
- [JWT.io - Token Inspector](https://jwt.io/)
- Docs: `docs/SECURITY_IAM_KEYCLOAK.md`

## 💡 Aanbeveling

### Voor deze demo setup:
**Gebruik Database Roles** ✅

**Waarom?**
1. Al geïmplementeerd en getest
2. Voldoende voor demo/POC doeleinden
3. Toont belangrijkste concepten (RBAC, RLS, PII masking, audit)
4. Geen extra complexiteit
5. Focus blijft op data platform features

**Wanneer upgraden naar Keycloak?**
- Wanneer je externe users hebt
- Wanneer je SSO nodig hebt
- Wanneer je MFA wilt
- Wanneer je LDAP/AD integratie nodig hebt
- Wanneer je naar productie gaat

### Snelle start (Database Roles):
```bash
# 1. Check of security SQL al is uitgevoerd
docker exec dp_postgres psql -U superset -d superset -c "\du"

# 2. Als roles nog niet bestaan:
docker exec dp_postgres psql -U superset -d superset -f /docker-entrypoint-initdb.d/05_security_rbac.sql

# 3. Test security
./demo_security.sh

# 4. Done! 🎉
```

## 📞 Support

Vragen over implementatie?
- Database Roles: Zie `docs/SECURITY_IAM.md`
- Keycloak: Zie `docs/SECURITY_IAM_KEYCLOAK.md`
- Both: Check troubleshooting secties

---

**Version**: 1.0  
**Last Updated**: 16 oktober 2025  
**Decision**: Use Database Roles for demo, Keycloak for production
