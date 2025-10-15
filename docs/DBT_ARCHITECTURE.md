# dbt Architecture - Investigation Platform

## 📋 Overzicht

Dit document beschrijft hoe dbt werkt in ons investigation platform, hoe het geïntegreerd is met Dagster, en hoe het canonieke model is opgebouwd.

---

## 🏗️ Architectuur

### Data Flow

```
┌──────────────────────────────────────────────────────────────────────┐
│                         INGESTION LAYER                               │
│                                                                        │
│  CSV Upload → Dagster Sensor → Processing Assets                     │
│                    ↓                                                   │
│           ┌────────────────┐     ┌─────────────────────┐            │
│           │ MinIO          │     │ PostgreSQL          │            │
│           │ (Parquet)      │     │ (Raw Tables)        │            │
│           │                │     │ - raw_transactions  │            │
│           │ - Archival     │     │ - raw_calls         │            │
│           │ - Reprocessing │     │ - raw_messages      │            │
│           └────────────────┘     └─────────────────────┘            │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│                      dbt TRANSFORMATION LAYER                         │
│                                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ STAGING LAYER (Schema: staging, Materialized: VIEW)         │    │
│  │                                                               │    │
│  │  stg_bank_transactions                                       │    │
│  │  ├─ Source: raw_transactions                                 │    │
│  │  ├─ Transform: Clean IBANs, normalize columns                │    │
│  │  └─ Output: 84 records                                       │    │
│  │                                                               │    │
│  │  stg_telecom_calls                                           │    │
│  │  ├─ Source: raw_calls                                        │    │
│  │  ├─ Transform: Clean phones, combine date+time → timestamp   │    │
│  │  └─ Output: 44 records                                       │    │
│  │                                                               │    │
│  │  stg_telecom_messages                                        │    │
│  │  ├─ Source: raw_messages                                     │    │
│  │  ├─ Transform: Clean phones, normalize text                  │    │
│  │  └─ Output: 32 records                                       │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                              ↓                                         │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │ CANONICAL LAYER (Schema: canonical, Materialized: TABLE)    │    │
│  │                                                               │    │
│  │  DIMENSIONS (SCD Type 2):                                    │    │
│  │  ├─ dim_bank_account (6 unique IBANs)                        │    │
│  │  │  ├─ Surrogate key: account_key                            │    │
│  │  │  ├─ Business key: iban                                    │    │
│  │  │  ├─ Attributes: country_code, bank_code, bank_name        │    │
│  │  │  └─ SCD: valid_from, valid_to, is_current                 │    │
│  │  │                                                            │    │
│  │  └─ dim_phone_number (0 records - strict validation)         │    │
│  │     ├─ Surrogate key: phone_key                              │    │
│  │     ├─ Business key: phone_number                            │    │
│  │     ├─ Attributes: country_code, provider, phone_type        │    │
│  │     └─ SCD: valid_from, valid_to, is_current                 │    │
│  │                                                               │    │
│  │  FACTS (Transaction Grain):                                  │    │
│  │  ├─ fact_transaction (84 records)                            │    │
│  │  │  ├─ Keys: transaction_id, account_key_from, account_key_to│    │
│  │  │  ├─ Measures: amount, currency                            │    │
│  │  │  ├─ Dimensions: transaction_date, posted_date             │    │
│  │  │  └─ Enrichments: category, risk_score, is_suspicious      │    │
│  │  │                                                            │    │
│  │  ├─ fact_call (44 records)                                   │    │
│  │  │  ├─ Keys: call_id, caller_phone_key, called_phone_key     │    │
│  │  │  ├─ Measures: duration_seconds, duration_minutes          │    │
│  │  │  ├─ Dimensions: call_date, call_time                      │    │
│  │  │  └─ Enrichments: call_direction, risk_score               │    │
│  │  │                                                            │    │
│  │  └─ fact_message (32 records)                                │    │
│  │     ├─ Keys: message_id, sender_phone_key, recipient_phone_key│   │
│  │     ├─ Measures: message_length, word_count                  │    │
│  │     ├─ Dimensions: message_date, message_time                │    │
│  │     └─ Enrichments: tags, risk_score, is_suspicious          │    │
│  └─────────────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────────────┘
                              ↓
┌──────────────────────────────────────────────────────────────────────┐
│                        CONSUMPTION LAYER                              │
│                                                                        │
│  Superset Dashboards | Jupyter Notebooks | API Queries               │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 🔧 dbt Configuratie

### Project Structuur

```
dbt_investigations/
├── dbt_project.yml          # Project configuratie
├── profiles.yml             # Database connecties
├── packages.yml             # dbt packages (dbt_utils)
│
├── models/
│   ├── staging/
│   │   ├── schema.yml       # Source & model definities + tests
│   │   ├── stg_bank_transactions.sql
│   │   ├── stg_telecom_calls.sql
│   │   └── stg_telecom_messages.sql
│   │
│   └── canonical/
│       ├── schema.yml       # Model definities + tests
│       ├── dim_bank_account.sql
│       ├── dim_phone_number.sql
│       ├── fact_transaction.sql
│       ├── fact_call.sql
│       └── fact_message.sql
│
├── macros/
│   ├── generic_helpers.sql  # Helper functies (UUID, timestamps)
│   ├── iban_helpers.sql     # IBAN validatie & parsing
│   └── phone_helpers.sql    # Phone number validatie & parsing
│
└── tests/
    └── generic/
        ├── valid_iban_format.sql
        ├── valid_phone_format.sql
        ├── positive_value.sql
        └── value_between.sql
```

### Database Configuratie

**profiles.yml**:
```yaml
investigations:
  target: dev
  outputs:
    dev:
      type: postgres
      host: dp_postgres
      port: 5432
      user: superset
      password: superset
      dbname: superset
      schema: staging      # Default schema voor staging models
      threads: 4
```

**Schemas**:
- `public` - Raw tabellen (raw_transactions, raw_calls, raw_messages)
- `staging` - dbt staging views
- `canonical` - dbt canonical tables

---

## 📊 Canoniek Model Detail

### Dimensional Model Design (Star Schema)

```
              ┌─────────────────────────┐
              │  dim_bank_account       │
              │  PK: account_key        │
              │  BK: iban               │
              │  - country_code         │
              │  - bank_code            │
              │  - bank_name            │
              │  - account_type         │
              │  - valid_from/to        │
              └───────────┬─────────────┘
                          │
                          │ 1:N
                          │
       ┌──────────────────┴──────────────────┐
       │                                      │
       ▼                                      ▼
┌──────────────────────────┐    ┌──────────────────────────┐
│  fact_transaction        │    │  dim_phone_number        │
│  PK: transaction_id      │    │  PK: phone_key           │
│  FK: account_key_from    │◄───┤  BK: phone_number        │
│  FK: account_key_to      │    │  - country_code          │
│  - transaction_date      │    │  - provider              │
│  - amount                │    │  - phone_type            │
│  - category              │    │  - valid_from/to         │
│  - risk_score            │    └────────┬─────────────────┘
│  - is_suspicious         │             │
└──────────────────────────┘             │ 1:N
                                         │
                    ┌────────────────────┴─────────────────┐
                    │                                       │
                    ▼                                       ▼
       ┌──────────────────────────┐        ┌──────────────────────────┐
       │  fact_call               │        │  fact_message            │
       │  PK: call_id             │        │  PK: message_id          │
       │  FK: caller_phone_key    │        │  FK: sender_phone_key    │
       │  FK: called_phone_key    │        │  FK: recipient_phone_key │
       │  - call_date             │        │  - message_date          │
       │  - duration_seconds      │        │  - message_text          │
       │  - call_direction        │        │  - message_length        │
       │  - risk_score            │        │  - risk_score            │
       └──────────────────────────┘        └──────────────────────────┘
```

### Fact Tables Detail

#### **fact_transaction**

**Granularity**: 1 rij per transactie

**Kolommen**:
```sql
- transaction_id          UUID PRIMARY KEY
- investigation_id        VARCHAR(50)
- source_id               VARCHAR(50)
- transaction_date        DATE
- transaction_timestamp   TIMESTAMP
- posted_date             DATE
- iban_from               VARCHAR(34)
- iban_to                 VARCHAR(34)
- account_key_from        UUID (FK → dim_bank_account)
- account_key_to          UUID (FK → dim_bank_account)
- amount                  DECIMAL(15,2)
- currency                VARCHAR(3)
- transaction_type        VARCHAR(20)  -- credit/debit/neutral
- category                VARCHAR(50)  -- income/housing/groceries/etc
- description             TEXT
- counter_party_name      VARCHAR(255)
- reference               VARCHAR(100)
- is_suspicious           BOOLEAN
- risk_score              DECIMAL(3,2) -- 0.00 tot 1.00
- tags                    VARCHAR[]
- created_at              TIMESTAMP
- updated_at              TIMESTAMP
```

**Enrichments**:
- **Category Classification**: Automatische categorisatie op basis van description
  - Income: salaris, salary
  - Housing: huur, rent
  - Groceries: albert heijn, jumbo, boodschappen
  - Utilities: gas, water, energie, electric
  - Subscription: netflix, spotify
  - Transfer: overschrijving, transfer
  
- **Risk Scoring**:
  ```sql
  CASE
      WHEN ABS(amount) > 50000 THEN 1.00
      WHEN ABS(amount) > 10000 THEN 0.75
      WHEN ABS(amount) > 5000  THEN 0.50
      WHEN ABS(amount) > 1000  THEN 0.25
      ELSE 0.10
  END AS risk_score
  ```

- **Suspicious Detection**:
  - Bedrag > €10,000
  - Description bevat "suspicious"

#### **fact_call**

**Granularity**: 1 rij per gesprek

**Kolommen**:
```sql
- call_id                 UUID PRIMARY KEY
- investigation_id        VARCHAR(50)
- source_id               VARCHAR(50)
- call_date               TIMESTAMP
- call_date_only          DATE
- call_time               TIME
- caller_number           VARCHAR(20)
- called_number           VARCHAR(20)
- caller_phone_key        UUID (FK → dim_phone_number)
- called_phone_key        UUID (FK → dim_phone_number)
- duration_seconds        INTEGER
- duration_minutes        DECIMAL(10,2)
- call_type               VARCHAR(20)
- call_direction          VARCHAR(20)  -- inbound/outbound/missed
- is_suspicious           BOOLEAN
- risk_score              DECIMAL(3,2)
- tags                    VARCHAR[]
- created_at              TIMESTAMP
- updated_at              TIMESTAMP
```

**Enrichments**:
- **Duration Conversion**: Seconds → Minutes voor analyse
- **Direction Classification**: incoming/outgoing/missed → inbound/outbound/missed
- **Pattern Detection**:
  - Zeer lange gesprekken (> 1 uur)
  - Zeer korte gesprekken (< 1 seconde)
  - Late night calls (00:00-05:00) krijgen hogere risk score

#### **fact_message**

**Granularity**: 1 rij per bericht

**Kolommen**:
```sql
- message_id              UUID PRIMARY KEY
- investigation_id        VARCHAR(50)
- source_id               VARCHAR(50)
- message_date            TIMESTAMP
- message_date_only       DATE
- message_time            TIME
- sender_number           VARCHAR(20)
- recipient_number        VARCHAR(20)
- sender_phone_key        UUID (FK → dim_phone_number)
- recipient_phone_key     UUID (FK → dim_phone_number)
- message_text            TEXT
- message_length          INTEGER
- word_count              INTEGER
- message_type            VARCHAR(20)  -- sms/mms
- message_direction       VARCHAR(20)  -- inbound/outbound
- is_suspicious           BOOLEAN
- risk_score              DECIMAL(3,2)
- tags                    VARCHAR[]
- created_at              TIMESTAMP
- updated_at              TIMESTAMP
```

**Enrichments**:
- **Text Analytics**:
  - Message length berekening
  - Word count (via STRING_TO_ARRAY)
  
- **Keyword Detection & Tagging**:
  - Banking keywords: password, pin, bank, account
  - Urgency keywords: urgent, transfer
  - Meeting keywords: meet, appointment
  
- **Content-based Risk Scoring**:
  ```sql
  CASE
      WHEN message_text LIKE '%password%' THEN 1.00
      WHEN message_text LIKE '%bank%'     THEN 0.75
      WHEN message_text LIKE '%urgent%'   THEN 0.60
      WHEN LENGTH(message_text) > 500     THEN 0.50
      WHEN EXTRACT(HOUR FROM timestamp) BETWEEN 0 AND 5 THEN 0.40
      ELSE 0.10
  END AS risk_score
  ```

### Dimension Tables Detail

#### **dim_bank_account**

**Type**: Slowly Changing Dimension (SCD Type 2)

**Kolommen**:
```sql
- account_key             UUID PRIMARY KEY (Surrogate Key)
- iban                    VARCHAR(34) (Business Key)
- country_code            VARCHAR(2)   -- NL, DE, BE, etc
- bank_code               VARCHAR(10)  -- BIC/SWIFT code prefix
- account_number          VARCHAR(30)  -- Local account number
- bank_name               VARCHAR(100) -- Derived from bank_code
- account_type            VARCHAR(20)  -- checking/savings/unknown
- currency                VARCHAR(3)   -- EUR, USD, etc
- valid_from              TIMESTAMP
- valid_to                TIMESTAMP    -- NULL = current
- is_current              BOOLEAN
- source_system           VARCHAR(100)
- created_at              TIMESTAMP
- updated_at              TIMESTAMP
```

**Source**: UNION van alle unieke IBANs uit transactions (iban_from + iban_to)

#### **dim_phone_number**

**Type**: Slowly Changing Dimension (SCD Type 2)

**Kolommen**:
```sql
- phone_key               UUID PRIMARY KEY (Surrogate Key)
- phone_number            VARCHAR(20) (Business Key, normalized)
- country_code            VARCHAR(5)   -- +31, +32, etc
- area_code               VARCHAR(10)
- local_number            VARCHAR(20)
- phone_type              VARCHAR(20)  -- mobile/landline/voip
- provider                VARCHAR(100) -- KPN, Vodafone, T-Mobile
- is_valid                BOOLEAN
- valid_from              TIMESTAMP
- valid_to                TIMESTAMP
- is_current              BOOLEAN
- source_system           VARCHAR(100)
- created_at              TIMESTAMP
- updated_at              TIMESTAMP
```

**Source**: UNION van alle unieke phone numbers uit calls en messages

---

## 🔄 Dagster Integratie

### dbt Assets in Dagster

**Locatie**: `orchestration/investigations/dbt_assets.py`

Dagster laadt alle dbt models als individuele assets via het manifest.json bestand. Dit betekent dat je elk model apart kunt materialiseren of de hele groep in één keer.

**Beschikbare Asset Groepen**:

1. **Staging Models** (schema: `staging`):
   - `staging/stg_bank_transactions`
   - `staging/stg_telecom_calls`
   - `staging/stg_telecom_messages`

2. **Canonical Dimensions** (schema: `canonical`):
   - `canonical/dim_bank_account`
   - `canonical/dim_phone_number`

3. **Canonical Facts** (schema: `canonical`):
   - `canonical/fact_transaction`
   - `canonical/fact_call`
   - `canonical/fact_message`

4. **Utility Assets**:
   - `dbt_staging_models` - Run alle staging models
   - `dbt_canonical_models` - Run alle canonical models
   - `dbt_test_canonical` - Run tests op canonical layer
   - `dbt_source_freshness` - Check data freshness
   - `dbt_docs_generate` - Genereer documentatie

**Code Example**:
```python
from dagster import asset, AssetExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets

# Path naar dbt project
DBT_PROJECT_DIR = Path(__file__).parent.parent.parent / "dbt_investigations"

@dbt_assets(
    manifest=DBT_PROJECT_DIR / "target" / "manifest.json",
)
def dbt_investigations(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Build all dbt models for investigations.
    Dagster creëert automatisch een asset per dbt model.
    """
    yield from dbt.cli(["build"], context=context).stream()
```

### dbt Execution Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                    Dagster Orchestration                         │
│                                                                   │
│  1. File Upload Sensor                                          │
│     └─> detect_pending_files                                    │
│                                                                   │
│  2. Processing Assets (Sequential)                              │
│     ├─> process_bank_transactions                               │
│     │   └─> Write to: raw_transactions + Parquet                │
│     ├─> process_telecom_calls                                   │
│     │   └─> Write to: raw_calls + Parquet                       │
│     └─> process_telecom_messages                                │
│         └─> Write to: raw_messages + Parquet                    │
│                                                                   │
│  3. dbt Assets (Manual or Scheduled)                            │
│     └─> dbt_investigations                                      │
│         ├─> dbt run --select staging (views)                    │
│         ├─> dbt run --select canonical (tables)                 │
│         └─> dbt test (46 tests)                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Hoe dbt Assets te runnen in Dagster

#### **Via Dagster UI** (Aanbevolen voor Demo):

1. Open Dagster UI: `http://localhost:3000`

2. Navigeer naar **Assets** tab

3. Je ziet nu alle dbt models als individuele assets:
   - **Staging group**: `staging/stg_bank_transactions`, `staging/stg_telecom_calls`, `staging/stg_telecom_messages`
   - **Canonical group**: `canonical/dim_bank_account`, `canonical/fact_transaction`, etc.

4. **Optie A - Individueel model runnen**:
   - Selecteer één specifiek model (bijv. `canonical/fact_transaction`)
   - Klik **Materialize selected**
   - Monitor execution in real-time

5. **Optie B - Hele groep runnen**:
   - Gebruik de utility assets:
     - `dbt_staging_models` - Run alle 3 staging models
     - `dbt_canonical_models` - Run alle 5 canonical models
   - Of selecteer meerdere assets met SHIFT+klik

6. **Optie C - Volledige refresh**:
   - Selecteer het `dbt_investigations` asset (als aanwezig)
   - Of gebruik het utility asset dat alle models bouwt

7. Monitor execution logs:
   ```
   ┌─────────────────────────────────────┐
   │ Execution Details                   │
   ├─────────────────────────────────────┤
   │ ✓ stg_bank_transactions    (VIEW)  │
   │ ✓ stg_telecom_calls        (VIEW)  │
   │ ✓ stg_telecom_messages     (VIEW)  │
   │ ✓ dim_bank_account         (TABLE) │
   │ ✓ dim_phone_number         (TABLE) │
   │ ✓ fact_transaction         (TABLE) │
   │ ✓ fact_call                (TABLE) │
   │ ✓ fact_message             (TABLE) │
   │ ✓ Tests (46 passed)                │
   └─────────────────────────────────────┘
   ```

8. **Lineage Graph bekijken**:
   - Klik op een canonical model (bijv. `fact_transaction`)
   - Zie upstream dependencies: `raw_transactions` → `stg_bank_transactions` → `fact_transaction`
   - Zie downstream consumers (als je Superset dashboards hebt)

#### **Via Dagster CLI**:

```bash
# Materialize een specifiek dbt model
docker exec dp_dagster dagster asset materialize \
  -m investigations \
  --select canonical/fact_transaction

# Materialize alle staging models
docker exec dp_dagster dagster asset materialize \
  -m investigations \
  --select dbt_staging_models

# Materialize alle canonical models
docker exec dp_dagster dagster asset materialize \
  -m investigations \
  --select dbt_canonical_models

# Run alle dbt tests
docker exec dp_dagster dagster asset materialize \
  -m investigations \
  --select dbt_test_canonical
```

#### **Via Python API**:

```python
from dagster import materialize
from investigations import dbt_investigations

# Materialize dbt assets programmatically
result = materialize(
    [dbt_investigations],
    resources={
        "dbt": DbtCliResource(project_dir="/opt/dagster/dbt_investigations")
    }
)
```

### Scheduling dbt Runs

**Optie 1: Schedule in Dagster**

```python
# orchestration/investigations/schedules.py

from dagster import schedule, RunRequest

@schedule(
    cron_schedule="0 2 * * *",  # Daily at 2 AM
    job_name="dbt_investigations_job"
)
def daily_dbt_refresh(context):
    """
    Run dbt models daily to refresh canonical tables
    """
    return RunRequest(
        run_key=context.scheduled_execution_time.strftime("%Y%m%d"),
        tags={
            "schedule": "daily_dbt_refresh",
            "type": "canonical_refresh"
        }
    )
```

**Optie 2: Trigger na Processing**

```python
# Run dbt automatically after file processing completes
@asset(deps=[process_bank_transactions, process_telecom_calls])
def refresh_dbt_models(context, dbt: DbtCliResource):
    """
    Automatically refresh dbt models when new data arrives
    """
    yield from dbt.cli(["build"], context=context).stream()
```

---

## 🧪 Data Quality Tests

### Test Coverage: 46 Tests

#### **Source Tests (12 tests)**:
```yaml
raw_transactions:
  - unique: transaction_id
  - not_null: transaction_id, investigation_id, source_id

raw_calls:
  - unique: call_id
  - not_null: call_id, investigation_id, source_id

raw_messages:
  - unique: message_id
  - not_null: message_id, investigation_id, source_id
```

#### **Staging Tests (19 tests)**:
```yaml
stg_bank_transactions:
  - unique: transaction_id
  - not_null: transaction_id, investigation_id, source_id, bedrag, datum

stg_telecom_calls:
  - unique: call_id
  - not_null: call_id, investigation_id, source_id, duration_seconds

stg_telecom_messages:
  - unique: message_id
  - not_null: message_id, investigation_id, source_id
```

#### **Canonical Tests (15 tests)**:
```yaml
fact_transaction:
  - unique: transaction_id
  - not_null: transaction_id, amount

fact_call:
  - unique: call_id
  - not_null: call_id, investigation_id
  - accepted_values: 
      call_direction: [inbound, outbound, missed, unknown]

fact_message:
  - unique: message_id
  - not_null: message_id, investigation_id
  - accepted_values:
      message_direction: [inbound, outbound, unknown]
```

### Test Execution

```bash
# Run all tests
dbt test

# Run specific test
dbt test --select stg_bank_transactions

# Run tests by type
dbt test --select test_type:generic
dbt test --select test_type:singular
```

---

## 📈 Monitoring & Logging

### dbt Run Metadata

Elke dbt run produceert metadata:

```json
{
  "run_id": "abc123",
  "started_at": "2025-10-14T17:31:00Z",
  "completed_at": "2025-10-14T17:31:15Z",
  "models_built": 8,
  "tests_passed": 46,
  "tests_failed": 0,
  "results": [
    {
      "model": "stg_bank_transactions",
      "status": "success",
      "execution_time": 0.44,
      "rows_affected": 84
    }
  ]
}
```

### Lineage Tracking

**OpenLineage Integration** (toekomstig):
- dbt → Marquez lineage tracking
- Column-level lineage
- Impact analysis
- Data quality monitoring

### Query Performance

```sql
-- Check model refresh times
SELECT 
    model_name,
    execution_time_seconds,
    rows_affected,
    created_at
FROM dbt_run_results
ORDER BY execution_time_seconds DESC;
```

---

## 🎯 Best Practices

### 1. **Incremental Models** (voor grote datasets)

```sql
{{
    config(
        materialized='incremental',
        unique_key='transaction_id'
    )
}}

SELECT * FROM {{ ref('stg_bank_transactions') }}

{% if is_incremental() %}
  WHERE loaded_at > (SELECT MAX(loaded_at) FROM {{ this }})
{% endif %}
```

### 2. **Snapshots** (voor historische tracking)

```sql
{% snapshot dim_bank_account_snapshot %}

{{
    config(
      target_schema='snapshots',
      unique_key='iban',
      strategy='check',
      check_cols=['bank_name', 'account_type']
    )
}}

SELECT * FROM {{ ref('dim_bank_account') }}

{% endsnapshot %}
```

### 3. **Documentation**

```bash
# Generate and serve documentation
dbt docs generate
dbt docs serve --port 8080
```

### 4. **Testing Strategy**

- **Source**: Data integrity (unique, not_null)
- **Staging**: Business rules (valid formats, ranges)
- **Canonical**: Relationships (referential integrity)

---

## 🚀 Demo Scenario's

### Scenario 1: New Investigation Upload

```bash
# 1. Upload files via API
curl -X POST http://localhost:8080/upload \
  -F "file=@transaction.csv" \
  -F "investigation_id=OND-2025-000004"

# 2. Dagster processes automatically
# → raw_transactions populated

# 3. Run dbt via Dagster UI
# → Staging views refreshed
# → Canonical tables updated

# 4. Query results
SELECT 
    category,
    COUNT(*) as transaction_count,
    SUM(amount) as total_amount
FROM canonical.fact_transaction
WHERE investigation_id = 'OND-2025-000004'
GROUP BY category;
```

### Scenario 2: Risk Analysis

```sql
-- High risk transactions
SELECT 
    t.transaction_id,
    t.transaction_date,
    t.amount,
    t.category,
    t.risk_score,
    acc_from.iban as from_account,
    acc_to.iban as to_account
FROM canonical.fact_transaction t
LEFT JOIN canonical.dim_bank_account acc_from 
    ON t.account_key_from = acc_from.account_key
LEFT JOIN canonical.dim_bank_account acc_to 
    ON t.account_key_to = acc_to.account_key
WHERE t.risk_score > 0.75
ORDER BY t.risk_score DESC;
```

### Scenario 3: Communication Pattern Analysis

```sql
-- Find suspicious messaging patterns
SELECT 
    sender_number,
    recipient_number,
    COUNT(*) as message_count,
    AVG(risk_score) as avg_risk,
    ARRAY_AGG(DISTINCT tags) as all_tags
FROM canonical.fact_message
WHERE is_suspicious = TRUE
GROUP BY sender_number, recipient_number
HAVING COUNT(*) > 5
ORDER BY avg_risk DESC;
```

---

## 📚 Resources

### Documentation
- dbt Docs: http://localhost:8080 (after `dbt docs serve`)
- Dagster UI: http://localhost:3000
- Superset: http://localhost:8088

### Troubleshooting

```bash
# Check dbt connection
docker exec dp_dagster sh -c "cd /opt/dagster/dbt_investigations && dbt debug"

# View dbt logs
docker exec dp_dagster sh -c "cat /opt/dagster/dbt_investigations/logs/dbt.log"

# Re-parse project
docker exec dp_dagster sh -c "cd /opt/dagster/dbt_investigations && dbt parse"

# Full refresh (drop and recreate)
docker exec dp_dagster sh -c "cd /opt/dagster/dbt_investigations && dbt run --full-refresh"
```

---

## 🎓 Conclusie

Het dbt layer in ons platform biedt:

✅ **Separation of Concerns**: Raw → Staging → Canonical
✅ **Data Quality**: 46 automated tests
✅ **Traceability**: Full lineage van source naar analytics
✅ **Enrichment**: Automated categorization, risk scoring
✅ **Flexibility**: Easy to extend met nieuwe models
✅ **Observability**: Integrated met Dagster voor monitoring

Perfect voor investigation workflows met honderden tot duizenden records per case!
