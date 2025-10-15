#!/bin/bash

# Platform Cleanup Script
# This script removes ALL test data from the platform to prepare for a clean demo
# Use this before starting a fresh demonstration

set -e  # Exit on error

echo "=========================================="
echo "Data Platform - Complete Cleanup"
echo "=========================================="
echo ""
echo "⚠️  WARNING: This will delete ALL investigation data!"
echo ""
echo "This will remove:"
echo "  - All investigations (including OND-2025-000001, 000002, 000003, MARVEL)"
echo "  - All raw data (transactions, calls, messages)"
echo "  - All canonical data (canonical_transaction, canonical_communication)"
echo "  - All MinIO files (investigations bucket)"
echo "  - All dbt staging data will be regenerated on next run"
echo ""
read -p "Are you sure you want to continue? Type 'DELETE ALL' to confirm: " CONFIRM

if [ "$CONFIRM" != "DELETE ALL" ]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""
echo "Starting cleanup..."
echo ""

# Configuration - Use Docker
DOCKER_CONTAINER=${DOCKER_CONTAINER:-dp_postgres}
DB_NAME=${POSTGRES_DB:-superset}
DB_USER=${POSTGRES_USER:-superset}

echo "Database: $DB_NAME (via docker: $DOCKER_CONTAINER)"
echo "User: $DB_USER"
echo ""

# Get counts before cleanup
echo "[1/5] Checking current data counts..."
BEFORE_COUNTS=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM investigations) as investigations,
    (SELECT COUNT(*) FROM data_sources) as data_sources,
    (SELECT COUNT(*) FROM raw_transactions) as raw_transactions,
    (SELECT COUNT(*) FROM raw_calls) as raw_calls,
    (SELECT COUNT(*) FROM raw_messages) as raw_messages,
    (SELECT COUNT(*) FROM canonical.canonical_transaction) as canonical_transactions,
    (SELECT COUNT(*) FROM canonical.canonical_communication) as canonical_communications;
EOF
)

echo "Current data:"
echo "  - Investigations: $(echo $BEFORE_COUNTS | awk '{print $1}')"
echo "  - Data sources: $(echo $BEFORE_COUNTS | awk '{print $3}')"
echo "  - Raw transactions: $(echo $BEFORE_COUNTS | awk '{print $5}')"
echo "  - Raw calls: $(echo $BEFORE_COUNTS | awk '{print $7}')"
echo "  - Raw messages: $(echo $BEFORE_COUNTS | awk '{print $9}')"
echo "  - Canonical transactions: $(echo $BEFORE_COUNTS | awk '{print $11}')"
echo "  - Canonical communications: $(echo $BEFORE_COUNTS | awk '{print $13}')"
echo ""

# Step 2: Delete canonical data
echo "[2/5] Deleting canonical data..."
docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
DELETE FROM canonical.canonical_transaction;
DELETE FROM canonical.canonical_communication;
-- canonical_person table is empty, no need to delete
-- canonical_mapping_log is disabled, no need to delete
EOF
echo "✓ Canonical data deleted"
echo ""

# Step 3: Delete raw data
echo "[3/5] Deleting raw data..."
docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
DELETE FROM raw_transactions;
DELETE FROM raw_calls;
DELETE FROM raw_messages;
EOF
echo "✓ Raw data deleted"
echo ""

# Step 4: Delete investigations (with CASCADE DELETE, this is now redundant but kept for clarity)
echo "[4/6] Deleting all investigations..."
docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
DELETE FROM investigations;
EOF
echo "✓ Investigations deleted (CASCADE DELETE removed all related data)"
echo ""

# Step 5: Clean MinIO investigations bucket
echo "[5/6] Cleaning MinIO investigations bucket..."
MINIO_FILES=$(docker exec dp_dagster python3 -c "
from minio import Minio
client = Minio('minio:9000', access_key='minio', secret_key='minio12345', secure=False)

# List all objects in investigations bucket
try:
    objects = list(client.list_objects('investigations', recursive=True))
    count = len(objects)
    
    # Delete all objects
    for obj in objects:
        client.remove_object('investigations', obj.object_name)
    
    print(f'{count}')
except Exception as e:
    if 'NoSuchBucket' in str(e):
        print('0')
    else:
        print(f'Error: {e}')
" 2>&1)

if [[ "$MINIO_FILES" =~ ^[0-9]+$ ]]; then
    echo "✓ Deleted $MINIO_FILES files from MinIO investigations bucket"
else
    echo "⚠️  MinIO cleanup: $MINIO_FILES"
fi
echo ""

# Step 6: Verify cleanup
echo "[6/6] Verifying cleanup..."
AFTER_COUNTS=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM investigations) as investigations,
    (SELECT COUNT(*) FROM data_sources) as data_sources,
    (SELECT COUNT(*) FROM raw_transactions) as raw_transactions,
    (SELECT COUNT(*) FROM raw_calls) as raw_calls,
    (SELECT COUNT(*) FROM raw_messages) as raw_messages,
    (SELECT COUNT(*) FROM canonical.canonical_transaction) as canonical_transactions,
    (SELECT COUNT(*) FROM canonical.canonical_communication) as canonical_communications;
EOF
)

TOTAL_REMAINING=$(echo $AFTER_COUNTS | awk '{print $1 + $3 + $5 + $7 + $9 + $11 + $13}')

if [ "$TOTAL_REMAINING" = "0" ]; then
    echo "✓ All data successfully removed"
    echo ""
    echo "=========================================="
    echo "Cleanup Summary"
    echo "=========================================="
    echo "Database cleanup:"
    echo "  - Investigations: $(echo $BEFORE_COUNTS | awk '{print $1}') → 0"
    echo "  - Data sources: $(echo $BEFORE_COUNTS | awk '{print $3}') → 0"
    echo "  - Raw transactions: $(echo $BEFORE_COUNTS | awk '{print $5}') → 0"
    echo "  - Raw calls: $(echo $BEFORE_COUNTS | awk '{print $7}') → 0"
    echo "  - Raw messages: $(echo $BEFORE_COUNTS | awk '{print $9}') → 0"
    echo "  - Canonical transactions: $(echo $BEFORE_COUNTS | awk '{print $11}') → 0"
    echo "  - Canonical communications: $(echo $BEFORE_COUNTS | awk '{print $13}') → 0"
    echo ""
    echo "MinIO cleanup:"
    if [[ "$MINIO_FILES" =~ ^[0-9]+$ ]]; then
        echo "  - Files deleted: $MINIO_FILES"
    else
        echo "  - Status: Check logs above"
    fi
    echo ""
    echo "✅ Platform is now clean and ready for demo!"
    echo ""
    echo "=========================================="
    echo "Next Steps for Demo"
    echo "=========================================="
    echo "1. Verify clean state:"
    echo "   cd test-data/marvel-bandits"
    echo "   ./verify_marvel_case.sh  (should show 0 records)"
    echo ""
    echo "2. Start demo with fresh load:"
    echo "   Option A - Direct upload:"
    echo "     ./load_marvel_case.sh"
    echo ""
    echo "   Option B - GCS bucket ingestion (automatic):"
    echo "     Upload files to gs://public_data_demo/investigations/{ID}/{type}/"
    echo "     Files are auto-ingested within 60 seconds"
    echo ""
    echo "3. Show Dagster UI (empty state):"
    echo "   http://localhost:3000"
    echo ""
    echo "4. Materialize assets live during demo"
    echo ""
    echo "5. Show Marquez lineage (will populate after materialization):"
    echo "   http://localhost:3001"
    echo ""
    echo "6. Show dbt docs (data model structure):"
    echo "   http://localhost:8011"
    echo ""
    echo "=========================================="
    echo "Cleanup Complete! ✓"
    echo "=========================================="
else
    echo "⚠️  WARNING: $TOTAL_REMAINING records still remain"
    echo "Current state:"
    echo "  - Investigations: $(echo $AFTER_COUNTS | awk '{print $1}')"
    echo "  - Data sources: $(echo $AFTER_COUNTS | awk '{print $3}')"
    echo "  - Raw transactions: $(echo $AFTER_COUNTS | awk '{print $5}')"
    echo "  - Raw calls: $(echo $AFTER_COUNTS | awk '{print $7}')"
    echo "  - Raw messages: $(echo $AFTER_COUNTS | awk '{print $9}')"
    echo "  - Canonical transactions: $(echo $AFTER_COUNTS | awk '{print $11}')"
    echo "  - Canonical communications: $(echo $AFTER_COUNTS | awk '{print $13}')"
    echo ""
    echo "Manual cleanup may be required."
    exit 1
fi
