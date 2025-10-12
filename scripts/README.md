# Scripts Directory

This directory contains utility scripts for the data platform.

## Available Scripts

### Amundsen (Data Catalog)

#### `seed_amundsen_metadata.py`
Populates the Amundsen Neo4j database with metadata for weather datasets.

**Usage:**
```bash
python scripts/seed_amundsen_metadata.py
```

**What it does:**
- Creates Neo4j performance indexes
- Seeds 3 weather datasets (bronze, silver, gold layers)
- Adds table/column metadata, owners, tags, descriptions

#### `sync_neo4j_to_es.py`
Syncs metadata from Neo4j to Elasticsearch for search functionality.

**Usage:**
```bash
python scripts/sync_neo4j_to_es.py
```

**What it does:**
- Fetches all tables from Neo4j
- Creates/updates Elasticsearch index
- Enables full-text search in Amundsen UI

### Superset (Dashboards)

#### `create_weather_views.sql`
Creates SQL views for Superset dashboards.

**Usage:**
```bash
cat scripts/create_weather_views.sql | docker-compose exec -T postgres psql -U superset -d superset
```

**Views created:**
- `weather.latest_weather` - Latest observation per station
- `weather.hourly_trends` - Hourly aggregated weather data
- `weather.station_metrics` - Station-level metrics with location
- `weather.data_quality_summary` - Data quality statistics
- `weather.weather_tower_proximity` - Weather near cell towers (<10km)

#### `create_superset_dashboards.py`
Attempts to create Superset dashboards via API (WIP - CSRF issues).

**Note:** Currently not working due to CSRF token issues. Use manual setup from `docs/SUPERSET_DASHBOARDS.md` instead.

## Quick Start

1. **Setup Amundsen data catalog:**
   ```bash
   python scripts/seed_amundsen_metadata.py
   python scripts/sync_neo4j_to_es.py
   ```
   Then visit: http://localhost:5005

2. **Setup Superset views:**
   ```bash
   cat scripts/create_weather_views.sql | docker-compose exec -T postgres psql -U superset -d superset
   ```
   Then follow: `docs/SUPERSET_DASHBOARDS.md`

## Dependencies

All scripts use packages from the main project:
- `neo4j` - Neo4j Python driver
- `elasticsearch` - Elasticsearch Python client  
- `requests` - HTTP requests for APIs
- `psycopg2` - PostgreSQL adapter (via docker exec)

Install if needed:
```bash
pip install neo4j elasticsearch requests
```
