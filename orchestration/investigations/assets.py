"""
Dagster assets for investigations processing

Auto-processing pipeline for uploaded files:
1. File detection
2. Type-specific processing
3. Parquet storage
4. PostgreSQL indexing
"""

from dagster import asset, OpExecutionContext, Output, MetadataValue
from typing import Dict, Any
import pandas as pd
import io
from datetime import datetime
import logging
import json
import hashlib

from .resources import PostgresResource, MinioResource
from .file_detection import detect_file_type, validate_csv_structure

logger = logging.getLogger(__name__)


def write_transactions_to_postgres(
    postgres: PostgresResource,
    df: pd.DataFrame,
    investigation_id: str,
    source_id: str
) -> int:
    """
    Write transaction records to PostgreSQL raw_transactions table
    
    Args:
        postgres: PostgreSQL resource
        df: DataFrame with transaction data
        investigation_id: Investigation ID
        source_id: Source ID
    
    Returns:
        Number of records written
    """
    # Prepare data for insertion
    records = []
    for _, row in df.iterrows():
        # Try both column names (before/after cleaning)
        iban_to = row.get('tegenrekening_iban') or row.get('tegenrekening')
        
        record = {
            'investigation_id': investigation_id,
            'source_id': source_id,
            'iban_from': row.get('iban'),
            'iban_to': iban_to,
            'bedrag': row.get('bedrag'),
            'datum': row.get('datum'),
            'omschrijving': row.get('omschrijving'),
            'raw_data': row.to_json()  # Store full row as JSONB
        }
        records.append(record)
    
    # Bulk insert
    if records:
        conn = postgres.get_connection()
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO raw_transactions 
            (investigation_id, source_id, iban_from, iban_to, bedrag, datum, omschrijving, raw_data)
            VALUES (%(investigation_id)s, %(source_id)s, %(iban_from)s, %(iban_to)s, %(bedrag)s, %(datum)s, %(omschrijving)s, %(raw_data)s::jsonb)
        """
        
        cursor.executemany(insert_query, records)
        conn.commit()
        cursor.close()
        conn.close()
    
    return len(records)


def write_calls_to_postgres(
    postgres: PostgresResource,
    df: pd.DataFrame,
    investigation_id: str,
    source_id: str
) -> int:
    """
    Write call records to PostgreSQL raw_calls table
    
    Args:
        postgres: PostgreSQL resource
        df: DataFrame with call data
        investigation_id: Investigation ID
        source_id: Source ID
    
    Returns:
        Number of records written
    """
    records = []
    for _, row in df.iterrows():
        record = {
            'investigation_id': investigation_id,
            'source_id': source_id,
            'caller_number': row.get('calling_number') or row.get('caller'),
            'called_number': row.get('called_number') or row.get('recipient'),
            'call_date': row.get('date') or row.get('call_date'),
            'call_time': row.get('time') or row.get('call_time'),
            'duration_seconds': row.get('duration_seconds') or row.get('duration'),
            'call_type': row.get('call_type', 'unknown'),
            'raw_data': row.to_json()
        }
        records.append(record)
    
    if records:
        conn = postgres.get_connection()
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO raw_calls 
            (investigation_id, source_id, caller_number, called_number, call_date, call_time, duration_seconds, call_type, raw_data)
            VALUES (%(investigation_id)s, %(source_id)s, %(caller_number)s, %(called_number)s, %(call_date)s, %(call_time)s, %(duration_seconds)s, %(call_type)s, %(raw_data)s::jsonb)
        """
        
        cursor.executemany(insert_query, records)
        conn.commit()
        cursor.close()
        conn.close()
    
    return len(records)


def write_messages_to_postgres(
    postgres: PostgresResource,
    df: pd.DataFrame,
    investigation_id: str,
    source_id: str
) -> int:
    """
    Write message records to PostgreSQL raw_messages table
    
    Args:
        postgres: PostgreSQL resource
        df: DataFrame with message data
        investigation_id: Investigation ID
        source_id: Source ID
    
    Returns:
        Number of records written
    """
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
        conn = postgres.get_connection()
        cursor = conn.cursor()
        
        insert_query = """
            INSERT INTO raw_messages 
            (investigation_id, source_id, sender_number, recipient_number, message_date, message_time, message_text, message_type, raw_data)
            VALUES (%(investigation_id)s, %(source_id)s, %(sender_number)s, %(recipient_number)s, %(message_date)s, %(message_time)s, %(message_text)s, %(message_type)s, %(raw_data)s::jsonb)
        """
        
        cursor.executemany(insert_query, records)
        conn.commit()
        cursor.close()
        conn.close()
    
    return len(records)


def calculate_file_hash(file_content: bytes, algorithm: str = 'sha256') -> str:
    """
    Calculate cryptographic hash of file content
    
    Args:
        file_content: File content as bytes
        algorithm: Hash algorithm (sha256, sha1, md5)
    
    Returns:
        Hexadecimal hash string
    """
    if algorithm == 'sha256':
        hasher = hashlib.sha256()
    elif algorithm == 'sha1':
        hasher = hashlib.sha1()
    elif algorithm == 'md5':
        hasher = hashlib.md5()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    hasher.update(file_content)
    return hasher.hexdigest()


def generate_validation_metadata(
    source_id: str,
    filename: str,
    file_type: str,
    df: pd.DataFrame,
    raw_file_size: int = None,
    raw_file_content: bytes = None,
    validation_errors: list = None
) -> Dict[str, Any]:
    """
    Generate validation metadata for a processed file
    
    Args:
        source_id: Unique source identifier
        filename: Original filename
        file_type: Detected file type (bank_transactions, call_records, sms_records)
        df: Processed DataFrame
        raw_file_size: Original file size in bytes
        raw_file_content: Original file content as bytes (for hash calculation)
        validation_errors: List of validation errors if any
    
    Returns:
        Dict with validation metadata
    """
    metadata = {
        'source_id': source_id,
        'filename': filename,
        'file_type': file_type,
        'processed_at': datetime.utcnow().isoformat(),
        
        # File statistics
        'file_stats': {
            'raw_file_size_bytes': raw_file_size,
            'row_count': len(df),
            'column_count': len(df.columns),
            'columns': list(df.columns),
            'memory_usage_bytes': int(df.memory_usage(deep=True).sum())
        },
        
        # File integrity (checksums/hashes)
        'file_integrity': {},
        
        # Data quality checks
        'data_quality': {
            'null_counts': df.isnull().sum().to_dict(),
            'null_percentage': (df.isnull().sum() / len(df) * 100).round(2).to_dict(),
            'duplicate_rows': int(df.duplicated().sum()),
            'duplicate_percentage': round(df.duplicated().sum() / len(df) * 100, 2) if len(df) > 0 else 0
        },
        
        # Data types
        'data_types': {col: str(dtype) for col, dtype in df.dtypes.items()},
        
        # Validation status
        'validation': {
            'status': 'passed' if not validation_errors else 'failed',
            'errors': validation_errors or [],
            'error_count': len(validation_errors) if validation_errors else 0
        }
    }
    
    # Add type-specific statistics
    if file_type == 'bank_transactions':
        if 'bedrag' in df.columns:
            metadata['statistics'] = {
                'amount_sum': float(df['bedrag'].sum()),
                'amount_mean': float(df['bedrag'].mean()),
                'amount_min': float(df['bedrag'].min()),
                'amount_max': float(df['bedrag'].max()),
                'amount_std': float(df['bedrag'].std())
            }
        if 'iban' in df.columns:
            metadata['statistics']['unique_ibans'] = int(df['iban'].nunique())
        if 'datum' in df.columns:
            metadata['statistics']['date_range'] = {
                'min': str(df['datum'].min()) if not df['datum'].isna().all() else None,
                'max': str(df['datum'].max()) if not df['datum'].isna().all() else None
            }
    
    elif file_type in ['call_records', 'sms_records']:
        # Phone number statistics
        phone_cols = [col for col in df.columns if col in ['caller', 'callee', 'calling_number', 'called_number', 'sender', 'recipient']]
        if phone_cols:
            all_numbers = pd.concat([df[col] for col in phone_cols]).dropna()
            metadata['statistics'] = {
                'unique_phone_numbers': int(all_numbers.nunique()),
                'total_phone_numbers': int(len(all_numbers))
            }
        
        if 'timestamp' in df.columns or 'datetime' in df.columns:
            ts_col = 'timestamp' if 'timestamp' in df.columns else 'datetime'
            metadata['statistics']['timestamp_range'] = {
                'min': str(df[ts_col].min()) if not df[ts_col].isna().all() else None,
                'max': str(df[ts_col].max()) if not df[ts_col].isna().all() else None
            }
        
        # Call-specific statistics
        if file_type == 'call_records' and 'duration' in df.columns:
            metadata['statistics']['duration'] = {
                'total_seconds': int(df['duration'].sum()),
                'mean_seconds': float(df['duration'].mean()),
                'max_seconds': int(df['duration'].max())
            }
    
    # Calculate file integrity hashes if content provided
    if raw_file_content:
        try:
            metadata['file_integrity'] = {
                'sha256': calculate_file_hash(raw_file_content, 'sha256'),
                'sha1': calculate_file_hash(raw_file_content, 'sha1'),
                'md5': calculate_file_hash(raw_file_content, 'md5'),
                'calculated_at': datetime.utcnow().isoformat()
            }
        except Exception as e:
            logger.warning(f"Failed to calculate file hashes: {e}")
            metadata['file_integrity']['error'] = str(e)
    
    return metadata


def save_validation_metadata(
    minio: MinioResource,
    investigation_id: str,
    source_id: str,
    metadata: Dict[str, Any]
):
    """
    Save validation metadata to MinIO metadata folder
    
    Args:
        minio: MinIO resource
        investigation_id: Investigation ID
        source_id: Source ID
        metadata: Metadata dictionary to save
    """
    metadata_filename = f"{source_id}_validation.json"
    metadata_path = f"{investigation_id}/metadata/{metadata_filename}"
    
    # Convert to JSON
    metadata_json = json.dumps(metadata, indent=2, default=str)
    metadata_bytes = metadata_json.encode('utf-8')
    
    # Upload to MinIO
    minio.upload_file(
        metadata_path,
        metadata_bytes,
        content_type='application/json'
    )
    
    logger.info(f"Saved validation metadata to {metadata_path}")


@asset(
    group_name="investigations_ingestion",
    description="Detect file type and validate structure"
)
def detect_pending_files(
    context: OpExecutionContext,
    postgres: PostgresResource
) -> Dict[str, Any]:
    """
    Get pending files from database and detect their types
    
    Returns list of files ready for processing
    """
    # Get pending files
    pending_sources = postgres.get_pending_sources()
    
    context.log.info(f"Found {len(pending_sources)} pending files")
    
    detected_files = []
    
    for source in pending_sources:
        source_id = source['source_id']
        filename = source['file_name']
        
        # Detect file type
        detection = detect_file_type(filename)
        
        if detection['file_type'] != 'unknown':
            detected_files.append({
                'source_id': source_id,
                'investigation_id': source['investigation_id'],
                'file_name': filename,
                'file_path': source['file_path'],
                'source_type': source['source_type'],
                'provider': source['provider'],
                'detected_type': detection['file_type'],
                'pipeline': detection['pipeline'],
                'output_type': detection['output_type'],
                'confidence': detection['confidence']
            })
            
            context.log.info(
                f"Detected {source_id}: {detection['file_type']} "
                f"(confidence: {detection['confidence']})"
            )
        else:
            context.log.warning(f"Could not detect type for {source_id}: {filename}")
            # Mark as skipped
            postgres.update_source_status(
                source_id=source_id,
                status='skipped',
                error_message=f"Unknown file type: {filename}"
            )
    
    result = {
        'detected_files': detected_files,
        'total_pending': len(pending_sources),
        'total_detected': len(detected_files)
    }
    
    context.log.info(
        f"Detection complete: {len(detected_files)}/{len(pending_sources)} files detected"
    )
    
    return result


@asset(
    group_name="investigations_ingestion",
    description="Process bank transaction CSV files"
)
def process_bank_transactions(
    context: OpExecutionContext,
    postgres: PostgresResource,
    minio: MinioResource,
    detect_pending_files: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process bank transaction files
    
    Pipeline:
    1. Download CSV from MinIO
    2. Parse and validate
    3. Add investigation_id to each row
    4. Write to Parquet
    5. Index in PostgreSQL
    """
    # Filter for bank transaction files
    bank_files = [
        f for f in detect_pending_files['detected_files']
        if f['detected_type'] == 'bank_transactions'
    ]
    
    context.log.info(f"Processing {len(bank_files)} bank transaction files")
    
    processed_count = 0
    failed_count = 0
    total_records = 0
    
    for file_info in bank_files:
        source_id = file_info['source_id']
        investigation_id = file_info['investigation_id']
        
        try:
            # Update status to processing
            postgres.update_source_status(
                source_id=source_id,
                status='processing',
                pipeline='bank_transaction_pipeline'
            )
            
            # Download file from MinIO
            context.log.info(f"Downloading {file_info['file_name']}")
            file_content = minio.download_file(file_info['file_path'])
            
            # Parse CSV
            df = pd.read_csv(io.BytesIO(file_content))
            
            # Normalize column names (ensure they're strings first)
            df.columns = [str(col).lower().strip() for col in df.columns]
            
            # Validate required columns - accept different column name variants
            # Different banks use different column names, these will be normalized in clean_bank_transactions()
            required_iban_variants = [
                'iban', 'rekeningnummer', 'from_account', 'account_number', 'source_iban', 'dest_iban',
                'iban_from', 'iban_to', 'debit_account', 'credit_account'  # Bank A and Bank D variants
            ]
            required_amount_variants = [
                'bedrag', 'amount', 'bedrag (eur)', 'value', 'trans_amount'  # Added Bank D variant
            ]
            
            has_iban = any(col in df.columns for col in required_iban_variants)
            has_amount = any(col in df.columns for col in required_amount_variants)
            
            if not has_iban:
                raise ValueError(f"Missing IBAN column. Expected one of: {', '.join(required_iban_variants)}")
            if not has_amount:
                raise ValueError(f"Missing amount column. Expected one of: {', '.join(required_amount_variants)}")
            
            # Add investigation context
            df['investigation_id'] = investigation_id
            df['source_id'] = source_id
            df['processed_at'] = datetime.utcnow().isoformat()
            
            # Clean and transform data
            df = clean_bank_transactions(df)
            
            record_count = len(df)
            total_records += record_count
            
            # Write to Parquet in processed folder
            parquet_filename = f"{source_id}_transactions.parquet"
            parquet_path = f"{investigation_id}/processed/transactions/{parquet_filename}"
            
            # Convert to parquet bytes
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
            parquet_bytes = parquet_buffer.getvalue()
            
            # Upload to MinIO
            context.log.info(f"Writing {record_count} records to {parquet_path}")
            minio.upload_file(parquet_path, parquet_bytes, content_type='application/parquet')
            
            # Write detail records to PostgreSQL
            records_inserted = write_transactions_to_postgres(postgres, df, investigation_id, source_id)
            context.log.info(f"Inserted {records_inserted} records into raw_transactions table")
            
            # Generate and save validation metadata
            validation_metadata = generate_validation_metadata(
                source_id=source_id,
                filename=file_info['file_name'],
                file_type='bank_transactions',
                df=df,
                raw_file_size=len(file_content),
                raw_file_content=file_content
            )
            save_validation_metadata(minio, investigation_id, source_id, validation_metadata)
            context.log.info(f"Saved validation metadata for {source_id}")
            
            # Index summary in PostgreSQL
            summary = {
                'total_records': record_count,
                'total_amount': float(df['bedrag'].sum()) if 'bedrag' in df.columns else 0,
                'date_range': {
                    'min': str(df['datum'].min()) if 'datum' in df.columns and not df['datum'].isna().all() else None,
                    'max': str(df['datum'].max()) if 'datum' in df.columns and not df['datum'].isna().all() else None
                },
                'unique_ibans': int(df['iban'].nunique()) if 'iban' in df.columns else 0
            }
            
            postgres.insert_processed_record(
                investigation_id=investigation_id,
                source_id=source_id,
                record_type='transaction',
                record_date=summary['date_range']['min'] or datetime.utcnow().date().isoformat(),
                parquet_path=f"s3://investigations/{parquet_path}",
                summary=summary
            )
            
            # Update status to completed
            postgres.update_source_status(
                source_id=source_id,
                status='completed',
                pipeline='bank_transaction_pipeline'
            )
            
            processed_count += 1
            context.log.info(
                f"✅ Processed {source_id}: {record_count} transactions"
            )
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Error processing {source_id}: {str(e)}"
            context.log.error(error_msg)
            
            # Try to save validation metadata even on failure
            try:
                # If we got a DataFrame before the error, save metadata
                if 'df' in locals():
                    validation_metadata = generate_validation_metadata(
                        source_id=source_id,
                        filename=file_info['file_name'],
                        file_type='bank_transactions',
                        df=df,
                        raw_file_size=len(file_content) if 'file_content' in locals() else None,
                        raw_file_content=file_content if 'file_content' in locals() else None,
                        validation_errors=[error_msg]
                    )
                    save_validation_metadata(minio, investigation_id, source_id, validation_metadata)
            except Exception as meta_error:
                context.log.warning(f"Could not save error metadata: {str(meta_error)}")
            
            # Update status to failed
            postgres.update_source_status(
                source_id=source_id,
                status='failed',
                pipeline='bank_transaction_pipeline',
                error_message=error_msg
            )
    
    return {
        'processed_files': processed_count,
        'failed_files': failed_count,
        'total_records': total_records,
        'pipeline': 'bank_transaction_pipeline'
    }


def clean_bank_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """
    Clean and normalize bank transaction data
    
    Args:
        df: Raw transaction DataFrame
        
    Returns:
        Cleaned DataFrame
    """
    # Common column name mappings (Dutch banks use different names)
    column_mappings = {
        # Dutch bank format (Bank A, Bank C)
        'rekeningnummer': 'iban',
        'tegenrekening': 'tegenrekening_iban',
        'bedrag (eur)': 'bedrag',
        'valutadatum': 'datum',
        'boekdatum': 'boekdatum',
        'omschrijving': 'omschrijving',
        'naam tegenpartij': 'tegenpartij_naam',
        # Bank A format (Marvel test data)
        'iban_from': 'iban',
        'iban_to': 'tegenrekening_iban',
        # International format (Bank B - Rabobank)
        'from_account': 'iban',
        'to_account': 'tegenrekening_iban',
        'amount': 'bedrag',
        'date': 'datum',
        'description': 'omschrijving',
        'transaction_type': 'type',
        # Bank C format (English column names)
        'source_iban': 'iban',
        'dest_iban': 'tegenrekening_iban',
        'value': 'bedrag',
        'transaction_date': 'datum',
        'narrative': 'omschrijving',
        'ccy': 'valuta',
        # Bank D format (ABN AMRO branch - Marvel test data)
        'debit_account': 'iban',
        'credit_account': 'tegenrekening_iban',
        'trans_amount': 'bedrag',
        'trans_date': 'datum',
        'trans_description': 'omschrijving',
        'trans_type': 'type',
        'trans_currency': 'valuta'
    }
    
    # Rename columns if they exist
    for old_name, new_name in column_mappings.items():
        if old_name in df.columns and new_name not in df.columns:
            df = df.rename(columns={old_name: new_name})
    
    # Convert bedrag to float if it's a string
    if 'bedrag' in df.columns:
        if df['bedrag'].dtype == 'object' or df['bedrag'].dtype == 'string':
            # Handle Dutch format: 1.234,56 -> 1234.56
            # Convert to string first to ensure .str accessor works
            df['bedrag'] = df['bedrag'].astype(str).str.replace('.', '', regex=False).str.replace(',', '.', regex=False)
            df['bedrag'] = pd.to_numeric(df['bedrag'], errors='coerce')
    
    # Parse dates
    date_columns = ['datum', 'boekdatum', 'valutadatum']
    for col in date_columns:
        if col in df.columns:
            try:
                df[col] = pd.to_datetime(df[col], errors='coerce')
            except:
                pass
    
    # Validate IBANs (basic check)
    if 'iban' in df.columns:
        df['iban'] = df['iban'].astype(str).str.upper().str.strip()
        df['iban_valid'] = df['iban'].str.match(r'^[A-Z]{2}\d{2}[A-Z0-9]+$')
    
    return df


@asset(
    group_name="investigations_ingestion",
    description="Process telecom call records CSV files"
)
def process_telecom_calls(
    context: OpExecutionContext,
    postgres: PostgresResource,
    minio: MinioResource,
    detect_pending_files: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process telephone call records
    
    Similar pipeline to bank transactions but for call data
    """
    # Filter for call record files and SMS files (both use same pipeline)
    call_files = [
        f for f in detect_pending_files['detected_files']
        if f['detected_type'] in ['call_records', 'sms_records']
    ]
    
    context.log.info(f"Processing {len(call_files)} telecom files (calls + SMS)")
    
    processed_count = 0
    failed_count = 0
    total_records = 0
    
    for file_info in call_files:
        source_id = file_info['source_id']
        investigation_id = file_info['investigation_id']
        
        try:
            postgres.update_source_status(
                source_id=source_id,
                status='processing',
                pipeline='telecom_call_pipeline'
            )
            
            # Download and parse
            file_content = minio.download_file(file_info['file_path'])
            df = pd.read_csv(io.BytesIO(file_content))
            df.columns = [str(col).lower().strip() for col in df.columns]
            
            # Add context
            df['investigation_id'] = investigation_id
            df['source_id'] = source_id
            df['processed_at'] = datetime.utcnow().isoformat()
            
            # Clean data
            df = clean_call_records(df)
            
            record_count = len(df)
            total_records += record_count
            
            # Determine output type and paths based on file type
            # Check detected_type first, then output_type from file_info
            detected_type = file_info.get('detected_type', '')
            output_type = file_info.get('output_type', 'call_record')  # Default from config
            
            # For SMS records, force output_type to 'message'
            if detected_type == 'sms_records' or output_type == 'message':
                record_type = 'message'
                folder_name = 'messages'
                file_suffix = 'messages'
            else:
                record_type = 'call_record'
                folder_name = 'call_records'
                file_suffix = 'calls'
            
            context.log.info(f"Processing {source_id}: detected_type={detected_type}, output_type={output_type}, record_type={record_type}")
            
            # Write to Parquet
            parquet_filename = f"{source_id}_{file_suffix}.parquet"
            parquet_path = f"{investigation_id}/processed/{folder_name}/{parquet_filename}"
            
            parquet_buffer = io.BytesIO()
            df.to_parquet(parquet_buffer, index=False, engine='pyarrow')
            parquet_bytes = parquet_buffer.getvalue()
            minio.upload_file(parquet_path, parquet_bytes, content_type='application/parquet')
            
            # Write detail records to PostgreSQL
            if record_type == 'message':
                records_inserted = write_messages_to_postgres(postgres, df, investigation_id, source_id)
                context.log.info(f"Inserted {records_inserted} records into raw_messages table")
            else:
                records_inserted = write_calls_to_postgres(postgres, df, investigation_id, source_id)
                context.log.info(f"Inserted {records_inserted} records into raw_calls table")
            
            # Generate and save validation metadata
            validation_metadata = generate_validation_metadata(
                source_id=source_id,
                filename=file_info['file_name'],
                file_type=detected_type if detected_type else 'call_records',
                df=df,
                raw_file_size=len(file_content),
                raw_file_content=file_content
            )
            save_validation_metadata(minio, investigation_id, source_id, validation_metadata)
            context.log.info(f"Saved validation metadata for {source_id}")
            
            # Build summary based on record type
            if record_type == 'message':
                # SMS/Message statistics
                summary = {
                    'total_messages': record_count,
                    'unique_senders': int(df['sender'].nunique()) if 'sender' in df.columns else 0,
                    'unique_recipients': int(df['recipient'].nunique()) if 'recipient' in df.columns else 0,
                    'date_range': {
                        'min': str(df['timestamp'].min()) if 'timestamp' in df.columns and not df['timestamp'].isna().all() else None,
                        'max': str(df['timestamp'].max()) if 'timestamp' in df.columns and not df['timestamp'].isna().all() else None
                    }
                }
            else:
                # Call record statistics
                summary = {
                    'total_calls': record_count,
                    'unique_callers': int(df['caller'].nunique()) if 'caller' in df.columns else 0,
                    'unique_callees': int(df['callee'].nunique()) if 'callee' in df.columns else 0,
                    'total_duration_minutes': float(df['duration'].sum() / 60) if 'duration' in df.columns else 0,
                    'date_range': {
                        'min': str(df['timestamp'].min()) if 'timestamp' in df.columns and not df['timestamp'].isna().all() else None,
                        'max': str(df['timestamp'].max()) if 'timestamp' in df.columns and not df['timestamp'].isna().all() else None
                    }
                }
            
            postgres.insert_processed_record(
                investigation_id=investigation_id,
                source_id=source_id,
                record_type=record_type,  # 'call_record' or 'message'
                record_date=summary['date_range']['min'] or datetime.utcnow().date().isoformat(),
                parquet_path=f"s3://investigations/{parquet_path}",
                summary=summary
            )
            
            postgres.update_source_status(
                source_id=source_id,
                status='completed',
                pipeline='telecom_call_pipeline'
            )
            
            processed_count += 1
            context.log.info(f"✅ Processed {source_id}: {record_count} {record_type}s")
            
        except Exception as e:
            failed_count += 1
            error_msg = f"Error processing {source_id}: {str(e)}"
            context.log.error(error_msg)
            
            # Try to save validation metadata even on failure
            try:
                if 'df' in locals() and 'detected_type' in locals():
                    validation_metadata = generate_validation_metadata(
                        source_id=source_id,
                        filename=file_info['file_name'],
                        file_type=detected_type if detected_type else 'call_records',
                        df=df,
                        raw_file_size=len(file_content) if 'file_content' in locals() else None,
                        raw_file_content=file_content if 'file_content' in locals() else None,
                        validation_errors=[error_msg]
                    )
                    save_validation_metadata(minio, investigation_id, source_id, validation_metadata)
            except Exception as meta_error:
                context.log.warning(f"Could not save error metadata: {str(meta_error)}")
            
            postgres.update_source_status(
                source_id=source_id,
                status='failed',
                pipeline='telecom_call_pipeline',
                error_message=error_msg
            )
    
    return {
        'processed_files': processed_count,
        'failed_files': failed_count,
        'total_records': total_records,
        'pipeline': 'telecom_call_pipeline'
    }


def clean_call_records(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize call record and SMS data"""
    
    # Column mappings for different telecom providers
    column_mappings = {
        # Telecom A (KPN) - Marvel test data
        'from_number': 'caller',
        'to_number': 'callee',
        'duration_seconds': 'duration',
        'message_content': 'message_text',
        # Telecom B (Vodafone) - Marvel test data
        'caller_number': 'caller',
        'callee_number': 'callee',
        'call_duration': 'duration',
        'receiver': 'recipient',
        'text_content': 'message_text',
        # Telecom C (T-Mobile) - Marvel test data
        'origin': 'caller',
        'destination': 'callee',
        'duration_sec': 'duration',
        'origin_msisdn': 'sender',
        'dest_msisdn': 'recipient',
        'message_body': 'message_text',
        # Generic mappings
        'calling_number': 'caller',
        'called_number': 'callee'
    }
    
    # Rename columns if they exist
    for old_name, new_name in column_mappings.items():
        if old_name in df.columns and new_name not in df.columns:
            df = df.rename(columns={old_name: new_name})
    
    # Normalize phone numbers (works for both calls and SMS)
    phone_columns = ['caller', 'callee', 'calling_number', 'called_number', 'sender', 'recipient']
    for col in phone_columns:
        if col in df.columns:
            # Remove spaces, dashes, etc.
            df[col] = df[col].astype(str).str.replace(r'[\s\-\(\)]', '', regex=True)
            # Standardize international format
            df[col] = df[col].str.replace(r'^\+', '00', regex=True)
    
    # Parse timestamps
    if 'timestamp' in df.columns:
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    elif 'datetime' in df.columns:
        df['timestamp'] = pd.to_datetime(df['datetime'], errors='coerce')
    
    # Convert duration to seconds if not already (for calls)
    if 'duration' in df.columns:
        if df['duration'].dtype == 'object':
            # Try to parse HH:MM:SS format
            try:
                df['duration'] = pd.to_timedelta(df['duration']).dt.total_seconds()
            except:
                df['duration'] = pd.to_numeric(df['duration'], errors='coerce')
    
    return df
