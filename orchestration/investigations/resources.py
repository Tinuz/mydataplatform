"""
Resources for investigations pipelines

Provides connections to:
- PostgreSQL (investigations database)
- MinIO (file storage)
- Investigation API (status updates)
- dbt CLI (canonical models)
"""

from dagster import ConfigurableResource
from dagster_dbt import DbtCliResource
from pydantic import Field
import psycopg2
from psycopg2.extras import RealDictCursor
from minio import Minio
from minio.error import S3Error
import httpx
from typing import Optional, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

import psycopg2
from psycopg2.extras import Json
import boto3
from dagster import ConfigurableResource
from dagster_dbt import DbtCliResource
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

from dagster import ConfigurableResource
from pydantic import Field
import psycopg2
from psycopg2.extras import RealDictCursor
from minio import Minio
from minio.error import S3Error
import httpx
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PostgresResource(ConfigurableResource):
    """PostgreSQL connection for investigations database"""
    
    host: str = Field(default="postgres", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    database: str = Field(default="superset", description="Database name")
    user: str = Field(default="superset", description="Database user")
    password: str = Field(default="superset", description="Database password")
    
    def get_connection(self):
        """Get database connection"""
        return psycopg2.connect(
            host=self.host,
            port=self.port,
            database=self.database,
            user=self.user,
            password=self.password,
            cursor_factory=RealDictCursor
        )
    
    def execute_query(self, query: str, params: Optional[Dict] = None) -> list:
        """Execute query and return results"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or {})
                if cursor.description:
                    return cursor.fetchall()
                conn.commit()
                return []
    
    def execute_update(self, query: str, params: Optional[Dict] = None) -> int:
        """Execute UPDATE/INSERT/DELETE/CREATE query and return affected rows"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or {})
                conn.commit()
                return cursor.rowcount if cursor.rowcount else 0
    
    def get_pending_sources(self) -> list:
        """Get data sources with pending processing status"""
        query = """
            SELECT source_id, investigation_id, file_name, file_path, source_type, provider
            FROM data_sources
            WHERE processing_status = 'pending'
            ORDER BY received_date ASC
        """
        return self.execute_query(query)
    
    def update_source_status(
        self,
        source_id: str,
        status: str,
        pipeline: Optional[str] = None,
        error_message: Optional[str] = None
    ):
        """Update data source processing status"""
        query = """
            UPDATE data_sources
            SET processing_status = %(status)s,
                processing_started_at = CASE WHEN %(status)s = 'processing' THEN NOW() ELSE processing_started_at END,
                processing_completed_at = CASE WHEN %(status)s IN ('completed', 'failed') THEN NOW() ELSE processing_completed_at END,
                processor_pipeline = COALESCE(%(pipeline)s, processor_pipeline),
                error_message = %(error_message)s,
                updated_at = NOW()
            WHERE source_id = %(source_id)s
        """
        self.execute_query(query, {
            'source_id': source_id,
            'status': status,
            'pipeline': pipeline,
            'error_message': error_message
        })
        logger.info(f"Updated {source_id} status to {status}")
    
    def insert_processed_record(
        self,
        investigation_id: str,
        source_id: str,
        record_type: str,
        record_date: str,
        parquet_path: str,
        summary: Dict[str, Any]
    ):
        """Insert processed record into index"""
        query = """
            INSERT INTO processed_records 
            (investigation_id, source_id, record_type, record_date, parquet_path, summary)
            VALUES (%(investigation_id)s, %(source_id)s, %(record_type)s, %(record_date)s, %(parquet_path)s, %(summary)s)
        """
        import json
        self.execute_query(query, {
            'investigation_id': investigation_id,
            'source_id': source_id,
            'record_type': record_type,
            'record_date': record_date,
            'parquet_path': parquet_path,
            'summary': json.dumps(summary)
        })
        logger.info(f"Indexed processed record for {source_id}")


class MinioResource(ConfigurableResource):
    """MinIO connection for file storage"""
    
    endpoint: str = Field(default="minio:9000", description="MinIO endpoint")
    access_key: str = Field(default="minio", description="MinIO access key")
    secret_key: str = Field(default="minio123", description="MinIO secret key")
    secure: bool = Field(default=False, description="Use HTTPS")
    bucket: str = Field(default="investigations", description="Bucket name")
    
    def get_client(self) -> Minio:
        """Get MinIO client"""
        return Minio(
            self.endpoint,
            access_key=self.access_key,
            secret_key=self.secret_key,
            secure=self.secure
        )
    
    def download_file(self, object_path: str) -> bytes:
        """Download file from MinIO"""
        client = self.get_client()
        
        # Remove s3://bucket/ prefix if present
        if object_path.startswith("s3://"):
            object_path = object_path.split("/", 3)[3]
        
        try:
            response = client.get_object(self.bucket, object_path)
            data = response.read()
            response.close()
            response.release_conn()
            logger.info(f"Downloaded file: {object_path}")
            return data
        except S3Error as e:
            logger.error(f"Error downloading file: {e}")
            raise
    
    def upload_file(self, object_path: str, data: bytes, content_type: str = "application/octet-stream"):
        """Upload file to MinIO"""
        from io import BytesIO
        client = self.get_client()
        
        try:
            client.put_object(
                bucket_name=self.bucket,
                object_name=object_path,
                data=BytesIO(data),
                length=len(data),
                content_type=content_type
            )
            logger.info(f"Uploaded file: {object_path}")
        except S3Error as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    def list_files(self, prefix: str) -> list:
        """List files with prefix"""
        client = self.get_client()
        
        try:
            objects = client.list_objects(self.bucket, prefix=prefix, recursive=True)
            files = []
            for obj in objects:
                files.append({
                    'name': obj.object_name,
                    'size': obj.size,
                    'last_modified': obj.last_modified
                })
            return files
        except S3Error as e:
            logger.error(f"Error listing files: {e}")
            raise


class InvestigationAPIResource(ConfigurableResource):
    """Investigation API client for status updates"""
    
    base_url: str = Field(default="http://investigations-api:8000", description="API base URL")
    
    def get_client(self) -> httpx.Client:
        """Get HTTP client"""
        return httpx.Client(base_url=self.base_url, timeout=30.0)
    
    def get_investigation(self, investigation_id: str) -> Dict:
        """Get investigation details"""
        client = self.get_client()
        response = client.get(f"/api/v1/investigations/{investigation_id}")
        response.raise_for_status()
        return response.json()
    
    def get_source(self, investigation_id: str, source_id: str) -> Dict:
        """Get data source details"""
        client = self.get_client()
        response = client.get(f"/api/v1/investigations/{investigation_id}/files/{source_id}")
        response.raise_for_status()
        return response.json()


# Resource configuration for local development
investigation_resources = {
    "postgres": PostgresResource(
        host="postgres",
        port=5432,
        database="superset",
        user="superset",
        password="superset"
    ),
    "minio": MinioResource(
        endpoint="minio:9000",
        access_key="minio",
        secret_key="minio12345",
        secure=False
    ),
    "api": InvestigationAPIResource(
        base_url="http://investigations-api:8000"
    ),
    "dbt": DbtCliResource(
        project_dir="/opt/dagster/dbt_investigations",
        profiles_dir="/opt/dagster/dbt_investigations",
        target="dev",
    ),
}
