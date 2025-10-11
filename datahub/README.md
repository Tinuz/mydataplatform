# DataHub Integration

## 🎯 Wat is DataHub?

DataHub is een moderne metadata platform voor data discovery, governance en lineage tracking. Het biedt wat Marquez niet heeft:

- **Data Glossary** - Business terms en definities
- **Rich Search** - Full-text search over alle metadata
- **Column-level Tags** - PII, sensitivity, compliance labels
- **Impact Analysis** - Welke dashboards gebruiken deze data?
- **Ownership** - Teams en personen per dataset
- **Domains** - Organizeer data per business domain

## 🚀 Quick Start

### Start DataHub

```bash
# Start DataHub services (naast bestaande platform)
docker-compose --profile datahub up -d

# Check status
docker-compose ps | grep datahub

# Wait for services to be healthy (~2 minutes)
docker-compose logs -f datahub-gms
```

### Access DataHub

- **UI**: http://localhost:9002
- **API**: http://localhost:8081

**Default credentials**: (first login creates admin account)

### Ingest Metadata

```bash
# Run metadata ingestion script
python3 datahub/ingest_metadata.py

# Or use Docker
docker run --rm --network data-platform_default \
  -v $(pwd)/datahub:/app \
  python:3.11-slim \
  sh -c "pip install requests && python /app/ingest_metadata.py"
```

## 📊 What Gets Ingested

### Business Glossary (5 terms)

1. **Mobile Country Code** - ITU-T E.212 standard
2. **Cell Tower** - Physical telecommunications infrastructure  
3. **Radio Access Technology** - GSM, LTE, 5G standards
4. **Geographic Coordinates** - WGS84 coordinate system
5. **Signal Strength** - dBm measurements

### Dataset Metadata

**cell_towers.clean_204** - 14 columns documented with:
- Column descriptions
- Data types
- Nullable constraints
- Business glossary links
- Tags (PII, location, metric, etc.)
- Compliance notes (GDPR for location data)

### Tags Applied

- `pii` - Personal Identifiable Information (lat/lon)
- `location` - Geographic data
- `sensitive` - Requires access control
- `production` - Production-ready dataset
- `validated` - Quality checks passed
- `telecommunications` - Industry domain

## 🎬 Demo Flow

### 1. Data Discovery (2 min)

Open http://localhost:9002

1. **Search bar** → Type "cell tower"
2. Click on `cell_towers.clean_204` dataset
3. Show **Schema** tab with column descriptions
4. Show **Tags**: telecommunications, netherlands, production
5. Show **Owners**: Data Engineering Team

### 2. Business Glossary (1 min)

1. Click **Glossary** in sidebar
2. Show glossary terms:
   - Mobile Country Code
   - Cell Tower
   - Radio Access Technology
3. Click term → Show definition and usage

### 3. Data Governance (2 min)

1. Go back to dataset
2. Show **PII columns**: lat, lon (tagged as sensitive)
3. Show **Compliance**: GDPR - Location data
4. Show **Quality Score**: 97%
5. Show **Update Frequency**: Daily

### 4. Column-Level Metadata (1 min)

Click on column `mcc`:
- Description: "Mobile Country Code (204 = Netherlands)"
- Glossary Link: → Mobile Country Code
- Tags: identifier, country
- Type: INTEGER NOT NULL

## 🔄 Comparison: DataHub vs Marquez

| Feature | Marquez | DataHub |
|---------|---------|---------|
| **Lineage** | ✅ Excellent | ✅ Excellent |
| **Data Glossary** | ❌ No | ✅ Yes |
| **Column Tags** | ✅ Basic | ✅ Advanced |
| **Search** | ⚠️ Limited | ✅ Full-text |
| **UI** | ⚠️ Basic | ✅ Modern |
| **Ownership** | ⚠️ Basic | ✅ Rich |
| **Domains** | ❌ No | ✅ Yes |
| **Impact Analysis** | ❌ No | ✅ Yes |
| **API** | ✅ REST | ✅ REST + GraphQL |
| **Resource Usage** | ⭐ Light (2 services) | ⭐⭐ Medium (4 services) |

## 💡 When to Use What?

**Use Marquez for:**
- Quick lineage visualization
- OpenLineage integration
- Lightweight setup
- ETL job tracking

**Use DataHub for:**
- Complete data governance
- Business glossary management
- Data discovery at scale
- Compliance requirements (PII, GDPR)
- Impact analysis
- Cross-team collaboration

**Use Both for:**
- **Marquez**: Technical lineage (automated from ETL)
- **DataHub**: Business context (manual curation)

## 🛠️ Advanced Setup

### Full PostgreSQL Ingestion

For production, use DataHub's PostgreSQL connector:

```bash
# Install datahub CLI
pip install acryl-datahub

# Run PostgreSQL ingestion
datahub ingest -c datahub/postgres_recipe.yml
```

### Lineage from dbt

If you add dbt later:

```bash
# dbt auto-generates lineage
dbt docs generate
datahub ingest -c datahub/dbt_recipe.yml
```

### Trino Catalog Ingestion

```bash
datahub ingest -c datahub/trino_recipe.yml
```

## 📦 Services

DataHub consists of:

1. **datahub-mysql** - Metadata storage (Port: internal only)
2. **datahub-elasticsearch** - Search index (Port: internal only)
3. **datahub-gms** - GraphQL metadata service (Port: 8081)
4. **datahub-frontend** - React UI (Port: 9002)

## 🚨 Troubleshooting

### DataHub UI not loading

```bash
# Check all services are healthy
docker-compose ps | grep datahub

# Check GMS logs
docker-compose logs datahub-gms | tail -50

# Check frontend logs
docker-compose logs datahub-frontend | tail -20

# Restart if needed
docker-compose restart datahub-frontend datahub-gms
```

### Elasticsearch issues

```bash
# Increase Docker memory to 8GB+
# Docker Desktop → Settings → Resources

# Check ES health
curl http://localhost:9200/_cluster/health
```

### Port conflicts

- **8081**: DataHub GMS (conflicted with old Swagger on 8081)
  - **Solution**: Moved Swagger to 8082
- **9002**: DataHub UI (no conflicts)

### Clean restart

```bash
# Stop DataHub
docker-compose --profile datahub down

# Remove volumes (DESTRUCTIVE!)
docker volume rm data-platform_datahub_mysql data-platform_datahub_elasticsearch

# Start fresh
docker-compose --profile datahub up -d
```

## 📚 Resources

- [DataHub Docs](https://datahubproject.io/)
- [DataHub GitHub](https://github.com/datahub-project/datahub)
- [Metadata Modeling](https://datahubproject.io/docs/metadata-modeling/metadata-model)
- [API Guide](https://datahubproject.io/docs/api/graphql/overview)

## 🎯 Demo Checklist

Before demo:

- [ ] DataHub services running (`docker-compose ps`)
- [ ] UI accessible (http://localhost:9002)
- [ ] Metadata ingested (`python3 datahub/ingest_metadata.py`)
- [ ] Glossary terms visible
- [ ] Dataset `cell_towers.clean_204` documented
- [ ] PII tags visible on lat/lon columns
- [ ] Search works (type "cell" in search bar)

## 🔐 Security Note

⚠️ **Development setup - NOT for production!**

For production:
- Enable authentication (OIDC, LDAP)
- Configure HTTPS
- Set proper RBAC policies
- Enable audit logging
- Secure Elasticsearch cluster
