# Canonical Integration Layer - Implementation Status

**Datum**: 15 oktober 2025  
**Status**: ✅ **Schema Deployed, Assets Created, Ready for Testing**

---

## 🎯 Overzicht

De **Integration Canonical Layer** is succesvol geïmplementeerd als fundamentele laag tussen raw data ingestion en analytics. Deze laag zorgt voor:

1. **Semantische consistentie** tijdens data ingestion
2. **Cross-source integratie** (Bank A + Bank B → unified canonical)
3. **Data quality enforcement** bij bron (niet pas in analytics)
4. **Traceability** met complete audit trail

---

## 🏗️ Architectuur Update

### Voor (2-layer):
```
Raw Data → dbt Staging → Analytical Canonical (Star Schema) → BI
```

### Na (3-layer):
```
Raw Data → Integration Canonical → dbt Staging → Analytical Canonical → BI
           ↑ (semantic enforcement)
```

---

## 📦 Geïmplementeerde Componenten

### 1. Database Schema ✅

**Bestand**: `postgres-init/03_canonical_schema.sql`

#### Canonical Tables (4 nieuwe):

1. **`canonical.canonical_transaction`** (30 columns)
   - Purpose: Unified representation van financial transactions
   - Key features:
     - Standardized amount (DECIMAL 15,2), currency (ISO 4217)
     - Debtor/creditor accounts with type flexibility (IBAN, account_number, etc.)
     - Validation framework (validation_status, validation_messages JSONB)
     - Source traceability (source_system_id, source_record_id, source_raw_data)
   - Indexes: 8 (investigation, datetime, accounts, amount, source, validation, currency)
   - Constraints: UNIQUE(source_system_id, source_record_id)

2. **`canonical.canonical_communication`** (32 columns)
   - Purpose: Unified representation van calls, SMS, email
   - Types: call, sms, mms, email, voicemail, data
   - Participants: originator/recipient with JSONB metadata
   - Content: message_content (TEXT) with full-text search (GIN index)
   - Indexes: 7 B-tree + 1 GIN

3. **`canonical.canonical_person`** (36 columns)
   - Purpose: Entity resolution across sources
   - Types: natural (person), legal (organization)
   - Identifiers: primary + alternatives (JSONB array)
   - Quality: confidence_score (0.00-1.00), data_completeness_pct
   - Investigation: person_role (suspect/victim/witness), risk_level
   - Full-text search on names

4. **`canonical.canonical_mapping_log`** (10 columns)
   - Purpose: Audit trail for raw → canonical mappings
   - Tracks: mapper_version, mapping_rules_applied (JSONB)
   - Performance: processing_time_ms
   - Validation: validation_results (JSONB)

#### Views (3):
- `v_valid_transactions` - Only valid transactions
- `v_valid_communications` - Only valid communications  
- `v_transaction_source_summary` - Aggregated stats per source

**Deployment Status**: ✅ Deployed to `dp_postgres` container

```bash
# Verified tables exist:
docker exec -i dp_postgres psql -U superset -d superset -c "\dt canonical.*"
# Result: 4 new tables + 5 existing analytical tables
```

---

### 2. Dagster Canonical Assets ✅

**Bestand**: `orchestration/investigations/canonical_assets.py` (~500+ lines)

#### Assets (2):

1. **`canonical_transactions`**
   - Dependencies: `process_bank_transactions`
   - Purpose: Map raw_transactions → canonical_transaction
   - Features:
     - Incremental processing (only unmapped records)
     - Source-specific mapping (map_bank_a_to_canonical)
     - Validation (validate_canonical_transaction)
     - Data completeness scoring
   - Metrics: records_mapped, valid/warning/error counts, quality_rate

2. **`canonical_communications`**
   - Dependencies: `process_telecom_calls`
   - Purpose: Map raw_calls + raw_messages → canonical_communication
   - Features:
     - Dual source mapping (calls + SMS)
     - Phone normalization to E.164
     - Content hashing for deduplication
   - Metrics: records_mapped, calls, messages, validation stats

#### Validation Functions (8):

| Function | Purpose | Example |
|----------|---------|---------|
| `validate_iban_format()` | Basic IBAN check | `NL91ABNA0417164300` → `True` |
| `validate_e164_phone()` | E.164 phone format | `+31612345678` → `True` |
| `validate_iso_currency()` | ISO 4217 currency | `EUR`, `USD`, `GBP` → `True` |
| `validate_canonical_transaction()` | Business rules | Returns status + errors/warnings |
| `validate_canonical_communication()` | Communication rules | Validates duration, participants |
| `normalize_iban()` | Remove whitespace | `NL91 ABNA 0417 1643 00` → `NL91ABNA0417164300` |
| `normalize_phone()` | Convert to E.164 | `0612345678` → `+31612345678` |
| `calculate_completeness_score()` | Data quality % | Based on required/optional fields |

#### Mapping Functions (3):

1. **`map_bank_a_to_canonical()`**
   - Input: Raw Bank A record (Dutch format, IBANs, EUR)
   - Output: Canonical transaction dict
   - Transformations:
     - Parse Dutch dates (DD-MM-YYYY)
     - Normalize IBANs (remove spaces)
     - Infer transaction_type from amount (+ = credit, - = debit)
     - Clean descriptions (remove prefixes)

2. **`map_telecom_a_call_to_canonical()`**
   - Input: Raw Telecom A call record
   - Output: Canonical communication dict
   - Transformations:
     - Normalize phone to E.164
     - Map call_type → direction (incoming/outgoing)
     - Convert duration to seconds

3. **`map_telecom_a_sms_to_canonical()`**
   - Input: Raw Telecom A SMS record
   - Output: Canonical communication dict
   - Transformations:
     - Normalize phone numbers
     - Hash message content (SHA256)
     - Set communication_type = 'sms'

#### Helper Functions (2):

1. **`insert_canonical_transactions()`**
   - Bulk insert with ON CONFLICT handling
   - Updates validation status on conflict
   - Uses UUID for canonical_transaction_id

2. **`insert_canonical_communications()`**
   - Bulk insert for communications
   - JSONB serialization for location data
   - Conflict resolution on (source_system_id, source_record_id)

**Integration Status**: ✅ Imported in `orchestration/investigations/__init__.py`

---

### 3. Documentation ✅

**Bestand**: `docs/CANONICAL_INTEGRATION_MODEL.md` (~8,000 words)

Sections:
- **Overzicht**: Why integration canonical ≠ analytical canonical
- **Waarom**: Problem statement with heterogeneous sources
- **Architectuur**: 3-layer model (Raw → Canonical → Analytical)
- **Canonical Entities**: Complete schema definitions
- **Mapping Rules**: Python code examples per source
- **Validation Framework**: Business rules with YAML definitions
- **Benefits & Use Cases**: Cross-source integration queries
- **Implementation Checklist**: 5-phase plan
- **Migration Strategy**: Parallel run approach (6-8 weeks)
- **Monitoring**: Health dashboard queries

---

## 📊 Data Flow

### Before:
```
Bank A CSV → raw_transactions → dbt stg_bank_transactions → fact_transaction
Bank B JSON → raw_transactions → dbt stg_bank_transactions → fact_transaction
                                  ↑ (verschillende formaten, semantiek niet consistent!)
```

### After:
```
Bank A CSV → raw_transactions → canonical_transaction → dbt stg_bank_transactions → fact_transaction
              (source_id='bank_a')  ↑ (standardized)
              
Bank B JSON → raw_transactions → canonical_transaction → dbt stg_bank_transactions → fact_transaction
               (source_id='bank_b')  ↑ (same schema!)
                                     
✅ Unified semantic layer BEFORE analytics
```

---

## 🧪 Testing Strategy

### Phase 1: Schema Validation ✅
```sql
-- Verify tables exist
\dt canonical.*;

-- Check constraints
SELECT conname, pg_get_constraintdef(oid) 
FROM pg_constraint 
WHERE connamespace = 'canonical'::regnamespace;

-- Check indexes
SELECT tablename, indexname 
FROM pg_indexes 
WHERE schemaname = 'canonical';
```
**Status**: ✅ Schema deployed successfully

### Phase 2: Asset Functionality (NEXT)
```bash
# Start Dagster UI
docker-compose up -d

# Materialize canonical_transactions asset
# Expected: Map 84 existing raw_transactions → canonical_transaction

# Verify in database
docker exec -i dp_postgres psql -U superset -d superset -c "
  SELECT COUNT(*), validation_status 
  FROM canonical.canonical_transaction 
  GROUP BY validation_status;
"
```

### Phase 3: Validation Testing
```python
# Test IBAN validation
validate_iban_format("NL91ABNA0417164300")  # → True
validate_iban_format("INVALID")  # → False

# Test phone normalization
normalize_phone("0612345678")  # → "+31612345678"
normalize_phone("+31 6 1234 5678")  # → "+31612345678"

# Test currency validation
validate_iso_currency("EUR")  # → True
validate_iso_currency("XXX")  # → False
```

### Phase 4: End-to-End (TODO)
```
1. Upload new Bank B file (different format)
2. Process to raw_transactions
3. Map to canonical_transaction (Bank B mapper)
4. Verify unified schema with Bank A records
5. Run dbt models (should work seamlessly)
6. Check Superset dashboards
```

---

## 🔄 Next Steps

### Immediate (P0):
- [ ] **Test canonical_transactions asset**
  - Materialize in Dagster UI
  - Verify 84 records mapped
  - Check validation_status distribution
  
- [ ] **Test canonical_communications asset**
  - Should map 44 calls + 32 messages = 76 records
  - Verify phone normalization works

### Short-term (P1):
- [ ] **Update dbt staging models**
  - Change source from `raw_transactions` to `canonical.canonical_transaction`
  - Benefits: Only process valid records, semantic consistency
  - Files: `stg_bank_transactions.sql`, `stg_telecom_calls.sql`, `stg_telecom_messages.sql`

- [ ] **Add Bank B mapper**
  - Create `map_bank_b_to_canonical()` function
  - Handle different format (account_number instead of IBAN)
  - Test with Bank B sample data

### Medium-term (P2):
- [ ] **Create monitoring dashboard**
  - Mapping coverage by source
  - Validation status over time
  - Data quality trends
  - Processing performance

- [ ] **Backfill historical data**
  - Script to map all existing raw records
  - Verify record counts match
  - Check data completeness scores

### Long-term (P3):
- [ ] **Person entity resolution**
  - Implement `canonical_person` mapping
  - Link transactions to persons
  - Cross-source person matching

- [ ] **Advanced validation rules**
  - Suspicious amount detection
  - Duplicate detection (across sources)
  - PEP/sanctions list checking

---

## 📈 Expected Metrics

After full implementation:

| Metric | Target | Current |
|--------|--------|---------|
| Raw records | 160 | 160 ✅ |
| Canonical transactions | 84 | 0 (not mapped yet) |
| Canonical communications | 76 | 0 (not mapped yet) |
| Validation success rate | >95% | TBD |
| Mapping coverage | 100% | 0% |
| Data completeness avg | >85% | TBD |

---

## 🚀 Benefits Realized

### 1. Semantic Consistency
- **Before**: Bank A uses "bedrag", Bank B uses "amount", inconsistent decimals
- **After**: All use `amount DECIMAL(15,2)`, `currency_code CHAR(3)`

### 2. Cross-Source Integration
```sql
-- NEW: Query across all banks in unified format
SELECT 
  source_system_id,
  COUNT(*) as transaction_count,
  SUM(amount) as total_amount,
  AVG(data_completeness_score) as avg_quality
FROM canonical.canonical_transaction
WHERE validation_status = 'valid'
GROUP BY source_system_id;
```

### 3. Data Quality at Source
- Validation happens during ingestion (not just in analytics)
- Invalid records flagged immediately
- Business can fix source issues faster

### 4. Extensibility
- Adding Bank C = just create `map_bank_c_to_canonical()`
- No need to change downstream dbt models
- Canonical schema is stable

### 5. Traceability
- `source_raw_data` JSONB preserves original record
- Can always trace back to source
- Audit trail in `canonical_mapping_log`

---

## 🔍 SQL Queries voor Monitoring

### Mapping Coverage
```sql
SELECT 
  r.source_id,
  COUNT(DISTINCT r.transaction_id) as raw_records,
  COUNT(DISTINCT c.canonical_transaction_id) as canonical_records,
  ROUND(COUNT(DISTINCT c.canonical_transaction_id)::numeric / 
        COUNT(DISTINCT r.transaction_id) * 100, 2) as coverage_pct
FROM raw_transactions r
LEFT JOIN canonical.canonical_transaction c 
  ON c.source_system_id = r.source_id 
  AND c.source_record_id = r.transaction_id::text
GROUP BY r.source_id;
```

### Validation Status Distribution
```sql
SELECT 
  validation_status,
  COUNT(*) as record_count,
  ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as percentage
FROM canonical.canonical_transaction
GROUP BY validation_status
ORDER BY record_count DESC;
```

### Data Quality Over Time
```sql
SELECT 
  DATE_TRUNC('day', created_at) as date,
  AVG(data_completeness_score) as avg_completeness,
  COUNT(CASE WHEN validation_status = 'valid' THEN 1 END) as valid_count,
  COUNT(CASE WHEN validation_status = 'warning' THEN 1 END) as warning_count,
  COUNT(CASE WHEN validation_status = 'error' THEN 1 END) as error_count
FROM canonical.canonical_transaction
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;
```

### Top Validation Errors
```sql
SELECT 
  jsonb_array_elements_text(validation_messages->'errors') as error_message,
  COUNT(*) as occurrence_count
FROM canonical.canonical_transaction
WHERE validation_status = 'error'
GROUP BY error_message
ORDER BY occurrence_count DESC
LIMIT 10;
```

---

## 📝 Implementation Notes

### Design Decisions

1. **JSONB for Flexibility**
   - `source_raw_data`: Preserves original format
   - `validation_messages`: Structured error/warning storage
   - `originator_location`, `recipient_location`: Flexible geographic data

2. **UUID Primary Keys**
   - `canonical_transaction_id`, `canonical_communication_id`
   - Prevents collisions across distributed systems
   - Better for eventual consistency

3. **Validation Status Enum**
   - `valid`: Passes all checks
   - `warning`: Minor issues (e.g., non-standard format)
   - `error`: Critical issues (e.g., missing required field)

4. **Data Completeness Score**
   - Percentage of filled fields (required + optional)
   - Enables quality tracking over time
   - Can prioritize high-quality records for analysis

### Performance Considerations

1. **Indexes**
   - 8 indexes on canonical_transaction (investigation, datetime, accounts, amount)
   - GIN index on message_content for full-text search
   - Composite index on (source_system_id, source_record_id) for lookups

2. **Incremental Processing**
   - Assets only process unmapped records (LEFT JOIN with NULL check)
   - LIMIT 1000 per run to prevent memory issues
   - Can be increased after performance testing

3. **Bulk Inserts**
   - `insert_canonical_transactions()` uses batch inserts
   - ON CONFLICT DO UPDATE for idempotency
   - Can be optimized with COPY command later

---

## 🎓 Training Materials

Voor engineers die met de canonical layer gaan werken:

1. **Conceptueel**: Lees `CANONICAL_INTEGRATION_MODEL.md`
2. **Schema**: Bekijk `postgres-init/03_canonical_schema.sql`
3. **Code**: Bestudeer `canonical_assets.py` mapping functions
4. **Testing**: Draai de SQL queries in deze doc

Vragen? Check de stakeholder presentation of open een discussion in GitHub.

---

## 🏁 Conclusion

De **Integration Canonical Layer** is nu volledig geïmplementeerd en klaar voor testing. De fundamenten zijn gelegd voor:

- ✅ Semantic consistency across heterogeneous sources
- ✅ Data quality enforcement at ingestion
- ✅ Extensible architecture for new sources
- ✅ Complete audit trail and traceability

**Next Step**: Materialize de canonical assets in Dagster en verifieer de data flow!

---

**Document Version**: 1.0  
**Last Updated**: 15 oktober 2025  
**Author**: Data Platform Team
