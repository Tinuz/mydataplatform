# Data Platform Pipeline Overview

## Complete Pipeline Flow

The investigation-detail.html now shows the complete end-to-end data pipeline with 7 stages:

### 1. 📤 Upload (File to MinIO/GCS)
- **Sources**: Direct upload to MinIO OR automatic detection from GCS bucket
- **GCS Integration**: `gcs_bucket_monitor` sensor polls `gs://public_data_demo` every 60s
- **Path format**: `investigations/{investigation_id}/{source_type}/{filename}`
- **Storage**: Files stored in MinIO `investigations` bucket

### 2. 🔍 Detect (Sensor 30s)
- **Sensor**: `file_upload_sensor` checks MinIO every 30 seconds
- **Triggers**: `process_bank_transactions` or `process_telecom_calls/messages` assets
- **Status**: Investigation moves from `pending` → `processing`

### 3. ⚙️ Process (Raw tables)
- **Target schemas**: `raw_transactions`, `raw_calls`, `raw_messages`
- **Column mapping**: Handles heterogeneous data sources (7 providers: Bank A-D, Telecom A-C)
- **Validation**: IBAN/MSISDN validation, amount/duration checks
- **Output**: Clean, validated raw data ready for transformation

### 4. 🔄 Canonical (dbt: clean_*)
- **Sensor**: `check_canonical_data` checks every 60 seconds for unmapped raw data
- **dbt models**: 
  - `clean_bank_transactions` → `canonical_transaction`
  - `clean_call_records` + `clean_message_records` → `canonical_communication`
- **Process**: Schema standardization, deduplication, enrichment
- **Output**: Provider-agnostic canonical layer

### 5. 📊 Staging (dbt: stg_*)
- **Sensor**: `check_staging_data` monitors canonical layer changes
- **dbt models**:
  - `stg_transactions` (from `canonical_transaction`)
  - `stg_communications` (from `canonical_communication`)
- **Process**: Business rules, derived fields, type conversions
- **Output**: Analytics-ready staging tables

### 6. ✨ Analytical (dbt: fact_*)
- **Sensor**: `check_analytical_data` monitors staging layer changes
- **dbt models**:
  - `fact_financial_network` (transaction patterns, IBAN relationships)
  - `fact_communication_pattern` (call/SMS patterns, MSISDN relationships)
- **Process**: Aggregations, network analysis, pattern detection
- **Output**: Fact tables for analysis and visualization

### 7. ✓ Complete (Ready for analysis)
- **Status**: Investigation marked as `completed`
- **Available in**: Superset dashboards, Trino queries, Dagster lineage
- **Total time**: ~2-3 minutes from upload to analytical layer

## Automated Pipeline Card (investigation-detail.html)

The "Automated Pipeline" section now shows 6 key components:

1. **File Detection (30s)**: MinIO/GCS upload monitoring
2. **Raw Processing**: Auto-load to raw tables
3. **Canonical Layer (60s dbt sensor)**: Schema standardization
4. **Staging Layer**: stg_transactions, stg_communications
5. **Analytical Layer**: fact_financial_network, fact_communication_pattern
6. **Total Throughput**: Upload → Analytical in ~2-3 minutes

## Visual Pipeline Representation

```
┌─────────────────────────────────────────────────────────────────────┐
│                     DATA INGESTION LAYER                            │
├─────────────────────────────────────────────────────────────────────┤
│  📤 Upload (MinIO/GCS)  →  🔍 Detect (30s sensor)                  │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                        RAW DATA LAYER                               │
├─────────────────────────────────────────────────────────────────────┤
│  ⚙️ Process → raw_transactions / raw_calls / raw_messages          │
│  (Column mapping, validation, heterogeneous source handling)        │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     CANONICAL DATA LAYER (dbt)                      │
├─────────────────────────────────────────────────────────────────────┤
│  🔄 Canonical (60s sensor) → canonical_transaction / canonical_comm │
│  (Schema standardization, deduplication, provider-agnostic)         │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                      STAGING DATA LAYER (dbt)                       │
├─────────────────────────────────────────────────────────────────────┤
│  📊 Staging → stg_transactions / stg_communications                 │
│  (Business rules, derived fields, type conversions)                 │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    ANALYTICAL DATA LAYER (dbt)                      │
├─────────────────────────────────────────────────────────────────────┤
│  ✨ Analytical → fact_financial_network / fact_communication_pattern│
│  (Aggregations, network analysis, pattern detection)                │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                          READY FOR USE                              │
├─────────────────────────────────────────────────────────────────────┤
│  ✓ Complete → Superset / Trino / Marquez                           │
│  (Visualization, ad-hoc queries, lineage tracking)                  │
└─────────────────────────────────────────────────────────────────────┘
```

## Changes Made to investigation-detail.html

### 1. Updated `getPipelineHTML()` function (lines 900-997)

**Before** (6 steps):
- Upload → Detect → Process → Map → Canonical → Complete
- Ended at "Ready for dbt"
- Missing dbt transformation stages

**After** (7 steps):
- Upload (MinIO/GCS) → Detect → Process → Canonical (dbt) → Staging (dbt) → Analytical (dbt) → Complete
- Shows complete data transformation pipeline
- Includes specific dbt model references

### 2. Updated "Automated Pipeline" card (lines 670-720)

**Before** (4 components):
- File Detection → Auto Processing → Canonical Mapping → Total Time (90s)
- Missing staging and analytical layers

**After** (6 components):
- File Detection (MinIO/GCS) → Raw Processing → Canonical Layer → Staging Layer → Analytical Layer → Total Time (2-3 min)
- Shows complete dbt pipeline with model names
- Updated total time to reflect full pipeline

## Key Benefits

1. **Complete Visibility**: Users see the entire data flow from upload to analytics
2. **GCS Integration**: Shows GCS as an ingestion source alongside MinIO
3. **dbt Transparency**: Clear visibility of dbt transformation layers and model names
4. **Accurate Timing**: Realistic end-to-end timing (~2-3 minutes vs. ~90 seconds)
5. **Educational**: Users understand the multi-layer architecture (Raw → Canonical → Staging → Analytical)

## Testing

To see the updated pipeline visualization:

1. Start the platform: `docker-compose up -d`
2. Upload a test file or trigger GCS ingestion
3. Open: `http://localhost:8090/investigation-detail.html?id=OND-2025-000001`
4. Check the pipeline progress bar shows all 7 stages
5. Check the "Automated Pipeline" card shows all 6 components

## Related Files

- **investigation-detail.html**: Main UI file with pipeline visualization
- **orchestration/investigations/assets.py**: Raw processing assets
- **orchestration/investigations/dbt_assets.py**: dbt transformation assets
- **orchestration/investigations/gcs_sensor.py**: GCS bucket monitoring
- **dbt/investigations/**: dbt models (canonical, staging, analytical)

## Commit

```
commit dbe7244
feat: Update investigation detail page with complete pipeline visualization

- 7-stage pipeline: Upload → Detect → Process → Canonical → Staging → Analytical → Complete
- 6-component automation card showing all dbt layers
- Fixed corrupted emoji, updated timing to 2-3 minutes
- Added dbt model references in descriptions
```
