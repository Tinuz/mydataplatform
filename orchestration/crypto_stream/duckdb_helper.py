"""
DuckDB Connection Helper for Superset
Provides pre-configured DuckDB connections with S3/MinIO access
"""
import duckdb
from pathlib import Path

def get_configured_connection(db_path: str = None) -> duckdb.DuckDBPyConnection:
    """
    Create a DuckDB connection with S3/MinIO configuration pre-loaded.
    
    Args:
        db_path: Path to persistent database file. If None, uses :memory:
    
    Returns:
        Configured DuckDB connection
    """
    conn = duckdb.connect(db_path or ':memory:')
    
    # Install and load httpfs extension
    conn.execute("INSTALL httpfs")
    conn.execute("LOAD httpfs")
    
    # Configure S3/MinIO
    conn.execute("""
        SET s3_endpoint='minio:9000';
        SET s3_access_key_id='minio';
        SET s3_secret_access_key='minio12345';
        SET s3_use_ssl=false;
        SET s3_url_style='path';
        SET s3_region='us-east-1';
    """)
    
    # Create views
    conn.execute("""
        CREATE OR REPLACE VIEW trades_bronze AS
        SELECT * FROM read_parquet('s3://lake/crypto/trades_bronze/data/*.parquet');
    """)
    
    conn.execute("""
        CREATE OR REPLACE VIEW trades_1min AS
        SELECT * FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet');
    """)
    
    return conn


def quick_query(sql: str, db_path: str = None):
    """
    Execute a query with automatic S3 configuration.
    
    Args:
        sql: SQL query to execute
        db_path: Path to persistent database file
        
    Returns:
        Query results as DataFrame
    """
    conn = get_configured_connection(db_path)
    result = conn.execute(sql).fetchdf()
    conn.close()
    return result


if __name__ == "__main__":
    # Test the connection
    print("🦆 Testing DuckDB connection with S3 views...\n")
    
    conn = get_configured_connection()
    
    # Test bronze view
    print("=== TRADES_BRONZE ===")
    result = conn.execute("SELECT COUNT(*) as total FROM trades_bronze").fetchone()
    print(f"Total trades: {result[0]}")
    
    result = conn.execute("""
        SELECT symbol, COUNT(*) as count
        FROM trades_bronze 
        GROUP BY symbol
    """).fetchdf()
    print(result)
    
    # Test silver view
    print("\n=== TRADES_1MIN ===")
    result = conn.execute("SELECT COUNT(*) as total FROM trades_1min").fetchone()
    print(f"Total candles: {result[0]}")
    
    result = conn.execute("""
        SELECT symbol, minute, close_price, volume
        FROM trades_1min 
        ORDER BY minute DESC 
        LIMIT 5
    """).fetchdf()
    print(result)
    
    conn.close()
    print("\n✅ Connection test successful!")
