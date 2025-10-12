# 🚀 Modern Data Platform

Complete lokale data platform met API gateway, SQL engine, visualization, data lake en governance.

## 🎯 Dashboard

**Open [dashboard.html](dashboard.html) in je browser voor een visueel overzicht van alle componenten!**

## 📋 Quick Links

- **Weather API**: http://localhost:8000/api/v1/weather (see [docs/WEATHER_API.md](docs/WEATHER_API.md)) 🌤️
- **Amundsen**: http://localhost:5005 (Data Catalog & Glossary) ⭐
- **Superset**: http://localhost:8088 (admin/admin)
- **Marquez**: http://localhost:3001
- **MinIO**: http://localhost:9001 (minio/minio12345)
- **Trino**: http://localhost:8080
- **Konga**: http://localhost:1337
- **API Docs**: http://localhost:8000/docs
- **Dagster**: http://localhost:3000

## 🏗️ Architectuur

```
API Gateway (Kong + Konga)
    ↓
Application Layer (Superset, Cell API)
    ↓
Analytics (Trino, Marquez)
    ↓
Storage (PostgreSQL, MinIO)
```

## ⚡ Start

```bash
# Start core platform
docker-compose --profile standard up -d

# Start Amundsen (data catalog)
docker-compose --profile amundsen up -d

# Load data
docker-compose up etl

# Load metadata into Amundsen
python3 amundsen/databuilder_ingestion.py
python3 amundsen/create_glossary.py

# Check status
docker-compose ps
```

## 🛠️ Services

| Service | Port | Credentials |
|---------|------|-------------|
| **Weather API** | 8000/api/v1/weather | API Key: demo-weather-api-key-2025 |
| **Amundsen** | 5005 | - |
| PostgreSQL | 5432 | superset/superset |
| MinIO | 9000, 9001 | minio/minio12345 |
| Superset | 8088 | admin/admin |
| Trino | 8080 | admin/- |
| Marquez | 5000, 3001 | - |
| Kong | 8000, 8001 | - |
| Konga | 1337 | Setup bij eerste run |
| Cell API | 3100 | - |
| Neo4j (Amundsen) | 7474, 7687 | neo4j/test |

## 🌤️ Weather API

**Base URL:** http://localhost:8000/api/v1/weather

**Authentication:** API Key required (Header: `X-API-Key`)

**Rate Limits:**
- 100 requests/minute
- 5,000 requests/hour

**Endpoints:**
- `GET /observations/latest` - Latest weather per station
- `GET /observations` - Historical observations (with filters)
- `GET /stations` - Station metadata with GPS coordinates

**Quick Start:**
```bash
# Get latest weather
curl -H "X-API-Key: demo-weather-api-key-2025" \
  http://localhost:8000/api/v1/weather/observations/latest

# Get Amsterdam observations
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations?station=Amsterdam&limit=10"

# Get all stations
curl -H "X-API-Key: demo-weather-api-key-2025" \
  http://localhost:8000/api/v1/weather/stations
```

**Documentation:** See [docs/WEATHER_API.md](docs/WEATHER_API.md) for complete API reference.

## 🔄 ETL Pipeline

**Flow:**
```
Google Cloud Storage → MinIO → PostgreSQL → Marquez
```

**Run:**
```bash
docker-compose up etl
```

**Result:** 47,114 cell tower records in `cell_towers.clean_204`

## 📊 Data Governance

### Amundsen - Data Catalog ⭐

**UI:** http://localhost:5005

**Features:**
- 🔍 Data discovery & search
- 📚 Business glossary (5 terms)
- 📖 Column-level metadata (14 columns)
- 🏷️ Tags & PII classification
- 👥 Data ownership
- 📈 Quality metrics (97%)

**Setup:**
```bash
# Start Amundsen
docker-compose --profile amundsen up -d

# Load metadata
python3 amundsen/databuilder_ingestion.py

# Create business glossary
python3 amundsen/create_glossary.py
```

**Demo:** See `amundsen/DEMO_SCRIPT.md` for 8-minute presentation

### Marquez - Data Lineage

**UI:** http://localhost:3001

**Features:**
- Visual lineage graph
- Automated via OpenLineage
- Job execution history
- Technical metadata

**API:**
```bash
# List datasets
curl http://localhost:5000/api/v1/namespaces/demo/datasets

# Get dataset
curl http://localhost:5000/api/v1/namespaces/demo/datasets/cell_towers.clean_204
```

**Governance Strategy:**
- **Amundsen**: Business context, glossary, discovery
- **Marquez**: Technical lineage, job tracking

## 🔍 Query Examples

### PostgreSQL
```bash
docker-compose exec postgres psql -U superset -d superset
```

```sql
-- Data overview
SELECT COUNT(*) FROM cell_towers.clean_204;

-- By radio type
SELECT radio, COUNT(*) FROM cell_towers.clean_204 GROUP BY radio;

-- By country
SELECT mcc, COUNT(*) as towers 
FROM cell_towers.clean_204 
GROUP BY mcc 
ORDER BY towers DESC 
LIMIT 10;
```

### Trino
```bash
docker-compose exec trino trino
```

```sql
-- Show catalogs
SHOW CATALOGS;

-- Query PostgreSQL
SELECT radio, COUNT(*) 
FROM postgresql.cell_towers.clean_204 
GROUP BY radio;

-- Sample data
SELECT * FROM tpch.tiny.nation LIMIT 10;
```

### MinIO (AWS CLI)
```bash
aws --endpoint-url http://localhost:9000 s3 ls s3://lake/raw/celltowers/
```

## 🌐 REST API

**Base URL:** http://localhost:3100

```bash
# Health
GET /health

# All towers
GET /api/v1/celltowers

# By country
GET /api/v1/celltowers/country/204

# By radio
GET /api/v1/celltowers/radio/LTE

# Bounding box
GET /api/v1/celltowers/bbox?minLat=50&maxLat=54&minLon=3&maxLon=7
```

**Via Kong:**
```bash
curl http://localhost:8000/celltowers/health
```

## 🚨 Troubleshooting

### Service issues
```bash
# Logs
docker-compose logs [service-name]

# Restart
docker-compose restart [service-name]

# Full restart
docker-compose down && docker-compose --profile standard up -d
```

### Common problems

**PostgreSQL not ready:**
```bash
docker-compose ps postgres
docker-compose exec postgres pg_isready -U superset
```

**Superset admin missing:**
```bash
docker-compose exec superset superset fab create-admin \
  --username admin --password admin \
  --firstname Admin --lastname User \
  --email admin@localhost
```

**Marquez empty:**
```bash
docker-compose up etl
```

**Clean restart:**
```bash
docker-compose down -v
docker-compose --profile standard up -d
docker-compose up etl
```

## 📦 Project Structure

```
├── api/                  # Cell Towers REST API
├── etl/                 # ETL Pipeline
│   ├── pipeline.py
│   └── sql/
├── kong/                # API Gateway config
├── marquez/             # Lineage config
├── postgres-init/       # DB initialization
├── superset/            # Superset customization
├── trino/               # Trino configuration
│   └── catalog/
└── docker-compose.yml
```

## 🎯 Data Quality

ETL implementeert:
- ✅ Coordinate validation (lat/lon ranges)
- ✅ Deduplication (unique cell IDs)
- ✅ NULL checks
- ✅ Type validation
- ✅ Performance indexes

## 🔐 Security

⚠️ **Development setup - NOT for production!**

**Voor productie:**
- Wijzig alle passwords
- Enable SSL/TLS
- Configure authentication
- Enable Kong auth plugins
- Use secrets management
- Enable CSRF protection
- Configure network security
- Enable audit logging

## 📚 Resources

- [Superset](https://superset.apache.org/)
- [Trino](https://trino.io/)
- [Marquez](https://marquezproject.github.io/marquez/)
- [Kong](https://docs.konghq.com/)
- [MinIO](https://min.io/docs/)

## 💡 Platform Status

```bash
curl http://localhost:5000/api/v1/namespaces    # Marquez
curl http://localhost:8088/health               # Superset  
curl http://localhost:8080/v1/info              # Trino
curl http://localhost:3100/health               # Cell API
```
