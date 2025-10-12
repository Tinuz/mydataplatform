# Data Catalog - Weather Pipeline

**Last Updated:** 12 Oktober 2025  
**Owner:** Data Engineering Team  
**Status:** 🟢 Production Ready

---

## Overview

This document provides comprehensive metadata for all datasets in the Weather Pipeline. Use this catalog to understand what data is available, how it's structured, quality metrics, and lineage information.

### Quick Links
- **Lineage Visualization:** http://localhost:5001 (Marquez)
- **Data Quality Dashboards:** http://localhost:8088 (Superset)
- **Pipeline Orchestration:** http://localhost:3000 (Dagster)
- **API Gateway:** http://localhost:8000 (Kong)

---

## 📊 Dataset Inventory

| Dataset | Layer | Format | Update Frequency | Retention | Owner |
|---------|-------|--------|------------------|-----------|-------|
| `minio://bronze/weather` | Bronze | Parquet | Hourly | 30 days | Data Engineering |
| `minio://silver/weather` | Silver | Parquet | Hourly | 90 days | Data Engineering |
| `postgres://weather.observations` | Gold | PostgreSQL | Hourly | Indefinite | Analytics Team |

---

## 🥉 Bronze Layer: `minio://bronze/weather`

### Description
Raw weather data ingested from the Open-Meteo API for 7 major Dutch cities. This is the landing zone for external weather data with minimal transformation.

### Technical Details
- **Namespace:** `minio`
- **Path:** `s3://lake/bronze/weather/YYYY/MM/DD/`
- **Format:** Parquet (snappy compression)
- **Partition Strategy:** Hive-style by date (year/month/day)
- **Update Schedule:** Hourly at :00 (e.g., 10:00, 11:00, 12:00)
- **Retention Policy:** 30 days (automatically cleaned via MinIO lifecycle)

### Schema

| Column Name | Type | Nullable | Description | Example |
|-------------|------|----------|-------------|---------|
| `city` | string | No | City name from list of 7 Dutch cities | Amsterdam |
| `timestamp` | timestamp | No | Observation time (UTC) | 2025-10-12 10:00:00 |
| `temperature` | float | No | Temperature in Celsius | 15.7 |
| `humidity` | int | No | Relative humidity percentage (0-100) | 75 |
| `wind_speed` | float | No | Wind speed in km/h | 18.5 |
| `weather_code` | int | No | WMO weather interpretation code | 3 |
| `latitude` | float | No | City latitude coordinate | 52.3676 |
| `longitude` | float | No | City longitude coordinate | 4.9041 |

### Weather Code Reference
| Code | Condition |
|------|-----------|
| 0 | Clear sky ☀️ |
| 1-3 | Partly cloudy ⛅ |
| 45, 48 | Fog 🌫️ |
| 51-57 | Drizzle 🌧️ |
| 61-67 | Rain 🌧️ |
| 71-77 | Snow ❄️ |
| 80-82 | Rain showers 🌦️ |
| 95-99 | Thunderstorm ⛈️ |

### Data Quality
- **Quality Score:** 95-100% (Great Expectations checks)
- **Validation Rules:**
  - Temperature must be between -30°C and 50°C
  - Humidity must be between 0% and 100%
  - Wind speed must be >= 0 km/h
  - All cities must report data each hour
  - No duplicate timestamps per city

### Source Information
- **API Provider:** Open-Meteo (https://open-meteo.com)
- **API Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Rate Limit:** None (free tier)
- **Authentication:** Not required
- **SLA:** Best effort (no guaranteed uptime)

### Lineage
- **Produced By:** `raw_weather_data` (Dagster asset)
- **Consumed By:** `weather_quality_check` (quality validation)
- **Marquez Job:** http://localhost:5001/#/jobs/raw_weather_data

### Example Query (Trino)
```sql
SELECT 
    city,
    timestamp,
    temperature,
    weather_code
FROM minio.bronze.weather
WHERE date = current_date
  AND hour = current_hour
ORDER BY city;
```

### Sample Data
```json
{
  "city": "Amsterdam",
  "timestamp": "2025-10-12T10:00:00Z",
  "temperature": 15.7,
  "humidity": 75,
  "wind_speed": 18.5,
  "weather_code": 3,
  "latitude": 52.3676,
  "longitude": 4.9041
}
```

### Access Control
- **Read Access:** `data-engineering`, `data-analysts`, `data-scientists`
- **Write Access:** `data-engineering` (via pipeline only)
- **PII Classification:** None
- **Data Sensitivity:** Public

---

## 🥈 Silver Layer: `minio://silver/weather`

### Description
Cleaned and enriched weather data with calculated fields. Quality validated and ready for analytics. This is the curated layer for business consumption.

### Technical Details
- **Namespace:** `minio`
- **Path:** `s3://lake/silver/weather/YYYY/MM/DD/`
- **Format:** Parquet (snappy compression)
- **Partition Strategy:** Hive-style by date (year/month/day)
- **Update Schedule:** Hourly at :02 (2 minutes after bronze)
- **Retention Policy:** 90 days

### Schema

| Column Name | Type | Nullable | Description | Derived From | Example |
|-------------|------|----------|-------------|--------------|---------|
| `city` | string | No | City name | Bronze: city | Amsterdam |
| `timestamp` | timestamp | No | Observation time (UTC) | Bronze: timestamp | 2025-10-12 10:00:00 |
| `temperature` | float | No | Temperature in Celsius | Bronze: temperature | 15.7 |
| `humidity` | int | No | Relative humidity percentage | Bronze: humidity | 75 |
| `wind_speed` | float | No | Wind speed in km/h | Bronze: wind_speed | 18.5 |
| `weather_code` | int | No | WMO weather code | Bronze: weather_code | 3 |
| `feels_like_temp` | float | No | **Calculated** feels-like temperature | temperature - (wind_speed × 0.2 + (100 - humidity) × 0.01) | 12.8 |
| `weather_condition` | string | No | **Enriched** human-readable condition | Mapping from weather_code | Partly Cloudy |
| `latitude` | float | No | City latitude | Bronze: latitude | 52.3676 |
| `longitude` | float | No | City longitude | Bronze: longitude | 4.9041 |

### Business Logic

#### Feels-Like Temperature Formula
```python
feels_like_temp = temperature - (wind_speed * 0.2 + (100 - humidity) * 0.01)
```
This approximates the perceived temperature based on:
- **Wind Chill Factor:** Higher wind speed → colder feeling
- **Humidity Impact:** Higher humidity → warmer feeling

#### Weather Condition Mapping
```python
WEATHER_CONDITIONS = {
    0: "Clear",
    1: "Mainly Clear",
    2: "Partly Cloudy",
    3: "Overcast",
    45: "Foggy",
    48: "Depositing Rime Fog",
    51: "Light Drizzle",
    53: "Moderate Drizzle",
    55: "Dense Drizzle",
    61: "Slight Rain",
    63: "Moderate Rain",
    65: "Heavy Rain",
    71: "Slight Snow",
    73: "Moderate Snow",
    75: "Heavy Snow",
    80: "Slight Rain Showers",
    81: "Moderate Rain Showers",
    82: "Violent Rain Showers",
    95: "Thunderstorm",
    96: "Thunderstorm with Slight Hail",
    99: "Thunderstorm with Heavy Hail"
}
```

### Data Quality
- **Quality Score:** 95-100% (validated from bronze)
- **Validation Rules:**
  - All bronze validations +
  - `feels_like_temp` must be within ±20°C of actual temperature
  - `weather_condition` must be valid string (not "Unknown")
  - No null values in calculated fields

### Lineage
- **Produced By:** `clean_weather_data` (Dagster asset)
- **Consumes:** `minio://bronze/weather` (after quality check)
- **Consumed By:** `weather_to_postgres` (loads to warehouse)
- **Marquez Job:** http://localhost:5001/#/jobs/clean_weather_data

### Example Query (Trino)
```sql
SELECT 
    city,
    timestamp,
    temperature,
    feels_like_temp,
    temperature - feels_like_temp as feels_difference,
    weather_condition
FROM minio.silver.weather
WHERE date = current_date
  AND feels_like_temp < 10  -- Cold conditions
ORDER BY feels_like_temp;
```

### Sample Data
```json
{
  "city": "Amsterdam",
  "timestamp": "2025-10-12T10:00:00Z",
  "temperature": 15.7,
  "humidity": 75,
  "wind_speed": 18.5,
  "weather_code": 3,
  "feels_like_temp": 12.8,
  "weather_condition": "Overcast",
  "latitude": 52.3676,
  "longitude": 4.9041
}
```

### Use Cases
- **Analytics:** Temperature trend analysis by city
- **Dashboards:** Real-time weather monitoring
- **Alerts:** Cold weather warnings (feels_like < 5°C)
- **ML Training:** Historical weather patterns

### Access Control
- **Read Access:** `data-engineering`, `data-analysts`, `data-scientists`, `business-users`
- **Write Access:** `data-engineering` (via pipeline only)
- **PII Classification:** None
- **Data Sensitivity:** Internal

---

## 🥇 Gold Layer: `postgres://weather.observations`

### Description
Production-ready weather observations stored in PostgreSQL data warehouse. Serves dashboards, APIs, and business applications. This is the single source of truth for weather data.

### Technical Details
- **Database:** `superset` (PostgreSQL 16)
- **Schema:** `weather`
- **Table:** `observations`
- **Connection String:** `postgresql://superset:superset@postgres:5432/superset`
- **Update Strategy:** Upsert (ON CONFLICT DO UPDATE on city + timestamp)
- **Indexes:**
  - Primary Key: `(city, timestamp)`
  - Index on `timestamp` (for time-series queries)
  - Index on `city` (for city-specific queries)

### Schema

| Column Name | Type | Nullable | Constraint | Description |
|-------------|------|----------|------------|-------------|
| `city` | varchar(100) | No | PK (part 1) | City name |
| `timestamp` | timestamptz | No | PK (part 2) | Observation timestamp with timezone |
| `temperature` | numeric(5,2) | No | | Temperature in Celsius (±999.99) |
| `humidity` | integer | No | CHECK (0-100) | Relative humidity percentage |
| `wind_speed` | numeric(5,2) | No | CHECK (>= 0) | Wind speed in km/h |
| `weather_code` | integer | No | | WMO weather code |
| `feels_like_temp` | numeric(5,2) | No | | Calculated feels-like temperature |
| `weather_condition` | varchar(50) | No | | Human-readable weather condition |
| `latitude` | numeric(10,7) | No | | City latitude |
| `longitude` | numeric(10,7) | No | | City longitude |

### Table Definition (SQL)
```sql
CREATE TABLE weather.observations (
    city varchar(100) NOT NULL,
    timestamp timestamptz NOT NULL,
    temperature numeric(5,2) NOT NULL,
    humidity integer NOT NULL CHECK (humidity >= 0 AND humidity <= 100),
    wind_speed numeric(5,2) NOT NULL CHECK (wind_speed >= 0),
    weather_code integer NOT NULL,
    feels_like_temp numeric(5,2) NOT NULL,
    weather_condition varchar(50) NOT NULL,
    latitude numeric(10,7) NOT NULL,
    longitude numeric(10,7) NOT NULL,
    PRIMARY KEY (city, timestamp)
);

CREATE INDEX idx_observations_timestamp ON weather.observations(timestamp);
CREATE INDEX idx_observations_city ON weather.observations(city);
```

### Data Quality
- **Quality Score:** 100% (inherited from silver + database constraints)
- **Validation Rules:**
  - All silver validations +
  - Primary key constraint (no duplicates)
  - Check constraints on humidity and wind_speed
  - NOT NULL constraints on all columns

### Lineage
- **Produced By:** `weather_to_postgres` (Dagster asset)
- **Consumes:** `minio://silver/weather`
- **Consumed By:**
  - Superset dashboards (weather KPIs)
  - Kong API (public weather endpoint)
  - Ad-hoc SQL queries (analysts)
- **Marquez Job:** http://localhost:5001/#/jobs/weather_to_postgres

### Example Queries

#### Latest Weather by City
```sql
SELECT 
    city,
    temperature,
    feels_like_temp,
    weather_condition,
    timestamp
FROM weather.observations
WHERE timestamp >= NOW() - INTERVAL '1 hour'
ORDER BY city;
```

#### Temperature Trends (Last 24 Hours)
```sql
SELECT 
    city,
    DATE_TRUNC('hour', timestamp) as hour,
    AVG(temperature) as avg_temp,
    MIN(temperature) as min_temp,
    MAX(temperature) as max_temp
FROM weather.observations
WHERE timestamp >= NOW() - INTERVAL '24 hours'
GROUP BY city, DATE_TRUNC('hour', timestamp)
ORDER BY city, hour;
```

#### Coldest Feels-Like Temperatures
```sql
SELECT 
    city,
    feels_like_temp,
    temperature,
    wind_speed,
    humidity,
    weather_condition,
    timestamp
FROM weather.observations
WHERE timestamp >= CURRENT_DATE
ORDER BY feels_like_temp ASC
LIMIT 10;
```

#### Weather Distribution
```sql
SELECT 
    weather_condition,
    COUNT(*) as occurrence_count,
    AVG(temperature) as avg_temp,
    AVG(humidity) as avg_humidity
FROM weather.observations
WHERE timestamp >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY weather_condition
ORDER BY occurrence_count DESC;
```

### Performance Tuning
- **Partitioning:** Consider time-based partitioning if data grows beyond 10M rows
- **Vacuum:** Auto-vacuum enabled (due to upserts)
- **Statistics:** Updated automatically after bulk loads
- **Query Optimization:** Indexes cover most common query patterns

### Backup & Recovery
- **Backup Strategy:** Daily PostgreSQL dumps (included in postgres backup)
- **Retention:** 30 days
- **Recovery Time Objective (RTO):** 4 hours
- **Recovery Point Objective (RPO):** 1 hour

### Access Control
- **Read Access:** `data-engineering`, `data-analysts`, `data-scientists`, `business-users`, `api-gateway`
- **Write Access:** `data-engineering` (via pipeline only)
- **Admin Access:** `platform-team`
- **PII Classification:** None
- **Data Sensitivity:** Public

---

## 🔗 Data Lineage

### End-to-End Flow

```mermaid
graph LR
    A[Open-Meteo API] -->|HTTP GET| B[raw_weather_data]
    B -->|Parquet| C[minio://bronze/weather]
    C -->|Read| D[weather_quality_check]
    D -->|Validated| E[clean_weather_data]
    E -->|Transform| F[minio://silver/weather]
    F -->|Read| G[weather_to_postgres]
    G -->|Upsert| H[postgres://weather.observations]
    H -->|Query| I[Superset Dashboards]
    H -->|API| J[Kong Gateway]
```

### Asset Dependencies

| Asset | Type | Depends On | Produces |
|-------|------|------------|----------|
| `raw_weather_data` | Source | Open-Meteo API | `minio://bronze/weather` |
| `weather_quality_check` | Validation | `minio://bronze/weather` | Quality metrics |
| `clean_weather_data` | Transform | `minio://bronze/weather` (validated) | `minio://silver/weather` |
| `weather_to_postgres` | Load | `minio://silver/weather` | `postgres://weather.observations` |

### Lineage Visualization
View complete lineage graph in Marquez: http://localhost:5001

---

## 📈 Data Quality Metrics

### Quality Score Calculation
```python
quality_score = (checks_passed / total_checks) * 100
```

### Quality Checks (Great Expectations)

#### Bronze Layer Checks
1. **Expect column values to be in range:**
   - `temperature`: [-30, 50]
   - `humidity`: [0, 100]
   - `wind_speed`: [0, ∞]

2. **Expect column values to not be null:**
   - All columns required

3. **Expect compound columns to be unique:**
   - `(city, timestamp)` must be unique

4. **Expect table row count to be between:**
   - Min: 7 (one per city)
   - Max: 7 (exactly 7 cities)

#### Silver Layer Checks
- All bronze checks +
- **Expect column values to match regex:**
  - `weather_condition`: Must be valid condition name
  - `city`: Must be one of 7 Dutch cities

### Quality Trends
Quality metrics are logged to Dagster metadata and can be queried via:
```python
from dagster import get_dagster_logger

# View quality check results
context.log.info(f"Quality score: {quality_score}%")
context.log.info(f"Checks passed: {checks_passed}/{total_checks}")
```

---

## 🏷️ Metadata Tags

### Dataset Tags
- **Layer:** `bronze`, `silver`, `gold`
- **Domain:** `weather`, `external-api`
- **Update Frequency:** `hourly`
- **Data Classification:** `public`
- **Source:** `open-meteo`

### Column Tags
- **PII:** None
- **Business Critical:** `temperature`, `feels_like_temp`
- **Calculated:** `feels_like_temp`, `weather_condition`
- **Geographic:** `latitude`, `longitude`, `city`

---

## 👥 Ownership & Contacts

### Data Engineering Team
- **Responsibility:** Pipeline development, data quality, infrastructure
- **Contact:** data-engineering@company.com
- **On-Call:** PagerDuty rotation

### Analytics Team
- **Responsibility:** Dashboard creation, SQL queries, reporting
- **Contact:** analytics@company.com

### Platform Team
- **Responsibility:** Dagster, Trino, PostgreSQL, MinIO operations
- **Contact:** platform@company.com

---

## 📝 Change Log

| Date | Version | Change | Author |
|------|---------|--------|--------|
| 2025-10-12 | 1.0 | Initial data catalog creation | Data Engineering |
| 2025-10-12 | 1.1 | Added Marquez lineage integration | Data Engineering |
| 2025-10-12 | 1.2 | Added input dataset tracking | Data Engineering |

---

## 🔍 FAQs

### Q: How do I access the data?
**A:** 
- **Trino:** Use DBeaver or `trino-cli` to query `minio.bronze.weather`, `minio.silver.weather`
- **PostgreSQL:** Use any PostgreSQL client to query `weather.observations`
- **API:** Use Kong gateway at http://localhost:8000/weather

### Q: What's the data freshness?
**A:** Data is updated hourly. Bronze layer is refreshed at :00, silver at :02, gold at :05.

### Q: Can I write to these datasets?
**A:** No. All datasets are managed by the data pipeline. Submit a request to Data Engineering for new data sources.

### Q: Where can I see data quality issues?
**A:** Check Dagster UI → Assets → View materialization → Metadata tab for quality scores.

### Q: How do I request a new column?
**A:** Create a ticket with Data Engineering describing the business logic and use case.

### Q: Is there a data dictionary?
**A:** Yes! This document serves as the data dictionary with full schema definitions.

---

**End of Data Catalog**
