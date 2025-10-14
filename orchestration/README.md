# Weather Data Pipeline - Orchestration

## Overview

This directory contains the Dagster orchestration setup for the weather data pipeline.

### Pipeline Architecture

```
Open-Meteo API → Bronze Layer (MinIO) → Quality Checks → Silver Layer (MinIO) → PostgreSQL
```

### Components

- **Dagster**: Modern data orchestration platform
- **Great Expectations**: Data quality validation framework
- **Open-Meteo API**: Free weather data (no API key required)
- **MinIO**: S3-compatible object storage for data lake
- **PostgreSQL**: Data warehouse for cleaned weather data

## Pipeline Assets

### 1. `raw_weather_data` (Bronze Layer)
- Fetches current weather from Open-Meteo API
- Covers 7 major Dutch cities (Amsterdam, Rotterdam, Utrecht, etc.)
- Saves raw data as Parquet in MinIO: `bronze/weather/YYYY/MM/DD/HH/`
- Fields: temperature, humidity, wind, precipitation, pressure

### 2. `weather_quality_check` (Quality Gates)
- Runs 7 data quality validations:
  - Temperature range: -30°C to 45°C
  - Humidity: 0-100%
  - Wind speed: >= 0
  - Precipitation: >= 0
  - No null values in critical fields
  - Coordinates within Netherlands bounds
- Returns quality score (% of checks passed)

### 3. `clean_weather_data` (Silver Layer)
- Transforms and enriches raw data
- Adds "feels like" temperature calculation
- Rounds numeric values for consistency
- Saves to MinIO: `silver/weather/YYYY/MM/DD/`

### 4. `weather_to_postgres` (Gold Layer)
- Loads validated data into PostgreSQL
- Schema: `weather.observations`
- Upsert logic prevents duplicates
- Ready for analytics and visualization

## Database Schema

### `weather.stations`
Dimension table for weather stations:
- `station_name` (PK)
- `latitude`, `longitude`
- `elevation`, `country`

### `weather.observations`
Fact table for weather measurements:
- `id` (PK, serial)
- `station_name` (FK)
- `timestamp` (observation time)
- `temperature`, `humidity`, `wind_speed`, etc.
- `feels_like_temp` (calculated)
- `data_quality` status

### `weather.weather_near_towers` (View)
Joins weather data with nearest cell towers using Haversine distance:
- Shows weather conditions at each cell tower location
- Finds nearest weather station for each tower
- Useful for telecom analytics (weather impact on network)

## Running the Pipeline

### Start Dagster

```bash
# Build the Dagster image
docker-compose build dagster

# Start all services including Dagster
docker-compose --profile standard up -d

# Or start just Dagster (requires postgres + minio already running)
docker-compose up -d dagster
```

### Access Dagster UI

Open http://localhost:3000

### Manual Run

1. Go to http://localhost:3000
2. Click "Assets" in the left sidebar
3. Select all weather assets
4. Click "Materialize selected"
5. Watch the pipeline execute in real-time

### Scheduled Runs

The pipeline includes an hourly schedule (`weather_hourly`):
- Cron: `0 * * * *` (every hour)
- Default status: STOPPED (start manually)

To enable:
1. Go to "Schedules" in Dagster UI
2. Find `weather_hourly`
3. Click "Start Schedule"

## Data Flow

```
┌─────────────────┐
│  Open-Meteo API │
│  (7 Dutch cities)│
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Bronze Layer   │
│  (MinIO)        │
│  Parquet files  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│ Quality Checks  │
│ (7 validations) │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Silver Layer   │
│  (MinIO)        │
│  Clean Parquet  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│   PostgreSQL    │
│ weather schema  │
│ 2 tables + view │
└─────────────────┘
```

## Environment Variables

Set in `docker-compose.yml`:

- `MINIO_ENDPOINT`: MinIO host (default: `minio:9000`)
- `MINIO_ACCESS_KEY`: MinIO username (default: `minio`)
- `MINIO_SECRET_KEY`: MinIO password (default: `minio12345`)
- `MINIO_BUCKET`: S3 bucket name (default: `lake`)
- `POSTGRES_CONN`: PostgreSQL connection string

## File Structure

```
orchestration/
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
├── dagster.yaml           # Dagster instance config
├── README.md              # This file
└── weather_pipeline/
    ├── __init__.py        # Dagster Definitions
    ├── assets.py          # Pipeline assets (4 main steps)
    └── schedules.py       # Hourly schedule definition
```

## Development

### Local Testing (without Docker)

```bash
# Install dependencies
cd orchestration
pip install -r requirements.txt

# Set environment variables
export MINIO_ENDPOINT=localhost:9000
export MINIO_ACCESS_KEY=minio
export MINIO_SECRET_KEY=minio12345
export POSTGRES_CONN=postgresql://superset:superset@localhost:5432/superset

# Run Dagster dev server
dagster dev -f weather_pipeline
```

### Troubleshooting

**Import errors in VS Code:**
- This is expected - packages are installed in Docker container
- Lint errors don't affect runtime execution

**MinIO connection errors:**
- Ensure MinIO is running: `docker-compose ps minio`
- Check bucket exists: http://localhost:9001 (login: minio/minio12345)
- Create bucket manually if needed: `lake`

**PostgreSQL errors:**
- Check database is initialized: `docker-compose logs postgres`
- Verify weather schema exists: `docker-compose exec postgres psql -U superset -c "\dn"`
- Re-run init script if needed: `docker-compose exec postgres psql -U superset -f /docker-entrypoint-initdb.d/02_init_weather.sql`

## Integration with Data Platform

### Amundsen
- Weather tables will appear in Amundsen metadata
- Need to run `sync_to_elasticsearch.py` after first data load
- Tags: weather, observations, quality-checked

### PostgreSQL Queries
- Query weather data alongside cell towers:
  ```sql
  SELECT * FROM weather.weather_near_towers
  WHERE distance_km < 10
  LIMIT 100;
  ```

### Superset
- Create dashboards using `weather.observations`
- Join with cell towers via `weather.weather_near_towers` view
- Visualize: temperature trends, tower coverage vs weather

### Marquez
- Lineage tracking can be added with `dagster-marquez` integration
- Shows data flow from API → MinIO → PostgreSQL

## Next Steps

1. ✅ Build and start Dagster container
2. ✅ Run pipeline manually to test
3. ⏳ Enable hourly schedule
4. ⏳ Add weather data to Amundsen catalog
5. ⏳ Create Superset dashboards
6. ⏳ Add Marquez lineage tracking

## Quality Metrics

Current validations:
- Temperature: -30°C to 45°C
- Humidity: 0-100%
- Wind speed: ≥ 0 km/h
- Precipitation: ≥ 0 mm
- No null temperatures
- No null station names
- Coordinates within NL bounds

Quality score target: **≥ 95%** (all checks should pass)
