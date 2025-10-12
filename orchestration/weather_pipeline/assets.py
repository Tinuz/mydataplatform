"""
Weather data pipeline assets
Fetches weather data from Open-Meteo API (no API key required)
Performs quality checks and loads into data warehouse
"""

import os
from datetime import datetime, timedelta
from io import BytesIO

import pandas as pd
import requests
from dagster import asset, AssetExecutionContext, Output, MetadataValue
from minio import Minio
from sqlalchemy import create_engine, text
import great_expectations as gx
from great_expectations.core.batch import RuntimeBatchRequest

# Import Marquez lineage tracking
try:
    from .marquez_client import emit_lineage_start, emit_lineage_complete, emit_lineage_fail
    MARQUEZ_AVAILABLE = True
except ImportError:
    MARQUEZ_AVAILABLE = False
    print("⚠️  Marquez client not available")


# Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio12345")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "lake")

POSTGRES_CONN = os.getenv(
    "POSTGRES_CONN",
    "postgresql://superset:superset@postgres:5432/superset"
)


def get_minio_client():
    """Get MinIO client"""
    return Minio(
        MINIO_ENDPOINT,
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        secure=False
    )


def get_postgres_engine():
    """Get PostgreSQL engine"""
    return create_engine(POSTGRES_CONN)


@asset(
    group_name="weather_bronze",
    op_tags={"kind": "api", "source": "open-meteo"}
)
def raw_weather_data(context: AssetExecutionContext) -> Output[pd.DataFrame]:
    """
    Fetch current weather data from Open-Meteo API for major Dutch cities
    
    Open-Meteo API: Free, no API key required, high quality weather data
    """
    # Start lineage tracking
    run_id = None
    if MARQUEZ_AVAILABLE:
        run_id = emit_lineage_start("raw_weather_data")
    
    try:
        # Major Dutch cities coordinates
        cities = [
            {"name": "Amsterdam", "lat": 52.3676, "lon": 4.9041},
            {"name": "Rotterdam", "lat": 51.9244, "lon": 4.4777},
            {"name": "Den Haag", "lat": 52.0705, "lon": 4.3007},
            {"name": "Utrecht", "lat": 52.0907, "lon": 5.1214},
            {"name": "Eindhoven", "lat": 51.4416, "lon": 5.4697},
            {"name": "Groningen", "lat": 53.2194, "lon": 6.5665},
            {"name": "Maastricht", "lat": 50.8514, "lon": 5.6909},
        ]
        
        all_weather_data = []
        
        for city in cities:
            context.log.info(f"Fetching weather data for {city['name']}")
            
            # Open-Meteo API - current weather
            url = "https://api.open-meteo.com/v1/forecast"
            params = {
                "latitude": city["lat"],
                "longitude": city["lon"],
                "current": [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "precipitation",
                    "rain",
                    "wind_speed_10m",
                    "wind_direction_10m",
                    "pressure_msl",
                ],
                "timezone": "Europe/Amsterdam"
            }
            
            try:
                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()
                
                # Extract current weather
                current = data.get("current", {})
                
                weather_record = {
                    "station_name": city["name"],
                    "latitude": city["lat"],
                    "longitude": city["lon"],
                    "timestamp": current.get("time"),
                    "temperature": current.get("temperature_2m"),
                    "humidity": current.get("relative_humidity_2m"),
                    "precipitation": current.get("precipitation"),
                    "rain": current.get("rain"),
                    "wind_speed": current.get("wind_speed_10m"),
                    "wind_direction": current.get("wind_direction_10m"),
                    "pressure": current.get("pressure_msl"),
                    "ingestion_time": datetime.now().isoformat(),
                }
                
                all_weather_data.append(weather_record)
                context.log.info(f"✓ {city['name']}: {weather_record['temperature']}°C")
                
            except Exception as e:
                context.log.error(f"Failed to fetch data for {city['name']}: {e}")
        
        # Create DataFrame
        df = pd.DataFrame(all_weather_data)
        
        # Save to MinIO as Parquet (bronze layer)
        minio_client = get_minio_client()
        
        # Create partition path: bronze/weather/YYYY/MM/DD/HH/
        now = datetime.now()
        partition_path = f"bronze/weather/{now.year}/{now.month:02d}/{now.day:02d}/{now.hour:02d}"
        filename = f"weather_{now.strftime('%Y%m%d_%H%M%S')}.parquet"
        object_name = f"{partition_path}/{filename}"
        
        # Convert to parquet bytes
        parquet_buffer = BytesIO()
        df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
        parquet_buffer.seek(0)
        
        # Upload to MinIO
        minio_client.put_object(
            MINIO_BUCKET,
            object_name,
            parquet_buffer,
            length=len(parquet_buffer.getvalue()),
            content_type="application/octet-stream"
        )
        
        context.log.info(f"Saved raw weather data to MinIO: {object_name}")
        
        # Emit lineage complete event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_complete("raw_weather_data", run_id, outputs=[{
                "namespace": "minio",
                "name": f"bronze/weather/{now.year}/{now.month:02d}/{now.day:02d}",
                "source": "MinIO Bronze Layer",
                "uri": f"s3://{MINIO_BUCKET}/{object_name}"
            }])
        
        return Output(
            df,
            metadata={
                "num_records": len(df),
                "num_cities": df["station_name"].nunique(),
                "avg_temperature": float(df["temperature"].mean()),
                "minio_path": object_name,
                "marquez_tracked": MARQUEZ_AVAILABLE,
                "preview": MetadataValue.md(df.head(3).to_markdown()),
            }
        )
    
    except Exception as e:
        # Emit lineage failure event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_fail("raw_weather_data", run_id, str(e))
        raise


@asset(
    group_name="weather_bronze", 
    deps=[raw_weather_data],
    op_tags={"kind": "quality", "framework": "great-expectations"}
)
def weather_quality_check(context: AssetExecutionContext) -> Output[dict]:
    """
    Run Great Expectations quality checks on raw weather data
    """
    # Start lineage tracking
    run_id = None
    if MARQUEZ_AVAILABLE:
        run_id = emit_lineage_start("weather_quality_check")
    
    try:
        context.log.info("Starting data quality checks with Great Expectations")
        
        # Get latest weather data from MinIO
        minio_client = get_minio_client()
        now = datetime.now()
        partition_path = f"bronze/weather/{now.year}/{now.month:02d}/{now.day:02d}/{now.hour:02d}"
        
        # List objects in partition (recursive to get actual files, not directories)
        objects = list(minio_client.list_objects(MINIO_BUCKET, prefix=partition_path, recursive=True))
        
        # Filter out directories (objects ending with /)
        objects = [obj for obj in objects if not obj.object_name.endswith('/')]
        
        if not objects:
            context.log.warning("No weather data found in bronze layer")
            return Output({"status": "no_data", "checks_passed": 0, "checks_failed": 0})
        
        # Get most recent file
        latest_object = sorted(objects, key=lambda x: x.last_modified, reverse=True)[0]
        
        context.log.info(f"Found {len(objects)} file(s), using: {latest_object.object_name}")
        
        # Download from MinIO
        response = minio_client.get_object(MINIO_BUCKET, latest_object.object_name)
        df = pd.read_parquet(BytesIO(response.read()))
        response.close()
        response.release_conn()
        
        context.log.info(f"Running quality checks on {len(df)} records")
        
        # Great Expectations validations
        quality_results = {
            "total_checks": 0,
            "passed_checks": 0,
            "failed_checks": 0,
            "details": []
        }
        
        # Manual quality checks (simplified - full GE setup would be more complex)
        checks = [
            {
                "name": "temperature_range",
                "condition": (df["temperature"] >= -30) & (df["temperature"] <= 45),
                "description": "Temperature within realistic bounds (-30°C to 45°C)"
            },
            {
                "name": "humidity_range",
                "condition": (df["humidity"] >= 0) & (df["humidity"] <= 100),
                "description": "Humidity between 0% and 100%"
            },
            {
                "name": "wind_speed_positive",
                "condition": df["wind_speed"] >= 0,
                "description": "Wind speed is non-negative"
            },
            {
                "name": "precipitation_positive",
                "condition": df["precipitation"] >= 0,
                "description": "Precipitation is non-negative"
            },
            {
                "name": "no_null_temperature",
                "condition": df["temperature"].notna(),
                "description": "Temperature has no null values"
            },
            {
                "name": "no_null_station",
                "condition": df["station_name"].notna(),
                "description": "Station name has no null values"
            },
            {
                "name": "valid_coordinates",
                "condition": (df["latitude"] >= 50.7) & (df["latitude"] <= 53.6) & 
                            (df["longitude"] >= 3.3) & (df["longitude"] <= 7.2),
                "description": "Coordinates within Netherlands bounds"
            }
        ]
        
        for check in checks:
            quality_results["total_checks"] += 1
            passed = check["condition"].all()
            
            if passed:
                quality_results["passed_checks"] += 1
                status = "✓ PASS"
            else:
                quality_results["failed_checks"] += 1
                status = "✗ FAIL"
                failed_count = (~check["condition"]).sum()
                context.log.warning(f"{check['name']} failed for {failed_count} records")
            
            quality_results["details"].append({
                "check": check["name"],
                "description": check["description"],
                "status": status,
                "passed": bool(passed)
            })
            
            context.log.info(f"{status}: {check['description']}")
        
        # Overall result
        quality_results["quality_score"] = (
            quality_results["passed_checks"] / quality_results["total_checks"] * 100
        )
        
        context.log.info(
            f"Quality Score: {quality_results['quality_score']:.1f}% "
            f"({quality_results['passed_checks']}/{quality_results['total_checks']} checks passed)"
        )
        
        # Emit lineage complete event with inputs from bronze
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_complete("weather_quality_check", run_id, outputs=[{
                "namespace": "minio",
                "name": f"bronze/weather/{now.year}/{now.month:02d}/{now.day:02d}",
                "source": "MinIO Bronze Layer",
                "uri": f"s3://lake/bronze/weather/{now.year}/{now.month:02d}/{now.day:02d}"
            }])
        
        return Output(
            quality_results,
            metadata={
                "quality_score": quality_results["quality_score"],
                "checks_passed": quality_results["passed_checks"],
                "checks_failed": quality_results["failed_checks"],
                "marquez_tracked": MARQUEZ_AVAILABLE,
                "summary": MetadataValue.md(
                    f"**Quality Score:** {quality_results['quality_score']:.1f}%\n\n"
                    + "\n".join([
                        f"- {d['status']} {d['description']}"
                        for d in quality_results["details"]
                    ])
                )
            }
        )
    
    except Exception as e:
        # Emit lineage failure event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_fail("weather_quality_check", run_id, str(e))
        raise


@asset(
    group_name="weather_silver", 
    deps=[weather_quality_check],
    op_tags={"kind": "transformation", "layer": "silver"}
)
def clean_weather_data(context: AssetExecutionContext) -> Output[pd.DataFrame]:
    """
    Transform and clean weather data, save to silver layer
    """
    # Start lineage tracking
    run_id = None
    if MARQUEZ_AVAILABLE:
        run_id = emit_lineage_start("clean_weather_data")
    
    try:
        context.log.info("Transforming weather data to silver layer")
        
        # Get latest raw data
        minio_client = get_minio_client()
        now = datetime.now()
        partition_path = f"bronze/weather/{now.year}/{now.month:02d}/{now.day:02d}/{now.hour:02d}"
        
        objects = list(minio_client.list_objects(MINIO_BUCKET, prefix=partition_path, recursive=True))
        objects = [obj for obj in objects if not obj.object_name.endswith('/')]
        
        if not objects:
            context.log.warning("No data to transform")
            return Output(pd.DataFrame())
        
        latest_object = sorted(objects, key=lambda x: x.last_modified, reverse=True)[0]
        context.log.info(f"Reading from: {latest_object.object_name}")
        response = minio_client.get_object(MINIO_BUCKET, latest_object.object_name)
        df = pd.read_parquet(BytesIO(response.read()))
        response.close()
        response.release_conn()
        
        # Transformations
        df_clean = df.copy()
        
        # Add derived columns
        df_clean["feels_like_temp"] = df_clean["temperature"] - (
            (df_clean["wind_speed"] * 0.2) + (100 - df_clean["humidity"]) * 0.01
        )
        
        # Round numeric columns
        numeric_cols = ["temperature", "humidity", "wind_speed", "pressure", "feels_like_temp"]
        for col in numeric_cols:
            if col in df_clean.columns:
                df_clean[col] = df_clean[col].round(2)
        
        # Add processing metadata
        df_clean["processed_at"] = datetime.now().isoformat()
        df_clean["data_quality"] = "validated"
        
        # Save to silver layer
        silver_path = f"silver/weather/{now.year}/{now.month:02d}/{now.day:02d}"
        filename = f"weather_clean_{now.strftime('%Y%m%d_%H%M%S')}.parquet"
        object_name = f"{silver_path}/{filename}"
        
        parquet_buffer = BytesIO()
        df_clean.to_parquet(parquet_buffer, index=False, engine='pyarrow')
        parquet_buffer.seek(0)
        
        minio_client.put_object(
            MINIO_BUCKET,
            object_name,
            parquet_buffer,
            length=len(parquet_buffer.getvalue()),
            content_type="application/octet-stream"
        )
        
        context.log.info(f"Saved clean weather data to MinIO: {object_name}")
        
        # Emit lineage complete event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_complete("clean_weather_data", run_id, outputs=[{
                "namespace": "minio",
                "name": f"silver/weather/{now.year}/{now.month:02d}/{now.day:02d}",
                "source": "MinIO Silver Layer",
                "uri": f"s3://lake/silver/weather/{now.year}/{now.month:02d}/{now.day:02d}"
            }])
        
        return Output(
            df_clean,
            metadata={
                "num_records": len(df_clean),
                "minio_path": object_name,
                "avg_temperature": float(df_clean["temperature"].mean()),
                "avg_feels_like": float(df_clean["feels_like_temp"].mean()),
                "marquez_tracked": MARQUEZ_AVAILABLE,
                "preview": MetadataValue.md(df_clean.head(3).to_markdown()),
            }
        )
    
    except Exception as e:
        # Emit lineage failure event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_fail("clean_weather_data", run_id, str(e))
        raise


@asset(
    group_name="weather_gold", 
    deps=[clean_weather_data],
    op_tags={"kind": "database", "destination": "postgresql"}
)
def weather_to_postgres(context: AssetExecutionContext) -> Output[int]:
    """
    Load clean weather data into PostgreSQL warehouse
    """
    # Start lineage tracking
    run_id = None
    if MARQUEZ_AVAILABLE:
        run_id = emit_lineage_start("weather_to_postgres")
    
    try:
        context.log.info("Loading weather data into PostgreSQL")
        
        # Get latest clean data
        minio_client = get_minio_client()
        now = datetime.now()
        silver_path = f"silver/weather/{now.year}/{now.month:02d}/{now.day:02d}"
        
        objects = list(minio_client.list_objects(MINIO_BUCKET, prefix=silver_path, recursive=True))
        objects = [obj for obj in objects if not obj.object_name.endswith('/')]
        
        if not objects:
            context.log.warning("No clean data to load")
            if MARQUEZ_AVAILABLE and run_id:
                emit_lineage_complete("weather_to_postgres", run_id, outputs=[])
            return Output(0)
        
        latest_object = sorted(objects, key=lambda x: x.last_modified, reverse=True)[0]
        response = minio_client.get_object(MINIO_BUCKET, latest_object.object_name)
        df = pd.read_parquet(BytesIO(response.read()))
        response.close()
        response.release_conn()
        
        # Load to PostgreSQL
        engine = get_postgres_engine()
        
        # Schema already exists from init script, but check anyway
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS weather"))
            conn.commit()
        
        # First, ensure stations exist (upsert into stations table)
        df_stations = df[['station_name', 'latitude', 'longitude']].drop_duplicates()
        
        # Upsert stations (INSERT ... ON CONFLICT DO NOTHING)
        for _, row in df_stations.iterrows():
            with engine.connect() as conn:
                conn.execute(text("""
                    INSERT INTO weather.stations (station_name, latitude, longitude)
                    VALUES (:name, :lat, :lon)
                    ON CONFLICT (station_name) DO UPDATE
                    SET latitude = EXCLUDED.latitude,
                        longitude = EXCLUDED.longitude,
                        updated_at = NOW()
                """), {"name": row['station_name'], "lat": row['latitude'], "lon": row['longitude']})
                conn.commit()
        
        context.log.info(f"Ensured {len(df_stations)} stations exist in weather.stations")
        
        # Drop latitude/longitude columns - they're now in stations table
        # Keep only observations data
        df_observations = df.drop(columns=['latitude', 'longitude'], errors='ignore')
        
        # Upsert observations to handle duplicates
        # Convert DataFrame to list of dicts for batch insert
        records = df_observations.to_dict('records')
        
        # Batch upsert using INSERT ... ON CONFLICT DO UPDATE
        with engine.connect() as conn:
            for record in records:
                conn.execute(text("""
                    INSERT INTO weather.observations (
                        station_name, timestamp, temperature, humidity, 
                        precipitation, rain, wind_speed, wind_direction, 
                        pressure, feels_like_temp, ingestion_time, 
                        processed_at, data_quality
                    )
                    VALUES (
                        :station_name, :timestamp, :temperature, :humidity,
                        :precipitation, :rain, :wind_speed, :wind_direction,
                        :pressure, :feels_like_temp, :ingestion_time,
                        :processed_at, :data_quality
                    )
                    ON CONFLICT (station_name, timestamp) DO UPDATE
                    SET temperature = EXCLUDED.temperature,
                        humidity = EXCLUDED.humidity,
                        precipitation = EXCLUDED.precipitation,
                        rain = EXCLUDED.rain,
                        wind_speed = EXCLUDED.wind_speed,
                        wind_direction = EXCLUDED.wind_direction,
                        pressure = EXCLUDED.pressure,
                        feels_like_temp = EXCLUDED.feels_like_temp,
                        processed_at = EXCLUDED.processed_at,
                        data_quality = EXCLUDED.data_quality
                """), record)
            conn.commit()
        
        context.log.info(f"Upserted {len(df_observations)} records into weather.observations")
        
        # Get total count
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM weather.observations"))
            total_count = result.scalar()
        
        # Emit lineage complete event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_complete("weather_to_postgres", run_id, outputs=[{
                "namespace": "postgres",
                "name": "weather.observations",
                "source": "PostgreSQL",
                "uri": f"postgresql://postgres:5432/superset/weather/observations"
            }])
        
        return Output(
            len(df_observations),
            metadata={
                "records_loaded": len(df_observations),
                "total_records_in_table": total_count,
                "table": "weather.observations",
                "marquez_tracked": MARQUEZ_AVAILABLE,
            }
        )
    
    except Exception as e:
        # Emit lineage failure event
        if MARQUEZ_AVAILABLE and run_id:
            emit_lineage_fail("weather_to_postgres", run_id, str(e))
        raise
