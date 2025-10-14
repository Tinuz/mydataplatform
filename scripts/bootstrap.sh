#!/bin/bash
# 🚀 Data Platform Bootstrap Script
# This script ensures the platform is fully initialized after docker-compose up
# Run: ./scripts/bootstrap.sh

set -e

echo "🚀 Data Platform Bootstrap Starting..."
echo "======================================"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to wait for service
wait_for_service() {
    local service=$1
    local url=$2
    local max_attempts=30
    local attempt=1
    
    echo -e "${YELLOW}⏳ Waiting for $service to be ready...${NC}"
    while ! curl -sf "$url" > /dev/null 2>&1; do
        if [ $attempt -eq $max_attempts ]; then
            echo -e "${RED}❌ $service failed to start after $max_attempts attempts${NC}"
            return 1
        fi
        echo "   Attempt $attempt/$max_attempts..."
        sleep 2
        attempt=$((attempt + 1))
    done
    echo -e "${GREEN}✅ $service is ready${NC}"
}

# 1. Wait for core services
echo ""
echo "📊 Step 1: Waiting for core services..."
wait_for_service "PostgreSQL" "http://localhost:5432" || echo "PostgreSQL check via curl failed (expected), checking via docker exec..."
docker-compose exec -T postgres pg_isready -U superset > /dev/null 2>&1
echo -e "${GREEN}✅ PostgreSQL is ready${NC}"

wait_for_service "MinIO" "http://localhost:9000/minio/health/live"
wait_for_service "Superset" "http://localhost:8088/health"

# 2. Initialize Superset
echo ""
echo "🎨 Step 2: Initializing Superset..."
docker-compose exec -T superset superset db upgrade > /dev/null 2>&1
echo -e "${GREEN}✅ Superset database upgraded${NC}"

# Check if admin exists, create if not
if ! docker-compose exec -T superset superset fab list-users | grep -q "admin"; then
    echo "   Creating admin user..."
    docker-compose exec -T superset superset fab create-admin \
        --username admin \
        --firstname Admin \
        --lastname User \
        --email admin@superset.com \
        --password admin > /dev/null 2>&1
    echo -e "${GREEN}✅ Admin user created${NC}"
else
    echo -e "${GREEN}✅ Admin user already exists${NC}"
fi

docker-compose exec -T superset superset init > /dev/null 2>&1
echo -e "${GREEN}✅ Superset initialized${NC}"

# 3. Create MinIO bucket if it doesn't exist
echo ""
echo "🪣 Step 3: Setting up MinIO bucket..."
docker-compose exec -T dagster python3 << 'EOF'
from minio import Minio
from minio.error import S3Error

client = Minio(
    "minio:9000",
    access_key="minio",
    secret_key="minio12345",
    secure=False
)

bucket_name = "lake"
try:
    if not client.bucket_exists(bucket_name):
        client.make_bucket(bucket_name)
        print(f"✅ Created bucket: {bucket_name}")
    else:
        print(f"✅ Bucket already exists: {bucket_name}")
except S3Error as e:
    print(f"❌ Error: {e}")
EOF

# 4. Sync crypto data to PostgreSQL (if assets are materialized)
echo ""
echo "🔄 Step 4: Syncing crypto data to PostgreSQL..."
docker-compose exec -T dagster python3 << 'EOF'
from crypto_stream.duckdb_helper import quick_query
import psycopg2
from psycopg2.extras import execute_values

try:
    # Check if Iceberg data exists
    df_bronze = quick_query('SELECT * FROM trades_bronze LIMIT 1')
    
    print("📊 Iceberg data found, syncing to PostgreSQL...")
    
    # Get full data
    df_bronze = quick_query('SELECT * FROM trades_bronze')
    df_silver = quick_query('SELECT * FROM trades_1min')
    
    # Connect to PostgreSQL
    conn = psycopg2.connect(
        host='postgres', 
        database='superset', 
        user='superset', 
        password='superset'
    )
    cur = conn.cursor()
    
    # Create schema
    cur.execute('CREATE SCHEMA IF NOT EXISTS crypto')
    
    # Bronze table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS crypto.trades_bronze (
            symbol VARCHAR(20),
            price DOUBLE PRECISION,
            quantity DOUBLE PRECISION,
            trade_id BIGINT,
            event_time TIMESTAMP
        )
    ''')
    cur.execute('TRUNCATE TABLE crypto.trades_bronze')
    execute_values(cur, 
        'INSERT INTO crypto.trades_bronze VALUES %s',
        df_bronze[['symbol', 'price', 'quantity', 'trade_id', 'event_time']].values.tolist()
    )
    
    # Silver table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS crypto.trades_1min (
            symbol VARCHAR(20),
            minute TIMESTAMP,
            open_price DOUBLE PRECISION,
            high_price DOUBLE PRECISION,
            low_price DOUBLE PRECISION,
            close_price DOUBLE PRECISION,
            volume DOUBLE PRECISION,
            trade_count INTEGER
        )
    ''')
    cur.execute('TRUNCATE TABLE crypto.trades_1min')
    execute_values(cur, 
        'INSERT INTO crypto.trades_1min VALUES %s',
        df_silver.values.tolist()
    )
    
    # Latest prices view
    cur.execute('''
        CREATE OR REPLACE VIEW crypto.latest_prices AS
        SELECT DISTINCT ON (symbol)
            symbol,
            price as latest_price,
            quantity,
            event_time
        FROM crypto.trades_bronze
        ORDER BY symbol, event_time DESC
    ''')
    
    conn.commit()
    conn.close()
    
    print(f"✅ Synced {len(df_bronze)} trades and {len(df_silver)} candles to PostgreSQL")
    
except Exception as e:
    print(f"⚠️  No crypto data found (this is OK if you haven't run crypto assets yet)")
    print(f"   Run: docker-compose exec dagster dagster asset materialize -m crypto_stream")
EOF

# 5. Print summary
echo ""
echo "======================================"
echo -e "${GREEN}🎉 Bootstrap Complete!${NC}"
echo "======================================"
echo ""
echo "📍 Service URLs:"
echo "   Superset:       http://localhost:8088 (admin/admin)"
echo "   Dagster:        http://localhost:3000"
echo "   MinIO Console:  http://localhost:9001 (minio/minio12345)"
echo ""
echo "📊 Available Data:"
echo "   PostgreSQL:"
echo "   - cell_towers.clean_204 (47K records)"
echo "   - crypto.trades_bronze (if materialized)"
echo "   - crypto.trades_1min (if materialized)"
echo ""
echo "💡 Next Steps:"
echo "   1. Materialize crypto assets:"
echo "      docker-compose exec dagster dagster asset materialize -m crypto_stream --select crypto_trades_bronze"
echo ""
echo "   2. Run this bootstrap again to sync crypto data to PostgreSQL"
echo ""
echo "   3. Create Superset dashboards:"
echo "      - Connect to PostgreSQL database"
echo "      - Query: SELECT * FROM crypto.latest_prices;"
echo ""
