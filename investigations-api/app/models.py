from sqlalchemy import Column, String, Date, TIMESTAMP, Text, BigInteger, Integer, ARRAY, JSON, CheckConstraint
from sqlalchemy.sql import func
from app.database import Base


class Investigation(Base):
    """Investigation model matching PostgreSQL schema"""
    __tablename__ = "investigations"
    
    investigation_id = Column(String(20), primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date)
    status = Column(String(20), nullable=False, default='active')
    lead_investigator = Column(String(100))
    team_members = Column(ARRAY(Text))
    retention_until = Column(Date)
    investigation_metadata = Column('metadata', JSON, default={})
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    created_by = Column(String(100))
    updated_by = Column(String(100))
    
    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'archived', 'closed')",
            name='check_investigation_status'
        ),
    )


class DataSource(Base):
    """Data source model for uploaded files"""
    __tablename__ = "data_sources"
    
    source_id = Column(String(30), primary_key=True)
    investigation_id = Column(String(20), nullable=False)
    source_type = Column(String(50), nullable=False)
    provider = Column(String(100))
    file_name = Column(String(255), nullable=False)
    file_path = Column(Text, nullable=False)
    file_size_bytes = Column(BigInteger)
    file_hash = Column(String(64))
    received_date = Column(Date, nullable=False)
    uploaded_by = Column(String(100))
    processing_status = Column(String(20), default='pending')
    processing_started_at = Column(TIMESTAMP)
    processing_completed_at = Column(TIMESTAMP)
    processor_pipeline = Column(String(100))
    error_message = Column(Text)
    source_metadata = Column('metadata', JSON, default={})
    created_at = Column(TIMESTAMP, server_default=func.now())
    updated_at = Column(TIMESTAMP, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        CheckConstraint(
            "processing_status IN ('pending', 'processing', 'completed', 'failed', 'skipped')",
            name='check_processing_status'
        ),
    )


class AuditLog(Base):
    """Audit log model for tracking all actions"""
    __tablename__ = "audit_log"
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    action = Column(String(50), nullable=False)
    investigation_id = Column(String(20))
    resource_type = Column(String(50))
    resource_id = Column(Text)
    ip_address = Column(String(45))  # INET as string
    user_agent = Column(Text)
    request_path = Column(Text)
    status_code = Column(Integer)
    error_message = Column(Text)
    log_metadata = Column('metadata', JSON, default={})
    timestamp = Column(TIMESTAMP, server_default=func.now())


class UserPermission(Base):
    """User permissions model for RBAC"""
    __tablename__ = "user_permissions"
    
    permission_id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    investigation_id = Column(String(20), nullable=False)
    role = Column(String(20), nullable=False)
    granted_by = Column(String(100))
    granted_at = Column(TIMESTAMP, server_default=func.now())
    expires_at = Column(TIMESTAMP)
    
    __table_args__ = (
        CheckConstraint(
            "role IN ('lead', 'member', 'analyst', 'auditor', 'viewer')",
            name='check_user_role'
        ),
    )
