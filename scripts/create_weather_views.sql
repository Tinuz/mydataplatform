-- Weather Dashboard Views
-- These views simplify dashboard creation in Superset

-- View 1: Latest weather per station
CREATE OR REPLACE VIEW weather.latest_weather AS
SELECT DISTINCT ON (station_name)
    station_name,
    timestamp,
    temperature,
    humidity,
    wind_speed,
    feels_like_temp,
    pressure,
    data_quality
FROM weather.observations
ORDER BY station_name, timestamp DESC;

COMMENT ON VIEW weather.latest_weather IS 'Latest weather observation per station';

-- View 2: Weather trends (hourly averages)
CREATE OR REPLACE VIEW weather.hourly_trends AS
SELECT 
    date_trunc('hour', timestamp) as hour,
    station_name,
    AVG(temperature) as avg_temperature,
    AVG(humidity) as avg_humidity,
    AVG(wind_speed) as avg_wind_speed,
    AVG(feels_like_temp) as avg_feels_like,
    COUNT(*) as observation_count
FROM weather.observations
GROUP BY date_trunc('hour', timestamp), station_name
ORDER BY hour DESC, station_name;

COMMENT ON VIEW weather.hourly_trends IS 'Hourly averaged weather trends per station';

-- View 3: Weather station metrics (with location)
CREATE OR REPLACE VIEW weather.station_metrics AS
SELECT 
    s.station_name,
    s.latitude,
    s.longitude,
    COUNT(o.id) as total_observations,
    MAX(o.timestamp) as last_observation,
    AVG(o.temperature) as avg_temperature,
    MIN(o.temperature) as min_temperature,
    MAX(o.temperature) as max_temperature,
    AVG(o.humidity) as avg_humidity,
    AVG(o.wind_speed) as avg_wind_speed
FROM weather.stations s
LEFT JOIN weather.observations o ON s.station_name = o.station_name
GROUP BY s.station_name, s.latitude, s.longitude;

COMMENT ON VIEW weather.station_metrics IS 'Aggregated metrics per weather station with location';

-- View 4: Data quality summary
CREATE OR REPLACE VIEW weather.data_quality_summary AS
SELECT 
    data_quality,
    COUNT(*) as record_count,
    COUNT(*) * 100.0 / SUM(COUNT(*)) OVER () as percentage,
    MIN(timestamp) as first_seen,
    MAX(timestamp) as last_seen
FROM weather.observations
WHERE data_quality IS NOT NULL
GROUP BY data_quality
ORDER BY record_count DESC;

COMMENT ON VIEW weather.data_quality_summary IS 'Data quality distribution and statistics';

-- View 5: Weather near cell towers (for map visualization)
CREATE OR REPLACE VIEW weather.weather_tower_proximity AS
SELECT 
    wnt.station_name,
    wnt.tower_radio,
    wnt.tower_mcc,
    wnt.tower_net,
    wnt.tower_area,
    wnt.tower_cell,
    wnt.distance_km,
    s.latitude as station_lat,
    s.longitude as station_lon,
    o.temperature,
    o.humidity,
    o.wind_speed,
    o.timestamp as weather_timestamp
FROM weather.weather_near_towers wnt
JOIN weather.stations s ON wnt.station_name = s.station_name
LEFT JOIN LATERAL (
    SELECT temperature, humidity, wind_speed, timestamp
    FROM weather.observations
    WHERE station_name = wnt.station_name
    ORDER BY timestamp DESC
    LIMIT 1
) o ON true
WHERE wnt.distance_km < 10;  -- Only towers within 10km

COMMENT ON VIEW weather.weather_tower_proximity IS 'Weather conditions near cell towers (within 10km)';

-- Grant access
GRANT SELECT ON weather.latest_weather TO superset;
GRANT SELECT ON weather.hourly_trends TO superset;
GRANT SELECT ON weather.station_metrics TO superset;
GRANT SELECT ON weather.data_quality_summary TO superset;
GRANT SELECT ON weather.weather_tower_proximity TO superset;

-- Summary
SELECT 'Created 5 views for Superset dashboards' as status;
