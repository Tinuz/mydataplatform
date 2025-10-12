-- Create weather schema and tables for weather data pipeline
-- This will be run on database initialization

CREATE SCHEMA IF NOT EXISTS weather;

-- Weather stations dimension table
CREATE TABLE IF NOT EXISTS weather.stations (
    station_name VARCHAR(100) PRIMARY KEY,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    elevation INTEGER,
    country VARCHAR(50) DEFAULT 'Netherlands',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Weather observations fact table
CREATE TABLE IF NOT EXISTS weather.observations (
    id SERIAL PRIMARY KEY,
    station_name VARCHAR(100) REFERENCES weather.stations(station_name),
    timestamp TIMESTAMP NOT NULL,
    temperature DOUBLE PRECISION,
    humidity INTEGER,
    precipitation DOUBLE PRECISION,
    rain DOUBLE PRECISION,
    wind_speed DOUBLE PRECISION,
    wind_direction INTEGER,
    pressure DOUBLE PRECISION,
    feels_like_temp DOUBLE PRECISION,
    ingestion_time TIMESTAMP,
    processed_at TIMESTAMP,
    data_quality VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT unique_observation UNIQUE(station_name, timestamp)
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_observations_station ON weather.observations(station_name);
CREATE INDEX IF NOT EXISTS idx_observations_timestamp ON weather.observations(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_observations_station_timestamp ON weather.observations(station_name, timestamp DESC);

-- Create view: weather data near cell towers
-- Joins weather observations with nearest cell tower data
-- Uses simplified distance calculation (Haversine formula approximation)
CREATE OR REPLACE VIEW weather.weather_near_towers AS
WITH nearest_stations AS (
    SELECT 
        ct.radio,
        ct.mcc,
        ct.net,
        ct.area,
        ct.cell,
        ct.lon AS tower_lon,
        ct.lat AS tower_lat,
        ws.station_name,
        ws.latitude AS station_lat,
        ws.longitude AS station_lon,
        -- Haversine distance in km
        (
            6371 * acos(
                cos(radians(ct.lat)) * cos(radians(ws.latitude)) * 
                cos(radians(ws.longitude) - radians(ct.lon)) + 
                sin(radians(ct.lat)) * sin(radians(ws.latitude))
            )
        ) AS distance_km,
        ROW_NUMBER() OVER (PARTITION BY ct.cell, ct.area, ct.net, ct.mcc ORDER BY 
            (
                6371 * acos(
                    cos(radians(ct.lat)) * cos(radians(ws.latitude)) * 
                    cos(radians(ws.longitude) - radians(ct.lon)) + 
                    sin(radians(ct.lat)) * sin(radians(ws.latitude))
                )
            )
        ) AS rn
    FROM cell_towers.clean_204 ct
    CROSS JOIN weather.stations ws
)
SELECT 
    ns.radio,
    ns.mcc,
    ns.net,
    ns.area,
    ns.cell,
    ns.tower_lon,
    ns.tower_lat,
    ns.station_name,
    ns.distance_km,
    wo.timestamp AS observation_time,
    wo.temperature,
    wo.humidity,
    wo.wind_speed,
    wo.wind_direction,
    wo.precipitation,
    wo.pressure,
    wo.feels_like_temp
FROM nearest_stations ns
INNER JOIN weather.observations wo ON wo.station_name = ns.station_name
WHERE ns.rn = 1  -- Only nearest station per tower
ORDER BY ns.cell, wo.timestamp DESC;

-- Grant permissions
GRANT USAGE ON SCHEMA weather TO superset;
GRANT SELECT ON ALL TABLES IN SCHEMA weather TO superset;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA weather TO superset;
GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA weather TO superset;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA weather GRANT SELECT ON TABLES TO superset;

-- Add comment on schema
COMMENT ON SCHEMA weather IS 'Weather data from Open-Meteo API - orchestrated by Dagster';
COMMENT ON TABLE weather.stations IS 'Weather station dimension table with coordinates';
COMMENT ON TABLE weather.observations IS 'Weather observations fact table with hourly data';
COMMENT ON VIEW weather.weather_near_towers IS 'Weather data joined with nearest cell towers using Haversine distance';
