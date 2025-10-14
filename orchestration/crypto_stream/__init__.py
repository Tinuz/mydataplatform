"""
Crypto Stream Analytics Project

Real-time cryptocurrency trading data pipeline.

Architecture:
    Binance WebSocket → Kafka → Iceberg (MinIO) → DuckDB/PostgreSQL → Superset

Components:
- producers/binance_producer.py: WebSocket → Kafka ingestion
- assets/crypto_assets.py: Dagster assets (Kafka → Iceberg)
- resources.py: Reusable Kafka + Iceberg connections

Usage:
    # Start WebSocket producer
    python -m crypto_stream.producers.binance_producer
    
    # Materialize assets in Dagster UI
    http://localhost:3000 → crypto_stream_location
"""

from dagster import Definitions, load_assets_from_modules
from . import assets
from .resources import kafka_resource, iceberg_resource

# Load all assets
all_assets = load_assets_from_modules([assets])

# Define the Dagster repository
defs = Definitions(
    assets=all_assets,
    resources={
        "kafka": kafka_resource,
        "iceberg": iceberg_resource,
    }
)
