#!/usr/bin/env python3
"""
Map ALL transactions with improved error handling
"""
import sys
sys.path.insert(0, '/opt/dagster/app')

from investigations.canonical_assets import (
    map_bank_a_to_canonical, 
    validate_canonical_transaction,
    calculate_completeness_score
)
import psycopg2
import uuid
import json

conn = psycopg2.connect(
    host='postgres',
    port=5432,
    database='superset',
    user='superset',
    password='superset'
)

cursor = conn.cursor()

# Get ALL unmapped transactions
cursor.execute("""
    SELECT r.* 
    FROM raw_transactions r
    LEFT JOIN canonical.canonical_transaction c 
        ON c.source_system_id = r.source_id 
        AND c.source_record_id = r.transaction_id::text
    WHERE c.canonical_transaction_id IS NULL
    ORDER BY r.loaded_at DESC
""")

columns = [desc[0] for desc in cursor.description]
raw_records = cursor.fetchall()

print(f"Found {len(raw_records)} unmapped transactions")

canonical_records = []
stats = {'valid': 0, 'warning': 0, 'error': 0}

for row in raw_records:
    try:
        raw_record = dict(zip(columns, row))
        canonical = map_bank_a_to_canonical(raw_record)
        
        # Validate
        validation = validate_canonical_transaction(canonical)
        canonical['validation_status'] = validation['status']
        canonical['validation_messages'] = {
            'errors': validation['errors'],
            'warnings': validation['warnings']
        } if (validation['errors'] or validation['warnings']) else None
        
        # Completeness
        required_fields = ['transaction_datetime', 'amount', 'currency_code']
        optional_fields = ['debtor_account_id', 'creditor_account_id', 'description', 
                         'reference_number', 'debtor_name', 'creditor_name']
        canonical['data_completeness_score'] = calculate_completeness_score(
            canonical, required_fields, optional_fields
        )
        
        canonical_records.append(canonical)
        stats[validation['status']] += 1
        
    except Exception as e:
        print(f"Failed to map {raw_record.get('transaction_id')}: {e}")
        stats['error'] += 1

print(f"Mapped {len(canonical_records)} transactions: {stats}")

# Separate valid/warning from errors
valid_records = [r for r in canonical_records if r.get('validation_status') in ['valid', 'warning']]
error_records = [r for r in canonical_records if r.get('validation_status') == 'error']

print(f"\nProcessing: {len(valid_records)} valid/warning, {len(error_records)} errors")

# Insert only valid/warning records
insert_sql = """
INSERT INTO canonical.canonical_transaction (
    canonical_transaction_id, source_system_id, source_record_id, source_file_name,
    investigation_id, transaction_reference, transaction_datetime, posting_date, value_date,
    amount, currency_code, debtor_account_id, debtor_account_type, debtor_name, debtor_bank_code,
    creditor_account_id, creditor_account_type, creditor_name, creditor_bank_code,
    transaction_type, payment_method, description, reference_number,
    validation_status, validation_messages, data_completeness_score,
    is_cancelled, is_reversal, source_raw_data
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
)
"""

insert_count = 0
for record in valid_records:
    try:
        cursor.execute(insert_sql, (
            str(uuid.uuid4()),
            record.get('source_system_id'),
            record.get('source_record_id'),
            record.get('source_file_name'),
            record.get('investigation_id'),
            record.get('transaction_reference'),
            record.get('transaction_datetime'),
            record.get('posting_date'),
            record.get('value_date'),
            float(record.get('amount')) if record.get('amount') else None,
            record.get('currency_code'),
            record.get('debtor_account_id'),
            record.get('debtor_account_type'),
            record.get('debtor_name'),
            record.get('debtor_bank_code'),
            record.get('creditor_account_id'),
            record.get('creditor_account_type'),
            record.get('creditor_name'),
            record.get('creditor_bank_code'),
            record.get('transaction_type'),
            record.get('payment_method'),
            record.get('description'),
            record.get('reference_number'),
            record.get('validation_status', 'valid'),
            json.dumps(record.get('validation_messages'), default=str) if record.get('validation_messages') else None,
            record.get('data_completeness_score', 0),
            record.get('is_cancelled', False),
            record.get('is_reversal', False),
            json.dumps(record.get('source_raw_data'), default=str)
        ))
        insert_count += 1
    except Exception as e:
        print(f"Insert failed: {e}")
        conn.rollback()
        cursor.close()
        cursor = conn.cursor()  # Get new cursor after rollback

conn.commit()
print(f"\n✅ Inserted {insert_count} valid/warning records")

# Show error records
if error_records:
    print(f"\n⚠️  {len(error_records)} records rejected:")
    for i, record in enumerate(error_records[:5]):
        errors = record.get('validation_messages', {}).get('errors', [])
        print(f"  {i+1}. Investigation: {record.get('investigation_id')}, "
              f"Source: {record.get('source_record_id')[:8]}..., "
              f"Errors: {', '.join(errors[:2])}")
    if len(error_records) > 5:
        print(f"  ... and {len(error_records) - 5} more")

# Verify
cursor.execute("SELECT COUNT(*), validation_status FROM canonical.canonical_transaction GROUP BY validation_status")
print("\n📊 Final counts:")
for row in cursor.fetchall():
    print(f"  {row[1]}: {row[0]} records")

cursor.close()
conn.close()
