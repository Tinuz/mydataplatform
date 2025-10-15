#!/usr/bin/env python3
"""
Test canonical_communications asset directly
"""

import sys
sys.path.insert(0, '/opt/dagster/app')

from investigations.canonical_assets import canonical_communications
from investigations.resources import PostgresResource
from dagster import build_asset_context

# Create mock context
context = build_asset_context()

# Create postgres resource
postgres = PostgresResource(
    host="dp_postgres",
    port=5432,
    database="superset",
    user="superset",
    password="superset"
)

print("=" * 80)
print("Testing canonical_communications asset")
print("=" * 80)

try:
    # Execute the asset
    result = list(canonical_communications(context, postgres))
    
    print("\n" + "=" * 80)
    print("Asset execution completed successfully!")
    print("=" * 80)
    print(f"Result: {result}")
    
    # Check database
    conn = postgres.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM canonical.canonical_communication")
    count = cursor.fetchone()['count']
    cursor.close()
    conn.close()
    
    print(f"\n✅ Records in canonical_communication: {count}")
    
except Exception as e:
    print("\n" + "=" * 80)
    print("❌ Asset execution FAILED!")
    print("=" * 80)
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
