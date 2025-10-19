#!/bin/bash

# Platform Cleanup Script
# This script removes ALL test data from the platform to prepare for a clean demo
# Use this before starting a fresh demonstration
#
# Usage:
#   ./cleanup_platform.sh         - Interactive mode (requires confirmation)
#   ./cleanup_platform.sh --force - Skip confirmation prompt

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

# Check for --force flag
if [ "$1" = "--force" ]; then
    echo "🚀 Force mode enabled - skipping confirmation"
    CONFIRM="DELETE ALL"
else
    read -p "Are you sure you want to continue? Type 'DELETE ALL' to confirm: " CONFIRM
fi

if [ "$CONFIRM" != "DELETE ALL" ]; then
    echo "Operation cancelled. You typed: '$CONFIRM'"
    echo "Expected: 'DELETE ALL' (case sensitive)"
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
echo "[1/6] Checking current data counts..."
BEFORE_COUNTS=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -F'|' -c "
SELECT 
    (SELECT COUNT(*) FROM investigations),
    (SELECT COUNT(*) FROM data_sources),
    (SELECT COUNT(*) FROM processed_records),
    (SELECT COUNT(*) FROM raw_transactions),
    (SELECT COUNT(*) FROM raw_calls),
    (SELECT COUNT(*) FROM raw_messages),
    (SELECT COUNT(*) FROM canonical.canonical_transaction),
    (SELECT COUNT(*) FROM canonical.canonical_communication);
")

# Parse counts using IFS
IFS='|' read -r INV_COUNT DS_COUNT PR_COUNT RAW_TX_COUNT RAW_CALL_COUNT RAW_MSG_COUNT CAN_TX_COUNT CAN_COMM_COUNT <<< "$BEFORE_COUNTS"

echo "Current data:"
echo "  - Investigations: $INV_COUNT"
echo "  - Data sources: $DS_COUNT"
echo "  - Processed records: $PR_COUNT"
echo "  - Raw transactions: $RAW_TX_COUNT"
echo "  - Raw calls: $RAW_CALL_COUNT"
echo "  - Raw messages: $RAW_MSG_COUNT"
echo "  - Canonical transactions: $CAN_TX_COUNT"
echo "  - Canonical communications: $CAN_COMM_COUNT"
echo ""

# Step 2: Delete in correct order (using TRUNCATE CASCADE for efficiency)
echo "[2/6] Deleting all data (using TRUNCATE CASCADE)..."

docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
-- Disable triggers temporarily for faster deletion
SET session_replication_role = 'replica';

-- Truncate all tables with CASCADE to ignore FK constraints
TRUNCATE TABLE canonical.canonical_transaction, 
                canonical.canonical_communication,
                raw_transactions,
                raw_calls,
                raw_messages,
                processed_records,
                data_sources,
                investigations
CASCADE;

-- Re-enable triggers
SET session_replication_role = 'origin';
"

echo "✓ All data deleted successfully"
echo ""

# Step 3: Clean MinIO investigations bucket
echo "[3/6] Cleaning MinIO investigations bucket..."
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

# Step 4: Verify cleanup
echo "[4/6] Verifying cleanup..."
AFTER_COUNTS=$(docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -t -A -F'|' -c "
SELECT 
    (SELECT COUNT(*) FROM investigations),
    (SELECT COUNT(*) FROM data_sources),
    (SELECT COUNT(*) FROM processed_records),
    (SELECT COUNT(*) FROM raw_transactions),
    (SELECT COUNT(*) FROM raw_calls),
    (SELECT COUNT(*) FROM raw_messages),
    (SELECT COUNT(*) FROM canonical.canonical_transaction),
    (SELECT COUNT(*) FROM canonical.canonical_communication);
")

# Parse after counts
IFS='|' read -r AFTER_INV AFTER_DS AFTER_PR AFTER_RAW_TX AFTER_RAW_CALL AFTER_RAW_MSG AFTER_CAN_TX AFTER_CAN_COMM <<< "$AFTER_COUNTS"

# Calculate total remaining
TOTAL_REMAINING=$((AFTER_INV + AFTER_DS + AFTER_PR + AFTER_RAW_TX + AFTER_RAW_CALL + AFTER_RAW_MSG + AFTER_CAN_TX + AFTER_CAN_COMM))

if [ "$TOTAL_REMAINING" = "0" ]; then
    echo "✓ All data successfully removed"
    echo ""
    echo "=========================================="
    echo "Cleanup Summary"
    echo "=========================================="
    echo "Database cleanup:"
    echo "  - Investigations: $INV_COUNT → 0"
    echo "  - Data sources: $DS_COUNT → 0"
    echo "  - Processed records: $PR_COUNT → 0"
    echo "  - Raw transactions: $RAW_TX_COUNT → 0"
    echo "  - Raw calls: $RAW_CALL_COUNT → 0"
    echo "  - Raw messages: $RAW_MSG_COUNT → 0"
    echo "  - Canonical transactions: $CAN_TX_COUNT → 0"
    echo "  - Canonical communications: $CAN_COMM_COUNT → 0"
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
    echo "  - Investigations: $AFTER_INV"
    echo "  - Data sources: $AFTER_DS"
    echo "  - Processed records: $AFTER_PR"
    echo "  - Raw transactions: $AFTER_RAW_TX"
    echo "  - Raw calls: $AFTER_RAW_CALL"
    echo "  - Raw messages: $AFTER_RAW_MSG"
    echo "  - Canonical transactions: $AFTER_CAN_TX"
    echo "  - Canonical communications: $AFTER_CAN_COMM"
    echo ""
    echo "Manual cleanup may be required."
    exit 1
fi
