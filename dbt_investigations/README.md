# dbt Investigations - Canonical Data Models

## 🎯 Doel
Definieer en enforceert **canonical data models** voor investigation data met:
- **Data contracts** - Gegarandeerde schema's voor alle entities
- **Data quality tests** - Geautomatiseerde validatie met Great Expectations
- **Documentation** - Auto-generated docs voor alle modellen
- **Lineage tracking** - Van raw → staging → canonical

## 📦 Stack
- **dbt Core** - Data transformations
- **DuckDB** - Local database (kan ook PostgreSQL)
- **Great Expectations** - Data quality validatie
- **dbt docs** - Documentation site

## 🏗️ Architectuur

### Data Flow
```
Raw Files (MinIO)
    ↓
Staging Models (views)
    ↓ Transform & Validate
Canonical Models (tables)
    ↓
Analytics Assets
```

### Canonical Entities

#### **Dimensions** (Master Data)
- `dim_bank_account` - Bank rekeningen (IBAN, bank, type)
- `dim_phone_number` - Telefoonnummers (nummer, provider, type)
- `dim_person` - Personen/entiteiten (naam, type, identifiers)

#### **Facts** (Transactioneel)
- `fact_transaction` - Bank transacties (bedrag, datum, type)
- `fact_phone_call` - Telefoon gesprekken (duration, timestamp)
- `fact_text_message` - SMS berichten (timestamp, type)

## 📋 Data Contracts

Elk canonical model heeft een **data contract** in `schema.yml`:

```yaml
models:
  - name: fact_transaction
    config:
      contract:
        enforced: true
    columns:
      - name: transaction_id
        data_type: varchar
        constraints:
          - type: not_null
          - type: unique
      - name: amount
        data_type: decimal(15,2)
        constraints:
          - type: not_null
      - name: iban_from
        data_type: varchar(34)
        constraints:
          - type: not_null
          - type: check
            expression: "iban_from ~ '^[A-Z]{2}[0-9]{2}[A-Z0-9]+$'"
```

**Voordelen:**
- ✅ Schema wordt geenforced tijdens runtime
- ✅ Breaking changes worden gedetecteerd
- ✅ Type safety gegarandeerd
- ✅ Documentatie auto-generated

## 🧪 Data Quality Tests

### Built-in dbt Tests
```yaml
columns:
  - name: amount
    tests:
      - not_null
      - positive_value
  - name: iban
    tests:
      - unique
      - not_null
      - valid_iban_format
```

### Great Expectations Integration
```yaml
models:
  - name: fact_transaction
    meta:
      great_expectations:
        expectations:
          - expectation_type: expect_column_values_to_be_between
            column: amount
            min_value: -1000000
            max_value: 1000000
          - expectation_type: expect_column_values_to_match_regex
            column: iban_from
            regex: "^[A-Z]{2}[0-9]{2}[A-Z0-9]+$"
```

## 🚀 Setup & Usage

### 1. Installeer Dependencies
```bash
pip install dbt-duckdb great-expectations
```

### 2. Configureer Profile
```bash
# profiles.yml wordt automatisch aangemaakt
dbt debug
```

### 3. Run Models
```bash
# Alle models
dbt run

# Alleen canonical
dbt run --select canonical

# Met tests
dbt build
```

### 4. Test Data Quality
```bash
# Run alle tests
dbt test

# Alleen canonical tests
dbt test --select canonical

# Store failures voor analyse
dbt test --store-failures
```

### 5. Generate Documentation
```bash
# Generate docs
dbt docs generate

# Serve docs site
dbt docs serve
# Open: http://localhost:8080
```

## 📊 Canonical Schema Definitions

### dim_bank_account
```sql
CREATE TABLE canonical.dim_bank_account (
    account_key VARCHAR PRIMARY KEY,      -- Surrogate key
    iban VARCHAR(34) NOT NULL UNIQUE,     -- NL91ABNA0417164300
    country_code CHAR(2) NOT NULL,        -- NL
    bank_code VARCHAR(4),                 -- ABNA
    account_number VARCHAR(18),           -- 0417164300
    bank_name VARCHAR(100),               -- ABN AMRO
    account_type VARCHAR(20),             -- checking, savings
    currency CHAR(3) DEFAULT 'EUR',       -- EUR
    valid_from TIMESTAMP NOT NULL,
    valid_to TIMESTAMP,
    is_current BOOLEAN DEFAULT TRUE,
    source_system VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### fact_transaction
```sql
CREATE TABLE canonical.fact_transaction (
    transaction_id VARCHAR PRIMARY KEY,
    investigation_id VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    
    -- When
    transaction_date DATE NOT NULL,
    transaction_timestamp TIMESTAMP NOT NULL,
    posted_date DATE,
    
    -- Who
    iban_from VARCHAR(34) NOT NULL,
    iban_to VARCHAR(34) NOT NULL,
    account_key_from VARCHAR,             -- FK to dim_bank_account
    account_key_to VARCHAR,               -- FK to dim_bank_account
    
    -- What
    amount DECIMAL(15,2) NOT NULL,
    currency CHAR(3) DEFAULT 'EUR',
    transaction_type VARCHAR(50),         -- debit, credit, transfer
    category VARCHAR(100),                -- groceries, salary, rent
    
    -- Details
    description TEXT,
    counter_party_name VARCHAR(200),
    reference VARCHAR(100),
    
    -- Metadata
    is_suspicious BOOLEAN DEFAULT FALSE,
    risk_score DECIMAL(3,2),
    tags ARRAY,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### fact_phone_call
```sql
CREATE TABLE canonical.fact_phone_call (
    call_id VARCHAR PRIMARY KEY,
    investigation_id VARCHAR NOT NULL,
    source_id VARCHAR NOT NULL,
    
    -- When
    call_timestamp TIMESTAMP NOT NULL,
    call_date DATE NOT NULL,
    call_duration_seconds INTEGER NOT NULL,
    
    -- Who
    caller_number VARCHAR(20) NOT NULL,
    callee_number VARCHAR(20) NOT NULL,
    phone_key_caller VARCHAR,             -- FK to dim_phone_number
    phone_key_callee VARCHAR,             -- FK to dim_phone_number
    
    -- What
    call_type VARCHAR(20),                -- incoming, outgoing, missed
    call_direction VARCHAR(20),           -- inbound, outbound
    
    -- Details
    provider VARCHAR(50),                 -- KPN, Vodafone
    cell_tower_id VARCHAR(50),
    location_lat DECIMAL(9,6),
    location_lon DECIMAL(9,6),
    
    -- Metadata
    is_suspicious BOOLEAN DEFAULT FALSE,
    
    -- Audit
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

## 🔄 Integration met Dagster

### Dagster Asset voor dbt
```python
from dagster_dbt import dbt_cli_resource, dbt_run_op

@asset(group_name="canonical_models")
def dbt_canonical_models(context, dbt: dbt_cli_resource):
    """Run dbt canonical models with data contracts"""
    dbt_result = dbt.run(select="canonical")
    context.log.info(f"dbt run completed: {dbt_result}")
    return dbt_result

@asset(group_name="canonical_models", deps=[dbt_canonical_models])
def dbt_test_canonical(context, dbt: dbt_cli_resource):
    """Test canonical models data quality"""
    dbt_result = dbt.test(select="canonical")
    context.log.info(f"dbt test completed: {dbt_result}")
    return dbt_result
```

## 📈 Workflow

### Development
```bash
# 1. Create new model
echo "SELECT * FROM staging.stg_transactions" > models/canonical/fact_transaction.sql

# 2. Add data contract
vim models/canonical/schema.yml

# 3. Test locally
dbt run --select fact_transaction
dbt test --select fact_transaction

# 4. Generate docs
dbt docs generate
dbt docs serve
```

### Production (via Dagster)
```python
# Dagster sensor detecteert nieuwe files
# → Process raw files
# → Load to staging
# → dbt run (transforms to canonical)
# → dbt test (validates quality)
# → Analytics assets (downstream)
```

## 🎯 Benefits

1. **Schema Governance** - Één bron van waarheid voor data structuur
2. **Data Quality** - Geautomatiseerde tests voorkomen bad data
3. **Documentation** - Auto-generated docs voor data teams
4. **Lineage** - Zie waar data vandaan komt
5. **Collaboration** - Git-based workflow voor schema changes
6. **Type Safety** - Data contracts enforced at runtime
7. **Testing** - Comprehensive test suite met GX

## 📚 Resources

- [dbt Docs](https://docs.getdbt.com/)
- [dbt Data Contracts](https://docs.getdbt.com/docs/collaborate/govern/model-contracts)
- [Great Expectations](https://docs.greatexpectations.io/)
- [dbt + GX Integration](https://docs.greatexpectations.io/docs/deployment_patterns/how_to_use_great_expectations_with_dbt)

---

**Next Steps:**
1. ✅ Setup dbt project
2. ⏳ Create staging models
3. ⏳ Define canonical schemas with contracts
4. ⏳ Add data quality tests
5. ⏳ Integrate with Dagster
6. ⏳ Generate documentation
