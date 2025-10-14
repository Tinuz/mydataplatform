from minio import Minio
from minio.error import S3Error
from app.config import settings
import io
from typing import BinaryIO
import logging

logger = logging.getLogger(__name__)


class MinioClient:
    """MinIO client for file operations"""
    
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_use_ssl
        )
        self.bucket = settings.minio_bucket
        self._ensure_bucket()
    
    def _ensure_bucket(self):
        """Create bucket if it doesn't exist"""
        try:
            if not self.client.bucket_exists(self.bucket):
                self.client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
        except S3Error as e:
            logger.error(f"Error creating bucket: {e}")
            raise
    
    def upload_file(
        self,
        investigation_id: str,
        file_obj: BinaryIO,
        file_name: str,
        file_size: int,
        content_type: str = "application/octet-stream"
    ) -> str:
        """
        Upload file to MinIO
        
        Args:
            investigation_id: Investigation ID
            file_obj: File object to upload
            file_name: Original filename
            file_size: File size in bytes
            content_type: MIME type
            
        Returns:
            S3 path to uploaded file
        """
        # Generate path: investigations/{investigation_id}/raw/{filename}
        object_path = f"{investigation_id}/raw/{file_name}"
        
        try:
            self.client.put_object(
                bucket_name=self.bucket,
                object_name=object_path,
                data=file_obj,
                length=file_size,
                content_type=content_type
            )
            
            s3_path = f"s3://{self.bucket}/{object_path}"
            logger.info(f"Uploaded file to: {s3_path}")
            return s3_path
            
        except S3Error as e:
            logger.error(f"Error uploading file: {e}")
            raise
    
    def get_file(self, object_path: str) -> bytes:
        """
        Get file from MinIO
        
        Args:
            object_path: Path without s3:// prefix
            
        Returns:
            File content as bytes
        """
        try:
            # Remove s3://bucket/ prefix if present
            if object_path.startswith("s3://"):
                object_path = object_path.split("/", 3)[3]
            
            response = self.client.get_object(self.bucket, object_path)
            data = response.read()
            response.close()
            response.release_conn()
            return data
            
        except S3Error as e:
            logger.error(f"Error getting file: {e}")
            raise
    
    def delete_file(self, object_path: str):
        """
        Delete file from MinIO
        
        Args:
            object_path: Path without s3:// prefix
        """
        try:
            # Remove s3://bucket/ prefix if present
            if object_path.startswith("s3://"):
                object_path = object_path.split("/", 3)[3]
            
            self.client.remove_object(self.bucket, object_path)
            logger.info(f"Deleted file: {object_path}")
            
        except S3Error as e:
            logger.error(f"Error deleting file: {e}")
            raise
    
    def list_files(self, investigation_id: str, prefix: str = "") -> list:
        """
        List files for investigation
        
        Args:
            investigation_id: Investigation ID
            prefix: Optional prefix (e.g., 'raw/', 'processed/')
            
        Returns:
            List of file objects
        """
        try:
            full_prefix = f"{investigation_id}/{prefix}"
            objects = self.client.list_objects(
                self.bucket,
                prefix=full_prefix,
                recursive=True
            )
            
            files = []
            for obj in objects:
                files.append({
                    "name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified,
                    "etag": obj.etag
                })
            
            return files
            
        except S3Error as e:
            logger.error(f"Error listing files: {e}")
            raise
    
    def create_investigation_structure(self, investigation_id: str):
        """
        Create folder structure for investigation
        
        Creates:
        - {investigation_id}/raw/
        - {investigation_id}/processed/
        - {investigation_id}/metadata/
        """
        # MinIO doesn't have folders, but we can create empty objects
        # to represent folder structure (optional)
        folders = ["raw/", "processed/", "metadata/"]
        
        for folder in folders:
            path = f"{investigation_id}/{folder}.keep"
            try:
                self.client.put_object(
                    bucket_name=self.bucket,
                    object_name=path,
                    data=io.BytesIO(b""),
                    length=0
                )
            except S3Error as e:
                logger.warning(f"Could not create folder marker {path}: {e}")
        
        logger.info(f"Created folder structure for investigation: {investigation_id}")


# Singleton instance
minio_client = MinioClient()
