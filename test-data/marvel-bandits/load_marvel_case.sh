#!/bin/bash

# Marvel Bandits Test Case - Data Load Script
# This script loads all test data for the Marvel Bandits investigation case
# Investigation ID: OND-2025-MARVEL
# Multiple sources: 4 banks (ABN AMRO, Rabobank, ING, ABN AMRO branch) + 3 telecom providers (KPN, Vodafone, T-Mobile)

set -e  # Exit on error

echo "=========================================="
echo "Marvel Bandits Test Case - Load Data"
echo "Investigation: OND-2025-MARVEL"
echo "=========================================="
echo ""

# Configuration
DB_NAME=${POSTGRES_DB:-superset}
DB_USER=${POSTGRES_USER:-superset}
DOCKER_CONTAINER=${DOCKER_CONTAINER:-dp_postgres}

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "Database: $DB_NAME (via docker: $DOCKER_CONTAINER)"
echo "User: $DB_USER"
echo ""

# Step 1: Create investigation record
echo "[1/8] Creating investigation record..."
docker exec -i $DOCKER_CONTAINER psql -U $DB_USER -d $DB_NAME <<EOF
INSERT INTO investigations (
    investigation_id, 
    case_name, 
    status, 
    start_date, 
    description,
    lead_investigator
) VALUES (
    'OND-2025-MARVEL',
    'Marvel Bandits Money Laundering',
    'active',
    '2024-06-01',
    'International money laundering operation involving cryptocurrency and offshore accounts. Four suspects coordinating financial crimes across multiple jurisdictions. Data from 4 banks and 3 telecom providers.',
    'Det. Inspector J. Smith'
) ON CONFLICT (investigation_id) DO NOTHING;
EOF
echo "✓ Investigation record created"
echo ""

# Step 2: Load bank transactions from Bank A (ABN AMRO - Tony Stark)
echo "[2/8] Loading Bank A transactions (ABN AMRO - 17 records)..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- Bank A: ABN AMRO format (Tony Stark's main account)
\\COPY raw_transactions (transaction_id, datum, bedrag, valuta, iban_from, iban, omschrijving, categorie, investigation_id, source_id) FROM '$SCRIPT_DIR/bank_a_transactions.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

-- Update raw_data JSONB field for Bank A
UPDATE raw_transactions 
SET raw_data = jsonb_build_object(
    'transaction_id', transaction_id,
    'datum', datum::text,
    'bedrag', bedrag,
    'valuta', valuta,
    'iban_from', iban_from,
    'iban', iban,
    'omschrijving', omschrijving,
    'categorie', categorie,
    'timestamp', timestamp::text,
    'source', 'bank_a',
    'bank_name', 'ABN AMRO'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'bank_a'
AND raw_data IS NULL;
EOF
echo "✓ Bank A (ABN AMRO) transactions loaded"
echo ""

# Step 3: Load bank transactions from Bank B (Rabobank - Peter Parker)
echo "[3/8] Loading Bank B transactions (Rabobank - 12 records)..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- Bank B: Rabobank format (different column names)
CREATE TEMP TABLE temp_bank_b (
    trx_id TEXT,
    date DATE,
    amount DECIMAL(15,2),
    currency TEXT,
    from_account TEXT,
    to_account TEXT,
    description TEXT,
    transaction_type TEXT,
    created_at TIMESTAMP
);

\\COPY temp_bank_b FROM '$SCRIPT_DIR/bank_b_transactions.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_transactions (
    transaction_id, datum, bedrag, valuta, iban_from, iban, 
    omschrijving, categorie, investigation_id, source_id, timestamp
)
SELECT 
    trx_id,
    date,
    amount,
    currency,
    from_account,
    to_account,
    description,
    transaction_type,
    'OND-2025-MARVEL',
    'bank_b',
    created_at
FROM temp_bank_b;

-- Update raw_data JSONB field for Bank B
UPDATE raw_transactions 
SET raw_data = jsonb_build_object(
    'trx_id', transaction_id,
    'date', datum::text,
    'amount', bedrag,
    'currency', valuta,
    'from_account', iban_from,
    'to_account', iban,
    'description', omschrijving,
    'transaction_type', categorie,
    'created_at', timestamp::text,
    'source', 'bank_b',
    'bank_name', 'Rabobank'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'bank_b'
AND raw_data IS NULL;

DROP TABLE temp_bank_b;
EOF
echo "✓ Bank B (Rabobank) transactions loaded"
echo ""

# Step 4: Load bank transactions from Bank C (ING - Natasha Romanoff)
echo "[4/8] Loading Bank C transactions (ING - 14 records)..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- Bank C: ING format (different column names)
CREATE TEMP TABLE temp_bank_c (
    id TEXT,
    transaction_date DATE,
    value DECIMAL(15,2),
    ccy TEXT,
    source_iban TEXT,
    dest_iban TEXT,
    narrative TEXT,
    category TEXT,
    timestamp TIMESTAMP
);

\\COPY temp_bank_c FROM '$SCRIPT_DIR/bank_c_transactions.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_transactions (
    transaction_id, datum, bedrag, valuta, iban_from, iban, 
    omschrijving, categorie, investigation_id, source_id, timestamp
)
SELECT 
    id,
    transaction_date,
    value,
    ccy,
    source_iban,
    dest_iban,
    narrative,
    category,
    'OND-2025-MARVEL',
    'bank_c',
    timestamp
FROM temp_bank_c;

-- Update raw_data JSONB field for Bank C
UPDATE raw_transactions 
SET raw_data = jsonb_build_object(
    'id', transaction_id,
    'transaction_date', datum::text,
    'value', bedrag,
    'ccy', valuta,
    'source_iban', iban_from,
    'dest_iban', iban,
    'narrative', omschrijving,
    'category', categorie,
    'timestamp', timestamp::text,
    'source', 'bank_c',
    'bank_name', 'ING'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'bank_c'
AND raw_data IS NULL;

DROP TABLE temp_bank_c;
EOF
echo "✓ Bank C (ING) transactions loaded"
echo ""

# Step 5: Load bank transactions from Bank D (ABN AMRO branch - Bruce Banner)
echo "[5/8] Loading Bank D transactions (ABN AMRO branch - 8 records)..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- Bank D: ABN AMRO branch format (different column names)
CREATE TEMP TABLE temp_bank_d (
    trans_ref TEXT,
    trans_date DATE,
    trans_amount DECIMAL(15,2),
    trans_currency TEXT,
    debit_account TEXT,
    credit_account TEXT,
    trans_description TEXT,
    trans_type TEXT,
    process_time TIMESTAMP
);

\\COPY temp_bank_d FROM '$SCRIPT_DIR/bank_d_transactions.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_transactions (
    transaction_id, datum, bedrag, valuta, iban_from, iban, 
    omschrijving, categorie, investigation_id, source_id, timestamp
)
SELECT 
    trans_ref,
    trans_date,
    trans_amount,
    trans_currency,
    debit_account,
    credit_account,
    trans_description,
    trans_type,
    'OND-2025-MARVEL',
    'bank_d',
    process_time
FROM temp_bank_d;

-- Update raw_data JSONB field for Bank D
UPDATE raw_transactions 
SET raw_data = jsonb_build_object(
    'trans_ref', transaction_id,
    'trans_date', datum::text,
    'trans_amount', bedrag,
    'trans_currency', valuta,
    'debit_account', iban_from,
    'credit_account', iban,
    'trans_description', omschrijving,
    'trans_type', categorie,
    'process_time', timestamp::text,
    'source', 'bank_d',
    'bank_name', 'ABN AMRO Branch'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'bank_d'
AND raw_data IS NULL;

DROP TABLE temp_bank_d;
EOF
echo "✓ Bank D (ABN AMRO branch) transactions loaded"
echo ""

# Step 6: Load telecom calls from 3 providers
echo "[6/8] Loading telecom calls from 3 providers (50 records)..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- Telecom A: KPN format
\\COPY raw_calls (call_id, call_date, call_time, caller, callee, duration, investigation_id, source_id) FROM '$SCRIPT_DIR/telecom_a_calls.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

UPDATE raw_calls 
SET raw_data = jsonb_build_object(
    'call_id', call_id,
    'call_date', call_date::text,
    'call_time', call_time::text,
    'caller', caller,
    'callee', callee,
    'duration', duration,
    'source', 'telecom_a',
    'provider', 'KPN'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'telecom_a'
AND raw_data IS NULL;

-- Telecom B: Vodafone format (different column names)
CREATE TEMP TABLE temp_telecom_b (
    cdr_id TEXT,
    date DATE,
    time TIME,
    caller_number TEXT,
    callee_number TEXT,
    call_duration INTEGER,
    location_id TEXT
);

\\COPY temp_telecom_b FROM '$SCRIPT_DIR/telecom_b_calls.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_calls (
    call_id, call_date, call_time, caller, callee, 
    duration, investigation_id, source_id
)
SELECT 
    cdr_id,
    date,
    time,
    caller_number,
    callee_number,
    call_duration,
    'OND-2025-MARVEL',
    'telecom_b'
FROM temp_telecom_b;

UPDATE raw_calls 
SET raw_data = jsonb_build_object(
    'cdr_id', call_id,
    'date', call_date::text,
    'time', call_time::text,
    'caller_number', caller,
    'callee_number', callee,
    'call_duration', duration,
    'location_id', NULL,
    'source', 'telecom_b',
    'provider', 'Vodafone'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'telecom_b'
AND raw_data IS NULL;

DROP TABLE temp_telecom_b;

-- Telecom C: T-Mobile format (different column names)
CREATE TEMP TABLE temp_telecom_c (
    record_id TEXT,
    event_date DATE,
    event_time TIME,
    origin TEXT,
    destination TEXT,
    duration_sec INTEGER,
    tower_ref TEXT
);

\\COPY temp_telecom_c FROM '$SCRIPT_DIR/telecom_c_calls.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_calls (
    call_id, call_date, call_time, caller, callee, 
    duration, investigation_id, source_id
)
SELECT 
    record_id,
    event_date,
    event_time,
    origin,
    destination,
    duration_sec,
    'OND-2025-MARVEL',
    'telecom_c'
FROM temp_telecom_c;

UPDATE raw_calls 
SET raw_data = jsonb_build_object(
    'record_id', call_id,
    'event_date', call_date::text,
    'event_time', call_time::text,
    'origin', caller,
    'destination', callee,
    'duration_sec', duration,
    'tower_ref', NULL,
    'source', 'telecom_c',
    'provider', 'T-Mobile'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'telecom_c'
AND raw_data IS NULL;

DROP TABLE temp_telecom_c;
EOF
echo "✓ Telecom calls loaded from 3 providers (KPN, Vodafone, T-Mobile)"
echo ""

# Step 7: Load SMS messages from 3 providers
echo "[7/8] Loading SMS messages from 3 providers (30 records)..."
PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME <<EOF
-- Telecom A: KPN SMS format
\\COPY raw_messages (message_id, message_date, message_time, sender, receiver, content, investigation_id, source_id) FROM '$SCRIPT_DIR/telecom_a_messages.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

UPDATE raw_messages 
SET raw_data = jsonb_build_object(
    'message_id', message_id,
    'message_date', message_date::text,
    'message_time', message_time::text,
    'sender', sender,
    'receiver', receiver,
    'content', content,
    'source', 'telecom_a',
    'provider', 'KPN'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'telecom_a'
AND raw_data IS NULL;

-- Telecom B: Vodafone SMS format (different column names)
CREATE TEMP TABLE temp_sms_b (
    sms_id TEXT,
    sms_date DATE,
    sms_time TIME,
    sender TEXT,
    receiver TEXT,
    text_content TEXT
);

\\COPY temp_sms_b FROM '$SCRIPT_DIR/telecom_b_messages.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_messages (
    message_id, message_date, message_time, sender, receiver, 
    content, investigation_id, source_id
)
SELECT 
    sms_id,
    sms_date,
    sms_time,
    sender,
    receiver,
    text_content,
    'OND-2025-MARVEL',
    'telecom_b'
FROM temp_sms_b;

UPDATE raw_messages 
SET raw_data = jsonb_build_object(
    'sms_id', message_id,
    'sms_date', message_date::text,
    'sms_time', message_time::text,
    'sender', sender,
    'receiver', receiver,
    'text_content', content,
    'source', 'telecom_b',
    'provider', 'Vodafone'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'telecom_b'
AND raw_data IS NULL;

DROP TABLE temp_sms_b;

-- Telecom C: T-Mobile SMS format (different column names)
CREATE TEMP TABLE temp_sms_c (
    msg_ref TEXT,
    msg_date DATE,
    msg_time TIME,
    origin_msisdn TEXT,
    dest_msisdn TEXT,
    message_body TEXT
);

\\COPY temp_sms_c FROM '$SCRIPT_DIR/telecom_c_messages.csv' WITH (FORMAT CSV, HEADER true, DELIMITER ',');

INSERT INTO raw_messages (
    message_id, message_date, message_time, sender, receiver, 
    content, investigation_id, source_id
)
SELECT 
    msg_ref,
    msg_date,
    msg_time,
    origin_msisdn,
    dest_msisdn,
    message_body,
    'OND-2025-MARVEL',
    'telecom_c'
FROM temp_sms_c;

UPDATE raw_messages 
SET raw_data = jsonb_build_object(
    'msg_ref', message_id,
    'msg_date', message_date::text,
    'msg_time', message_time::text,
    'origin_msisdn', sender,
    'dest_msisdn', receiver,
    'message_body', content,
    'source', 'telecom_c',
    'provider', 'T-Mobile'
)
WHERE investigation_id = 'OND-2025-MARVEL' 
AND source_id = 'telecom_c'
AND raw_data IS NULL;

DROP TABLE temp_sms_c;
EOF
echo "✓ SMS messages loaded from 3 providers (KPN, Vodafone, T-Mobile)"
echo ""

# Step 8: Verify data counts
echo "[8/8] Verifying data counts..."
COUNTS=$(PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -t <<EOF
SELECT 
    (SELECT COUNT(*) FROM raw_transactions WHERE investigation_id = 'OND-2025-MARVEL') as transactions,
    (SELECT COUNT(*) FROM raw_calls WHERE investigation_id = 'OND-2025-MARVEL') as calls,
    (SELECT COUNT(*) FROM raw_messages WHERE investigation_id = 'OND-2025-MARVEL') as messages,
    (SELECT COUNT(DISTINCT source_id) FROM raw_transactions WHERE investigation_id = 'OND-2025-MARVEL') as bank_sources,
    (SELECT COUNT(DISTINCT source_id) FROM raw_calls WHERE investigation_id = 'OND-2025-MARVEL') as telecom_sources;
EOF
)

echo ""
echo "=========================================="
echo "Load Summary"
echo "=========================================="
echo "Raw Data Loaded:"
echo "  - Transactions: $(echo $COUNTS | awk '{print $1}') (from $(echo $COUNTS | awk '{print $7}') banks)"
echo "    • Bank A (ABN AMRO): 17 records"
echo "    • Bank B (Rabobank): 12 records"
echo "    • Bank C (ING): 14 records"
echo "    • Bank D (ABN AMRO branch): 8 records"
echo ""
echo "  - Calls: $(echo $COUNTS | awk '{print $3}') (from $(echo $COUNTS | awk '{print $9}') providers)"
echo "    • Telecom A (KPN): 17 records"
echo "    • Telecom B (Vodafone): 15 records"
echo "    • Telecom C (T-Mobile): 18 records"
echo ""
echo "  - Messages: $(echo $COUNTS | awk '{print $5}')"
echo "    • Telecom A (KPN): 10 SMS"
echo "    • Telecom B (Vodafone): 10 SMS"
echo "    • Telecom C (T-Mobile): 10 SMS"
echo ""
echo "Total: 131 raw records from 7 different sources"
echo ""
echo "✓ Investigation: OND-2025-MARVEL created"
echo "✓ Multi-source data integration successful"
echo ""
echo "=========================================="
echo "Next Steps"
echo "=========================================="
echo "1. Run Dagster assets to map to canonical schema:"
echo "   - canonical_transactions"
echo "   - canonical_communications"
echo ""
echo "2. View data in dbt documentation:"
echo "   http://localhost:8011"
echo ""
echo "3. Check Marquez lineage:"
echo "   http://localhost:3001"
echo ""
echo "4. Documents available at:"
echo "   $SCRIPT_DIR/documents/"
echo "   - chat_logs.txt (encrypted messages)"
echo "   - crypto_wallets.txt (blockchain analysis)"
echo "   - meeting_notes.txt (surveillance logs)"
echo ""
echo "=========================================="
echo "Load Complete! ✓"
echo "=========================================="
