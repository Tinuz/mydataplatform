from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text
from typing import List, Optional
from datetime import datetime, date
from enum import Enum
import logging

from app.database import get_db
from app.models import Investigation, DataSource
from app.schemas import (
    InvestigationCreate,
    InvestigationUpdate,
    InvestigationResponse,
    InvestigationSummary,
    MessageResponse
)
from app.minio_client import minio_client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/investigations", tags=["investigations"])


def get_current_user() -> str:
    """Get current user (simplified - implement proper auth later)"""
    return "test_user"


@router.post(
    "/",
    response_model=InvestigationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new investigation"
)
async def create_investigation(
    investigation: InvestigationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Create a new strafrechtelijk onderzoek
    
    - Generates unique investigation_id (format: OND-YYYY-NNNNNN)
    - Creates folder structure in MinIO
    - Returns complete investigation object
    """
    try:
        # Generate investigation_id
        year = investigation.start_date.year
        result = await db.execute(
            text("SELECT generate_investigation_id(:year)"),
            {"year": year}
        )
        investigation_id = result.scalar_one()
        
        # Create investigation record
        db_investigation = Investigation(
            investigation_id=investigation_id,
            name=investigation.name,
            description=investigation.description,
            start_date=investigation.start_date,
            end_date=investigation.end_date,
            status=investigation.status.value,
            lead_investigator=investigation.lead_investigator,
            team_members=investigation.team_members,
            retention_until=investigation.retention_until,
            metadata=investigation.metadata,
            created_by=current_user,
            updated_by=current_user
        )
        
        db.add(db_investigation)
        await db.commit()
        await db.refresh(db_investigation)
        
        # Create MinIO folder structure
        try:
            minio_client.create_investigation_structure(investigation_id)
        except Exception as e:
            logger.error(f"Error creating MinIO structure: {e}")
            # Don't fail the request, just log the error
        
        logger.info(f"Created investigation: {investigation_id}")
        return db_investigation
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Error creating investigation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create investigation: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[InvestigationSummary],
    summary="List all investigations"
)
async def list_investigations(
    status_filter: Optional[str] = None,
    lead_investigator: Optional[str] = None,
    start_date_from: Optional[date] = None,
    start_date_to: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    List all investigations with optional filters
    
    - Filter by status, lead investigator, date range
    - Returns summary with file counts and statistics
    - Pagination supported
    """
    try:
        # Use the investigation_summary view
        query = select(text("*")).select_from(text("investigation_summary"))
        
        # Apply filters (note: need to adjust for text query)
        conditions = []
        if status_filter:
            conditions.append(f"status = '{status_filter}'")
        if lead_investigator:
            conditions.append(f"lead_investigator = '{lead_investigator}'")
        if start_date_from:
            conditions.append(f"start_date >= '{start_date_from}'")
        if start_date_to:
            conditions.append(f"start_date <= '{start_date_to}'")
        
        if conditions:
            query = text(
                f"SELECT * FROM investigation_summary WHERE {' AND '.join(conditions)} "
                f"ORDER BY start_date DESC LIMIT {limit} OFFSET {skip}"
            )
        else:
            query = text(
                f"SELECT * FROM investigation_summary "
                f"ORDER BY start_date DESC LIMIT {limit} OFFSET {skip}"
            )
        
        result = await db.execute(query)
        investigations = result.mappings().all()
        
        return [InvestigationSummary(**dict(row)) for row in investigations]
        
    except Exception as e:
        logger.error(f"Error listing investigations: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list investigations: {str(e)}"
        )


@router.get(
    "/{investigation_id}",
    # response_model=InvestigationResponse,  # Disabled due to metadata serialization
    summary="Get investigation details"
)
async def get_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get detailed information about specific investigation"""
    try:
        result = await db.execute(
            select(Investigation).where(Investigation.investigation_id == investigation_id)
        )
        investigation = result.scalar_one_or_none()
        
        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        # Manual serialization to handle metadata and datetime fields
        return {
            "investigation_id": investigation.investigation_id,
            "name": investigation.name,
            "description": investigation.description,
            "status": investigation.status,
            "start_date": investigation.start_date.isoformat() if investigation.start_date and hasattr(investigation.start_date, "isoformat") else None,
            "end_date": investigation.end_date.isoformat() if investigation.end_date and hasattr(investigation.end_date, "isoformat") else None,
            "lead_investigator": investigation.lead_investigator,
            "team_members": investigation.team_members or [],
            "retention_until": investigation.retention_until.isoformat() if investigation.retention_until and hasattr(investigation.retention_until, "isoformat") else None,
            "metadata": investigation.investigation_metadata or {},  # Map to metadata in response
            "created_at": investigation.created_at.isoformat() if investigation.created_at and hasattr(investigation.created_at, "isoformat") else None,
            "updated_at": investigation.updated_at.isoformat() if investigation.updated_at and hasattr(investigation.updated_at, "isoformat") else None,
            "created_by": investigation.created_by,
            "updated_by": investigation.updated_by
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting investigation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get investigation: {str(e)}"
        )


@router.put(
    "/{investigation_id}",
    response_model=InvestigationResponse,
    summary="Update investigation"
)
async def update_investigation(
    investigation_id: str,
    investigation_update: InvestigationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Update investigation details"""
    try:
        # Get existing investigation
        result = await db.execute(
            select(Investigation).where(Investigation.investigation_id == investigation_id)
        )
        db_investigation = result.scalar_one_or_none()
        
        if not db_investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        # Update fields
        update_data = investigation_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if hasattr(db_investigation, field):
                if isinstance(value, Enum):
                    setattr(db_investigation, field, value.value)
                else:
                    setattr(db_investigation, field, value)
        
        db_investigation.updated_by = current_user
        
        await db.commit()
        await db.refresh(db_investigation)
        
        logger.info(f"Updated investigation: {investigation_id}")
        return db_investigation
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error updating investigation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update investigation: {str(e)}"
        )


@router.delete(
    "/{investigation_id}",
    response_model=MessageResponse,
    summary="Archive investigation"
)
async def archive_investigation(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Archive investigation (soft delete - sets status to 'archived')
    
    Note: To permanently delete, use DELETE /investigations/{id}/permanent
    """
    try:
        result = await db.execute(
            select(Investigation).where(Investigation.investigation_id == investigation_id)
        )
        db_investigation = result.scalar_one_or_none()
        
        if not db_investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        db_investigation.status = "archived"
        db_investigation.updated_by = current_user
        
        await db.commit()
        
        logger.info(f"Archived investigation: {investigation_id}")
        return MessageResponse(
            message=f"Investigation {investigation_id} archived successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Error archiving investigation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to archive investigation: {str(e)}"
        )


@router.get(
    "/{investigation_id}/summary",
    response_model=InvestigationSummary,
    summary="Get investigation summary"
)
async def get_investigation_summary(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """Get investigation summary with file counts and statistics"""
    try:
        query = text(
            "SELECT * FROM investigation_summary WHERE investigation_id = :inv_id"
        )
        result = await db.execute(query, {"inv_id": investigation_id})
        summary = result.mappings().one_or_none()
        
        if not summary:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        return InvestigationSummary(**dict(summary))
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting investigation summary: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get investigation summary: {str(e)}"
        )


@router.get(
    "/{investigation_id}/analytics",
    summary="Get investigation analytics statistics"
)
async def get_investigation_analytics(
    investigation_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: str = Depends(get_current_user)
):
    """
    Get analytics statistics from investigation_stats table
    
    Returns:
    - Total transactions, calls, messages
    - Unique IBANs, phone numbers, message participants
    - Activity date range and active days
    """
    try:
        # Query investigation_stats table
        query = text("""
            SELECT 
                investigation_id,
                investigation_name,
                total_transactions,
                total_transaction_amount,
                unique_ibans,
                total_calls,
                total_call_duration_hours,
                unique_phone_numbers,
                total_messages,
                unique_message_participants,
                first_activity_date,
                last_activity_date,
                active_days,
                updated_at
            FROM investigation_stats
            WHERE investigation_id = :inv_id
        """)
        
        result = await db.execute(query, {"inv_id": investigation_id})
        stats = result.mappings().one_or_none()
        
        if not stats:
            # Return empty stats if not yet processed
            return {
                "investigation_id": investigation_id,
                "total_transactions": 0,
                "total_transaction_amount": 0.0,
                "unique_ibans": 0,
                "total_calls": 0,
                "total_call_duration_hours": 0.0,
                "unique_phone_numbers": 0,
                "total_messages": 0,
                "unique_message_participants": 0,
                "first_activity_date": None,
                "last_activity_date": None,
                "active_days": 0,
                "updated_at": None
            }
        
        # Convert to dict and format dates
        result_dict = dict(stats)
        if result_dict.get('first_activity_date'):
            result_dict['first_activity_date'] = result_dict['first_activity_date'].isoformat()
        if result_dict.get('last_activity_date'):
            result_dict['last_activity_date'] = result_dict['last_activity_date'].isoformat()
        if result_dict.get('updated_at'):
            result_dict['updated_at'] = result_dict['updated_at'].isoformat()
        
        # Convert Decimal to float
        if 'total_transaction_amount' in result_dict:
            result_dict['total_transaction_amount'] = float(result_dict['total_transaction_amount'])
        if 'total_call_duration_hours' in result_dict:
            result_dict['total_call_duration_hours'] = float(result_dict['total_call_duration_hours'])
        
        return result_dict
        
    except Exception as e:
        logger.error(f"Error getting investigation analytics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get investigation analytics: {str(e)}"
        )


@router.get(
    "/{investigation_id}/metadata",
    summary="List validation metadata files"
)
async def list_validation_metadata(
    investigation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    List all validation metadata files for an investigation
    
    Returns list of metadata JSON files in metadata/ folder
    """
    try:
        # Verify investigation exists
        result = await db.execute(
            select(Investigation).where(Investigation.investigation_id == investigation_id)
        )
        investigation = result.scalar_one_or_none()
        
        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        # List metadata files
        files = minio_client.list_files(investigation_id, prefix="metadata/")
        
        # Filter out .keep files
        metadata_files = [
            {
                'filename': f['name'].split('/')[-1],
                'source_id': f['name'].split('/')[-1].replace('_validation.json', ''),
                'size': f['size'],
                'last_modified': f['last_modified'].isoformat() if f['last_modified'] else None
            }
            for f in files
            if f['name'].endswith('_validation.json')
        ]
        
        return {
            'investigation_id': investigation_id,
            'metadata_files': metadata_files,
            'total_count': len(metadata_files)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list metadata: {str(e)}"
        )


@router.get(
    "/{investigation_id}/metadata/{source_id}",
    summary="Get validation metadata for a source"
)
async def get_validation_metadata(
    investigation_id: str,
    source_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get validation metadata JSON for a specific source file
    
    Returns complete validation report including:
    - File statistics (row count, column count, size)
    - Data quality metrics (null counts, duplicates)
    - Data types
    - Validation status and errors
    - Type-specific statistics (amounts, dates, phone numbers, etc.)
    """
    try:
        # Verify investigation exists
        result = await db.execute(
            select(Investigation).where(Investigation.investigation_id == investigation_id)
        )
        investigation = result.scalar_one_or_none()
        
        if not investigation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Investigation {investigation_id} not found"
            )
        
        # Download metadata file
        metadata_path = f"{investigation_id}/metadata/{source_id}_validation.json"
        
        try:
            metadata_bytes = minio_client.get_file(metadata_path)
            import json
            metadata = json.loads(metadata_bytes.decode('utf-8'))
            return metadata
        except Exception as e:
            if 'NoSuchKey' in str(e) or 'does not exist' in str(e):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Validation metadata not found for source {source_id}"
                )
            raise
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting metadata: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get metadata: {str(e)}"
        )


