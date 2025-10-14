# 🚀 Data Platform Quick Reference

Handig overzicht van de meest gebruikte commando's en workflows.

---

## 📦 Platform Management

```bash
# Start platform (minimaal)
docker-compose up -d postgres minio dagster

# Start platform (volledig)
docker-compose --profile standard up -d

# Start met Amundsen catalog
docker-compose --profile amundsen up -d

# Start met Kafka streaming
docker-compose --profile streaming up -d

# Stop alles
docker-compose down

# Stop en verwijder volumes (⚠️ DATA LOSS)
docker-compose down -v

# Rebuild een service
docker-compose build dagster
docker-compose up -d dagster

# Check status
docker-compose ps

# Bekijk logs
docker-compose logs -f dagster
docker-compose logs --tail 50 postgres
```

---

## 🎯 Dagster Workflows

### Via UI (http://localhost:3000)

1. **Materialize een asset:**
   - Assets tab → Select asset → "Materialize"

2. **Enable een schedule:**
   - Automation tab → Schedules → Toggle ON

3. **Enable een sensor:**
   - Automation tab → Sensors → Toggle ON

### Via CLI

```bash
# List all assets
docker-compose exec dagster dagster asset list

# Materialize een asset
docker-compose exec dagster dagster asset materialize --select bronze_weather

# Materialize meerdere assets
docker-compose exec dagster dagster asset materialize --select silver_*

# Run een job
docker-compose exec dagster dagster job execute -j weather_pipeline_job

# Check code location
docker-compose exec dagster dagster code-location list

# Reload definitions (na code change)
# → Gebeurt automatisch via hot reload
```

---

## 🗄️ Database Queries

### PostgreSQL

```bash
# Open psql
docker-compose exec postgres psql -U superset -d superset

# Direct query
docker-compose exec postgres psql -U superset -d superset -c "SELECT COUNT(*) FROM bronze.weather;"
```

**Useful Queries:**

```sql
-- List alle schemas
\dn

-- List alle tables in schema
\dt bronze.*

-- Bekijk table structure
\d bronze.weather

-- Check data freshness
SELECT 
    schemaname, 
    tablename, 
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables 
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;

-- Recent ingestions
SELECT * FROM bronze.weather ORDER BY ingested_at DESC LIMIT 10;
```

### DuckDB (Embedded Query Engine)

```python
# Query Iceberg tables with DuckDB
from crypto_stream.duckdb_helper import quick_query

# Query Parquet/Iceberg data
df = quick_query("""
    SELECT symbol, AVG(price) as avg_price
    FROM trades_bronze
    WHERE timestamp > NOW() - INTERVAL '1 hour'
    GROUP BY symbol
""")

# DuckDB CLI (alternative)
docker-compose exec dagster python -c "
from crypto_stream.duckdb_helper import quick_query
print(quick_query('SELECT COUNT(*) FROM trades_bronze'))
"
```

### Cross-Database Queries

```sql
# PostgreSQL for OLTP data
````
```

### Trino

```bash
# Open Trino CLI
docker-compose exec trino trino

# Query MinIO data
SELECT * FROM minio.bronze.weather LIMIT 10;

# Cross-database join
SELECT 
    m.station_name,
    p.temperature
FROM minio.bronze.stations m
JOIN postgresql.weather.observations p ON m.station_name = p.station_name;
```

---

## 🪣 MinIO (Data Lake)

### Via UI
- http://localhost:9001
- Login: minio / minio12345

### Via CLI

```bash
# List buckets
docker-compose exec minio mc ls local

# List files in bucket
docker-compose exec minio mc ls local/lake/bronze/

# Upload file
docker-compose exec minio mc cp /tmp/data.csv local/lake/bronze/

# Download file
docker-compose exec minio mc cp local/lake/bronze/data.csv /tmp/

# Create bucket
docker-compose exec minio mc mb local/my-new-bucket
```

### Via Python

```python
import boto3

s3 = boto3.client('s3',
    endpoint_url='http://localhost:9000',
    aws_access_key_id='minio',
    aws_secret_access_key='minio12345'
)

# List objects
response = s3.list_objects_v2(Bucket='lake', Prefix='bronze/')
for obj in response.get('Contents', []):
    print(obj['Key'])

# Upload
s3.upload_file('local.csv', 'lake', 'bronze/data.csv')

# Download
s3.download_file('lake', 'bronze/data.csv', 'local.csv')
```

---

## 🌐 API Usage

### Weather API

```bash
# Get latest weather (authenticated)
curl -H "X-API-Key: demo-weather-api-key-2025" \
  http://localhost:8000/api/v1/weather/observations/latest

# Filter by station
curl -H "X-API-Key: demo-weather-api-key-2025" \
  "http://localhost:8000/api/v1/weather/observations?station=Amsterdam&limit=5"

# Get all stations
curl -H "X-API-Key: demo-weather-api-key-2025" \
  http://localhost:8000/api/v1/weather/stations

# Check rate limit
for i in {1..105}; do 
  curl -s -o /dev/null -w "%{http_code}\n" \
    -H "X-API-Key: demo-weather-api-key-2025" \
    http://localhost:8000/api/v1/weather/observations/latest
done | tail -10
# Should show 429 after 100 requests
```

### Cell Towers API

```bash
# Get towers (no auth needed)
curl "http://localhost:8000/api/towers?limit=10&radio=LTE"

# Get specific tower
curl "http://localhost:8000/api/towers/7517892683"

# Filter by bounding box
curl "http://localhost:8000/api/towers?bbox=4.7,52.2,5.2,52.5"
```

---

## 📊 Superset

### Via UI
- http://localhost:8088
- Login: admin / admin

### Via CLI

```bash
# Create admin user (if needed)
docker-compose exec superset superset fab create-admin \
  --username admin \
  --firstname Admin \
  --lastname User \
  --email admin@example.com \
  --password admin

# Initialize database
docker-compose exec superset superset db upgrade

# Load examples (optional)
docker-compose exec superset superset load-examples

# Import dashboard
docker-compose exec superset superset import-dashboards -p /path/to/dashboard.zip
```

---

## 🔍 Amundsen

### Via UI
- http://localhost:5005

### Sync Metadata

```bash
# Via Python scripts
python3 scripts/seed_amundsen_metadata.py
python3 scripts/sync_neo4j_to_es.py

# Check Neo4j
docker-compose exec neo4j cypher-shell -u neo4j -p test
```

**Cypher Queries:**

```cypher
// Count tables
MATCH (t:Table) RETURN count(t);

// Search tables
MATCH (t:Table) WHERE t.name CONTAINS 'weather' RETURN t.name, t.key;

// Get table with columns
MATCH (t:Table {name: 'observations'})-[:COLUMN]->(c:Column)
RETURN t.name, collect(c.name) as columns;
```

---

## 🔗 Marquez (Lineage)

### Via UI
- http://localhost:3001

### Via API

```bash
# List namespaces
curl http://localhost:5000/api/v1/namespaces

# List datasets
curl http://localhost:5000/api/v1/namespaces/demo/datasets

# Get dataset lineage
curl http://localhost:5000/api/v1/lineage?nodeId=dataset:demo:weather.observations

# List jobs
curl http://localhost:5000/api/v1/namespaces/demo/jobs
```

---

## 🔧 Debugging

### Check Logs

```bash
# All services
docker-compose logs -f

# Specific service with filter
docker-compose logs dagster --tail 100 | grep ERROR

# Follow logs
docker-compose logs -f dagster postgres

# Save logs to file
docker-compose logs > platform-logs.txt
```

### Service Health Checks

```bash
# Dagster
curl -s http://localhost:3000/server_info | jq '.dagster_webserver_version'

# Superset
curl -s http://localhost:8088/health

# MinIO
curl -s http://localhost:9000/minio/health/live

# PostgreSQL
docker-compose exec postgres pg_isready -U superset

# Neo4j
curl -u neo4j:test http://localhost:7474/db/neo4j/tx/commit
```

### Restart Services

```bash
# Restart één service
docker-compose restart dagster

# Restart meerdere services
docker-compose restart dagster postgres

# Force recreate
docker-compose up -d --force-recreate dagster

# Rebuild en restart
docker-compose build dagster && docker-compose up -d dagster
```

### Clean Up

```bash
# Remove stopped containers
docker-compose rm -f

# Clean dangling images
docker image prune -f

# Clean everything (⚠️ removes all Docker resources)
docker system prune -a --volumes

# Reset alleen dit platform
docker-compose down -v
docker volume ls | grep dp_ | awk '{print $2}' | xargs docker volume rm
```

---

## 🐍 Python Development

### Install Dependencies

```bash
# Install in Dagster container
docker-compose exec dagster pip install requests pandas boto3

# Or rebuild after updating requirements.txt
docker-compose build dagster
```

### Test Python Code

```bash
# Python shell in container
docker-compose exec dagster python

# Run a script
docker-compose exec dagster python /opt/dagster/app/scripts/test.py

# Test imports
docker-compose exec dagster python -c "import weather_pipeline; print('OK')"
```

### Format Code

```bash
# Run black formatter
docker-compose exec dagster black /opt/dagster/app/weather_pipeline/

# Run flake8 linter
docker-compose exec dagster flake8 /opt/dagster/app/weather_pipeline/
```

---

## 📈 Performance Monitoring

```bash
# Container resource usage
docker stats

# Disk usage
docker-compose exec postgres df -h

# Database size
docker-compose exec postgres psql -U superset -d superset -c "
SELECT 
    pg_size_pretty(pg_database_size('superset')) as db_size,
    pg_size_pretty(pg_total_relation_size('weather.observations')) as table_size;
"

# Active connections
docker-compose exec postgres psql -U superset -d superset -c "
SELECT count(*) FROM pg_stat_activity WHERE state = 'active';
"
```

---

## 🔐 Security

```bash
# Change API keys
# Edit kong/kong.yml → consumers → keyauth_credentials

# Change database passwords
# Edit docker-compose.yml → environment → POSTGRES_PASSWORD

# Rotate MinIO credentials
docker-compose exec minio mc admin user add local newuser newpassword

# Check open ports
netstat -tulpn | grep -E '(3000|5432|8088|9000)'
```

---

## 📚 Documentation Links

- **Weather API Docs:** http://localhost:8000/docs
- **GitHub Repo:** https://github.com/Tinuz/mydataplatform
- **Dagster Docs:** https://docs.dagster.io
- **Superset Docs:** https://superset.apache.org/docs
- **Trino Docs:** https://trino.io/docs

---

## 🆘 Get Help

```bash
# Check platform status
docker-compose ps

# Full diagnostic
docker-compose logs > logs.txt
docker-compose ps > status.txt
docker stats --no-stream > resources.txt

# Open GitHub issue with:
# - logs.txt
# - status.txt  
# - resources.txt
# - Description of problem
```

---

**💡 Pro Tip:** Bookmark `dashboard.html` voor quick access to all services!
