"""
DuckDB queries for Iceberg tables in MinIO.
Provides SQL interface to crypto streaming data.
"""

import duckdb
import os
from pathlib import Path


def get_duckdb_connection(read_only=True):
    """
    Create DuckDB connection with Iceberg and S3 extensions configured.
    
    Args:
        read_only: If True, creates in-memory connection. If False, uses persistent DB.
    
    Returns:
        duckdb.DuckDBPyConnection
    """
    if read_only:
        # In-memory for queries
        conn = duckdb.connect(":memory:")
    else:
        # Persistent database for Superset
        db_path = Path("/opt/dagster/app/crypto_stream/crypto_analytics.db")
        db_path.parent.mkdir(exist_ok=True, parents=True)
        conn = duckdb.connect(str(db_path))
    
    # Install and load extensions
    conn.execute("INSTALL httpfs;")
    conn.execute("LOAD httpfs;")
    
    # Configure S3/MinIO credentials
    conn.execute(f"""
        SET s3_endpoint='minio:9000';
        SET s3_access_key_id='minio';
        SET s3_secret_access_key='minio12345';
        SET s3_use_ssl=false;
        SET s3_url_style='path';
        SET s3_region='us-east-1';
    """)
    
    return conn


def create_iceberg_views(conn):
    """
    Create DuckDB views that point to Iceberg Parquet files in MinIO.
    We read Parquet directly instead of using iceberg_scan() to avoid metadata issues.
    """
    # Bronze layer view - direct Parquet read
    conn.execute("""
        CREATE OR REPLACE VIEW trades_bronze AS
        SELECT * FROM read_parquet('s3://lake/crypto/trades_bronze/data/*.parquet');
    """)
    
    # Silver layer view - direct Parquet read
    conn.execute("""
        CREATE OR REPLACE VIEW trades_1min AS
        SELECT * FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet');
    """)
    
    print("✅ Created Parquet views: trades_bronze, trades_1min")


def query_latest_prices():
    """Get latest price per symbol"""
    conn = get_duckdb_connection()
    create_iceberg_views(conn)
    
    result = conn.execute("""
        SELECT 
            symbol,
            price as latest_price,
            quantity,
            event_time
        FROM trades_bronze
        QUALIFY ROW_NUMBER() OVER (PARTITION BY symbol ORDER BY event_time DESC) = 1
        ORDER BY symbol;
    """).fetchdf()
    
    return result


def query_ohlcv_candles(symbol=None, limit=100):
    """Get OHLCV candles from silver layer"""
    conn = get_duckdb_connection()
    create_iceberg_views(conn)
    
    where_clause = f"WHERE symbol = '{symbol}'" if symbol else ""
    
    result = conn.execute(f"""
        SELECT 
            symbol,
            minute,
            open_price,
            high_price,
            low_price,
            close_price,
            volume,
            trade_count
        FROM trades_1min
        {where_clause}
        ORDER BY minute DESC
        LIMIT {limit};
    """).fetchdf()
    
    return result


def query_volume_by_symbol():
    """Get total volume per symbol"""
    conn = get_duckdb_connection()
    create_iceberg_views(conn)
    
    result = conn.execute("""
        SELECT 
            symbol,
            COUNT(*) as trade_count,
            SUM(quantity) as total_volume,
            MIN(price) as min_price,
            MAX(price) as max_price,
            AVG(price) as avg_price,
            MIN(event_time) as first_trade,
            MAX(event_time) as last_trade
        FROM trades_bronze
        GROUP BY symbol
        ORDER BY total_volume DESC;
    """).fetchdf()
    
    return result


def query_price_changes():
    """Calculate price changes over time"""
    conn = get_duckdb_connection()
    create_iceberg_views(conn)
    
    result = conn.execute("""
        WITH price_points AS (
            SELECT 
                symbol,
                minute,
                close_price,
                LAG(close_price) OVER (PARTITION BY symbol ORDER BY minute) as prev_close
            FROM trades_1min
        )
        SELECT 
            symbol,
            minute,
            close_price,
            prev_close,
            CASE 
                WHEN prev_close IS NOT NULL 
                THEN ROUND(((close_price - prev_close) / prev_close * 100), 2)
                ELSE NULL 
            END as pct_change
        FROM price_points
        WHERE prev_close IS NOT NULL
        ORDER BY minute DESC;
    """).fetchdf()
    
    return result


def query_trade_velocity():
    """Trades per minute analysis"""
    conn = get_duckdb_connection()
    create_iceberg_views(conn)
    
    result = conn.execute("""
        SELECT 
            symbol,
            DATE_TRUNC('minute', event_time) as minute,
            COUNT(*) as trades_per_minute,
            SUM(quantity) as volume_per_minute,
            AVG(price) as avg_price
        FROM trades_bronze
        GROUP BY symbol, DATE_TRUNC('minute', event_time)
        ORDER BY minute DESC;
    """).fetchdf()
    
    return result


if __name__ == "__main__":
    print("\n🦆 DuckDB Iceberg Query Examples\n")
    print("=" * 70)
    
    # Test connection
    print("\n1️⃣ Testing DuckDB connection to Iceberg...")
    conn = get_duckdb_connection()
    create_iceberg_views(conn)
    print("✅ Connection successful!\n")
    
    # Latest prices
    print("\n2️⃣ Latest Prices:")
    print("-" * 70)
    latest = query_latest_prices()
    print(latest.to_string(index=False))
    
    # Volume by symbol
    print("\n\n3️⃣ Volume by Symbol:")
    print("-" * 70)
    volume = query_volume_by_symbol()
    print(volume.to_string(index=False))
    
    # OHLCV candles
    print("\n\n4️⃣ Recent OHLCV Candles (latest 5):")
    print("-" * 70)
    candles = query_ohlcv_candles(limit=5)
    print(candles.to_string(index=False))
    
    # Price changes
    print("\n\n5️⃣ Price Changes:")
    print("-" * 70)
    changes = query_price_changes()
    print(changes.head(10).to_string(index=False))
    
    print("\n\n✅ All queries executed successfully!")
    print("💡 Use these functions in your Superset or analytics workflows.\n")
