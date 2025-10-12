# Superset Weather Dashboards Setup Guide

## Overview
This guide explains how to create weather visualization dashboards in Superset using the prepared SQL views.

## Prerequisites
- Superset running on http://localhost:8088
- Login credentials: admin / admin
- Database views created via `scripts/create_weather_views.sql`

## Available Views

### 1. `weather.latest_weather`
Latest weather observation per station (7 rows)
```sql
SELECT * FROM weather.latest_weather;
```
**Columns:** station_name, timestamp, temperature, humidity, wind_speed, feels_like_temp, pressure, data_quality

### 2. `weather.hourly_trends` 
Hourly averaged weather trends per station
```sql
SELECT * FROM weather.hourly_trends;
```
**Columns:** hour, station_name, avg_temperature, avg_humidity, avg_wind_speed, avg_feels_like, observation_count

### 3. `weather.station_metrics`
Aggregated metrics per weather station with location (for maps)
```sql
SELECT * FROM weather.station_metrics;
```
**Columns:** station_name, latitude, longitude, total_observations, last_observation, avg_temperature, min_temperature, max_temperature, avg_humidity, avg_wind_speed

### 4. `weather.data_quality_summary`
Data quality distribution and statistics
```sql
SELECT * FROM weather.data_quality_summary;
```
**Columns:** data_quality, record_count, percentage, first_seen, last_seen

### 5. `weather.weather_tower_proximity`
Weather conditions near cell towers (within 10km) - 24,334 rows
```sql
SELECT * FROM weather.weather_tower_proximity LIMIT 100;
```
**Columns:** station_name, radio, mcc, net, area, cell, distance_km, tower_lat, tower_lon, temperature, humidity, wind_speed, weather_timestamp

## Dashboard 1: 🌡️ Temperature Trends

### Setup Steps:
1. Navigate to **Data → Datasets** in Superset
2. Click **+ Dataset**
3. Select database: **Other**, schema: **weather**, table: **hourly_trends**
4. Click **Add**

### Chart 1: Temperature Over Time (Line Chart)
1. Click **+ → Chart** on the `hourly_trends` dataset
2. Choose visualization: **Line Chart**
3. Configuration:
   - **Dimensions:** `hour`
   - **Metrics:** `AVG(avg_temperature)`
   - **Group by:** `station_name`
   - **Time Range:** Last 7 days
   - **Title:** "Temperature Trends by Station"
4. Click **Save** → Create new dashboard "🌡️ Temperature Trends"

### Chart 2: Current Temperature (Big Number with Trendline)
1. Add dataset: **weather.latest_weather**
2. Create chart, visualization: **Big Number with Trendline**
3. Configuration:
   - **Metric:** `AVG(temperature)`
   - **Time Column:** `timestamp`
   - **Title:** "Current Average Temperature"
4. Add to dashboard "🌡️ Temperature Trends"

### Chart 3: Temperature by Station (Bar Chart)
1. Use dataset: **weather.latest_weather**
2. Visualization: **Bar Chart**
3. Configuration:
   - **Dimensions:** `station_name`
   - **Metrics:** `temperature`
   - **Sort:** Descending by temperature
   - **Title:** "Latest Temperature by Station"
4. Add to dashboard

---

## Dashboard 2: 🗺️ Weather Map

### Setup Steps:
1. Add dataset: **weather.station_metrics**
2. Add dataset: **weather.weather_tower_proximity**

### Chart 1: Weather Stations Map (Deck.gl Scatterplot)
1. Create chart on `station_metrics` dataset
2. Visualization: **deck.gl Scatterplot**
3. Configuration:
   - **Longitude:** `longitude`
   - **Latitude:** `latitude`
   - **Label Column:** `station_name`
   - **Point Size:** Fixed at 100
   - **Point Color:** Based on `avg_temperature` (color scale: red-blue)
   - **Tooltip:** station_name, avg_temperature, last_observation
   - **Title:** "Weather Station Locations"
4. Save to new dashboard "🗺️ Weather Map"

### Chart 2: Cell Towers with Weather (Deck.gl Hexagon)
1. Create chart on `weather_tower_proximity` dataset
2. Visualization: **deck.gl Hexagon**
3. Configuration:
   - **Longitude:** `tower_lon`
   - **Latitude:** `tower_lat`
   - **Metric:** `COUNT(*)`
   - **Hexagon Radius:** 1000 (meters)
   - **Elevation Scale:** 10
   - **Color:** Based on AVG(temperature)
   - **Title:** "Cell Towers Colored by Weather"
4. Add to dashboard

### Chart 3: Station Table
1. Use dataset: **weather.latest_weather**
2. Visualization: **Table**
3. Configuration:
   - **Columns:** station_name, temperature, humidity, wind_speed, timestamp
   - **Title:** "Current Weather Conditions"
4. Add to dashboard

---

## Dashboard 3: ✅ Data Quality Metrics

### Setup Steps:
1. Add datasets: **weather.data_quality_summary**, **weather.observations**

### Chart 1: Data Quality Distribution (Pie Chart)
1. Create chart on `data_quality_summary` dataset
2. Visualization: **Pie Chart**
3. Configuration:
   - **Dimensions:** `data_quality`
   - **Metrics:** `record_count`
   - **Title:** "Data Quality Distribution"
4. Save to new dashboard "✅ Data Quality Metrics"

### Chart 2: Total Observations (Big Number)
1. Use dataset: **weather.observations**
2. Visualization: **Big Number**
3. Configuration:
   - **Metric:** `COUNT(*)`
   - **Title:** "Total Weather Observations"
4. Add to dashboard

### Chart 3: Observations per Station (Bar Chart)
1. Use dataset: **weather.station_metrics**
2. Visualization: **Bar Chart**
3. Configuration:
   - **Dimensions:** `station_name`
   - **Metrics:** `total_observations`
   - **Sort:** Descending
   - **Title:** "Observations per Station"
4. Add to dashboard

### Chart 4: Data Freshness (Time Table)
1. Use dataset: **weather.latest_weather**
2. Visualization: **Table**
3. Configuration:
   - **Columns:** station_name, timestamp, data_quality
   - **Sort:** timestamp DESC
   - **Title:** "Data Freshness by Station"
4. Add to dashboard

---

## Automated Dashboard Creation

For automated creation, use the Superset CLI or API:

```bash
# Export existing dashboards
docker-compose exec superset superset export-dashboards -f /tmp/dashboards.zip

# Import dashboards
docker-compose exec superset superset import-dashboards -p /tmp/dashboards.zip
```

## Quick SQL Queries for Manual Charts

### Temperature Trends (Last 24 Hours)
```sql
SELECT 
    timestamp,
    station_name,
    temperature,
    feels_like_temp
FROM weather.observations
WHERE timestamp > NOW() - INTERVAL '24 hours'
ORDER BY timestamp DESC;
```

### Weather Hotspots Near Towers
```sql
SELECT 
    station_name,
    COUNT(DISTINCT cell) as nearby_towers,
    AVG(temperature) as avg_temp,
    AVG(distance_km) as avg_distance
FROM weather.weather_tower_proximity
GROUP BY station_name
ORDER BY nearby_towers DESC;
```

### Temperature Min/Max by Station
```sql
SELECT 
    station_name,
    MIN(temperature) as min_temp,
    MAX(temperature) as max_temp,
    MAX(temperature) - MIN(temperature) as temp_range
FROM weather.observations
GROUP BY station_name
ORDER BY temp_range DESC;
```

## Dashboard URLs

After creation, dashboards will be available at:
- http://localhost:8088/superset/dashboard/1/ (Temperature Trends)
- http://localhost:8088/superset/dashboard/2/ (Weather Map)
- http://localhost:8088/superset/dashboard/3/ (Data Quality Metrics)

## Tips

1. **Refresh Frequency:** Set automatic refresh to 5 minutes for real-time monitoring
2. **Filters:** Add dashboard-level filters for `station_name` and `timestamp`
3. **Colors:** Use consistent color scheme across all dashboards (blue for temperature, green for quality)
4. **Mobile:** Enable mobile layout in dashboard settings

## Troubleshooting

### "No data" in charts
- Check if the pipeline is running: `docker-compose logs dagster`
- Verify data exists: `SELECT COUNT(*) FROM weather.observations;`

### Database connection errors
- Ensure PostgreSQL is running: `docker-compose ps postgres`
- Check credentials in Superset: Data → Databases

### Slow chart loading
- Add indexes to timestamp columns (already done)
- Limit time range to last 7 days
- Use views instead of raw tables

---

**Next Steps:**
1. Open Superset: http://localhost:8088 (admin / admin)
2. Follow the setup steps above to create each dashboard
3. Customize colors, layouts, and filters as needed
4. Set up scheduled email reports (optional)
