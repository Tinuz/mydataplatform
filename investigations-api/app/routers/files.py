from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func
from typing import List, Optional
from datetime import date, datetime
import hashlib
import logging

from app.database import get_db
from app.models import Investigation, DataSource
from app.schemas import (
    DataSourceResponse,
    FileUploadResponse,
    MessageResponse
)
from app.minio_client import minio_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investigations", tags=["files"])


def get_current_user() -> str:
    """Get current user (simplified - implement proper auth later)"""
    return "test_user"


@router.post(
    "/{investigation_id}/upload",
    response_model=FileUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload file to investigation"
)
async def upload_file(
    investigation_id: str,
    file: UploadFile = File(..., description="File to upload"),
    source_type: str = Form(..., description="Type of data source (bank, telecom, etc.)"),
    provider: Optional[str] = Form(None, description="Data provider (ING, KPN, etc.)"),
    received_date: Optional[str] = Form(None, description="Date received (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Upload file to investigation
    
    - Validates investigation exists
    - Generates unique source_id
    - Uploads file to MinIO
    - Creates data_source record
    - Triggers processing (future: Dagster sensor)
    """
    try:
        # Validate investigation exists
        result = await db.execute(
            select(Investigation).where(Investigation.investigation_id == investigation_id)
        )
        investigation = result.scalar_one_or_none()
        
        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        # Parse received_date
        if received_date:
            try:
                received_date_obj = datetime.strptime(received_date, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid date format. Use YYYY-MM-DD"
                )
        else:
            received_date_obj = date.today()
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Calculate SHA256 hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # Generate source_id
        result = await db.execute(
            text("SELECT generate_source_id(:inv_id)"),
            {"inv_id": investigation_id}
        )
        source_id = result.scalar_one()
        
        # Upload to MinIO
        from io import BytesIO
        file_obj = BytesIO(file_content)
        
        s3_path = minio_client.upload_file(
            investigation_id=investigation_id,
            file_obj=file_obj,
            file_name=file.filename,
            file_size=file_size,
            content_type=file.content_type or "application/octet-stream"
        )
        
        # Create data_source record
        db_source = DataSource(
            source_id=source_id,
            investigation_id=investigation_id,
            source_type=source_type,
            provider=provider,
            file_name=file.filename,
            file_path=s3_path,
            file_size_bytes=file_size,
            file_hash=file_hash,
            received_date=received_date_obj,
            uploaded_by=current_user,
            processing_status="pending"
        )
        
        db.add(db_source)
        await db.commit()
        await db.refresh(db_source)
        
        logger.info(f"Uploaded file {file.filename} to investigation {investigation_id}")
        
        return FileUploadResponse(
            source_id=source_id,
            investigation_id=investigation_id,
            file_name=file.filename,
            file_size_bytes=file_size,
            file_path=s3_path,
            processing_status=db_source.processing_status,
            message=f"File uploaded successfully. Processing will start automatically."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.get(
    "/{investigation_id}/files",
    # response_model=List[DataSourceResponse],  # Disabled to avoid metadata serialization issues
    summary="List files for investigation"
)
async def list_files(
    investigation_id: str,
    source_type: Optional[str] = None,
    processing_status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    List all files for investigation
    
    - Optional filters by source_type and processing_status
    - Pagination supported
    """
    try:
        # Build query
        query = select(DataSource).where(DataSource.investigation_id == investigation_id)
        
        if source_type:
            query = query.where(DataSource.source_type == source_type)
        if processing_status:
            query = query.where(DataSource.processing_status == processing_status)
        
        query = query.order_by(DataSource.received_date.desc())
        query = query.offset(skip).limit(limit)
        
        result = await db.execute(query)
        files = result.scalars().all()
        
        # Manual conversion to handle datetime serialization
        return [{
            "source_id": f.source_id,
            "investigation_id": f.investigation_id,
            "source_type": f.source_type,
            "provider": f.provider,
            "file_name": f.file_name,
            "file_path": f.file_path,
            "file_size_bytes": f.file_size_bytes,
            "file_hash": f.file_hash,
            "received_date": f.received_date.isoformat() if hasattr(f.received_date, "isoformat") else str(f.received_date),
            "uploaded_by": f.uploaded_by,
            "processing_status": f.processing_status,
            "processing_started_at": f.processing_started_at.isoformat() if f.processing_started_at and hasattr(f.processing_started_at, "isoformat") else None,
            "processing_completed_at": f.processing_completed_at.isoformat() if f.processing_completed_at and hasattr(f.processing_completed_at, "isoformat") else None,
            "processor_pipeline": f.processor_pipeline,
            "error_message": f.error_message,
            "metadata": f.source_metadata or {},
            "created_at": f.created_at.isoformat() if f.created_at and hasattr(f.created_at, "isoformat") else None,
            "updated_at": f.updated_at.isoformat() if f.updated_at and hasattr(f.updated_at, "isoformat") else None
        } for f in files]
        
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.get(
    "/{investigation_id}/files/{source_id}",
    response_model=DataSourceResponse,
    summary="Get file details"
)
async def get_file_details(
    investigation_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about specific file"""
    try:
        result = await db.execute(
            select(DataSource).where(
                DataSource.source_id == source_id,
                DataSource.investigation_id == investigation_id
            )
        )
        file = result.scalar_one_or_none()
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {source_id} not found in investigation {investigation_id}"
            )
        
        return file
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting file details: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file details: {str(e)}"
        )


@router.delete(
    "/{investigation_id}/files/{source_id}",
    response_model=MessageResponse,
    summary="Delete file"
)
async def delete_file(
    investigation_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Delete file from investigation
    
    - Deletes from MinIO
    - Removes database record (cascade deletes processed_records)
    """
    try:
        # Get file record
        result = await db.execute(
            select(DataSource).where(
                DataSource.source_id == source_id,
                DataSource.investigation_id == investigation_id
            )
        )
        file = result.scalar_one_or_none()
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {source_id} not found"
            )
        
        # Delete from MinIO
        try:
            minio_client.delete_file(file.file_path)
        except Exception as e:
            logger.warning(f"Could not delete file from MinIO: {e}")
            # Continue with database deletion even if MinIO fails
        
        # Delete database record
        await db.delete(file)
        await db.commit()
        
        logger.info(f"Deleted file {source_id} from investigation {investigation_id}")
        
        return MessageResponse(
            message=f"File {source_id} deleted successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.post(
    "/{investigation_id}/files/{source_id}/retry",
    response_model=MessageResponse,
    summary="Retry processing file"
)
async def retry_processing(
    investigation_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Retry processing a failed or pending file
    
    - Resets processing status to 'pending'
    - Clears error messages
    - Dagster sensor will pick it up automatically
    """
    try:
        # Get file record
        result = await db.execute(
            select(DataSource).where(
                DataSource.source_id == source_id,
                DataSource.investigation_id == investigation_id
            )
        )
        file = result.scalar_one_or_none()
        
        if not file:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File {source_id} not found"
            )
        
        # Check if retry is allowed
        if file.processing_status == 'completed':
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot retry a successfully completed file"
            )
        
        # Reset status to pending
        file.processing_status = 'pending'
        file.error_message = None
        file.processing_started_at = None
        file.processing_completed_at = None
        file.updated_at = func.now()
        
        await db.commit()
        
        logger.info(f"Reset file {source_id} to pending for retry")
        
        return MessageResponse(
            message=f"File {source_id} queued for reprocessing. Dagster will pick it up shortly."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error retrying file processing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry processing: {str(e)}"
        )


@router.get(
    "/{investigation_id}/status",
    summary="Get processing status overview"
)
async def get_processing_status(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get processing status overview for investigation
    
    Returns counts by status and source_type
    """
    try:
        query = text("""
            SELECT 
                source_type,
                processing_status,
                COUNT(*) as count,
                SUM(file_size_bytes) as total_bytes
            FROM data_sources
            WHERE investigation_id = :inv_id
            GROUP BY source_type, processing_status
        """)
        
        result = await db.execute(query, {"inv_id": investigation_id})
        rows = result.mappings().all()
        
        # Format response
        status_overview = {}
        for row in rows:
            source_type = row["source_type"]
            if source_type not in status_overview:
                status_overview[source_type] = {}
            
            status_overview[source_type][row["processing_status"]] = {
                "count": row["count"],
                "total_bytes": row["total_bytes"]
            }
        
        return {
            "investigation_id": investigation_id,
            "status_by_source_type": status_overview
        }
        
    except Exception as e:
        logger.error(f"Error getting processing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get processing status: {str(e)}"
        )
