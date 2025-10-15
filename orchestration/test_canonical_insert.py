#!/usr/bin/env python3
"""
Test canonical INSERT directly
"""
import sys
sys.path.insert(0, '/opt/dagster/app')

from investigations.canonical_assets import map_bank_a_to_canonical
import psycopg2
import uuid
import json

# Connect to database
conn = psycopg2.connect(
    host='postgres',
    port=5432,
    database='superset',
    user='superset',
    password='superset'
)

# Get one raw transaction
cursor = conn.cursor()
cursor.execute("SELECT * FROM raw_transactions LIMIT 1")
columns = [desc[0] for desc in cursor.description]
row = cursor.fetchone()

if row:
    raw_record = dict(zip(columns, row))
    canonical = map_bank_a_to_canonical(raw_record)
    
    print("Attempting to insert canonical transaction...")
    
    try:
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
        
        cursor.execute(insert_sql, (
            str(uuid.uuid4()),
            canonical.get('source_system_id'),
            canonical.get('source_record_id'),
            canonical.get('source_file_name'),
            canonical.get('investigation_id'),
            canonical.get('transaction_reference'),
            canonical.get('transaction_datetime'),
            canonical.get('posting_date'),
            canonical.get('value_date'),
            float(canonical.get('amount')) if canonical.get('amount') else None,
            canonical.get('currency_code'),
            canonical.get('debtor_account_id'),
            canonical.get('debtor_account_type'),
            canonical.get('debtor_name'),
            canonical.get('debtor_bank_code'),
            canonical.get('creditor_account_id'),
            canonical.get('creditor_account_type'),
            canonical.get('creditor_name'),
            canonical.get('creditor_bank_code'),
            canonical.get('transaction_type'),
            canonical.get('payment_method'),
            canonical.get('description'),
            canonical.get('reference_number'),
            'valid',  # Test with valid status
            None,
            80,  # Test completeness score
            canonical.get('is_cancelled', False),
            canonical.get('is_reversal', False),
            json.dumps(canonical.get('source_raw_data'), default=str)
        ))
        
        conn.commit()
        print("✅ INSERT SUCCESS!")
        
        # Check if it's in the table
        cursor.execute("SELECT COUNT(*) FROM canonical.canonical_transaction")
        count = cursor.fetchone()[0]
        print(f"Total canonical transactions: {count}")
        
    except Exception as e:
        print(f"❌ INSERT FAILED: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()

cursor.close()
conn.close()
