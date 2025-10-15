#!/usr/bin/env python3
"""
Test canonical mapping functions directly
"""
import sys
sys.path.insert(0, '/opt/dagster/app')

from investigations.canonical_assets import map_bank_a_to_canonical, validate_canonical_transaction
from investigations.resources import PostgresResource
import psycopg2

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
    print(f"Raw record: {raw_record}")
    print()
    
    try:
        # Map to canonical
        canonical = map_bank_a_to_canonical(raw_record)
        print(f"Canonical record: {canonical}")
        print()
        
        # Validate
        validation = validate_canonical_transaction(canonical)
        print(f"Validation: {validation}")
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
else:
    print("No raw transactions found")

cursor.close()
conn.close()
