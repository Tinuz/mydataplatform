# 🚀 Superset Quick Reference Card

## Database Connection Strings

```bash
# PostgreSQL - Cell Towers & Crypto Data
postgresql://superset:superset@postgres:5432/superset

# DuckDB - Iceberg/Parquet Analytics (Recommended!)
duckdb:///:memory:
```

---

## Essential DuckDB Setup (Copy-Paste)

```sql
INSTALL httpfs; LOAD httpfs;
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio12345';
SET s3_use_ssl=false;
SET s3_url_style='path';
```

---

## Top 5 Queries

### 1. Latest Crypto Prices (DuckDB)
```sql
SELECT symbol, price, event_time
FROM read_parquet('s3://lake/crypto/trades_bronze/data/*.parquet')
QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY event_time DESC) = 1;
```

### 2. OHLCV Candles (DuckDB)
```sql
SELECT symbol, minute, open_price, high_price, low_price, close_price, volume
FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet')
ORDER BY minute DESC LIMIT 20;
```

### 3. Volume Analysis (DuckDB)
```sql
SELECT symbol, SUM(volume) as total_volume, AVG(close_price) as avg_price
FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet')
GROUP BY symbol;
```

### 4. Cell Tower Density (PostgreSQL)
```sql
SELECT mcc, COUNT(*) as tower_count
FROM cell_towers.clean_204 
GROUP BY mcc ORDER BY tower_count DESC LIMIT 20;
```

### 5. Network Distribution (PostgreSQL)
```sql
SELECT net, COUNT(*) as towers, AVG(samples) as avg_samples
FROM cell_towers.clean_204 
GROUP BY net ORDER BY towers DESC;
```

---

## Quick Chart Types

| Data Type | Best Chart | Example |
|-----------|------------|---------|
| Latest values | **Table** | Crypto prices |
| Time series | **Line Chart** | Price over time |
| Comparison | **Bar Chart** | Volume by symbol |
| Distribution | **Histogram** | Price distribution |
| Geographic | **Map** | Cell tower locations |

---

## Dashboard Tips

- ✅ **Auto-refresh**: 30s (crypto), 5min (cell towers)
- ✅ **Filters**: Add symbol selector, date range
- ✅ **Layout**: Use 2-3 columns, keep charts focused
- ✅ **Cache**: Enable for static data, disable for real-time
- ✅ **Alerts**: Set up for price thresholds

---

## Access URLs

```bash
# Superset UI
http://localhost:8088
Login: admin / admin

# MinIO Console (data verification)
http://localhost:9001
Login: minio / minio12345
```

---

## Emergency Commands

```bash
# Restart Superset
docker-compose restart superset

# Check database connections
docker-compose exec superset superset db upgrade

# Reset admin password
docker-compose exec superset superset fab create-admin \
  --username admin --firstname Admin --lastname User \
  --email admin@superset.com --password admin

# View logs
docker-compose logs -f superset
```
