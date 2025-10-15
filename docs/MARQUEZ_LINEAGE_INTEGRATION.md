# Marquez Lineage Integration - Canonical Data Model

## 📊 Overzicht

Marquez is ge integreerd met het canonical data model om **end-to-end data lineage** te tracken van raw sources → canonical layer → dbt models.

## 🎯 Wat wordt getrackt?

### 1. **Canonical Mapping Jobs**

Twee hoofdjobs die raw data mappen naar canonical layer:

#### `canonical_transactions`
- **Input**: `investigations-raw.bank_a.raw_transactions`
- **Output**: `canonical-integration.canonical.canonical_transaction`
- **Metrics**:
  - Total records processed
  - Valid records (validation_status='valid')
  - Warning records (validation_status='warning')  
  - Error records (validation_status='error')
  - Data quality score percentage

#### `canonical_communications`
- **Inputs**: 
  - `investigations-raw.telecom_a.raw_calls`
  - `investigations-raw.telecom_a.raw_messages`
- **Output**: `canonical-integration.canonical.canonical_communication`
- **Metrics**: Same as transactions

### 2. **dbt Transformation Jobs** (future)

dbt models die canonical data transformeren:
- `stg_bank_transactions` → reads from `canonical.canonical_transaction`
- `stg_telecom_calls` → reads from `canonical.canonical_communication`
- `stg_telecom_messages` → reads from `canonical.canonical_communication`

## 🔍 OpenLineage Events

Elk canonical mapping job emits 3 types van events:

### **START Event**
```json
{
  "eventType": "START",
  "job": {
    "namespace": "investigations-canonical",
    "name": "canonical_transactions"
  },
  "run": {
    "runId": "uuid-here"
  }
}
```

### **COMPLETE Event** (success)
```json
{
  "eventType": "COMPLETE",
  "job": {...},
  "run": {
    "runId": "uuid-here",
    "facets": {
      "dataQuality": {
        "totalRecords": 69,
        "validRecords": 59,
        "warningRecords": 10,
        "errorRecords": 0,
        "validationRate": 85.51,
        "qualityScore": 100.0
      }
    }
  },
  "inputs": [{
    "namespace": "investigations-raw",
    "name": "bank_a.raw_transactions",
    "facets": {
      "dataSource": {
        "name": "BANK_A",
        "uri": "postgresql://..."
      }
    }
  }],
  "outputs": [{
    "namespace": "canonical-integration",
    "name": "canonical.canonical_transaction",
    "facets": {
      "dataSource": {...},
      "dataQualityMetrics": {
        "rowCount": 69,
        "columnMetrics": {...}
      }
    },
    "outputFacets": {
      "outputStatistics": {
        "rowCount": 69,
        "size": 70656
      }
    }
  }]
}
```

### **FAIL Event** (on error)
```json
{
  "eventType": "FAIL",
  "run": {
    "runId": "uuid-here",
    "facets": {
      "errorMessage": {
        "message": "Error details...",
        "programmingLanguage": "Python"
      }
    }
  }
}
```

## 📈 Marquez UI Features

### 1. **Job View**
- Bekijk alle canonical mapping jobs
- Run history met timestamps
- Success/failure rates
- Last run duration

### 2. **Dataset Lineage**
Visuele lineage graphs:
```
raw_transactions 
    ↓ (canonical_transactions job)
canonical.canonical_transaction
    ↓ (dbt_run_stg_bank_transactions)
staging.stg_bank_transactions
    ↓ (dbt_run_fct_transactions)
analytics.fct_transactions
```

### 3. **Data Quality Metrics**
Per job run:
- **Validation Rate**: % valid records
- **Quality Score**: % valid + warning records
- **Record Counts**: total, valid, warning, error
- **Completeness**: field coverage percentage

### 4. **Dataset Details**
Voor elke dataset:
- Schema (columns, types)
- Source information
- Update frequency
- Data quality trends over time
- Upstream/downstream dependencies

## 🚀 Accessing Marquez

### Web UI
```bash
http://localhost:3001
```

### API
```bash
# Get all jobs
curl http://localhost:3001/api/v1/namespaces/investigations-canonical/jobs

# Get job details
curl http://localhost:3001/api/v1/namespaces/investigations-canonical/jobs/canonical_transactions

# Get dataset lineage
curl http://localhost:3001/api/v1/lineage?nodeId=dataset:canonical-integration:canonical.canonical_transaction
```

## 🔧 Implementation Details

### Code Structure

**`marquez_lineage.py`** - OpenLineage client functions:
- `emit_canonical_lineage_start()` - Start job run
- `emit_canonical_lineage_complete()` - Success with metrics
- `emit_canonical_lineage_fail()` - Failure with error details
- `emit_dbt_model_lineage()` - dbt model lineage (future)

**`canonical_assets.py`** - Integration in Dagster assets:
```python
@asset
def canonical_transactions(context, postgres):
    # Start lineage tracking
    run_id = emit_canonical_lineage_start("canonical_transactions")
    
    try:
        # ... mapping logic ...
        
        # Emit success with metrics
        emit_canonical_lineage_complete(
            job_name="canonical_transactions",
            run_id=run_id,
            source_system="bank_a",
            raw_table="raw_transactions",
            canonical_table="canonical_transaction",
            records_processed=69,
            records_valid=59,
            records_warning=10,
            records_error=0
        )
    except Exception as e:
        # Emit failure
        emit_canonical_lineage_fail("canonical_transactions", run_id, str(e))
        raise
```

### Environment Variables

```bash
# docker-compose.yml
MARQUEZ_URL=http://marquez:5000
```

## 📊 Current Status

**Active Lineage Tracking:**
- ✅ `canonical_transactions` job - 69 records, 82.1% valid
- ✅ `canonical_communications` job - 76 records, 100% mapped

**Namespaces:**
- `investigations-raw` - Raw source data
- `investigations-canonical` - Canonical mapping jobs
- `canonical-integration` - Canonical datasets
- `dbt-staging` - dbt transformation jobs (future)

**Datasets Tracked:**
1. `bank_a.raw_transactions` → `canonical.canonical_transaction`
2. `telecom_a.raw_calls` + `raw_messages` → `canonical.canonical_communication`

## 🎯 Benefits

### 1. **Impact Analysis**
- Welke downstream systemen worden geraakt als raw data verandert?
- Welke dbt models gebruiken canonical datasets?

### 2. **Data Quality Monitoring**
- Trend analysis: validation rates over tijd
- Alert bij quality score drops
- Identify problematic source systems

### 3. **Compliance & Auditing**
- Complete data provenance
- Wie heeft welke data aangemaakt/getransformeerd?
- Wanneer werd data laatst geüpdatet?

### 4. **Debugging**
- Trace data issues terug naar source
- Identify transformation failures
- Compare successful vs failed runs

## 🔮 Future Enhancements

1. **dbt Integration**
   - Automatic lineage via dbt-openlineage adapter
   - Track all dbt models (staging, intermediate, marts)

2. **Schema Evolution**
   - Track column additions/deletions
   - Breaking changes alerts

3. **Data SLAs**
   - Expected freshness per dataset
   - Alert op stale data

4. **Column-level Lineage**
   - Track individual column transformations
   - Field mapping documentation

## 📚 Resources

- [OpenLineage Spec](https://openlineage.io/spec/)
- [Marquez Documentation](https://marquezproject.ai/docs)
- [Dagster + OpenLineage](https://docs.dagster.io/integrations/openlineage)
- [dbt-openlineage](https://github.com/OpenLineage/dbt-openlineage)

---

**Last Updated**: 15 oktober 2025  
**Status**: ✅ Active - Tracking 145 canonical records across 2 jobs
