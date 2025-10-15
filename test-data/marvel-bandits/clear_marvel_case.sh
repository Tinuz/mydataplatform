#!/bin/bash

# Marvel Bandits Test Case - Clear Data Script
# This script removes all test data for the Marvel Bandits investigation case
# Investigation ID: OND-2025-MARVEL

set -e  # Exit on error

echo "=========================================="
echo "Marvel Bandits Test Case - Clear Data"
echo "Investigation: OND-2025-MARVEL"
echo "=========================================="
echo ""
echo "⚠️  WARNING: This will delete ALL data for investigation OND-2025-MARVEL"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Operation cancelled."
    exit 0
fi

echo ""

# Configuration
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-superset}
DB_USER=${POSTGRES_USER:-superset}
DB_PASSWORD=${POSTGRES_PASSWORD:-superset}

echo "Database: $DB_NAME@$DB_HOST:$DB_PORT"
echo "User: $DB_USER"
echo ""

# Step 1: Delete from canonical tables
echo "[1/4] Deleting from canonical tables..."
CANONICAL_COUNTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM canonical.canonical_transaction WHERE investigation_id = 'OND-2025-MARVEL') as transactions,
    (SELECT COUNT(*) FROM canonical.canonical_communication WHERE investigation_id = 'OND-2025-MARVEL') as communications;
EOF
)

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
DELETE FROM canonical.canonical_transaction WHERE investigation_id = 'OND-2025-MARVEL';
DELETE FROM canonical.canonical_communication WHERE investigation_id = 'OND-2025-MARVEL';
EOF

echo "✓ Deleted $(echo $CANONICAL_COUNTS | awk '{print $1}') canonical transactions"
echo "✓ Deleted $(echo $CANONICAL_COUNTS | awk '{print $3}') canonical communications"
echo ""

# Step 2: Delete from raw tables
echo "[2/4] Deleting from raw tables..."
RAW_COUNTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM raw_transactions WHERE investigation_id = 'OND-2025-MARVEL') as transactions,
    (SELECT COUNT(*) FROM raw_calls WHERE investigation_id = 'OND-2025-MARVEL') as calls,
    (SELECT COUNT(*) FROM raw_messages WHERE investigation_id = 'OND-2025-MARVEL') as messages;
EOF
)

PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
DELETE FROM raw_transactions WHERE investigation_id = 'OND-2025-MARVEL';
DELETE FROM raw_calls WHERE investigation_id = 'OND-2025-MARVEL';
DELETE FROM raw_messages WHERE investigation_id = 'OND-2025-MARVEL';
EOF

echo "✓ Deleted $(echo $RAW_COUNTS | awk '{print $1}') raw transactions"
echo "✓ Deleted $(echo $RAW_COUNTS | awk '{print $3}') raw calls"
echo "✓ Deleted $(echo $RAW_COUNTS | awk '{print $5}') raw messages"
echo ""

# Step 3: Delete investigation record
echo "[3/4] Deleting investigation record..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
DELETE FROM investigations WHERE investigation_id = 'OND-2025-MARVEL';
EOF
echo "✓ Investigation record deleted"
echo ""

# Step 4: Verify cleanup
echo "[4/4] Verifying cleanup..."
VERIFY=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM raw_transactions WHERE investigation_id = 'OND-2025-MARVEL') +
    (SELECT COUNT(*) FROM raw_calls WHERE investigation_id = 'OND-2025-MARVEL') +
    (SELECT COUNT(*) FROM raw_messages WHERE investigation_id = 'OND-2025-MARVEL') +
    (SELECT COUNT(*) FROM canonical.canonical_transaction WHERE investigation_id = 'OND-2025-MARVEL') +
    (SELECT COUNT(*) FROM canonical.canonical_communication WHERE investigation_id = 'OND-2025-MARVEL') as total;
EOF
)

REMAINING=$(echo $VERIFY | xargs)  # Trim whitespace

if [ "$REMAINING" = "0" ]; then
    echo "✓ All data successfully removed"
    echo ""
    echo "=========================================="
    echo "Cleanup Summary"
    echo "=========================================="
    echo "✓ All canonical records deleted"
    echo "✓ All raw records deleted"
    echo "✓ Investigation record deleted"
    echo "✓ Remaining records: 0"
    echo ""
    echo "System is ready for fresh data load."
    echo "Run: ./load_marvel_case.sh"
    echo "=========================================="
    echo "Cleanup Complete! ✓"
    echo "=========================================="
else
    echo "⚠️  WARNING: $REMAINING records still remain"
    echo "Manual cleanup may be required."
    exit 1
fi
