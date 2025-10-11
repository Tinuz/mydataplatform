# Trino Setup

Trino is een gedistribueerde SQL query engine voor big data analytics.

## Overzicht

Deze Trino setup is geoptimaliseerd voor lokale development op Apple Silicon (M2 Pro) met:
- **1GB JVM heap** (Xmx/Xms)
- **2GB Docker memory limit** (met 1GB reserved)
- **File-based Hive metastore** (geen externe metastore nodig)
- **Toegang tot**: PostgreSQL, MinIO (S3), en TPCH test data

## Services

### Trino Coordinator
- **Web UI**: http://localhost:8080
- **JDBC**: `jdbc:trino://localhost:8080/catalog/schema`
- **User**: standaard geen authenticatie (development mode)

### Catalogs (data sources)

| Catalog | Type | Beschrijving |
|---------|------|--------------|
| `postgresql` | PostgreSQL | Connectie naar dp_postgres (superset database) |
| `minio` | Hive/S3 | Data lake in MinIO (bucket: lake) |
| `tpch` | Test data | TPC-H benchmark dataset voor testen |

## Quick Start

### 1. Start Trino

```bash
cd /Users/leeum21/Documents/Werk/Projects/data-platform
docker-compose --profile standard up -d trino
```

### 2. Wacht tot Trino ready is

```bash
# Check health status
docker-compose ps trino

# Follow logs
docker-compose logs -f trino
```

Trino is ready wanneer je ziet:
```
======== SERVER STARTED ========
```

Dit kan 30-60 seconden duren.

### 3. Open Trino Web UI

Open http://localhost:8080 in je browser.

### 4. Test met Trino CLI

```bash
# Start Trino CLI
docker-compose exec trino trino

# Of vanaf je laptop (als je de Trino CLI geïnstalleerd hebt)
trino --server localhost:8080
```

## Basis SQL queries

### Catalogs en schemas bekijken

```sql
-- Toon alle catalogs
SHOW CATALOGS;

-- Toon schemas in een catalog
SHOW SCHEMAS FROM postgresql;
SHOW SCHEMAS FROM minio;

-- Toon tabellen
SHOW TABLES FROM postgresql.public;
```

### PostgreSQL queries

```sql
-- Query PostgreSQL data
SELECT * FROM postgresql.public.cell_towers.clean_204 LIMIT 10;

-- Cross-catalog joins mogelijk!
```

### MinIO (Data Lake) queries

```sql
-- Create schema in MinIO
CREATE SCHEMA IF NOT EXISTS minio.bronze
WITH (location = 's3a://lake/bronze/');

-- Create table from CSV in MinIO
CREATE TABLE minio.bronze.cell_towers (
    radio VARCHAR,
    mcc INTEGER,
    net INTEGER,
    area INTEGER,
    cell BIGINT,
    unit INTEGER,
    lon DOUBLE,
    lat DOUBLE,
    range INTEGER,
    samples INTEGER,
    changeable INTEGER,
    created BIGINT,
    updated BIGINT,
    average_signal INTEGER
)
WITH (
    external_location = 's3a://lake/raw/celltowers/',
    format = 'CSV',
    skip_header_line_count = 1
);

-- Query de data
SELECT * FROM minio.bronze.cell_towers LIMIT 10;
```

### TPCH test queries

```sql
-- Test data is direct beschikbaar
SELECT * FROM tpch.tiny.nation;
SELECT * FROM tpch.tiny.customer LIMIT 10;

-- Complexe test query
SELECT 
    n.name as country,
    COUNT(*) as customer_count
FROM tpch.tiny.customer c
JOIN tpch.tiny.nation n ON c.nationkey = n.nationkey
GROUP BY n.name
ORDER BY customer_count DESC;
```

## Use cases

### 1. Data Lake queries (MinIO)

Query je raw/clean data in MinIO zonder data te kopiëren:

```sql
-- Bronze layer (raw data)
SELECT COUNT(*) FROM minio.bronze.cell_towers;

-- Silver layer (cleaned/transformed)
CREATE TABLE minio.silver.cell_towers_netherlands AS
SELECT * 
FROM minio.bronze.cell_towers
WHERE mcc = 204;  -- Netherlands
```

### 2. Federated queries

Combineer data van verschillende bronnen:

```sql
-- Join PostgreSQL warehouse met MinIO data lake
SELECT 
    pg.radio,
    COUNT(*) as warehouse_count,
    AVG(minio.range) as avg_range_in_lake
FROM postgresql.cell_towers.clean_204 pg
LEFT JOIN minio.bronze.cell_towers minio 
    ON pg.cell = minio.cell
GROUP BY pg.radio;
```

### 3. ETL met CREATE TABLE AS

```sql
-- Extract van PostgreSQL, transform, load naar MinIO
CREATE TABLE minio.gold.cell_tower_summary
WITH (
    format = 'PARQUET',
    external_location = 's3a://lake/gold/cell_tower_summary/'
)
AS
SELECT 
    radio,
    COUNT(*) as tower_count,
    AVG(range) as avg_range,
    AVG(lat) as avg_latitude,
    AVG(lon) as avg_longitude
FROM postgresql.cell_towers.clean_204
GROUP BY radio;
```

## MinIO bucket setup

Zorg dat de MinIO bucket bestaat:

```bash
# Install MinIO client (eenmalig)
brew install minio/stable/mc

# Configure alias
mc alias set local http://localhost:9000 minio minio12345

# Create bucket (als die nog niet bestaat)
mc mb local/lake

# List buckets
mc ls local

# Upload test data
mc cp your-data.csv local/lake/raw/test/
```

## Performance tips

### Voor je M2 Pro (16GB RAM)

De huidige configuratie is geoptimaliseerd voor lokaal gebruik:

**JVM Settings** (`jvm.config`):
- Heap: 1GB (Xmx/Xms)
- G1GC garbage collector
- Geoptimaliseerd voor Apple Silicon

**Docker Resources**:
- Limit: 2GB
- Reserved: 1GB

### Query optimalisatie

```sql
-- Gebruik EXPLAIN om query plan te zien
EXPLAIN SELECT * FROM minio.bronze.cell_towers WHERE mcc = 204;

-- ANALYZE voor statistieken
ANALYZE minio.bronze.cell_towers;

-- Gebruik efficiënte formaten (Parquet > CSV)
CREATE TABLE ... WITH (format = 'PARQUET') AS ...
```

### Partitionering

Voor grote datasets, gebruik partitioning:

```sql
CREATE TABLE minio.silver.cell_towers_partitioned (
    radio VARCHAR,
    cell BIGINT,
    lat DOUBLE,
    lon DOUBLE,
    mcc INTEGER
)
WITH (
    external_location = 's3a://lake/silver/cell_towers/',
    format = 'PARQUET',
    partitioned_by = ARRAY['mcc']
);
```

## Configuratie bestanden

```
trino/
├── config.properties       # Trino server configuratie
├── node.properties         # Node identificatie
├── jvm.config             # JVM settings (geheugen, GC)
└── catalog/               # Data source connectors
    ├── postgresql.properties
    ├── minio.properties
    └── tpch.properties
```

## Troubleshooting

### Trino start niet op

```bash
# Check logs
docker-compose logs trino

# Veel voorkomende oorzaken:
# 1. Niet genoeg geheugen (verhoog Docker memory limit)
# 2. Poort 8080 al in gebruik (wijzig in docker-compose.yml)
# 3. Config syntax errors (check .properties files)
```

### MinIO connectie werkt niet

```bash
# Test MinIO toegang
docker-compose exec trino curl http://minio:9000

# Check credentials in minio.properties
# Moeten matchen met MINIO_ROOT_USER/PASSWORD in docker-compose.yml
```

### Query is traag

```sql
-- Check query details in Web UI
-- http://localhost:8080 → Click op je query

-- Optimalisaties:
-- 1. Gebruik Parquet ipv CSV
-- 2. Partitioneer grote tabellen
-- 3. Gebruik predicates (WHERE clauses) vroeg in query
-- 4. Vermijd SELECT * op grote datasets
```

### Out of memory errors

Als je OOM errors krijgt:

**Optie 1**: Verhoog JVM heap in `jvm.config`:
```
-Xmx2G
-Xms2G
```

**Optie 2**: Verhoog Docker memory limit in `docker-compose.yml`:
```yaml
deploy:
  resources:
    limits:
      memory: 3g
```

**Let op**: Je hebt 16GB totaal, dus verdeel slim over alle services.

## Python/Jupyter integratie

Installeer de Trino Python client:

```bash
pip install trino sqlalchemy-trino
```

Gebruik in Python:

```python
import trino

# Basic connection
conn = trino.dbapi.connect(
    host='localhost',
    port=8080,
    user='admin',
    catalog='postgresql',
    schema='public'
)

cur = conn.cursor()
cur.execute('SELECT * FROM cell_towers.clean_204 LIMIT 10')
rows = cur.fetchall()

# Met SQLAlchemy
from sqlalchemy import create_engine

engine = create_engine('trino://localhost:8080/postgresql')
df = pd.read_sql('SELECT * FROM cell_towers.clean_204 LIMIT 100', engine)
```

## DBeaver / SQL Client setup

**Connectie instellingen**:
- **Host**: localhost
- **Port**: 8080
- **Database/Catalog**: postgresql (of minio, tpch)
- **Schema**: public
- **User**: admin (of willekeurig)
- **Password**: (leeg laten)

## Monitoring

### Web UI

http://localhost:8080 toont:
- Active queries
- Query history
- Worker status
- Memory usage
- Data processed

### CLI monitoring

```bash
# Check running queries
docker-compose exec trino trino --execute "SHOW QUERIES"

# Check system info
docker-compose exec trino trino --execute "SELECT * FROM system.runtime.nodes"
```

## Resource gebruik overzicht

Voor je hele platform op 16GB MacBook:

| Service | Memory | Cumulative |
|---------|--------|-----------|
| postgres | 1GB | 1GB |
| superset | 1.5GB | 2.5GB |
| minio | 1GB | 3.5GB |
| **trino** | **2GB** | **5.5GB** |
| marquez | ~500MB | 6GB |
| postgres_konga | 512MB | 6.5GB |
| kong | 512MB | 7GB |
| konga | 512MB | 7.5GB |
| etl (tijdelijk) | ~500MB | 8GB |
| **macOS + apps** | **~6GB** | **~14GB** |
| **Buffer** | **~2GB** | **~16GB** |

Dit is krap maar haalbaar. Je kunt altijd services stoppen die je niet gebruikt:

```bash
# Stop services die je niet nodig hebt
docker-compose stop marquez marquez-web konga kong
```

## Nuttige links

- [Trino Docs](https://trino.io/docs/current/)
- [Hive Connector](https://trino.io/docs/current/connector/hive.html)
- [PostgreSQL Connector](https://trino.io/docs/current/connector/postgresql.html)
- [SQL Reference](https://trino.io/docs/current/sql.html)
- [Performance Tuning](https://trino.io/docs/current/admin/properties.html)
