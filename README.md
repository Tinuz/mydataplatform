# 🚀 Modern Data Platform

Complete modern data platform with streaming, lakehouse, visualization, and governance capabilities.

---

## 🎯 Platform Overview

**End-to-end data platform featuring:**
- 📊 **Data Warehousing**: PostgreSQL with cell towers & crypto data  
- 🌊 **Streaming**: Kafka + Iceberg REST catalog for real-time crypto trades
- 🎨 **Visualization**: Apache Superset for dashboards & analytics
- 🔧 **Orchestration**: Dagster for workflow management
- 🔍 **Query Engine**: DuckDB for fast SQL analytics
- 📦 **Data Lake**: MinIO (S3-compatible) for Iceberg tables
- 🚪 **API Gateway**: Kong + Konga for API management
- 📈 **Lineage**: Marquez for data lineage tracking
- 🔎 **Catalog**: Amundsen for data discovery

---

## ⚡ Quick Start (5 minutes)

### 1. Start the Platform

```bash
# Option A: Minimal (Superset + PostgreSQL + MinIO + Dagster)
docker-compose --profile tiny up -d

# Option B: Full platform (all features except streaming)
docker-compose --profile standard up -d

# Option C: With streaming (includes Kafka + Iceberg)
docker-compose --profile streaming up -d

# Option D: With data catalog (includes Amundsen)
docker-compose --profile amundsen up -d
```

### 2. Initialize Platform

```bash
# Run bootstrap script to initialize all services
./scripts/bootstrap.sh
```

**This script will:**
- ✅ Wait for all services to be healthy
- ✅ Initialize Superset (DB migrations, admin user, permissions)
- ✅ Create MinIO bucket for data lake
- ✅ Sync crypto data to PostgreSQL (if available)

**First-time setup:** Takes ~2 minutes

### 3. Access Services

| Service | URL | Credentials | Purpose |
|---------|-----|-------------|---------|
| **Superset** | http://localhost:8088 | admin/admin | Dashboards & Visualization |
| **Dagster** | http://localhost:3000 | - | Workflow Orchestration |
| **MinIO Console** | http://localhost:9001 | minio/minio12345 | S3-compatible Data Lake |
| **Marquez UI** | http://localhost:3001 | - | Data Lineage |
| **Konga** | http://localhost:1337 | Setup on first run | API Gateway UI |
| **Amundsen** | http://localhost:5005 | - | Data Catalog |

---

## 📊 Available Datasets

### Cell Towers Dataset
- **Source**: OpenCellID via Google Cloud Storage
- **Records**: 47,114 cell tower locations
- **Schema**: `cell_towers.clean_204`
- **Columns**: mcc, net, area, cell, unit, lon, lat, range, samples, changeable, created, updated, averageSignal

### Crypto Streaming Dataset (Optional)
- **Source**: Binance WebSocket → Kafka → Iceberg
- **Bronze Layer**: `crypto.trades_bronze` (raw trades)
- **Silver Layer**: `crypto.trades_1min` (OHLCV candles aggregated per minute)
- **Symbols**: ETHUSDT, BNBUSDT
- **Setup**: See [Crypto Stream Quickstart](docs/CRYPTO_STREAM_QUICKSTART.md)

---

## 🚀 Common Workflows

### Load Cell Towers Data (One-time)

```bash
# Run ETL job to load cell towers from GCS
docker-compose up etl
```

**What it does:**
1. Downloads 204.csv from Google Cloud Storage
2. Loads to staging table in PostgreSQL
3. Cleans and validates data
4. Creates final table `cell_towers.clean_204`
5. Registers metadata in Marquez

### Start Crypto Streaming Pipeline

```bash
# 1. Start streaming services
docker-compose --profile streaming up -d

# 2. Materialize bronze layer (consumes Kafka → Iceberg)
docker-compose exec dagster dagster asset materialize -m crypto_stream --select crypto_trades_bronze

# 3. Materialize silver layer (aggregates to 1-minute candles)
docker-compose exec dagster dagster asset materialize -m crypto_stream --select crypto_trades_1min

# 4. Sync to PostgreSQL for Superset
./scripts/bootstrap.sh
```

### Query Data in Superset

```bash
# 1. Open Superset
open http://localhost:8088

# 2. Login: admin / admin

# 3. SQL Lab → Database: PostgreSQL - Data Platform

# 4. Run queries:
# Cell towers by country
SELECT mcc, COUNT(*) as tower_count
FROM cell_towers.clean_204
GROUP BY mcc
ORDER BY tower_count DESC
LIMIT 10;

# Latest crypto prices
SELECT * FROM crypto.latest_prices;

# OHLCV candles
SELECT * FROM crypto.trades_1min
ORDER BY minute DESC
LIMIT 20;
```

---

## 📚 Documentation

### 🎓 Getting Started
- 🚀 **[Quick Reference](docs/QUICK_REFERENCE.md)** - Essential commands & workflows
- 👨‍💻 **[Data Engineer Onboarding](docs/DATA_ENGINEER_ONBOARDING.md)** - Complete onboarding guide
- 📊 **[Platform Status](docs/PLATFORM_STATUS.md)** - Current capabilities

### 💰 Crypto Streaming
- 🏗️ **[Crypto Stream Architecture](docs/CRYPTO_STREAM_ARCHITECTURE.md)** - System design
- ⚡ **[Crypto Stream Quickstart](docs/CRYPTO_STREAM_QUICKSTART.md)** - Get started guide

### 📊 Superset & Visualization
- 🔌 **[Superset Database Connections](docs/SUPERSET_DATABASE_CONNECTIONS.md)** - PostgreSQL & DuckDB setup
- ✅ **[Superset Problem Solved](docs/SUPERSET_PROBLEM_SOLVED.md)** - DuckDB workarounds
- 🦆 **[DuckDB Superset Guide](docs/DUCKDB_SUPERSET_GUIDE.md)** - Fast analytics on Parquet/Iceberg
- 📋 **[Superset Quick Reference](docs/SUPERSET_QUICK_REFERENCE.md)** - Connection strings & queries

### 🔧 Platform Components
- 🌤️ **[Weather API](docs/WEATHER_API.md)** - RESTful weather data API (bonus feature)
- 🔧 **[Dagster gRPC Fix](docs/DAGSTER_GRPC_FIX.md)** - Troubleshooting guide
- 📈 **[Marquez Integration](docs/MARQUEZ_INTEGRATION.md)** - Data lineage setup

---

## 🏗️ Architecture

### Data Flow

```
┌─────────────────┐
│  Data Sources   │
│  - GCS (CSV)    │
│  - Binance WS   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Ingestion      │
│  - ETL Jobs     │
│  - Kafka        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Storage        │
│  - PostgreSQL   │
│  - MinIO/Iceberg│
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Query Layer    │
│  - DuckDB       │
│  - PostgreSQL   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Presentation   │
│  - Superset     │
│  - APIs         │
└─────────────────┘
```

### Service Dependencies

```
PostgreSQL (Core Database)
    ├── Superset (requires PostgreSQL)
    ├── Dagster (metadata storage)
    ├── Marquez (lineage storage)
    └── ETL jobs (data warehouse)

MinIO (Data Lake)
    ├── Iceberg REST Catalog
    └── Dagster (Iceberg I/O)

Kafka (Streaming)
    └── Dagster crypto_stream (consumer)
```

---

## 🧹 Maintenance

### Stop & Clean

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (DELETES ALL DATA!)
docker-compose down -v

# Clean up unused images
docker system prune -a
```

### Restart from Scratch

```bash
# 1. Stop everything and remove volumes
docker-compose down -v

# 2. Start services
docker-compose --profile standard up -d

# 3. Run bootstrap
./scripts/bootstrap.sh

# 4. Load data
docker-compose up etl

# Done! Everything is fresh and initialized
```

### Backup Important Data

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U superset superset > backup_$(date +%Y%m%d).sql

# Backup MinIO bucket
docker-compose exec dagster python3 -c "
from minio import Minio
client = Minio('minio:9000', access_key='minio', secret_key='minio12345', secure=False)
# Use minio client to download bucket contents
"

# Restore PostgreSQL
cat backup_20251012.sql | docker-compose exec -T postgres psql -U superset -d superset
```

---

## 🐛 Troubleshooting

### Service won't start

```bash
# Check service status
docker-compose ps

# View logs
docker-compose logs -f <service_name>

# Restart specific service
docker-compose restart <service_name>
```

### Superset can't connect to database

```bash
# Re-initialize Superset
docker-compose exec superset superset db upgrade
docker-compose exec superset superset init
docker-compose restart superset
```

### Dagster assets won't materialize

```bash
# Check Dagster logs
docker-compose logs -f dagster

# Verify MinIO is accessible
docker-compose exec dagster curl http://minio:9000/minio/health/live

# Check Kafka (if using streaming)
docker-compose exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092
```

### Out of memory errors

```bash
# Check resource usage
docker stats

# Increase Docker Desktop memory (Preferences → Resources → Memory)
# Recommended: 8GB minimum for full platform
```

---

## 🤝 Contributing

### Project Structure

```
data-platform/
├── docker-compose.yml          # Service orchestration
├── scripts/
│   └── bootstrap.sh           # Platform initialization
├── postgres-init/             # PostgreSQL init scripts
│   ├── 01_init_marquez.sql
│   ├── 02_init_weather.sql
│   └── 03_init_crypto.sql
├── orchestration/             # Dagster workflows
│   ├── crypto_stream/         # Crypto streaming pipeline
│   └── weather_pipeline/      # Weather data pipeline
├── superset/                  # Superset configuration
├── etl/                       # Cell towers ETL
├── api/                       # RESTful APIs
└── docs/                      # Documentation
```

### Development Workflow

1. Make changes to service configuration
2. Test with `docker-compose up -d`
3. Run `./scripts/bootstrap.sh` to verify initialization
4. Update documentation in `docs/`
5. Commit and push

---

## 📝 License

This project is for educational and demonstration purposes.

---

## 🎉 What's Next?

1. ✅ **Load cell towers data**: `docker-compose up etl`
2. ✅ **Create your first Superset dashboard** (see [docs/SUPERSET_DATABASE_CONNECTIONS.md](docs/SUPERSET_DATABASE_CONNECTIONS.md))
3. ✅ **Start crypto streaming** (see [docs/CRYPTO_STREAM_QUICKSTART.md](docs/CRYPTO_STREAM_QUICKSTART.md))
4. ✅ **Explore data lineage** in Marquez: http://localhost:3001
5. ✅ **Query with DuckDB**: Fast analytics on Iceberg tables

**Questions?** Check the [docs/](docs/) folder for detailed guides!
