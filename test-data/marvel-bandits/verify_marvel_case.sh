#!/bin/bash

# Marvel Bandits Test Case - Verify Data Script
# This script verifies data counts and quality for the Marvel Bandits investigation
# Investigation ID: OND-2025-MARVEL

# Configuration
DB_HOST=${POSTGRES_HOST:-localhost}
DB_PORT=${POSTGRES_PORT:-5432}
DB_NAME=${POSTGRES_DB:-superset}
DB_USER=${POSTGRES_USER:-superset}
DB_PASSWORD=${POSTGRES_PASSWORD:-superset}

echo "=========================================="
echo "Marvel Bandits Test Case - Verify Data"
echo "Investigation: OND-2025-MARVEL"
echo "=========================================="
echo ""
echo "Database: $DB_NAME@$DB_HOST:$DB_PORT"
echo ""

# Check if investigation exists
INV_EXISTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t -c \
    "SELECT COUNT(*) FROM investigations WHERE investigation_id = 'OND-2025-MARVEL';")

INV_EXISTS=$(echo $INV_EXISTS | xargs)  # Trim whitespace

if [ "$INV_EXISTS" = "0" ]; then
    echo "❌ Investigation OND-2025-MARVEL not found"
    echo ""
    echo "Run: ./load_marvel_case.sh to load test data"
    echo ""
    exit 1
fi

echo "✓ Investigation found"
echo ""

# Raw Data Counts
echo "=========================================="
echo "RAW DATA LAYER"
echo "=========================================="

RAW_DATA=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    'Transactions' as type,
    COUNT(*) as count,
    MIN(datum) as first_date,
    MAX(datum) as last_date
FROM raw_transactions 
WHERE investigation_id = 'OND-2025-MARVEL'
UNION ALL
SELECT 
    'Calls' as type,
    COUNT(*) as count,
    MIN(call_date) as first_date,
    MAX(call_date) as last_date
FROM raw_calls 
WHERE investigation_id = 'OND-2025-MARVEL'
UNION ALL
SELECT 
    'Messages' as type,
    COUNT(*) as count,
    MIN(message_date) as first_date,
    MAX(message_date) as last_date
FROM raw_messages 
WHERE investigation_id = 'OND-2025-MARVEL';
EOF
)

echo "$RAW_DATA" | while IFS='|' read -r type count first last; do
    type=$(echo $type | xargs)
    count=$(echo $count | xargs)
    first=$(echo $first | xargs)
    last=$(echo $last | xargs)
    echo "$type: $count records ($first to $last)"
done

# Get total raw
TOTAL_RAW=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM raw_transactions WHERE investigation_id = 'OND-2025-MARVEL') +
    (SELECT COUNT(*) FROM raw_calls WHERE investigation_id = 'OND-2025-MARVEL') +
    (SELECT COUNT(*) FROM raw_messages WHERE investigation_id = 'OND-2025-MARVEL') as total;
EOF
)
TOTAL_RAW=$(echo $TOTAL_RAW | xargs)

echo ""
echo "Total Raw Records: $TOTAL_RAW"
echo ""

# Canonical Data Counts
echo "=========================================="
echo "CANONICAL LAYER"
echo "=========================================="

CANONICAL_EXISTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT EXISTS (
    SELECT FROM information_schema.tables 
    WHERE table_schema = 'canonical' 
    AND table_name IN ('canonical_transaction', 'canonical_communication')
);
EOF
)

CANONICAL_EXISTS=$(echo $CANONICAL_EXISTS | xargs)

if [ "$CANONICAL_EXISTS" = "t" ]; then
    CANONICAL_DATA=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
    SELECT 
        'Transactions' as type,
        COUNT(*) as count,
        COUNT(*) FILTER (WHERE validation_status = 'valid') as valid,
        COUNT(*) FILTER (WHERE validation_status = 'warning') as warning,
        COUNT(*) FILTER (WHERE validation_status = 'error') as error
    FROM canonical.canonical_transaction 
    WHERE investigation_id = 'OND-2025-MARVEL'
    UNION ALL
    SELECT 
        'Communications' as type,
        COUNT(*) as count,
        COUNT(*) FILTER (WHERE validation_status = 'valid') as valid,
        COUNT(*) FILTER (WHERE validation_status = 'warning') as warning,
        COUNT(*) FILTER (WHERE validation_status = 'error') as error
    FROM canonical.canonical_communication 
    WHERE investigation_id = 'OND-2025-MARVEL';
EOF
    )

    echo "$CANONICAL_DATA" | while IFS='|' read -r type count valid warning error; do
        type=$(echo $type | xargs)
        count=$(echo $count | xargs)
        valid=$(echo $valid | xargs)
        warning=$(echo $warning | xargs)
        error=$(echo $error | xargs)
        
        if [ "$count" = "0" ]; then
            echo "$type: ❌ No records (run Dagster assets)"
        else
            quality=$(awk "BEGIN {printf \"%.1f\", ($valid / $count) * 100}")
            echo "$type: $count records ($valid valid, $warning warning, $error error) - Quality: ${quality}%"
        fi
    done

    # Get total canonical
    TOTAL_CANONICAL=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
    SELECT 
        (SELECT COUNT(*) FROM canonical.canonical_transaction WHERE investigation_id = 'OND-2025-MARVEL') +
        (SELECT COUNT(*) FROM canonical.canonical_communication WHERE investigation_id = 'OND-2025-MARVEL') as total;
EOF
    )
    TOTAL_CANONICAL=$(echo $TOTAL_CANONICAL | xargs)

    echo ""
    echo "Total Canonical Records: $TOTAL_CANONICAL"
else
    echo "❌ Canonical schema not found"
    TOTAL_CANONICAL=0
fi

echo ""

# Suspects Analysis
echo "=========================================="
echo "SUSPECT ANALYSIS"
echo "=========================================="

if [ "$CANONICAL_EXISTS" = "t" ]; then
    SUSPECT_DATA=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
    -- Transaction activity per suspect
    SELECT 
        CASE iban
            WHEN 'NL91ABNA0417164300' THEN 'Tony Stark'
            WHEN 'NL20RABO0123456789' THEN 'Peter Parker'
            WHEN 'NL69INGB0123456789' THEN 'Natasha Romanoff'
            WHEN 'NL43ABNA0123456789' THEN 'Bruce Banner'
            ELSE 'Other'
        END as suspect,
        COUNT(*) as transactions,
        SUM(amount) FILTER (WHERE amount IS NOT NULL) as total_amount,
        COUNT(*) FILTER (WHERE amount IS NULL) as atm_withdrawals
    FROM canonical.canonical_transaction
    WHERE investigation_id = 'OND-2025-MARVEL'
    GROUP BY iban
    ORDER BY total_amount DESC NULLS LAST;
    
    -- Communication activity per suspect
    SELECT 
        CASE person_phone
            WHEN '+31612345001' THEN 'Tony Stark'
            WHEN '+31612345002' THEN 'Peter Parker'
            WHEN '+31612345003' THEN 'Natasha Romanoff'
            WHEN '+31612345004' THEN 'Bruce Banner'
            ELSE 'Other'
        END as suspect,
        communication_type,
        COUNT(*) as count
    FROM canonical.canonical_communication
    WHERE investigation_id = 'OND-2025-MARVEL'
    GROUP BY person_phone, communication_type
    ORDER BY suspect, communication_type;
EOF
    )
    echo "$SUSPECT_DATA"
fi

echo ""

# Summary and Recommendations
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo "✓ Investigation: OND-2025-MARVEL"
echo "✓ Raw Data: $TOTAL_RAW records"
echo "✓ Canonical Data: $TOTAL_CANONICAL records"
echo ""

if [ "$TOTAL_CANONICAL" = "0" ]; then
    echo "⚠️  NEXT STEPS:"
    echo "1. Navigate to Dagster UI: http://localhost:3000"
    echo "2. Materialize assets:"
    echo "   - canonical_transactions"
    echo "   - canonical_communications"
    echo "3. Re-run this verification script"
    echo ""
elif [ "$TOTAL_CANONICAL" -lt "$TOTAL_RAW" ]; then
    MAPPING_RATE=$(awk "BEGIN {printf \"%.1f\", ($TOTAL_CANONICAL / $TOTAL_RAW) * 100}")
    echo "⚠️  Mapping Rate: ${MAPPING_RATE}%"
    echo "   Expected: ~130 canonical records from $TOTAL_RAW raw records"
    echo ""
    echo "NEXT STEPS:"
    echo "1. Check Dagster logs for mapping errors"
    echo "2. Verify validation rules in canonical_assets.py"
    echo ""
else
    echo "✅ Data mapping complete!"
    echo ""
    echo "EXPLORE THE DATA:"
    echo "1. Marquez Lineage: http://localhost:3001"
    echo "2. dbt Documentation: http://localhost:8011"
    echo "3. Dashboard: http://localhost:8080/dashboard.html"
    echo ""
fi

echo "DOCUMENTS AVAILABLE:"
echo "- Chat logs: test-data/marvel-bandits/documents/chat_logs.txt"
echo "- Crypto wallets: test-data/marvel-bandits/documents/crypto_wallets.txt"
echo "- Meeting notes: test-data/marvel-bandits/documents/meeting_notes.txt"
echo ""
echo "=========================================="
