-- DuckDB Init File for Superset
-- This file automatically loads S3 configuration

-- Install and load S3 support
INSTALL httpfs;
LOAD httpfs;

-- Configure MinIO connection
SET s3_endpoint='minio:9000';
SET s3_access_key_id='minio';
SET s3_secret_access_key='minio12345';
SET s3_use_ssl=false;
SET s3_url_style='path';
SET s3_region='us-east-1';

-- Create views for Iceberg data
CREATE OR REPLACE VIEW trades_bronze AS
SELECT * FROM read_parquet('s3://lake/crypto/trades_bronze/data/*.parquet');

CREATE OR REPLACE VIEW trades_1min AS
SELECT * FROM read_parquet('s3://lake/crypto/trades_1min/data/*.parquet');
