"""
GCS Bucket Monitoring Sensor

Monitors Google Cloud Storage bucket for new bank/telecom files and ingests them
into the investigations platform automatically.

Workflow:
1. Poll GCS bucket for new files
2. Detect file type (bank transactions, call records, SMS)
3. Download from GCS
4. Upload to MinIO (investigations bucket)
5. Create data_source record
6. Trigger processing pipeline
"""

import os
import io
from datetime import datetime
from typing import Dict, Any, List, Optional

from dagster import (
    sensor,
    RunRequest,
    SkipReason,
    SensorEvaluationContext,
    DagsterRunStatus,
    DefaultSensorStatus
)
from google.cloud import storage
from google.oauth2 import service_account

from .resources import PostgresResource, MinioResource
from .file_detection import detect_file_type


# GCS Configuration
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME", "public_data_demo")
GCS_CREDENTIALS_PATH = os.getenv("GCS_CREDENTIALS_PATH", "/opt/dagster/gcs-credentials.json")
GCS_PREFIX = os.getenv("GCS_PREFIX", "investigations/")  # Only monitor this prefix

# Investigation mapping (based on folder structure in GCS)
# Format: investigations/{investigation_id}/{source_type}/{filename}
DEFAULT_INVESTIGATION_ID = os.getenv("DEFAULT_INVESTIGATION_ID", "GCS-AUTO")


def get_gcs_client() -> storage.Client:
    """
    Create authenticated GCS client
    
    Returns:
        GCS storage client
    """
    if os.path.exists(GCS_CREDENTIALS_PATH):
        credentials = service_account.Credentials.from_service_account_file(
            GCS_CREDENTIALS_PATH
        )
        return storage.Client(credentials=credentials)
    else:
        # Use default credentials (workload identity, ADC, etc.)
        return storage.Client()


def list_new_files(
    context: SensorEvaluationContext,
    last_checked: Optional[datetime] = None
) -> List[Dict[str, Any]]:
    """
    List new files in GCS bucket since last check
    
    Args:
        context: Sensor context for logging
        last_checked: Timestamp of last check (None = check all)
        
    Returns:
        List of new file metadata dicts
    """
    try:
        client = get_gcs_client()
        bucket = client.bucket(GCS_BUCKET_NAME)
        
        # List all blobs with prefix
        blobs = bucket.list_blobs(prefix=GCS_PREFIX)
        
        new_files = []
        
        for blob in blobs:
            # Skip directories
            if blob.name.endswith('/'):
                continue
            
            # Check if file is new
            if last_checked and blob.time_created <= last_checked:
                continue
            
            # Parse GCS path: investigations/{investigation_id}/{source_type}/{filename}
            path_parts = blob.name.split('/')
            
            if len(path_parts) >= 4:
                investigation_id = path_parts[1]
                source_type = path_parts[2]
                filename = path_parts[-1]
            else:
                # Fallback: use default investigation
                investigation_id = DEFAULT_INVESTIGATION_ID
                source_type = "unknown"
                filename = os.path.basename(blob.name)
            
            file_info = {
                'blob_name': blob.name,
                'filename': filename,
                'size': blob.size,
                'created': blob.time_created,
                'investigation_id': investigation_id,
                'source_type': source_type,
                'content_type': blob.content_type,
                'md5_hash': blob.md5_hash
            }
            
            new_files.append(file_info)
            
        context.log.info(f"Found {len(new_files)} new files in GCS bucket {GCS_BUCKET_NAME}")
        
        return new_files
        
    except Exception as e:
        context.log.error(f"Error listing GCS files: {str(e)}")
        return []


def download_from_gcs(blob_name: str) -> bytes:
    """
    Download file content from GCS
    
    Args:
        blob_name: Full blob path in bucket
        
    Returns:
        File content as bytes
    """
    client = get_gcs_client()
    bucket = client.bucket(GCS_BUCKET_NAME)
    blob = bucket.blob(blob_name)
    return blob.download_as_bytes()


def upload_to_minio(
    context: SensorEvaluationContext,
    minio: MinioResource,
    investigation_id: str,
    filename: str,
    content: bytes
) -> str:
    """
    Upload file to MinIO investigations bucket
    
    Args:
        context: Sensor context for logging
        minio: MinIO resource
        investigation_id: Investigation ID
        filename: Target filename
        content: File content
        
    Returns:
        MinIO file path
    """
    # Upload to MinIO under investigation folder
    minio_path = f"{investigation_id}/raw/{filename}"
    
    minio.upload_file(
        object_path=minio_path,
        data=content,
        content_type='text/csv'
    )
    
    context.log.info(f"Uploaded to MinIO: {minio_path}")
    
    return minio_path


def create_data_source_record(
    context: SensorEvaluationContext,
    postgres: PostgresResource,
    investigation_id: str,
    source_type: str,
    filename: str,
    file_size: int,
    minio_path: str,
    gcs_metadata: Dict[str, Any]
) -> str:
    """
    Create data_source record in database
    
    Args:
        context: Sensor context
        postgres: Postgres resource
        investigation_id: Investigation ID
        source_type: Type of data source
        filename: Original filename
        file_size: File size in bytes
        minio_path: Path in MinIO
        gcs_metadata: GCS metadata
        
    Returns:
        Generated source_id
    """
    import uuid
    
    source_id = f"gcs_{uuid.uuid4().hex[:12]}"
    
    with postgres.get_connection() as conn:
        with conn.cursor() as cur:
            # Check if investigation exists, create if not
            cur.execute("""
                INSERT INTO investigations (investigation_id, name, status, start_date)
                VALUES (%s, %s, 'active', CURRENT_DATE)
                ON CONFLICT (investigation_id) DO NOTHING
            """, (investigation_id, f"GCS Auto-Import: {investigation_id}"))
            
            # Insert data_source record
            import json
            metadata_json = json.dumps({
                'source': 'gcs',
                'gcs_bucket': GCS_BUCKET_NAME,
                'gcs_blob': gcs_metadata['blob_name'],
                'gcs_created': gcs_metadata['created'].isoformat(),
                'md5_hash': gcs_metadata['md5_hash']
            })
            
            cur.execute("""
                INSERT INTO data_sources (
                    source_id,
                    investigation_id,
                    source_type,
                    file_name,
                    file_path,
                    file_size_bytes,
                    received_date,
                    processing_status,
                    metadata
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, CURRENT_DATE, 'pending',
                    %s::jsonb
                )
            """, (
                source_id,
                investigation_id,
                source_type,
                filename,
                minio_path,
                file_size,
                metadata_json
            ))
            
            conn.commit()
    
    context.log.info(f"Created data_source record: {source_id}")
    
    return source_id


@sensor(
    name="gcs_bucket_monitor",
    description="Monitors GCS bucket for new investigation files and ingests them automatically",
    minimum_interval_seconds=60,  # Check every minute
    default_status=DefaultSensorStatus.RUNNING
)
def gcs_bucket_monitor(context: SensorEvaluationContext):
    """
    GCS Bucket Monitoring Sensor
    
    Workflow:
    1. List new files in GCS bucket
    2. Download and detect file type
    3. Upload to MinIO
    4. Create data_source record
    5. Trigger processing job
    
    Cursor: Stores last check timestamp to avoid reprocessing
    """
    from .resources import investigation_resources
    
    postgres = investigation_resources["postgres"]
    minio = investigation_resources["minio"]
    
    # Get last checked timestamp from cursor
    last_checked_str = context.cursor or None
    last_checked = datetime.fromisoformat(last_checked_str) if last_checked_str else None
    
    if last_checked:
        context.log.info(f"Checking GCS bucket for files since {last_checked}")
    else:
        context.log.info("First run - checking all files in GCS bucket")
    
    # List new files
    new_files = list_new_files(context, last_checked)
    
    if not new_files:
        return SkipReason(f"No new files in GCS bucket {GCS_BUCKET_NAME}")
    
    # Process each new file
    ingested_files = []
    
    for file_info in new_files:
        try:
            context.log.info(f"Processing GCS file: {file_info['filename']}")
            
            # Download from GCS
            content = download_from_gcs(file_info['blob_name'])
            
            # Detect file type
            detected_type = detect_file_type(file_info['filename'], content)
            
            if detected_type == 'unknown':
                context.log.warning(f"Could not detect file type for {file_info['filename']}, skipping")
                continue
            
            # Override source_type with detected type if it's more specific
            if file_info['source_type'] == 'unknown':
                file_info['source_type'] = detected_type
            
            # Upload to MinIO
            minio_path = upload_to_minio(
                context,
                minio,
                file_info['investigation_id'],
                file_info['filename'],
                content
            )
            
            # Create data_source record
            source_id = create_data_source_record(
                context,
                postgres,
                file_info['investigation_id'],
                file_info['source_type'],
                file_info['filename'],
                file_info['size'],
                minio_path,
                file_info
            )
            
            ingested_files.append({
                'source_id': source_id,
                'filename': file_info['filename'],
                'investigation_id': file_info['investigation_id'],
                'detected_type': detected_type
            })
            
        except Exception as e:
            context.log.error(f"Error processing {file_info['filename']}: {str(e)}")
            continue
    
    if not ingested_files:
        return SkipReason("All files failed processing or were skipped")
    
    # Update cursor to current timestamp
    new_cursor = datetime.utcnow().isoformat()
    
    # Trigger processing jobs based on file types
    run_requests = []
    
    # Group files by type
    bank_files = [f for f in ingested_files if 'transaction' in f['detected_type']]
    telecom_files = [f for f in ingested_files if f['detected_type'] in ['call_records', 'sms_records']]
    
    if bank_files:
        run_requests.append(
            RunRequest(
                run_key=f"gcs_bank_{new_cursor}",
                run_config={},
                tags={
                    "source": "gcs",
                    "file_count": str(len(bank_files)),
                    "files": ",".join([f['filename'] for f in bank_files])
                }
            )
        )
    
    if telecom_files:
        run_requests.append(
            RunRequest(
                run_key=f"gcs_telecom_{new_cursor}",
                run_config={},
                tags={
                    "source": "gcs",
                    "file_count": str(len(telecom_files)),
                    "files": ",".join([f['filename'] for f in telecom_files])
                }
            )
        )
    
    context.update_cursor(new_cursor)
    
    context.log.info(
        f"✅ Ingested {len(ingested_files)} files from GCS: "
        f"{len(bank_files)} bank, {len(telecom_files)} telecom"
    )
    
    return run_requests
