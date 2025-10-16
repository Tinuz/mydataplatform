# Security & IAM Implementation

## 🔒 Overview

Dit platform implementeert een complete security laag met Role-Based Access Control (RBAC), Row-Level Security (RLS), Column-Level Security voor PII masking, en Audit Logging.

## 📋 Security Layers

### 1. **Role-Based Access Control (RBAC)**

Vijf hoofdrollen met verschillende permissies:

| Role | Login | Permissions | Use Case |
|------|-------|-------------|----------|
| **platform_admin** | ✅ | Full superuser access | Platform beheer, configuratie |
| **data_engineer** | ✅ | Create/modify tables, run ETL, access raw data | Pipeline development, data engineering |
| **data_analyst** | ✅ | Read canonical data (PII masked) | Analytics, reporting, dashboards |
| **investigator** | ✅ | Access assigned investigations only (RLS) | Case investigators, restricted access |
| **auditor** | ✅ | Read-only audit logs | Compliance, security audits |

### 2. **Row-Level Security (RLS)**

Investigators kunnen alleen data zien van hun toegewezen onderzoeken:

```sql
-- Automatically filters based on user_investigation_access table
SELECT * FROM investigations;  -- Shows only assigned cases
SELECT * FROM raw_transactions WHERE investigation_id = 'OND-2025-000001';
```

**Features**:
- ✅ Automatic filtering by `investigation_id`
- ✅ Time-based expiration (access expires after N days)
- ✅ Multiple access levels: read, write, admin
- ✅ Audit trail of all access grants/revokes

### 3. **Column-Level Security (PII Masking)**

Data analysts krijgen gemaskeerde views:

| Original Data | Masked View |
|--------------|-------------|
| `NL91ABNA0417164300` | `NL91****4300` |
| `+31612345678` | `****5678` |
| `John Doe` | `***REDACTED***` |
| `Payment for services rendered` | `31` (length only) |

**Masked Views**:
- `canonical.fact_transaction_masked`
- `canonical.fact_call_masked`
- `canonical.fact_message_masked`

### 4. **Audit Logging**

Alle data modificaties worden gelogd:

```sql
SELECT * FROM audit_log ORDER BY event_timestamp DESC LIMIT 10;
```

**Logged Events**:
- INSERT, UPDATE, DELETE operations
- User identity and role
- Investigation context
- Timestamp and IP address (when available)
- Success/failure status

## 🚀 Setup & Installation

### Initiële Setup

1. **Database initialisatie** (automatisch bij eerste start):
```bash
# Script wordt uitgevoerd bij postgres container start
# File: postgres-init/05_security_rbac.sql
```

2. **Verify installation**:
```bash
docker exec dp_postgres psql -U superset -d superset -c "
SELECT rolname FROM pg_roles 
WHERE rolname LIKE 'investigator%' OR rolname LIKE 'analyst%';
"
```

### Demo Users

Voor testing zijn er drie demo users aangemaakt:

```bash
# Investigators
investigator_john:john_demo_2025!    # Toegang tot OND-2025-000001
investigator_jane:jane_demo_2025!    # Toegang tot OND-2025-000002

# Analyst
analyst_bob:bob_demo_2025!           # Read-only masked data
```

## 📖 Usage Examples

### Grant Investigation Access

```sql
-- Grant read access for 365 days
SELECT grant_investigation_access(
    'investigator_john',     -- user_id
    'OND-2025-000001',      -- investigation_id
    'read',                  -- access_level (read, write, admin)
    365                      -- expires_days (NULL for permanent)
);
```

### Revoke Investigation Access

```sql
SELECT revoke_investigation_access(
    'investigator_john',
    'OND-2025-000001'
);
```

### Check Your Access

```sql
-- As investigator
SET ROLE investigator_john;
SELECT * FROM my_investigation_access;
RESET ROLE;
```

### Test RLS

```bash
# Connect as investigator
docker exec -it dp_postgres psql -U investigator_john -d superset

# Run queries - automatic filtering by RLS
SELECT * FROM investigations;
SELECT * FROM raw_transactions;
SELECT * FROM canonical.canonical_transaction;
```

### Use Masked Views

```bash
# Connect as analyst
docker exec -it dp_postgres psql -U analyst_bob -d superset

# Query masked data
SELECT * FROM canonical.fact_transaction_masked LIMIT 10;
SELECT * FROM canonical.fact_call_masked LIMIT 10;
```

### View Audit Log

```sql
-- As admin or auditor
SELECT 
    event_timestamp,
    user_name,
    event_type,
    table_name,
    investigation_id,
    success
FROM audit_log
WHERE investigation_id = 'OND-2025-000001'
ORDER BY event_timestamp DESC;
```

## 🎬 Demo Script

Run het complete security demo script:

```bash
./demo_security.sh
```

Dit script demonstreert:
1. ✅ Database roles en permissions
2. ✅ Grant/revoke investigation access
3. ✅ Row-Level Security filtering
4. ✅ PII masking voor analysts
5. ✅ User access matrix
6. ✅ Audit log viewing

## 🔐 Security Best Practices

### Production Deployment

Voor productie omgevingen:

1. **Change Default Passwords**:
```sql
ALTER ROLE platform_admin WITH PASSWORD 'STRONG_RANDOM_PASSWORD';
ALTER ROLE data_engineer WITH PASSWORD 'STRONG_RANDOM_PASSWORD';
-- etc.
```

2. **Integrate with SSO/LDAP**:
```sql
-- Use external authentication instead of database users
-- Configure pg_hba.conf for LDAP/Kerberos/SAML
```

3. **Enable SSL/TLS**:
```bash
# In docker-compose.yml
postgres:
  environment:
    POSTGRES_HOST_SSL: "on"
  volumes:
    - ./certs:/etc/postgresql/certs
```

4. **Rotate Access Tokens**:
```sql
-- Periodically expire and renew investigation access
UPDATE user_investigation_access 
SET expires_at = NOW() + INTERVAL '90 days'
WHERE expires_at < NOW() + INTERVAL '30 days';
```

5. **Monitor Audit Logs**:
```sql
-- Alert on suspicious activity
SELECT * FROM audit_log 
WHERE success = false 
  AND event_timestamp > NOW() - INTERVAL '1 hour';
```

### Connection String Examples

```bash
# Platform Admin
psql "postgresql://platform_admin:admin_secure_pwd_2025!@localhost:5432/superset"

# Data Engineer
psql "postgresql://data_engineer:engineer_secure_pwd_2025!@localhost:5432/superset"

# Data Analyst
psql "postgresql://analyst_bob:bob_demo_2025!@localhost:5432/superset"

# Investigator
psql "postgresql://investigator_john:john_demo_2025!@localhost:5432/superset"
```

## 📊 Permission Matrix

| Action | Admin | Engineer | Analyst | Investigator | Auditor |
|--------|-------|----------|---------|--------------|---------|
| Create tables | ✅ | ✅ | ❌ | ❌ | ❌ |
| View raw data | ✅ | ✅ | ❌ | ✅ (RLS) | ❌ |
| View canonical data | ✅ | ✅ | ✅ (masked) | ✅ (RLS) | ❌ |
| Insert/Update data | ✅ | ✅ | ❌ | ❌ | ❌ |
| Delete data | ✅ | ✅ | ❌ | ❌ | ❌ |
| Grant access | ✅ | ❌ | ❌ | ❌ | ❌ |
| View audit logs | ✅ | ❌ | ❌ | ❌ | ✅ |
| Run dbt models | ✅ | ✅ | ❌ | ❌ | ❌ |
| Access all investigations | ✅ | ✅ | ✅ (masked) | ❌ | ❌ |

## 🔍 Troubleshooting

### User cannot see any data

```sql
-- Check if user has investigation access
SELECT * FROM user_investigation_access WHERE user_id = 'investigator_john';

-- Grant access if missing
SELECT grant_investigation_access('investigator_john', 'OND-2025-000001', 'read');
```

### Access expired

```sql
-- Extend expiration
UPDATE user_investigation_access 
SET expires_at = NOW() + INTERVAL '365 days'
WHERE user_id = 'investigator_john' 
  AND investigation_id = 'OND-2025-000001';
```

### Analyst sees full PII data

```sql
-- Ensure they use masked views
SELECT * FROM canonical.fact_transaction_masked;  -- ✅ Correct
-- NOT: SELECT * FROM canonical.fact_transaction;  -- ❌ Wrong
```

### Check effective permissions

```sql
-- As specific user
SET ROLE investigator_john;

-- Test what you can see
SELECT schemaname, tablename 
FROM pg_tables 
WHERE schemaname IN ('public', 'canonical');

-- Test RLS filtering
SELECT COUNT(*) FROM investigations;

RESET ROLE;
```

## 📚 Related Documentation

- [PostgreSQL Row Security Policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
- [PostgreSQL Roles and Privileges](https://www.postgresql.org/docs/current/user-manag.html)
- [GDPR Compliance Guide](./GDPR_COMPLIANCE.md) (te maken)
- [Audit Log Analysis](./AUDIT_LOG_GUIDE.md) (te maken)

## 🎯 Integration with Platform

### Dagster Integration

Voor Dagster jobs, gebruik de `data_engineer` role:

```python
# orchestration/investigations/resources.py
postgres_resource = PostgresClientResource(
    host="postgres",
    user="data_engineer",
    password=os.getenv("DATA_ENGINEER_PASSWORD"),
    database="superset"
)
```

### Superset Integration

Configureer Superset met `data_analyst` role voor dashboards:

```bash
# In docker-compose.yml
superset:
  environment:
    SUPERSET_DATABASE_URI: "postgresql://analyst_bob:bob_demo_2025!@postgres:5432/superset"
```

### API Integration

API moet verschillende connection strings gebruiken per endpoint:

```python
# api/server.js
const adminPool = new Pool({
  user: 'platform_admin',
  password: process.env.ADMIN_PASSWORD,
  database: 'superset'
});

const analystPool = new Pool({
  user: 'data_analyst',
  password: process.env.ANALYST_PASSWORD,
  database: 'superset'
});
```

## ⚖️ Compliance

Deze implementatie ondersteunt:

- ✅ **GDPR**: PII masking, right to be forgotten, audit trail
- ✅ **SOC 2**: Access control, audit logging, least privilege
- ✅ **ISO 27001**: Information security management
- ✅ **NEN 7510**: Healthcare data security (NL)

Voor volledige compliance, aanvullende maatregelen nodig:
- Data retention policies
- Encryption at rest (PostgreSQL TDE)
- Encryption in transit (SSL/TLS certificates)
- Regular access reviews
- Penetration testing

---

**Version**: 1.0  
**Last Updated**: 16 oktober 2025  
**Author**: Data Platform Team
