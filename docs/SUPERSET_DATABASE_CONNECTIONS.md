# 🔌 Superset Database Connections Guide

Complete guide voor het connecten van alle databases in Superset.

> **⚠️ UPDATE (12 okt 2025)**: Trino is verwijderd uit het platform.  
> Gebruik **DuckDB** voor Iceberg queries en **PostgreSQL** voor data warehouse.  
> Zie `TRINO_REMOVAL_SUMMARY.md` voor details.

---

## ⚡ Quick Setup (5 minuten)

### 1. Open Superset
```
http://localhost:8088
Login: admin / admin
```

### 2. Ga naar Database Connections
**Settings (⚙️) → Data → Database Connections → + Database**

---

## 📊 Database 1: PostgreSQL (Cell Towers Data)

### Connection Details

**Display Name**: `PostgreSQL - Data Platform`

**SQLAlchemy URI**:
```
postgresql://superset:superset@postgres:5432/superset
```

**Advanced → Security → Impersonate logged in user**: ❌ (uit)

**Advanced → SQL Lab**:
- ✅ Expose database in SQL Lab
- ✅ Allow CREATE TABLE AS
- ✅ Allow CREATE VIEW AS
- ✅ Allow DML

**Advanced → Performance**:
- ✅ Enable query cost estimation
- ✅ Cache timeout: `300` (5 minuten)

### Test Connection
Klik **"Test Connection"** → Moet ✅ zijn!

### Sample Query (Test in SQL Lab)
```sql
-- Bekijk beschikbare schemas
SELECT schema_name 
FROM information_schema.schemata 
WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name;

-- Cell towers data
SELECT 
    mcc,
    COUNT(*) as tower_count,
    COUNT(DISTINCT net) as network_count
FROM cell_towers.clean_204 
GROUP BY mcc
ORDER BY tower_count DESC
LIMIT 10;
```

---

## 🐘 ~~Database 2: Trino (Iceberg Catalog)~~ **DEPRECATED**

> **⚠️ DEPRECATED**: Trino has been removed from this platform.  
> **Alternative**: Use DuckDB for Iceberg queries (see Database 3 below).

<details>
<summary>📜 Legacy Trino Setup (for reference only)</summary>

### Connection Details

**Display Name**: `Trino - Iceberg`

**SQLAlchemy URI**:
```
trino://trino@trino:8080/iceberg
```

**Advanced → Security → Impersonate logged in user**: ❌ (uit)

**Advanced → SQL Lab**:
- ✅ Expose database in SQL Lab
- ✅ Allow CREATE TABLE AS
- ✅ Allow CREATE VIEW AS
- ⚠️ Allow DML: ❌ (uit voor Iceberg read-only)

**Advanced → Performance**:
- ✅ Asynchronous query execution
- ✅ Cancel query on window unload
- ✅ Cache timeout: `300` (5 minuten)

**Advanced → Other → Engine Parameters**:
```json
{
  "connect_args": {
    "session_properties": {
      "query_max_run_time": "10m",
      "query_max_execution_time": "10m"
    }
  }
}
```

### Test Connection
Klik **"Test Connection"** → Moet ✅ zijn!

⚠️ **Note**: Zoals we eerder ontdekten, Trino heeft issues met het `tabulario/iceberg-rest` catalog. Als je errors ziet bij queries, gebruik dan DuckDB (zie hieronder).

### Sample Query (Als Trino werkt)
```sql
-- Check beschikbare schemas
SHOW SCHEMAS FROM iceberg;

-- Check beschikbare tabellen
SHOW TABLES FROM iceberg.crypto;

-- Query crypto data (als het werkt)
SELECT 
    symbol,
    COUNT(*) as trade_count,
    SUM(quantity) as total_volume
FROM iceberg.crypto.trades_bronze
GROUP BY symbol;
```

</details>

---

## 🦆 Database 3: DuckDB (Recommended voor Iceberg/Parquet!)

### Connection Details

**Display Name**: `DuckDB - Crypto Analytics`

**SQLAlchemy URI**:
```
duckdb:///:memory:
```

**Advanced → SQL Lab**:
- ✅ Expose database in SQL Lab
- ✅ Allow CREATE TABLE AS
- ✅ Allow CREATE VIEW AS
- ✅ Allow DML

### Test Connection
Klik **"Test Connection"** → Moet ✅ zijn!

### Sample Queries

#### Setup Query (Run dit eerst in elke session!)
```sql
-- Installeer S3 extension en configureer MinIO
INSTALL httpfs; 
LOAD httpfs;

SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio12345';
SET s3_use_ssl=false;
SET s3_url_style='path';
```

#### Query 1: Latest Crypto Prices
```sql
SELECT 
    symbol,
    price as latest_price,
    quantity,
    event_time
FROM read_parquet('s3://lake/crypto/trades_bronze/data/*.parquet')
QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY event_time DESC) = 1
ORDER BY symbol;
```

#### Query 2: OHLCV Candles (Silver Layer)
```sql
SELECT 
    symbol,
    minute,
    open_price,
    high_price,
    low_price,
    close_price,
    volume,
    trade_count
FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet')
ORDER BY minute DESC
LIMIT 20;
```

#### Query 3: Volume Analysis
```sql
SELECT 
    symbol,
    SUM(volume) as total_volume,
    COUNT(*) as candle_count,
    ROUND(AVG(close_price), 2) as avg_price,
    MIN(close_price) as min_price,
    MAX(close_price) as max_price
FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet')
GROUP BY symbol
ORDER BY total_volume DESC;
```

---

## 📋 Connection Summary

| Database | Purpose | Performance | Best For |
|----------|---------|-------------|----------|
| **PostgreSQL** | Cell towers, crypto aggregates | Fast (local) | Traditional SQL, JOINs, dashboards |
| **DuckDB** | Iceberg/Parquet analytics | ⚡ Fastest (<100ms) | Raw data, OLAP, quick analytics |

---

## 🎨 Creating Your First Chart

### Chart 1: Latest Crypto Prices (DuckDB)

1. **SQL Lab** → Database: `DuckDB - Crypto Analytics`
2. **Run setup query** (INSTALL httpfs; SET s3_endpoint=...)
3. **Run this query**:
```sql
SELECT 
    symbol,
    price as latest_price,
    event_time
FROM read_parquet('s3://lake/crypto/trades_bronze/data/*.parquet')
QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY event_time DESC) = 1
ORDER BY symbol;
```
4. **Save → Save as Dataset** → Name: `crypto_latest_prices`
5. **Create Chart**:
   - Chart type: **Table**
   - Columns: `symbol`, `latest_price`, `event_time`
   - Save to dashboard: `Crypto Monitor`

### Chart 2: Cell Tower Density (PostgreSQL)

1. **SQL Lab** → Database: `PostgreSQL - Data Platform`
2. **Run this query**:
```sql
SELECT 
    mcc,
    COUNT(*) as tower_count,
    COUNT(DISTINCT net) as network_count
FROM cell_towers.clean_204 
GROUP BY mcc
ORDER BY tower_count DESC
LIMIT 20;
```
3. **Save → Save as Dataset** → Name: `cell_tower_density`
4. **Create Chart**:
   - Chart type: **Bar Chart**
   - X-axis: `mcc`
   - Y-axis: `tower_count`
   - Sort: Descending
   - Save to dashboard: `Cell Towers Analysis`

---

## 🔧 Troubleshooting

### Error: "Can't connect to database"

**PostgreSQL**:
```bash
# Check if postgres is running
docker-compose ps postgres

# Test connection from host
docker-compose exec postgres psql -U superset -d superset -c "SELECT version();"
```

**Trino**:
```bash
# Check if trino is running
docker-compose ps trino

# Check Trino status
curl -s http://localhost:8090/v1/info | jq .
```

**DuckDB**:
- No server needed! Just make sure Superset container has duckdb-engine installed
- Test: `docker-compose exec superset python -c "import duckdb; print('OK')"`

### Error: "Cannot read S3 files" (DuckDB)

Run setup query first:
```sql
INSTALL httpfs; 
LOAD httpfs;
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio12345';
SET s3_use_ssl=false;
SET s3_url_style='path';
```

### Error: "ICEBERG_CATALOG_ERROR" (Trino)

Dit is een bekend issue. Gebruik DuckDB als alternatief:
- DuckDB leest dezelfde Parquet files
- 10x sneller dan Trino
- Geen catalog issues
- Zie: `docs/DUCKDB_SUPERSET_GUIDE.md`

### Error: "Permission denied" (PostgreSQL)

Check user permissions:
```sql
-- In postgres container
GRANT ALL PRIVILEGES ON DATABASE superset TO superset;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA cell_towers TO superset;
GRANT USAGE ON SCHEMA cell_towers TO superset;
```

---

## 💡 Pro Tips

### 1. Save Frequent Queries as Saved Queries
**SQL Lab → Saved Queries → + Saved Query**
- Name: "Crypto Latest Prices"
- Label: "crypto, prices, latest"
- Description: "Shows latest trade price for each symbol"

### 2. Use Virtual Datasets for Complex Queries
Instead of creating views in the database, use Superset's virtual datasets:
- Run your query in SQL Lab
- Save → Save as Dataset
- Mark as "Virtual" (query-based)

### 3. Set Cache Timeouts
For real-time data:
- Crypto data: 30 seconds
- Cell tower data: 5 minutes (static)
- Configuration in Database → Edit → Advanced → Performance

### 4. Enable Asynchronous Queries (Trino)
For long-running queries:
- Database → Edit → Advanced → Performance
- ✅ Enable asynchronous query execution
- Set timeout: 10 minutes

### 5. Create Parameterized Queries
Use Jinja templates in SQL Lab:
```sql
SELECT * FROM crypto_trades 
WHERE symbol = '{{ symbol }}'
AND event_time > '{{ start_date }}'
LIMIT {{ limit }};
```

---

## 📚 Next Steps

1. ✅ **Connect databases** (PostgreSQL + DuckDB)
2. ✅ **Test sample queries** in SQL Lab
3. ✅ **Create your first chart** (Latest Crypto Prices)
4. ✅ **Build a dashboard** with 3-4 charts
5. ✅ **Set up auto-refresh** (30s for crypto, 5min for cell towers)
6. ✅ **Share dashboard** with team!

---

## 🔗 Related Documentation

- **DuckDB Setup**: `docs/DUCKDB_SUPERSET_GUIDE.md`
- **Data Catalog**: `docs/DATA_CATALOG.md`
- **Trino Removal**: `TRINO_REMOVAL_SUMMARY.md`

Happy querying! 🚀
