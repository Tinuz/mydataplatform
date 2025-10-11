# Superset + Trino Integratie

## Probleem
De standaard Apache Superset image bevat niet de Trino database driver. Dit moet apart worden geïnstalleerd.

## Oplossing

### Optie 1: Environment Variable (Eenvoudigst)

De `PIP_ADDITIONAL_REQUIREMENTS` environment variable is al geconfigureerd in docker-compose.yml:

```yaml
environment:
  PIP_ADDITIONAL_REQUIREMENTS: "psycopg2-binary==2.9.9 trino==0.328.0 sqlalchemy-trino==0.5.0"
```

**Let op**: Deze packages worden tijdens container startup geïnstalleerd, wat de startup tijd verlengt.

### Optie 2: Handmatige installatie (Tijdelijk)

Als de automatische installatie niet werkt, installeer handmatig:

```bash
# Installeer packages als root
docker-compose exec -u root superset pip install trino==0.328.0 sqlalchemy-trino==0.5.0

# Herstart Superset
docker-compose restart superset
```

**Nadeel**: Packages gaan verloren bij een complete container rebuild (`docker-compose down`).

### Optie 3: Custom Dockerfile (Permanent)

Voor een permanente oplossing, maak een custom Dockerfile:

```dockerfile
# superset/Dockerfile
FROM apache/superset:latest

# Switch to root voor pip install
USER root

# Installeer extra drivers
RUN pip install --no-cache-dir \
    trino==0.328.0 \
    sqlalchemy-trino==0.5.0 \
    psycopg2-binary==2.9.9

# Terug naar superset user
USER superset
```

Update docker-compose.yml:

```yaml
superset:
  build:
    context: ./superset
    dockerfile: Dockerfile
  container_name: dp_superset
  # ... rest van config
```

## Trino Connectie toevoegen in Superset

### 1. Login in Superset
- URL: http://localhost:8088
- User: `admin`
- Pass: `admin`

### 2. Ga naar Data → Databases

### 3. Klik "+ Database"

### 4. Selecteer "Trino" uit de lijst

Als Trino niet in de lijst staat, zijn de drivers nog niet geladen. Herstart Superset.

### 5. Vul connection details in

**SQL Alchemy URI**:
```
trino://trino:8080/catalog
```

Vervang `catalog` met de catalog die je wilt gebruiken:
- `trino://trino:8080/tpch` - Voor test data
- `trino://trino:8080/postgresql` - Voor PostgreSQL catalog
- `trino://trino:8080/minio` - Voor MinIO data lake

**Of gebruik deze format voor specifieke schema**:
```
trino://trino:8080/catalog/schema
```

Bijvoorbeeld:
- `trino://trino:8080/tpch/tiny`
- `trino://trino:8080/postgresql/public`
- `trino://trino:8080/minio/bronze`

### 6. Test de connectie

Klik op "Test Connection" onderaan.

Als het werkt zie je: ✅ "Connection looks good!"

### 7. Save

Geef de database een naam zoals "Trino - TPCH" of "Trino - Data Lake".

## Voorbeelden

### Dataset 1: TPCH Test Data

1. Database: `trino://trino:8080/tpch`
2. Create Dataset → Select table `tiny.nation`
3. Build chart met landen en hun regio's

### Dataset 2: PostgreSQL via Trino

1. Database: `trino://trino:8080/postgresql`
2. Query je warehouse data via Trino
3. Voordeel: Je kunt federeren met andere catalogs

### Dataset 3: MinIO Data Lake

1. Database: `trino://trino:8080/minio`
2. Create schemas eerst in Trino:
   ```sql
   CREATE SCHEMA minio.bronze WITH (location = 's3a://lake/bronze/');
   ```
3. Create tables in Trino
4. Query via Superset

## SQL Lab gebruiken

### 1. Ga naar SQL Lab → SQL Editor

### 2. Selecteer je Trino database

### 3. Run queries

```sql
-- Test query
SELECT * FROM tiny.nation;

-- Federated query (join verschillende catalogs)
SELECT 
    pg.id,
    tpch.name
FROM postgresql.public.my_table pg
JOIN tpch.tiny.nation tpch
    ON pg.nation_key = tpch.nationkey;
```

### 4. Save & Explore

Na een succesvolle query kun je:
- "Save" → Create dataset
- "Explore" → Direct chart maken

## Troubleshooting

### Error: "Could not load database driver: TrinoEngineSpec"

**Oorzaak**: Trino packages niet geïnstalleerd.

**Oplossing**:
```bash
docker-compose exec -u root superset pip install trino==0.328.0 sqlalchemy-trino==0.5.0
docker-compose restart superset
```

### Error: "No module named 'trino'"

**Oorzaak**: Zelfde als hierboven.

**Oplossing**: Installeer packages (zie boven).

### Connection timeout

**Oorzaak**: Trino is niet bereikbaar of nog niet opgestart.

**Check**:
```bash
# Is Trino healthy?
docker-compose ps trino

# Test connectie vanuit Superset container
docker-compose exec superset curl http://trino:8080/v1/info
```

### "Catalog not found"

**Oorzaak**: Verkeerde catalog naam in connection string.

**Oplossing**:
```bash
# Check beschikbare catalogs
docker-compose exec trino trino --execute "SHOW CATALOGS;"
```

Gebruik een van de getoonde catalog namen in je connection string.

### Query werkt in Trino CLI maar niet in Superset

**Mogelijke oorzaken**:
1. **Schema niet specified**: Voeg `/schema` toe aan connection string
2. **Permissions**: Superset user heeft geen rechten (niet van toepassing in onze setup)
3. **Syntax verschillen**: SQLAlchemy kan queries anders interpreteren

**Oplossing**: Test de exacte query eerst in SQL Lab.

## Performance Tips

### 1. Gebruik Trino voor grote datasets

Trino is geoptimaliseerd voor analytische queries op grote data. Gebruik het voor:
- Data lake queries (MinIO)
- Cross-database joins
- Heavy aggregations

### 2. Cache configureren in Superset

In Superset settings:
```python
CACHE_CONFIG = {
    'CACHE_TYPE': 'SimpleCache',
    'CACHE_DEFAULT_TIMEOUT': 60 * 60 * 24  # 24 hours
}
```

### 3. Gebruik materialized views

Create summary tables in Trino:
```sql
CREATE TABLE minio.gold.summary AS
SELECT 
    date_trunc('day', timestamp) as day,
    COUNT(*) as records
FROM minio.bronze.raw_data
GROUP BY 1;
```

Query de summary table in Superset voor snellere dashboards.

### 4. Partitioneer grote tabellen

```sql
CREATE TABLE minio.silver.partitioned (
    value DOUBLE,
    date_key VARCHAR
)
WITH (
    partitioned_by = ARRAY['date_key'],
    format = 'PARQUET'
);
```

Superset queries worden sneller door partition pruning.

## Alternatieve Connecties

### Via host.docker.internal (Mac/Windows)

Als `trino` hostname niet werkt:
```
trino://host.docker.internal:8080/catalog
```

### Via localhost (not recommended)

Alleen als je Superset buiten Docker draait:
```
trino://localhost:8080/catalog
```

## Voorbeeldgebruik: Complete Data Flow

### 1. Data in MinIO (via ETL)
```python
# ETL script schrijft naar MinIO
s3.upload_file('data.csv', 'lake', 'bronze/data.csv')
```

### 2. Create table in Trino
```sql
CREATE TABLE minio.bronze.data (
    id INTEGER,
    value DOUBLE
)
WITH (
    external_location = 's3a://lake/bronze/',
    format = 'CSV'
);
```

### 3. Transform in Trino
```sql
CREATE TABLE minio.silver.clean_data AS
SELECT id, value
FROM minio.bronze.data
WHERE value IS NOT NULL;
```

### 4. Query in Superset
- Connect: `trino://trino:8080/minio`
- Dataset: `silver.clean_data`
- Build charts & dashboards

### 5. Monitor in Marquez
ETL pipeline schrijft lineage naar Marquez:
- Source: MinIO bronze
- Transform: Trino SQL
- Destination: MinIO silver
- Consumer: Superset

## Package Versies

Huidige configuratie:
```
trino==0.328.0
sqlalchemy-trino==0.5.0
psycopg2-binary==2.9.9
```

**Update packages**:
```bash
# Check latest versions
pip index versions trino
pip index versions sqlalchemy-trino

# Update in docker-compose.yml
PIP_ADDITIONAL_REQUIREMENTS: "... trino==X.Y.Z sqlalchemy-trino==A.B.C"
```

## Resources

- [Superset Docs - Trino](https://superset.apache.org/docs/databases/trino/)
- [Trino Python Client](https://github.com/trinodb/trino-python-client)
- [SQLAlchemy Trino](https://github.com/trinodb/sqlalchemy-trino)
