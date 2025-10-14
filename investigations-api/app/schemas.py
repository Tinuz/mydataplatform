from pydantic import BaseModel, Field, validator, model_validator
from typing import Optional, List, Dict, Any
from datetime import date, datetime
from enum import Enum


class InvestigationStatus(str, Enum):
    """Investigation status enum"""
    active = "active"
    archived = "archived"
    closed = "closed"


class ProcessingStatus(str, Enum):
    """File processing status enum"""
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class UserRole(str, Enum):
    """User role enum"""
    lead = "lead"
    member = "member"
    analyst = "analyst"
    auditor = "auditor"
    viewer = "viewer"


# ============================================================================
# Investigation Schemas
# ============================================================================

class InvestigationBase(BaseModel):
    """Base investigation schema"""
    name: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    start_date: date
    end_date: Optional[date] = None
    lead_investigator: Optional[str] = Field(None, max_length=100)
    team_members: Optional[List[str]] = []
    retention_until: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = {}
    
    @validator('end_date')
    def end_date_must_be_after_start(cls, v, values):
        if v and 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v


class InvestigationCreate(InvestigationBase):
    """Schema for creating investigation"""
    status: Optional[InvestigationStatus] = InvestigationStatus.active


class InvestigationUpdate(BaseModel):
    """Schema for updating investigation"""
    name: Optional[str] = Field(None, min_length=3, max_length=255)
    description: Optional[str] = None
    end_date: Optional[date] = None
    status: Optional[InvestigationStatus] = None
    lead_investigator: Optional[str] = Field(None, max_length=100)
    team_members: Optional[List[str]] = None
    retention_until: Optional[date] = None
    metadata: Optional[Dict[str, Any]] = None


class InvestigationResponse(InvestigationBase):
    """Schema for investigation response"""
    investigation_id: str
    status: InvestigationStatus
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None
    
    @model_validator(mode='before')
    @classmethod
    def map_metadata(cls, data: Any) -> Any:
        """Map investigation_metadata to metadata for serialization"""
        if isinstance(data, dict):
            if 'investigation_metadata' in data and 'metadata' not in data:
                data['metadata'] = data['investigation_metadata']
        elif hasattr(data, 'investigation_metadata'):
            if not hasattr(data, 'metadata') or data.metadata is None:
                # Create a dict from the model for modification
                data_dict = {k: getattr(data, k) for k in dir(data) if not k.startswith('_')}
                data_dict['metadata'] = data.investigation_metadata or {}
                return data_dict
        return data
    
    class Config:
        from_attributes = True


class InvestigationSummary(BaseModel):
    """Summary schema with file counts"""
    investigation_id: str
    name: str
    status: InvestigationStatus
    start_date: date
    lead_investigator: Optional[str]
    total_files: int = 0
    processed_files: int = 0
    failed_files: int = 0
    total_records: int = 0
    total_storage_bytes: int = 0
    last_file_received: Optional[date] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Data Source Schemas
# ============================================================================

class DataSourceBase(BaseModel):
    """Base data source schema"""
    source_type: str = Field(..., max_length=50)
    provider: Optional[str] = Field(None, max_length=100)
    metadata: Optional[Dict[str, Any]] = {}


class DataSourceCreate(DataSourceBase):
    """Schema for creating data source (used internally)"""
    investigation_id: str
    file_name: str
    file_path: str
    file_size_bytes: Optional[int] = None
    file_hash: Optional[str] = None
    received_date: date
    uploaded_by: Optional[str] = None


class DataSourceResponse(DataSourceBase):
    """Schema for data source response"""
    source_id: str
    investigation_id: str
    file_name: str
    file_path: str
    file_size_bytes: Optional[int]
    file_hash: Optional[str]
    received_date: date
    uploaded_by: Optional[str]
    processing_status: ProcessingStatus
    processing_started_at: Optional[datetime]
    processing_completed_at: Optional[datetime]
    processor_pipeline: Optional[str]
    error_message: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    @model_validator(mode='before')
    @classmethod
    def map_metadata(cls, data: Any) -> Any:
        """Map source_metadata to metadata for serialization"""
        if isinstance(data, dict):
            if 'source_metadata' in data and 'metadata' not in data:
                data['metadata'] = data['source_metadata']
        elif hasattr(data, 'source_metadata'):
            if not hasattr(data, 'metadata') or data.metadata is None:
                # Create a dict from the model for modification
                data_dict = {k: getattr(data, k) for k in dir(data) if not k.startswith('_')}
                data_dict['metadata'] = data.source_metadata or {}
                return data_dict
        return data
    
    class Config:
        from_attributes = True


class DataSourceUpdate(BaseModel):
    """Schema for updating data source"""
    processing_status: Optional[ProcessingStatus] = None
    processor_pipeline: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


# ============================================================================
# File Upload Schemas
# ============================================================================

class FileUploadResponse(BaseModel):
    """Response after file upload"""
    source_id: str
    investigation_id: str
    file_name: str
    file_size_bytes: int
    file_path: str
    processing_status: ProcessingStatus
    message: str


# ============================================================================
# Audit Log Schemas
# ============================================================================

class AuditLogCreate(BaseModel):
    """Schema for creating audit log"""
    user_id: str
    action: str
    investigation_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    request_path: Optional[str] = None
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}


class AuditLogResponse(BaseModel):
    """Schema for audit log response"""
    log_id: int
    user_id: str
    action: str
    investigation_id: Optional[str]
    resource_type: Optional[str]
    resource_id: Optional[str]
    timestamp: datetime
    
    class Config:
        from_attributes = True


# ============================================================================
# Generic Responses
# ============================================================================

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str


class ErrorResponse(BaseModel):
    """Error response"""
    detail: str
    error_code: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MessageResponse(BaseModel):
    """Generic message response"""
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
