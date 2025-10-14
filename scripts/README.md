# 🔧 Data Platform Scripts# Scripts Directory



Helper scripts for platform initialization, maintenance, and operations.This directory contains utility scripts for the data platform.



---## Available Scripts



## 🚀 Essential Scripts### Amundsen (Data Catalog)



### bootstrap.sh (CRITICAL)#### `seed_amundsen_metadata.py`

Populates the Amundsen Neo4j database with metadata for weather datasets.

**Purpose**: Complete platform initialization after docker-compose up

**Usage:**

**When to use**:```bash

- ✅ After first time starting the platformpython scripts/seed_amundsen_metadata.py

- ✅ After `docker-compose down` (to re-sync data)```

- ✅ After deleting volumes

- ✅ When Superset admin user doesn't exist**What it does:**

- Creates Neo4j performance indexes

**What it does**:- Seeds 3 weather datasets (bronze, silver, gold layers)

1. ⏳ Waits for all services to be healthy (PostgreSQL, MinIO, Kafka, Superset)- Adds table/column metadata, owners, tags, descriptions

2. 🪣 Creates MinIO bucket (`lake`) for Iceberg tables

3. 📨 Creates Kafka topic (`crypto_trades`) with 3 partitions#### `sync_neo4j_to_es.py`

4. 🎨 Initializes Superset (DB migrations, admin user, permissions)Syncs metadata from Neo4j to Elasticsearch for search functionality.

5. 📊 Syncs crypto data from Iceberg to PostgreSQL (for Superset)

**Usage:**

**Usage**:```bash

```bashpython scripts/sync_neo4j_to_es.py

./scripts/bootstrap.sh```

```

**What it does:**

**Requirements**:- Fetches all tables from Neo4j

- docker-compose running with services- Creates/updates Elasticsearch index

- At least `postgres`, `minio`, `superset` services up- Enables full-text search in Amundsen UI



**Output**:### Superset (Dashboards)

```

🚀 Data Platform Bootstrap Starting...#### `create_weather_views.sql`

✅ PostgreSQL is readyCreates SQL views for Superset dashboards.

✅ MinIO is ready

✅ Superset is ready**Usage:**

✅ Superset database upgraded```bash

✅ Admin user createdcat scripts/create_weather_views.sql | docker-compose exec -T postgres psql -U superset -d superset

✅ Bucket created: lake```

✅ Kafka topic created: crypto_trades

✅ Synced 2000 trades and 4 candles to PostgreSQL**Views created:**

🎉 Bootstrap Complete!- `weather.latest_weather` - Latest observation per station

```- `weather.hourly_trends` - Hourly aggregated weather data

- `weather.station_metrics` - Station-level metrics with location

**Troubleshooting**:- `weather.data_quality_summary` - Data quality statistics

- If fails on service wait: Check service health with `docker-compose ps`- `weather.weather_tower_proximity` - Weather near cell towers (<10km)

- If admin user already exists: Safe to ignore warning

- If bucket already exists: Safe to ignore warning#### `create_superset_dashboards.py`

- If PostgreSQL sync fails: Ensure crypto assets are materialized firstAttempts to create Superset dashboards via API (WIP - CSRF issues).



---**Note:** Currently not working due to CSRF token issues. Use manual setup from `docs/SUPERSET_DASHBOARDS.md` instead.



### health_check.sh (VALIDATION)## Quick Start



**Purpose**: Quick system health validation1. **Setup Amundsen data catalog:**

   ```bash

**When to use**:   python scripts/seed_amundsen_metadata.py

- ✅ After bootstrap.sh completes   python scripts/sync_neo4j_to_es.py

- ✅ Before starting work   ```

- ✅ To diagnose issues   Then visit: http://localhost:5005

- ✅ In CI/CD pipelines

2. **Setup Superset views:**

**What it checks**:   ```bash

1. 📦 Service status (all docker-compose services)   cat scripts/create_weather_views.sql | docker-compose exec -T postgres psql -U superset -d superset

2. 📊 Data availability (cell towers, crypto bronze/silver)   ```

3. 🔌 HTTP endpoints (Superset, Dagster, MinIO)
   Then follow: `docs/SUPERSET_DASHBOARDS.md`

4. 📨 Kafka topics (if streaming profile)

5. 🪣 MinIO buckets## Dependencies



**Usage**:All scripts use packages from the main project:

```bash- `neo4j` - Neo4j Python driver

./scripts/health_check.sh- `elasticsearch` - Elasticsearch Python client  

```- `requests` - HTTP requests for APIs

- `psycopg2` - PostgreSQL adapter (via docker exec)

**Output** (all healthy):

```Install if needed:

🏥 Data Platform Health Check```bash

✅ PostgreSQL: Runningpip install neo4j elasticsearch requests

✅ Superset: Running```

...
Passed: 20
Failed: 0
🎉 All checks passed! Platform is healthy.
```

**Output** (issues found):
```
**Output** (issues found):
```
✅ PostgreSQL: Running
❌ Kafka: Not running
...
Passed: 17
Failed: 3
```
⚠️  Some checks failed. Review issues above.
```

**Exit codes**:
- `0`: All checks passed
- `1`: One or more checks failed

---

## 📊 Data Management Scripts

### seed_amundsen_metadata.py

**Purpose**: Seed metadata into Amundsen data catalog

**When to use**:
- ✅ After starting Amundsen profile
- ✅ To populate catalog with table metadata
- ✅ After adding new tables

**Requirements**:
- docker-compose with `amundsen` profile running
- Neo4j and Elasticsearch services healthy

**Usage**:
```bash
docker-compose exec dagster python3 /scripts/seed_amundsen_metadata.py
```

---

### sync_neo4j_to_es.py

**Purpose**: Sync Neo4j graph data to Elasticsearch for Amundsen search

**When to use**:
- ✅ After seeding Neo4j with metadata
- ✅ When search results are missing
- ✅ Periodic sync (can be scheduled)

**Requirements**:
- Amundsen Neo4j and Elasticsearch running

**Usage**:
```bash
docker-compose exec dagster python3 /scripts/sync_neo4j_to_es.py
```

---

## 🌤️ Weather Scripts

### create_weather_views.sql

**Purpose**: Creates PostgreSQL views for weather API

**When to use**:
- ✅ After loading weather data
- ✅ To create aggregated views
- ✅ When views are missing

**Usage**:
```bash
docker-compose exec postgres psql -U superset -d superset -f /scripts/create_weather_views.sql
```

**What it creates**:
- Materialized views for weather aggregations
- Indexes for performance
- Refresh procedures

---

## 🗂️ Script Inventory

| Script | Lines | Status | Priority |
|--------|-------|--------|----------|
| `bootstrap.sh` | 209 | ✅ Active | Critical |
| `health_check.sh` | 150 | ✅ Active | High |
| `seed_amundsen_metadata.py` | 313 | ✅ Active | Medium |
| `sync_neo4j_to_es.py` | 204 | ✅ Active | Medium |
| `create_weather_views.sql` | 107 | ✅ Active | Low |

**Total**: 5 scripts, 983 lines

---

## 🎯 Typical Workflows

### First Time Setup

```bash
# 1. Start services
docker-compose --profile streaming up -d

# 2. Initialize platform
./scripts/bootstrap.sh

# 3. Verify health
./scripts/health_check.sh

# 4. Load cell towers data (optional)
docker-compose up etl

# 5. Verify health again
./scripts/health_check.sh
```

### After Restart (docker-compose down → up)

```bash
# 1. Start services
docker-compose --profile streaming up -d

# 2. Re-initialize (sync data)
./scripts/bootstrap.sh

# 3. Verify
./scripts/health_check.sh
```

### Daily Development

```bash
# Check platform health
./scripts/health_check.sh

# If issues found, check logs
docker-compose logs -f <service>

# Restart specific service
docker-compose restart <service>

# Re-run bootstrap if needed
./scripts/bootstrap.sh
```

---

## 🧹 Deprecated Scripts (Removed)

The following scripts have been **deleted** as they are superseded by `bootstrap.sh`:

- ❌ `register_superset_data.sh` - Redundant (bootstrap.sh handles Superset init)
- ❌ `register_superset_data.py` - Redundant (bootstrap.sh handles Superset init)
- ❌ `register_in_container.py` - Redundant (bootstrap.sh handles Superset init)
- ❌ `create_superset_dashboards.py` - Unused (manual dashboard creation preferred)

**Total removed**: 787 lines (45% reduction in scripts)

---

## 📝 Contributing New Scripts

### Guidelines

1. **Add to appropriate category** (init, data, maintenance, etc.)
2. **Document in this README** with purpose, usage, requirements
3. **Make executable**: `chmod +x scripts/your_script.sh`
4. **Test thoroughly** before committing
5. **Add error handling** and clear output messages

### Script Template (Bash)

```bash
#!/bin/bash
# Script Name: your_script.sh
# Purpose: Brief description
# Usage: ./scripts/your_script.sh [args]

set +e  # Don't exit on error (or set -e if you want to)

echo "🚀 Your Script Starting..."

# Your logic here

echo "✅ Your Script Complete!"
```

### Script Template (Python)

```python
#!/usr/bin/env python3
"""
Script Name: your_script.py
Purpose: Brief description
Usage: python3 scripts/your_script.py [args]
"""
import sys

def main():
    print("🚀 Your Script Starting...")
    
    # Your logic here
    
    print("✅ Your Script Complete!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
```

---

## 🐛 Troubleshooting

### bootstrap.sh fails on service wait

**Symptoms**: Script times out waiting for service

**Solutions**:
1. Check service is actually running: `docker-compose ps`
2. Check service logs: `docker-compose logs -f <service>`
3. Restart service: `docker-compose restart <service>`
4. Increase wait time in bootstrap.sh (edit `MAX_ATTEMPTS`)

### health_check.sh shows failures

**Symptoms**: Health check reports failed services or data

**Solutions**:
1. **Service not running**: Start with `docker-compose up -d <service>`
2. **Data missing**: Run `./scripts/bootstrap.sh` or materialize assets
3. **Endpoint not accessible**: Check port bindings in docker-compose.yml
4. **False positive**: Some checks may fail safely (e.g., Kafka if streaming profile not used)

### Permission denied errors

**Symptoms**: `bash: ./scripts/script.sh: Permission denied`

**Solution**:
```bash
chmod +x scripts/script.sh
```

---

## 📚 See Also

- [Main README](../README.md) - Platform overview
- [Quick Reference](../docs/QUICK_REFERENCE.md) - Essential commands
- [Troubleshooting Guide](../docs/QUICK_REFERENCE.md#troubleshooting) - Common issues

---

**Last Updated**: October 12, 2025  
**Maintainer**: Data Platform Team
