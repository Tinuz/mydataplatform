#!/usr/bin/env python3
"""
Test script for Investigation Query Helper

Tests DuckDB queries against processed investigation data
"""
import sys
sys.path.insert(0, '/opt/dagster/app')

from investigations.query_helper import InvestigationQueryHelper, get_investigation_stats
import json

def main():
    investigation_id = 'OND-2025-000002'
    
    print("=" * 60)
    print("INVESTIGATION QUERY HELPER TEST")
    print("=" * 60)
    print(f"\nInvestigation: {investigation_id}\n")
    
    with InvestigationQueryHelper() as helper:
        # Test 1: Get all transactions
        print("📊 TEST 1: Get All Transactions")
        print("-" * 60)
        try:
            transactions = helper.get_transactions(investigation_id)
            print(f"✅ Found {len(transactions)} transactions")
            print(f"\nFirst 3 transactions:")
            print(transactions[['datum', 'iban', 'bedrag', 'omschrijving']].head(3).to_string(index=False))
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 2: Transaction Summary
        print("\n\n📊 TEST 2: Transaction Summary by IBAN")
        print("-" * 60)
        try:
            summary = helper.get_transaction_summary(investigation_id)
            print(f"✅ Found {len(summary)} unique IBANs")
            print(f"\nTop 5 by transaction count:")
            print(summary[['iban', 'total_transactions', 'net_amount']].head(5).to_string(index=False))
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 3: Get call records
        print("\n\n📞 TEST 3: Get Call Records")
        print("-" * 60)
        try:
            calls = helper.get_call_records(investigation_id)
            print(f"✅ Found {len(calls)} call records")
            print(f"\nFirst 3 calls:")
            print(calls[['timestamp', 'caller', 'callee', 'duration']].head(3).to_string(index=False))
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 4: Call Network
        print("\n\n🕸️  TEST 4: Call Network Analysis")
        print("-" * 60)
        try:
            network = helper.get_call_network(investigation_id)
            print(f"✅ Found {len(network)} call relationships")
            print(f"\nTop 5 by call count:")
            print(network[['caller', 'callee', 'call_count', 'avg_duration_seconds']].head(5).to_string(index=False))
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 5: Daily Activity
        print("\n\n📅 TEST 5: Daily Activity Timeline")
        print("-" * 60)
        try:
            daily = helper.get_daily_activity(investigation_id)
            print(f"✅ Found {len(daily)} days with activity")
            print(f"\nAll days:")
            print(daily.to_string(index=False))
        except Exception as e:
            print(f"❌ Error: {e}")
        
        # Test 6: Custom SQL Query
        print("\n\n🔍 TEST 6: Custom SQL Query")
        print("-" * 60)
        try:
            sql = f"""
            SELECT 
                COUNT(DISTINCT iban) as unique_ibans,
                SUM(bedrag) as total_amount,
                MIN(datum) as first_date,
                MAX(datum) as last_date
            FROM read_parquet('s3://investigations/{investigation_id}/processed/transactions/*.parquet')
            """
            result = helper.query(sql)
            print("✅ Query executed successfully")
            print(f"\nResults:")
            print(result.to_string(index=False))
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Test 7: Get Complete Stats
    print("\n\n📈 TEST 7: Complete Investigation Statistics")
    print("-" * 60)
    try:
        stats = get_investigation_stats(investigation_id)
        print("✅ Stats generated successfully")
        print(f"\n{json.dumps(stats, indent=2, default=str)}")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)

if __name__ == '__main__':
    main()
