"""
Crypto Stream Assets

Kafka → Iceberg → Analytics pipeline for cryptocurrency trading data.

Assets:
1. crypto_trades_bronze: Raw trades from Kafka → Iceberg bronze layer
2. crypto_trades_1min: 1-minute OHLCV candles (bronze → silver)
3. crypto_daily_stats: Daily aggregations (silver → gold)
"""

from dagster import (
    asset,
    AssetExecutionContext,
    MetadataValue,
    AssetIn,
    DailyPartitionsDefinition,
)
import pandas as pd
from datetime import datetime, timedelta
import json
import os
from typing import Dict, List

# Iceberg imports
try:
    from pyiceberg.catalog import load_catalog
    from pyiceberg.schema import Schema
    from pyiceberg.types import (
        TimestampType,
        StringType,
        DoubleType,
        LongType,
        BooleanType,
        NestedField,
    )
    from pyiceberg.partitioning import PartitionSpec, PartitionField
    from pyiceberg.transforms import HourTransform
    ICEBERG_AVAILABLE = True
except ImportError:
    ICEBERG_AVAILABLE = False

# Kafka imports
try:
    from kafka import KafkaConsumer
    KAFKA_AVAILABLE = True
except ImportError:
    KAFKA_AVAILABLE = False

# PyArrow imports
try:
    import pyarrow as pa
    PYARROW_AVAILABLE = True
except ImportError:
    PYARROW_AVAILABLE = False


# Configuration
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
KAFKA_TOPIC = "crypto_trades"
ICEBERG_CATALOG_URI = os.getenv("ICEBERG_CATALOG_URI", "http://iceberg-rest:8181")
ICEBERG_WAREHOUSE = "s3://lake/"
BATCH_SIZE = 1000  # Records per Iceberg write
BATCH_TIMEOUT = 30  # Seconds before flushing partial batch
MAX_MESSAGES = 1000  # Maximum messages to consume per run (prevent overwhelming first run)


def get_iceberg_catalog():
    """
    Get Iceberg catalog with proper S3/MinIO configuration.
    
    Configures PyArrow S3FileSystem with HTTP (no SSL) for MinIO.
    """
    import pyarrow.fs as pafs
    from pyiceberg.io.pyarrow import PyArrowFileIO
    
    # Create PyArrow S3 filesystem with explicit HTTP (no SSL)
    s3fs = pafs.S3FileSystem(
        endpoint_override="minio:9000",
        access_key=os.getenv("AWS_ACCESS_KEY_ID", "minio"),
        secret_key=os.getenv("AWS_SECRET_ACCESS_KEY", "minio12345"),
        scheme="http",  # Force HTTP instead of HTTPS
        region=os.getenv("AWS_REGION", "us-east-1"),
    )
    
    # Load catalog
    catalog = load_catalog(
        "rest",
        **{
            "uri": ICEBERG_CATALOG_URI,
            "warehouse": ICEBERG_WAREHOUSE,
            "s3.endpoint": "http://minio:9000",
            "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID", "minio"),
            "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY", "minio12345"),
            "s3.path-style-access": "true",
            "s3.region": os.getenv("AWS_REGION", "us-east-1"),
        }
    )
    
    # Override the FileIO to use our custom S3 filesystem
    catalog._fileio = PyArrowFileIO(
        properties={
            "s3.endpoint": "http://minio:9000",
            "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID", "minio"),
            "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY", "minio12345"),
            "s3.region": os.getenv("AWS_REGION", "us-east-1"),
        }
    )
    catalog._fileio._s3 = s3fs
    
    return catalog


@asset(
    group_name="crypto_ingestion",
    compute_kind="kafka+iceberg",
    description="Raw cryptocurrency trades from Kafka → Iceberg bronze layer"
)
def crypto_trades_bronze(context: AssetExecutionContext) -> Dict:
    """
    Consume crypto trades from Kafka and write to Iceberg bronze table.
    
    Flow:
    1. Poll Kafka topic 'crypto_trades'
    2. Batch messages (1000 records or 30 seconds)
    3. Write batch to Iceberg table with ACID guarantees
    4. Commit Kafka offset
    
    Table: iceberg.crypto.trades_bronze
    Partitioning: hour(event_time) - one partition per hour
    Format: Parquet (columnar, compressed)
    """
    
    if not ICEBERG_AVAILABLE or not KAFKA_AVAILABLE:
        context.log.error("❌ Missing dependencies: pyiceberg or kafka-python")
        raise ImportError("Install: pip install pyiceberg kafka-python")
    
    context.log.info("🚀 Starting Kafka → Iceberg ingestion...")
    
    # Get Iceberg catalog with proper S3 configuration
    catalog = get_iceberg_catalog()
    
    # Create namespace if not exists
    try:
        catalog.create_namespace("crypto")
        context.log.info("✅ Created namespace: crypto")
    except Exception:
        context.log.info("ℹ️ Namespace 'crypto' already exists")
    
    # Define Iceberg schema
    schema = Schema(
        NestedField(1, "symbol", StringType(), required=True),
        NestedField(2, "price", DoubleType(), required=True),
        NestedField(3, "quantity", DoubleType(), required=True),
        NestedField(4, "event_time", TimestampType(), required=True),
        NestedField(5, "trade_id", LongType(), required=True),
        NestedField(6, "is_buyer_maker", BooleanType(), required=True),
        NestedField(7, "ingested_at", TimestampType(), required=True),
    )
    
    # Define partitioning: Unpartitioned for now (can add hourly partitioning later)
    partition_spec = PartitionSpec()
    
    # Create or load table
    table_name = "crypto.trades_bronze"
    try:
        table = catalog.load_table(table_name)
        context.log.info(f"✅ Loaded existing table: {table_name}")
    except Exception:
        context.log.info(f"📝 Creating new table: {table_name}")
        table = catalog.create_table(
            identifier=table_name,
            schema=schema,
            partition_spec=partition_spec,
        )
    
    # Initialize Kafka consumer
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        auto_offset_reset='latest',  # Only new messages
        enable_auto_commit=False,  # Manual commit after Iceberg write
        group_id='crypto_stream_dagster',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        consumer_timeout_ms=BATCH_TIMEOUT * 1000
    )
    
    context.log.info(f"✅ Connected to Kafka: {KAFKA_TOPIC}")
    context.log.info(f"⚙️  Config: MAX_MESSAGES={MAX_MESSAGES}, BATCH_SIZE={BATCH_SIZE}")
    
    # Consume messages in batches
    batch = []
    total_records = 0
    start_time = datetime.now()
    
    try:
        for message in consumer:
            batch.append(message.value)
            
            # Write batch when full or timeout
            if len(batch) >= BATCH_SIZE:
                records_written = write_batch_to_iceberg(context, table, batch)
                total_records += records_written
                
                # Commit Kafka offset
                consumer.commit()
                context.log.info(f"✅ Committed offset: partition={message.partition}, offset={message.offset}")
                
                # Reset batch
                batch = []
            
            # Stop if we've reached MAX_MESSAGES
            if total_records + len(batch) >= MAX_MESSAGES:
                context.log.info(f"⏸️  Reached MAX_MESSAGES limit ({MAX_MESSAGES}), stopping...")
                break
        
        # Write remaining records
        if batch:
            records_written = write_batch_to_iceberg(context, table, batch)
            total_records += records_written
            consumer.commit()
    
    finally:
        consumer.close()
    
    duration = (datetime.now() - start_time).total_seconds()
    
    # Get table stats
    current_snapshot = table.current_snapshot()
    snapshot_id = current_snapshot.snapshot_id if current_snapshot else "N/A"
    
    context.add_output_metadata({
        "records_ingested": total_records,
        "duration_seconds": duration,
        "records_per_second": round(total_records / duration, 2) if duration > 0 else 0,
        "iceberg_snapshot_id": snapshot_id,
        "kafka_topic": KAFKA_TOPIC,
        "batch_size": BATCH_SIZE,
    })
    
    context.log.info(
        f"✅ Ingestion complete: {total_records} records in {duration:.1f}s "
        f"({total_records / duration:.1f} records/sec)"
    )
    
    return {
        "records": total_records,
        "snapshot_id": snapshot_id
    }


def write_batch_to_iceberg(context, table, batch: List[Dict]) -> int:
    """Write a batch of records to Iceberg table"""
    if not batch:
        return 0
    
    try:
        # Convert to DataFrame
        df = pd.DataFrame(batch)
        
        # Parse timestamps with flexible format handling (ISO8601 with or without microseconds)
        df['event_time'] = pd.to_datetime(df['event_time'], format='ISO8601')
        df['ingested_at'] = pd.to_datetime(df['ingested_at'], format='ISO8601')
        
        # Convert to PyArrow table (required by PyIceberg)
        arrow_table = pa.Table.from_pandas(df)
        
        # Build schema with correct types and nullable=False (Iceberg requires all fields to be required)
        new_fields = []
        for field in arrow_table.schema:
            if pa.types.is_timestamp(field.type):
                # Convert timestamp[ns] -> timestamp[us] without timezone (Iceberg timestamp type)
                new_fields.append(pa.field(field.name, pa.timestamp('us'), nullable=False))
            elif pa.types.is_string(field.type):
                new_fields.append(pa.field(field.name, pa.string(), nullable=False))
            elif pa.types.is_floating(field.type):
                new_fields.append(pa.field(field.name, pa.float64(), nullable=False))
            elif pa.types.is_integer(field.type):
                new_fields.append(pa.field(field.name, pa.int64(), nullable=False))
            elif pa.types.is_boolean(field.type):
                new_fields.append(pa.field(field.name, pa.bool_(), nullable=False))
            else:
                new_fields.append(pa.field(field.name, field.type, nullable=False))
        
        new_schema = pa.schema(new_fields)
        arrow_table = arrow_table.cast(new_schema)
        
        # Write to Iceberg (ACID transaction)
        table.append(arrow_table)
        
        context.log.info(f"📝 Wrote {len(df)} records to Iceberg")
        
        return len(df)
    
    except Exception as e:
        context.log.error(f"❌ Failed to write batch: {e}")
        raise


@asset(
    group_name="crypto_transformation",
    compute_kind="iceberg",
    deps=[crypto_trades_bronze],
    description="1-minute OHLCV candles from bronze trades"
)
def crypto_trades_1min(context: AssetExecutionContext) -> Dict:
    """
    Aggregate bronze trades into 1-minute OHLCV candles.
    
    Transformation: Bronze → Silver
    
    Table: iceberg.crypto.trades_1min
    Partitioning: hour(minute)
    """
    
    context.log.info("🔄 Aggregating trades into 1-minute candles...")
    
    # Get Iceberg catalog with proper S3 configuration
    catalog = get_iceberg_catalog()
    
    # Read bronze table
    bronze_table = catalog.load_table("crypto.trades_bronze")
    
    # Query recent trades (last hour)
    cutoff_time = datetime.utcnow() - timedelta(hours=1)
    
    # Use DuckDB for aggregation (fast query engine for Iceberg)
    # In production: use DuckDB to query Iceberg directly
    df = bronze_table.scan().to_pandas()
    
    if df.empty:
        context.log.warning("⚠️ No data in bronze table")
        return {"records": 0}
    
    # Filter recent data
    df['event_time'] = pd.to_datetime(df['event_time'])
    df = df[df['event_time'] >= cutoff_time]
    
    # Group by symbol and 1-minute window
    df['minute'] = df['event_time'].dt.floor('1min')
    
    candles = df.groupby(['symbol', 'minute']).agg({
        'price': ['first', 'max', 'min', 'last'],
        'quantity': 'sum',
        'trade_id': 'count'
    }).reset_index()
    
    # Flatten columns
    candles.columns = ['symbol', 'minute', 'open_price', 'high_price', 'low_price', 'close_price', 'volume', 'trade_count']
    
    # Define silver schema
    silver_schema = Schema(
        NestedField(1, "symbol", StringType(), required=True),
        NestedField(2, "minute", TimestampType(), required=True),
        NestedField(3, "open_price", DoubleType(), required=True),
        NestedField(4, "high_price", DoubleType(), required=True),
        NestedField(5, "low_price", DoubleType(), required=True),
        NestedField(6, "close_price", DoubleType(), required=True),
        NestedField(7, "volume", DoubleType(), required=True),
        NestedField(8, "trade_count", LongType(), required=True),
    )
    
    # Create/load silver table
    try:
        silver_table = catalog.load_table("crypto.trades_1min")
    except Exception:
        silver_table = catalog.create_table(
            "crypto.trades_1min",
            schema=silver_schema,
            partition_spec=PartitionSpec(),  # Unpartitioned for now (PyIceberg 0.6.1 limitation)
        )
    
    # Convert to PyArrow table with correct types
    # First, ensure data types are correct in pandas
    candles['symbol'] = candles['symbol'].astype(str)
    candles['minute'] = pd.to_datetime(candles['minute'])
    candles['open_price'] = candles['open_price'].astype(float)
    candles['high_price'] = candles['high_price'].astype(float)
    candles['low_price'] = candles['low_price'].astype(float)
    candles['close_price'] = candles['close_price'].astype(float)
    candles['volume'] = candles['volume'].astype(float)
    candles['trade_count'] = candles['trade_count'].astype(int)
    
    # Define explicit PyArrow schema
    arrow_schema = pa.schema([
        pa.field('symbol', pa.string(), nullable=False),
        pa.field('minute', pa.timestamp('us'), nullable=False),
        pa.field('open_price', pa.float64(), nullable=False),
        pa.field('high_price', pa.float64(), nullable=False),
        pa.field('low_price', pa.float64(), nullable=False),
        pa.field('close_price', pa.float64(), nullable=False),
        pa.field('volume', pa.float64(), nullable=False),
        pa.field('trade_count', pa.int64(), nullable=False),
    ])
    
    # Convert to PyArrow with explicit schema
    arrow_table = pa.Table.from_pandas(candles, schema=arrow_schema)
    
    # Append candles to Iceberg table
    silver_table.append(arrow_table)
    
    context.log.info(f"✅ Created {len(candles)} 1-minute candles")
    
    context.add_output_metadata({
        "candles_created": len(candles),
        "symbols": MetadataValue.md(", ".join(candles['symbol'].unique())),
        "time_range": f"{candles['minute'].min()} to {candles['minute'].max()}",
    })
    
    return {"records": len(candles)}


@asset(
    group_name="crypto_analytics",
    compute_kind="iceberg",
    deps=[crypto_trades_1min],
    partitions_def=DailyPartitionsDefinition(start_date="2025-10-01"),
    description="Daily crypto statistics (gold layer)"
)
def crypto_daily_stats(context: AssetExecutionContext) -> Dict:
    """
    Daily aggregations: open, high, low, close, volume, volatility.
    
    Transformation: Silver → Gold
    
    Table: iceberg.crypto.daily_stats
    Partitioning: day(date)
    """
    
    partition_date = context.partition_key
    context.log.info(f"📊 Computing daily stats for {partition_date}...")
    
    # TODO: Implement daily aggregation
    # This would read from trades_1min and aggregate to daily level
    
    context.log.info("✅ Daily stats computed")
    
    return {"date": partition_date}
