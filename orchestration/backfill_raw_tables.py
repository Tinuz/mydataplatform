#!/usr/bin/env python3
"""
Backfill raw PostgreSQL tables from existing Parquet files in MinIO

This script reads existing processed Parquet files and inserts the detail records
into the raw_* tables (raw_transactions, raw_calls, raw_messages).
"""

import sys
import os
import io
import logging
from pathlib import Path
import pandas as pd
import psycopg2
from minio import Minio

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': os.getenv('POSTGRES_HOST', 'dp_postgres'),
    'port': int(os.getenv('POSTGRES_PORT', '5432')),
    'database': os.getenv('POSTGRES_DB', 'superset'),
    'user': os.getenv('POSTGRES_USER', 'superset'),
    'password': os.getenv('POSTGRES_PASSWORD', 'superset')
}

# MinIO connection
MINIO_CONFIG = {
    'endpoint': os.getenv('MINIO_ENDPOINT', 'dp_minio:9000'),
    'access_key': os.getenv('MINIO_ACCESS_KEY', 'minio'),
    'secret_key': os.getenv('MINIO_SECRET_KEY', 'minio12345'),
    'secure': os.getenv('MINIO_SECURE', 'false').lower() == 'true'
}

BUCKET_NAME = 'investigations'


def get_db_connection():
    """Create PostgreSQL connection"""
    return psycopg2.connect(**DB_CONFIG)


def get_minio_client():
    """Create MinIO client"""
    return Minio(**MINIO_CONFIG)


def write_transactions_to_postgres(conn, df, investigation_id, source_id):
    """Write transaction records to raw_transactions table"""
    cursor = conn.cursor()
    
    records = []
    for _, row in df.iterrows():
        record = {
            'investigation_id': investigation_id,
            'source_id': source_id,
            'iban_from': row.get('iban'),
            'iban_to': row.get('tegenrekening'),
            'bedrag': row.get('bedrag'),
            'datum': row.get('datum'),
            'omschrijving': row.get('omschrijving'),
            'raw_data': row.to_json()
        }
        records.append(record)
    
    if records:
        insert_query = """
            INSERT INTO raw_transactions 
            (investigation_id, source_id, iban_from, iban_to, bedrag, datum, omschrijving, raw_data)
            VALUES (%(investigation_id)s, %(source_id)s, %(iban_from)s, %(iban_to)s, %(bedrag)s, %(datum)s, %(omschrijving)s, %(raw_data)s::jsonb)
            ON CONFLICT DO NOTHING
        """
        cursor.executemany(insert_query, records)
        conn.commit()
    
    cursor.close()
    return len(records)


def write_calls_to_postgres(conn, df, investigation_id, source_id):
    """Write call records to raw_calls table"""
    cursor = conn.cursor()
    
    records = []
    for _, row in df.iterrows():
        record = {
            'investigation_id': investigation_id,
            'source_id': source_id,
            'caller_number': row.get('caller') or row.get('calling_number'),
            'called_number': row.get('callee') or row.get('called_number'),
            'call_date': row.get('date') or row.get('call_date'),
            'call_time': row.get('time') or row.get('call_time'),
            'duration_seconds': row.get('duration') or row.get('duration_seconds'),
            'call_type': row.get('call_type', 'unknown'),
            'raw_data': row.to_json()
        }
        records.append(record)
    
    if records:
        insert_query = """
            INSERT INTO raw_calls 
            (investigation_id, source_id, caller_number, called_number, call_date, call_time, duration_seconds, call_type, raw_data)
            VALUES (%(investigation_id)s, %(source_id)s, %(caller_number)s, %(called_number)s, %(call_date)s, %(call_time)s, %(duration_seconds)s, %(call_type)s, %(raw_data)s::jsonb)
            ON CONFLICT DO NOTHING
        """
        cursor.executemany(insert_query, records)
        conn.commit()
    
    cursor.close()
    return len(records)


def write_messages_to_postgres(conn, df, investigation_id, source_id):
    """Write message records to raw_messages table"""
    cursor = conn.cursor()
    
    records = []
    for _, row in df.iterrows():
        record = {
            'investigation_id': investigation_id,
            'source_id': source_id,
            'sender_number': row.get('sender') or row.get('from_number'),
            'recipient_number': row.get('recipient') or row.get('to_number'),
            'message_date': row.get('date') or row.get('message_date'),
            'message_time': row.get('time') or row.get('message_time'),
            'message_text': row.get('message') or row.get('text'),
            'message_type': row.get('message_type', 'sms'),
            'raw_data': row.to_json()
        }
        records.append(record)
    
    if records:
        insert_query = """
            INSERT INTO raw_messages 
            (investigation_id, source_id, sender_number, recipient_number, message_date, message_time, message_text, message_type, raw_data)
            VALUES (%(investigation_id)s, %(source_id)s, %(sender_number)s, %(recipient_number)s, %(message_date)s, %(message_time)s, %(message_text)s, %(message_type)s, %(raw_data)s::jsonb)
            ON CONFLICT DO NOTHING
        """
        cursor.executemany(insert_query, records)
        conn.commit()
    
    cursor.close()
    return len(records)


def backfill_investigation(investigation_id, conn, minio_client):
    """Backfill all Parquet files for a specific investigation"""
    logger.info(f"Backfilling investigation: {investigation_id}")
    
    total_transactions = 0
    total_calls = 0
    total_messages = 0
    
    # List all objects in the investigation's processed folder
    prefix = f"{investigation_id}/processed/"
    objects = minio_client.list_objects(BUCKET_NAME, prefix=prefix, recursive=True)
    
    for obj in objects:
        if not obj.object_name.endswith('.parquet'):
            continue
        
        logger.info(f"Processing: {obj.object_name}")
        
        # Download Parquet file
        try:
            response = minio_client.get_object(BUCKET_NAME, obj.object_name)
            parquet_bytes = response.read()
            response.close()
            response.release_conn()
            
            # Read Parquet into DataFrame
            df = pd.read_parquet(io.BytesIO(parquet_bytes))
            
            # Extract source_id from filename or DataFrame
            if 'source_id' in df.columns:
                source_id = df['source_id'].iloc[0] if len(df) > 0 else 'unknown'
            else:
                # Extract from path: investigation_id/processed/type/source_id_type.parquet
                filename = obj.object_name.split('/')[-1]
                source_id = filename.split('_')[0]
            
            # Determine type and write to appropriate table
            if '/transactions/' in obj.object_name:
                records = write_transactions_to_postgres(conn, df, investigation_id, source_id)
                total_transactions += records
                logger.info(f"  ✅ Inserted {records} transactions (source: {source_id})")
            
            elif '/call_records/' in obj.object_name:
                records = write_calls_to_postgres(conn, df, investigation_id, source_id)
                total_calls += records
                logger.info(f"  ✅ Inserted {records} calls (source: {source_id})")
            
            elif '/messages/' in obj.object_name:
                records = write_messages_to_postgres(conn, df, investigation_id, source_id)
                total_messages += records
                logger.info(f"  ✅ Inserted {records} messages (source: {source_id})")
            
            else:
                logger.warning(f"  ⚠️  Unknown type: {obj.object_name}")
        
        except Exception as e:
            logger.error(f"  ❌ Failed to process {obj.object_name}: {e}")
    
    logger.info(f"\nBackfill complete for {investigation_id}:")
    logger.info(f"  - Transactions: {total_transactions}")
    logger.info(f"  - Calls: {total_calls}")
    logger.info(f"  - Messages: {total_messages}")
    
    return {
        'transactions': total_transactions,
        'calls': total_calls,
        'messages': total_messages
    }


def list_investigations(minio_client):
    """List all investigations in MinIO"""
    investigations = set()
    
    # List all top-level folders
    objects = minio_client.list_objects(BUCKET_NAME, recursive=False)
    for obj in objects:
        # Check if it looks like an investigation ID
        folder_name = obj.object_name.rstrip('/')
        if folder_name.startswith('OND-'):
            investigations.add(folder_name)
    
    return sorted(investigations)


def main():
    """Main backfill function"""
    logger.info("=== Raw Tables Backfill Script ===")
    
    # Connect to services
    logger.info("Connecting to PostgreSQL and MinIO...")
    conn = get_db_connection()
    minio_client = get_minio_client()
    
    # Get investigation ID from command line or list all
    if len(sys.argv) > 1:
        investigation_ids = sys.argv[1:]
    else:
        logger.info("\nListing available investigations:")
        investigation_ids = list_investigations(minio_client)
        
        if not investigation_ids:
            logger.error("No investigations found in MinIO bucket")
            return
        
        logger.info(f"Found {len(investigation_ids)} investigations:")
        for inv_id in investigation_ids:
            logger.info(f"  - {inv_id}")
        
        logger.info(f"\nBackfilling all investigations...")
    
    # Backfill each investigation
    grand_total = {'transactions': 0, 'calls': 0, 'messages': 0}
    
    for investigation_id in investigation_ids:
        try:
            results = backfill_investigation(investigation_id, conn, minio_client)
            grand_total['transactions'] += results['transactions']
            grand_total['calls'] += results['calls']
            grand_total['messages'] += results['messages']
            logger.info("")
        except Exception as e:
            logger.error(f"Failed to backfill {investigation_id}: {e}")
    
    # Close connection
    conn.close()
    
    # Print summary
    logger.info("\n" + "="*50)
    logger.info("BACKFILL COMPLETE")
    logger.info("="*50)
    logger.info(f"Total records inserted:")
    logger.info(f"  - Transactions: {grand_total['transactions']}")
    logger.info(f"  - Calls: {grand_total['calls']}")
    logger.info(f"  - Messages: {grand_total['messages']}")
    logger.info(f"  - TOTAL: {sum(grand_total.values())}")


if __name__ == '__main__':
    main()
