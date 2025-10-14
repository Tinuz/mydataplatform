# Investigations API

REST API voor het beheren van strafrechtelijke onderzoeken en bijbehorende gegevens.

## 📋 Features

- **Investigation Management**: CRUD operaties voor onderzoeken
- **File Upload**: Upload bestanden met automatische opslag in MinIO
- **Processing Status**: Track verwerkingsstatus van bestanden  
- **Data Isolation**: Strikte scheiding per onderzoek
- **Audit Trail**: Complete logging van alle acties
- **Auto ID Generation**: Automatische ID generatie (OND-YYYY-NNNNNN)

## 🚀 Quick Start

### 1. Start de API

```bash
# Start met docker-compose (from project root)
docker-compose up investigations-api

# Of start de volledige stack
docker-compose --profile standard up
```

### 2. Access API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

## 📡 API Endpoints

### Investigations

#### Create Investigation
```bash
curl -X POST "http://localhost:8000/api/v1/investigations/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Operatie Test 2025",
    "description": "Test onderzoek voor platform",
    "start_date": "2025-01-15",
    "lead_investigator": "J. van der Berg",
    "team_members": ["A. de Vries", "P. Janssen"]
  }'
```

**Response:**
```json
{
  "investigation_id": "OND-2025-000002",
  "name": "Operatie Test 2025",
  "description": "Test onderzoek voor platform",
  "start_date": "2025-01-15",
  "status": "active",
  "lead_investigator": "J. van der Berg",
  "team_members": ["A. de Vries", "P. Janssen"],
  "created_at": "2025-10-13T10:30:00",
  "updated_at": "2025-10-13T10:30:00"
}
```

#### List Investigations
```bash
# All investigations
curl "http://localhost:8000/api/v1/investigations/"

# With filters
curl "http://localhost:8000/api/v1/investigations/?status=active&limit=10"
```

#### Get Investigation Details
```bash
curl "http://localhost:8000/api/v1/investigations/OND-2025-000002"
```

#### Get Investigation Summary
```bash
curl "http://localhost:8000/api/v1/investigations/OND-2025-000002/summary"
```

**Response includes:**
- Total files uploaded
- Processing status counts
- Total storage used
- Record counts

#### Update Investigation
```bash
curl -X PUT "http://localhost:8000/api/v1/investigations/OND-2025-000002" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "closed",
    "end_date": "2025-12-31"
  }'
```

#### Archive Investigation
```bash
curl -X DELETE "http://localhost:8000/api/v1/investigations/OND-2025-000002"
```

### File Upload & Management

#### Upload File
```bash
curl -X POST "http://localhost:8000/api/v1/investigations/OND-2025-000002/upload" \
  -F "file=@/path/to/ing_transactions.csv" \
  -F "source_type=bank" \
  -F "provider=ING Bank" \
  -F "received_date=2025-10-13"
```

**Response:**
```json
{
  "source_id": "SRC-2025-000002-001",
  "investigation_id": "OND-2025-000002",
  "file_name": "ing_transactions.csv",
  "file_size_bytes": 1048576,
  "file_path": "s3://investigations/OND-2025-000002/raw/ing_transactions.csv",
  "processing_status": "pending",
  "message": "File uploaded successfully. Processing will start automatically."
}
```

#### List Files
```bash
# All files for investigation
curl "http://localhost:8000/api/v1/investigations/OND-2025-000002/files"

# Filter by type and status
curl "http://localhost:8000/api/v1/investigations/OND-2025-000002/files?source_type=bank&processing_status=completed"
```

#### Get File Details
```bash
curl "http://localhost:8000/api/v1/investigations/OND-2025-000002/files/SRC-2025-000002-001"
```

#### Get Processing Status Overview
```bash
curl "http://localhost:8000/api/v1/investigations/OND-2025-000002/status"
```

**Response:**
```json
{
  "investigation_id": "OND-2025-000002",
  "status_by_source_type": {
    "bank": {
      "pending": {"count": 2, "total_bytes": 2097152},
      "completed": {"count": 5, "total_bytes": 10485760}
    },
    "telecom": {
      "processing": {"count": 1, "total_bytes": 524288}
    }
  }
}
```

#### Delete File
```bash
curl -X DELETE "http://localhost:8000/api/v1/investigations/OND-2025-000002/files/SRC-2025-000002-001"
```

## 🗄️ Database Schema

### Tables

**investigations**
- Primary table for onderzoeken
- Includes metadata, team members, retention policy
- Auto-generated ID: `OND-YYYY-NNNNNN`

**data_sources**
- Tracks uploaded files
- Processing status and pipeline info
- SHA256 file hash for integrity

**processed_records**
- Index layer for processed data
- Full data in Parquet files
- Summary in JSONB for quick search

**audit_log**
- Complete audit trail
- All user actions tracked
- IP address, user agent, timestamps

**user_permissions**
- Role-based access control
- Per-investigation permissions
- Roles: lead, member, analyst, auditor, viewer

### Views

**investigation_summary**
- Aggregated statistics per investigation
- File counts, storage usage
- Processing status overview

**processing_status_overview**
- Processing metrics
- Group by investigation, source type, status

## 🏗️ File Storage Structure

```
s3://investigations/
├── OND-2025-000001/
│   ├── raw/                    # Original files
│   │   ├── ing_transactions.csv
│   │   ├── kpn_call_records.csv
│   │   └── whatsapp_export.json
│   ├── processed/              # Processed Parquet files
│   │   ├── transactions/
│   │   ├── call_records/
│   │   └── messages/
│   └── metadata/               # Investigation metadata
│       └── processing_log.json
├── OND-2025-000002/
└── ...
```

## 🔒 Security

### Authentication (TODO)
Currently uses simple mock user. **In production:**
- Implement JWT token authentication
- Integrate with organization's SSO/LDAP
- Add API key support for service accounts

### Authorization (TODO)
- Row-level security in PostgreSQL
- Role-based access per investigation
- Audit all data access

### Data Protection
- All files hashed (SHA256) on upload
- Audit trail for compliance
- Data retention policies enforced

## 🧪 Testing

### Manual Testing

```bash
# 1. Create investigation
INV_ID=$(curl -s -X POST "http://localhost:8000/api/v1/investigations/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Investigation",
    "start_date": "2025-10-13",
    "lead_investigator": "Test User"
  }' | jq -r '.investigation_id')

echo "Created: $INV_ID"

# 2. Upload file
curl -X POST "http://localhost:8000/api/v1/investigations/$INV_ID/upload" \
  -F "file=@test_data.csv" \
  -F "source_type=bank" \
  -F "provider=Test Bank"

# 3. Check status
curl "http://localhost:8000/api/v1/investigations/$INV_ID/summary" | jq

# 4. List files
curl "http://localhost:8000/api/v1/investigations/$INV_ID/files" | jq
```

### Unit Tests (TODO)
```bash
cd investigations-api
pytest tests/
```

## 🔧 Development

### Local Development

```bash
# Install dependencies
cd investigations-api
pip install -r requirements.txt

# Run locally (requires PostgreSQL and MinIO)
uvicorn app.main:app --reload --port 8000
```

### Environment Variables

Copy `.env.example` to `.env` and adjust:

```bash
# Database
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/investigations

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123
MINIO_BUCKET=investigations

# Security
SECRET_KEY=your-secret-key-here

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

## 📊 Integration with Data Platform

### 1. Dagster Pipelines (Next Step)
- File detection sensor
- Automatic processing based on file type
- Update processing status in database

### 2. Superset Dashboards (Next Step)
- Investigation overview dashboard
- Processing status monitoring
- Cross-investigation analytics

### 3. Marquez Lineage (Next Step)
- Track data lineage from raw to processed
- Pipeline execution tracking
- Data quality monitoring

## 🐛 Troubleshooting

### API won't start
```bash
# Check logs
docker-compose logs investigations-api

# Check database connection
docker-compose exec investigations-api python -c "from app.database import engine; print('DB OK')"

# Check MinIO connection
docker-compose exec investigations-api python -c "from app.minio_client import minio_client; print('MinIO OK')"
```

### Database schema not created
```bash
# Re-run init script
docker-compose exec postgres psql -U superset -f /docker-entrypoint-initdb.d/02_init_investigations.sql
```

### File upload fails
- Check MinIO is running: `docker-compose ps minio`
- Check bucket exists: `docker-compose exec minio mc ls local/investigations`
- Check disk space

## 🚀 Next Steps

1. ✅ **Phase 1: API Foundation** (CURRENT)
   - Basic CRUD operations
   - File upload/download
   - MinIO integration

2. **Phase 2: Auto Processing**
   - Dagster file detection sensor
   - Bank transaction pipeline
   - Status updates from pipelines

3. **Phase 3: Advanced Features**
   - JWT authentication
   - Role-based access control
   - DuckDB query interface
   - Superset dashboard integration

4. **Phase 4: Production Ready**
   - Comprehensive tests
   - Performance optimization
   - Security hardening
   - Documentation completion

## 📚 API Reference

Full API reference available at:
- **Swagger**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 📝 License

Internal use only - [Organization Name]
