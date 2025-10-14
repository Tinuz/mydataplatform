# Investigations Package - Dagster Pipelines

Automatische verwerking van strafrechtelijke onderzoeksgegevens.

## 📋 Overzicht

Dit package bevat Dagster pipelines voor het automatisch verwerken van geüploade bestanden naar onderzoeken:

1. **File Detection** - Detecteert bestandstype op basis van naam en inhoud
2. **Type-based Processing** - Routeert naar juiste processor (bank, telecom, forensic)
3. **Data Transformation** - Parseert en normaliseert data
4. **Parquet Storage** - Schrijft naar MinIO in gestructureerd formaat
5. **PostgreSQL Indexing** - Indexeert voor snelle search

## 🏗️ Architectuur

```
Upload File → MinIO (raw/)
    ↓
File Sensor (Dagster) - Check elke 30s
    ↓
detect_pending_files - Query database
    ↓
File Type Detection - Pattern + content matching
    ↓
    ├─→ Bank Transactions → process_bank_transactions
    ├─→ Call Records → process_telecom_calls
    ├─→ SMS Records → process_sms_records
    ├─→ WhatsApp → process_whatsapp
    ├─→ Forensic → process_forensic_metadata
    └─→ Social Media → process_social_media
         ↓
    Write Parquet → MinIO (processed/)
         ↓
    Index Summary → PostgreSQL (processed_records)
         ↓
    Update Status → data_sources.processing_status = 'completed'
```

## 📁 Package Structuur

```
orchestration/investigations/
├── __init__.py          # Package definition + exports
├── assets.py            # Dagster assets (processing logic)
├── sensors.py           # File upload sensor
├── jobs.py              # Pipeline definitions
├── resources.py         # Database + MinIO clients
├── file_detection.py    # File type detection
└── README.md            # This file
```

## 🔍 File Type Detection

### Supported File Types

| Type | Patterns | Keywords | Pipeline |
|------|----------|----------|----------|
| **Bank Transactions** | `*transacti*.csv`, `*mutaties*.csv` | iban, bedrag, tegenrekening | `bank_transaction_pipeline` |
| **Call Records** | `*call*.csv`, `*bel*.csv` | caller, callee, duration | `telecom_call_pipeline` |
| **SMS Records** | `*sms*.csv`, `*message*.csv` | sender, recipient, timestamp | `sms_processing_pipeline` |
| **WhatsApp** | `*whatsapp*.txt`, `*chat*.csv` | whatsapp, chat, message | `whatsapp_processing_pipeline` |
| **Forensic Metadata** | `*metadata*.json`, `*filesystem*.json` | file_path, hash, created_time | `forensic_metadata_pipeline` |
| **Social Media** | `*facebook*.json`, `*instagram*.json` | posts, friends, profile | `social_media_pipeline` |

### Detection Algorithm

```python
1. Filename Pattern Match (fast)
   - Check filename against regex patterns
   - High confidence if match

2. Content Inspection (fallback)
   - Read first 5 lines (CSV) or 1KB (JSON)
   - Count keyword matches
   - Medium confidence if ≥2 keywords match

3. Manual Type (if needed)
   - User can specify source_type on upload
   - Maps to appropriate pipeline
```

## 🔄 Processing Pipelines

### Bank Transaction Pipeline

**Input**: CSV met transacties  
**Required Columns**: `iban`, `bedrag`  
**Optional Columns**: `datum`, `tegenrekening`, `omschrijving`, `tegenpartij_naam`

**Processing Steps:**
1. Download CSV from MinIO
2. Parse with pandas
3. Normalize column names (lowercase, strip)
4. Add `investigation_id` and `source_id` to each row
5. Clean data:
   - Convert Dutch decimal format (1.234,56 → 1234.56)
   - Parse dates
   - Validate IBANs
   - Normalize names
6. Write to Parquet: `{investigation_id}/processed/transactions/{source_id}_transactions.parquet`
7. Index summary in PostgreSQL:
   ```json
   {
     "total_records": 1523,
     "total_amount": 145320.50,
     "date_range": {"min": "2025-01-01", "max": "2025-03-31"},
     "unique_ibans": 5
   }
   ```
8. Update `data_sources.processing_status = 'completed'`

**Output Schema** (Parquet):
```
investigation_id: string
source_id: string
iban: string
bedrag: float
datum: date
tegenrekening_iban: string
omschrijving: string
tegenpartij_naam: string
iban_valid: boolean
processed_at: timestamp
```

### Telecom Call Pipeline

**Input**: CSV met belgegevens  
**Required Columns**: `caller`, `callee`, `duration`  
**Optional**: `timestamp`, `cell_tower`, `imei`, `imsi`

**Processing Steps:**
1. Download CSV
2. Parse and normalize
3. Add investigation context
4. Clean data:
   - Normalize phone numbers (remove spaces, dashes)
   - Standardize format (00 prefix for international)
   - Parse timestamps
   - Convert duration to seconds
5. Write to Parquet: `{investigation_id}/processed/call_records/{source_id}_calls.parquet`
6. Index summary:
   ```json
   {
     "total_calls": 4567,
     "unique_callers": 23,
     "unique_callees": 156,
     "total_duration_minutes": 12450.5,
     "date_range": {"min": "2025-01-01", "max": "2025-03-31"}
   }
   ```

**Output Schema**:
```
investigation_id: string
source_id: string
caller: string
callee: string
timestamp: timestamp
duration: float (seconds)
cell_tower: string
imei: string
processed_at: timestamp
```

## 📊 Status Tracking

### Processing Status Flow

```
pending → processing → completed
             ↓
           failed
```

**Status Updates**:
- `pending`: Initial state after upload
- `processing`: Pipeline started
- `completed`: Successfully processed
- `failed`: Error occurred (with error_message)
- `skipped`: Unknown type or intentionally skipped

### Database Updates

**data_sources table**:
```sql
UPDATE data_sources
SET processing_status = 'completed',
    processing_started_at = '2025-10-13 10:30:00',
    processing_completed_at = '2025-10-13 10:32:15',
    processor_pipeline = 'bank_transaction_pipeline',
    updated_at = NOW()
WHERE source_id = 'SRC-2025-000001-001';
```

**processed_records table**:
```sql
INSERT INTO processed_records
(investigation_id, source_id, record_type, record_date, parquet_path, summary)
VALUES
('OND-2025-000001', 'SRC-2025-000001-001', 'transaction', '2025-01-01',
 's3://investigations/OND-2025-000001/processed/transactions/SRC-2025-000001-001_transactions.parquet',
 '{"total_records": 1523, "total_amount": 145320.50, ...}');
```

## 🚀 Usage

### 1. Upload File (via API)

```bash
curl -X POST "http://localhost:8000/api/v1/investigations/OND-2025-000001/upload" \
  -F "file=@ing_transactions_Q1.csv" \
  -F "source_type=bank" \
  -F "provider=ING Bank"

# Response:
{
  "source_id": "SRC-2025-000001-001",
  "processing_status": "pending"  # ← Sensor will detect this
}
```

### 2. Automatic Processing

File sensor automatically:
1. Detects new file (30s interval)
2. Determines file type
3. Triggers appropriate pipeline
4. Updates status throughout

### 3. Monitor Progress

```bash
# Check processing status
curl "http://localhost:8000/api/v1/investigations/OND-2025-000001/status"

# Get file details
curl "http://localhost:8000/api/v1/investigations/OND-2025-000001/files/SRC-2025-000001-001"
```

### 4. Query Processed Data

**DuckDB** (fast analytics):
```python
from crypto_stream.duckdb_helper import quick_query

# Query processed transactions
df = quick_query("""
    SELECT * FROM read_parquet('s3://investigations/OND-2025-000001/processed/transactions/*.parquet')
    WHERE bedrag > 10000
    ORDER BY datum DESC
""")
```

**PostgreSQL** (indexed search):
```sql
-- Find all bank transactions for investigation
SELECT * FROM processed_records
WHERE investigation_id = 'OND-2025-000001'
  AND record_type = 'transaction'
  AND summary->>'total_amount' > '50000';
```

## 🧪 Testing

### Test Upload Flow

```bash
# 1. Create test CSV
cat > test_transactions.csv << EOF
IBAN,Bedrag,Datum,Omschrijving,Tegenrekening
NL01BANK0123456789,1000.50,2025-10-13,Test transaction 1,NL02BANK9876543210
NL01BANK0123456789,2500.00,2025-10-14,Test transaction 2,NL03BANK1111111111
EOF

# 2. Upload via API
INV_ID="OND-2025-000001"  # Use existing investigation

curl -X POST "http://localhost:8000/api/v1/investigations/$INV_ID/upload" \
  -F "file=@test_transactions.csv" \
  -F "source_type=bank" \
  -F "provider=Test Bank"

# 3. Wait for processing (check Dagster UI)
open http://localhost:3000  # Dagster UI

# 4. Verify processed data
curl "http://localhost:8000/api/v1/investigations/$INV_ID/files" | jq

# 5. Query processed data
docker-compose exec dagster-webserver python -c "
from crypto_stream.duckdb_helper import quick_query
df = quick_query(\"\"\"
    SELECT investigation_id, COUNT(*) as records 
    FROM read_parquet('s3://investigations/$INV_ID/processed/transactions/*.parquet')
    GROUP BY investigation_id
\"\"\")
print(df)
"
```

## 🔧 Configuration

### Resources (resources.py)

```python
investigation_resources = {
    "postgres": PostgresResource(
        host="postgres",
        database="superset",
        user="superset",
        password="superset"
    ),
    "minio": MinioResource(
        endpoint="minio:9000",
        bucket="investigations"
    ),
    "api": InvestigationAPIResource(
        base_url="http://investigations-api:8000"
    )
}
```

### Sensor Configuration (sensors.py)

```python
@sensor(
    name="file_upload_sensor",
    minimum_interval_seconds=30,  # Check every 30s
)
```

## 📝 Extending with New File Types

### 1. Add File Type Definition

**file_detection.py**:
```python
FILE_PROCESSORS['new_type'] = {
    'description': 'Description of new type',
    'patterns': [r'.*pattern.*\.ext$'],
    'keywords': ['keyword1', 'keyword2'],
    'required_columns': ['col1', 'col2'],
    'pipeline': 'new_type_pipeline',
    'output_type': 'new_record_type'
}
```

### 2. Create Processing Asset

**assets.py**:
```python
@asset(group_name="investigations")
def process_new_type(
    context: AssetExecutionContext,
    postgres: PostgresResource,
    minio: MinioResource,
    detect_pending_files: Dict[str, Any]
) -> Dict[str, Any]:
    # Filter for new type files
    files = [f for f in detect_pending_files['detected_files']
             if f['detected_type'] == 'new_type']
    
    for file_info in files:
        # Your processing logic here
        pass
    
    return {'processed_files': len(files)}
```

### 3. Create Job

**jobs.py**:
```python
@job(name="process_new_type_job")
def process_new_type_job():
    files = detect_pending_files()
    process_new_type(files)
```

### 4. Update __init__.py

```python
from . import assets, sensors, jobs

defs = Definitions(
    assets=load_assets_from_modules([assets]),
    sensors=[sensors.file_upload_sensor],
    jobs=[
        jobs.process_bank_transactions_job,
        jobs.process_new_type_job,  # ← Add new job
    ],
    resources=resources.investigation_resources
)
```

## 🐛 Troubleshooting

### Files stuck in 'pending' status

**Check**:
```sql
SELECT source_id, file_name, received_date, processing_status
FROM data_sources
WHERE processing_status = 'pending'
ORDER BY received_date ASC;
```

**Fix**:
1. Check Dagster UI: http://localhost:3000
2. Check sensor is running: Sensors tab → file_upload_sensor
3. Manually trigger job: Jobs tab → process_all_pending_job → Launch Run

### Files marked as 'failed'

**Check error**:
```sql
SELECT source_id, file_name, error_message
FROM data_sources
WHERE processing_status = 'failed';
```

**Common issues**:
- Missing required columns → Check CSV headers
- Invalid format → Check file encoding (UTF-8)
- MinIO connection → Check minio service is running

**Reprocess**:
```sql
-- Reset status to pending
UPDATE data_sources
SET processing_status = 'pending',
    error_message = NULL,
    processing_started_at = NULL,
    processing_completed_at = NULL
WHERE source_id = 'SRC-2025-000001-001';
```

### Sensor not detecting files

**Check**:
```bash
# View sensor logs
docker-compose logs dagster-webserver | grep file_upload_sensor

# Check database connection
docker-compose exec dagster-webserver python -c "
from investigations.resources import PostgresResource
pg = PostgresResource()
print(pg.get_pending_sources())
"
```

## 📚 Related Documentation

- **API README**: `investigations-api/README.md`
- **Database Schema**: `postgres-init/02_init_investigations.sql`
- **Phase 1 Summary**: `INVESTIGATIONS_PHASE1_COMPLETE.md`
- **Dagster Docs**: https://docs.dagster.io/

## 🎯 Next Steps

- [ ] Add more file type processors (SMS, WhatsApp, forensic)
- [ ] Implement data quality checks
- [ ] Add Marquez lineage tracking
- [ ] Create Superset dashboards
- [ ] Add email notifications for processing failures
- [ ] Implement data retention policies
