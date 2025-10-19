#!/bin/bash

# Quick cleanup script - no confirmation needed
# Use this during development/testing for fast cleanup

DOCKER_CONTAINER=${DOCKER_CONTAINER:-dp_postgres}
DB_NAME=${POSTGRES_DB:-superset}
DB_USER=${POSTGRES_USER:-superset}

echo "🧹 Quick cleanup (no confirmation)..."

# Delete all data
docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
DELETE FROM canonical.canonical_communication;
DELETE FROM canonical.canonical_transaction;
DELETE FROM raw_messages;
DELETE FROM raw_calls;
DELETE FROM raw_transactions;
DELETE FROM data_sources;
DELETE FROM investigations;
"

# Verify cleanup
echo ""
echo "Verification:"
docker exec $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME -c "
SELECT 
    'investigations' as table_name, COUNT(*) as remaining FROM investigations
UNION ALL
SELECT 'data_sources', COUNT(*) FROM data_sources
UNION ALL
SELECT 'raw_transactions', COUNT(*) FROM raw_transactions
UNION ALL
SELECT 'raw_calls', COUNT(*) FROM raw_calls
UNION ALL
SELECT 'raw_messages', COUNT(*) FROM raw_messages
UNION ALL
SELECT 'canonical_transaction', COUNT(*) FROM canonical.canonical_transaction
UNION ALL
SELECT 'canonical_communication', COUNT(*) FROM canonical.canonical_communication
ORDER BY table_name;
"

echo "✅ Quick cleanup done!"
