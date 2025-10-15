# Canonical Data Model - Integration Layer

## 📋 Overzicht

Dit document beschrijft het **Integration Canonical Data Model** - een gestandaardiseerd datamodel dat semantische consistentie afdwingt tijdens ingest en integratie tussen bronnen faciliteert.

**Verschil met Analytical Model**:
- **Integration Canonical Model**: Brongetrouwe representatie met gestandaardiseerde semantiek (dit document)
- **Analytical Canonical Model**: Star schema voor analytics (fact_*, dim_* tabellen)

```
┌─────────────────────────────────────────────────────────────┐
│                    Source Systems                            │
│  Bank A | Bank B | Telecom A | Telecom B | Forensics       │
└────────────────────┬────────────────────────────────────────┘
                     ↓ (verschillende formaten)
┌─────────────────────────────────────────────────────────────┐
│              INTEGRATION CANONICAL MODEL                     │
│  Unified semantic model met standaard attributen            │
│  → Zorgt voor: Consistentie, Validatie, Integratie         │
└────────────────────┬────────────────────────────────────────┘
                     ↓ (gestandaardiseerd)
┌─────────────────────────────────────────────────────────────┐
│               ANALYTICAL CANONICAL MODEL                     │
│  Star schema (facts + dimensions) voor BI/Analytics         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎯 Waarom Een Integration Canonical Model?

### Probleem: Heterogene Bronnen

```
Bank A:                    Bank B:                   Telecom A:
- IBAN: "NL91ABNA..."     - account_number: "123"   - msisdn: "31612345678"
- amount: 100.00          - bedrag: "€100,00"       - caller: "+31-6-1234-5678"
- date: "2025-10-14"      - datum: "14-10-2025"     - call_date: "2025-10-14T10:30:00"
- description: "Transfer" - omschrijving: "OV"      - call_type: "OUT"
```

**Zonder canoniek model**: Elke bron heeft eigen formaat → Inconsistenties in downstream analytics

**Met canoniek model**: Alle bronnen gemapped naar uniform model → Consistente semantiek

### Voordelen

1. **Semantic Consistency**: Dezelfde begrippen betekenen hetzelfde
2. **Data Quality**: Validatie tijdens ingest (niet pas in analytics layer)
3. **Traceability**: Altijd duidelijk welk veld van welke bron komt
4. **Extensibility**: Nieuwe bronnen kunnen eenvoudig toegevoegd worden
5. **Integration**: Cross-source analyses mogelijk (Bank A + Bank B transacties)
6. **Compliance**: GDPR/AVG velden consistent gemarkeerd

---

## 🏗️ Architectuur: Drie-Laags Model

```
┌─────────────────────────────────────────────────────────────┐
│                    1. RAW LAYER                              │
│  Exacte kopie van bron data (geen transformaties)           │
│  - raw_transactions (Bank A, Bank B, etc.)                  │
│  - raw_calls (Telecom A, Telecom B)                         │
│  Schema: Source-specific columns + metadata                 │
└────────────────────┬────────────────────────────────────────┘
                     ↓ Mapping & Validation
┌─────────────────────────────────────────────────────────────┐
│              2. CANONICAL LAYER (Integration)                │
│  Gestandaardiseerd model met uniforme semantiek             │
│  - canonical_transaction                                     │
│  - canonical_communication                                   │
│  Schema: Standardized columns + source traceability         │
└────────────────────┬────────────────────────────────────────┘
                     ↓ Dimensional Modeling
┌─────────────────────────────────────────────────────────────┐
│              3. ANALYTICAL LAYER (Star Schema)               │
│  Geoptimaliseerd voor analytics & BI                        │
│  - fact_transaction, dim_bank_account                       │
│  Schema: Facts + Dimensions + Business enrichments          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📊 Canonical Entities

### 1. Canonical Transaction

**Doel**: Uniforme representatie van financiële transacties (ongeacht bron)

#### Schema

```sql
CREATE TABLE canonical.canonical_transaction (
    -- Primary Key
    canonical_transaction_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source Traceability
    source_system_id            VARCHAR(50) NOT NULL,     -- "bank_a", "bank_b"
    source_record_id            VARCHAR(100) NOT NULL,    -- Original PK from source
    source_file_name            VARCHAR(255),
    ingestion_timestamp         TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Investigation Context
    investigation_id            VARCHAR(50) NOT NULL,
    
    -- Transaction Core Attributes (STANDARDIZED)
    transaction_reference       VARCHAR(100),             -- Unique ref within source
    transaction_datetime        TIMESTAMP NOT NULL,       -- Canonical timestamp
    posting_date                DATE,                     -- When booked
    value_date                  DATE,                     -- When value transferred
    
    -- Monetary Attributes (STANDARDIZED)
    amount                      DECIMAL(15,2) NOT NULL,   -- Always in decimal format
    currency_code               CHAR(3) NOT NULL,         -- ISO 4217 (EUR, USD, etc.)
    
    -- Account Attributes (STANDARDIZED)
    debtor_account_id           VARCHAR(100),             -- IBAN or account number
    debtor_account_type         VARCHAR(20),              -- "iban", "account_number"
    debtor_name                 VARCHAR(255),
    creditor_account_id         VARCHAR(100),
    creditor_account_type       VARCHAR(20),
    creditor_name               VARCHAR(255),
    
    -- Transaction Details (STANDARDIZED)
    transaction_type            VARCHAR(50),              -- "debit", "credit", "transfer"
    payment_method              VARCHAR(50),              -- "wire", "card", "cash", "mobile"
    description                 TEXT,                     -- Cleaned description
    reference_number            VARCHAR(100),             -- Payment reference
    
    -- Metadata
    is_cancelled                BOOLEAN DEFAULT FALSE,
    is_reversal                 BOOLEAN DEFAULT FALSE,
    related_transaction_id      UUID,                     -- FK to self (for reversals)
    
    -- Data Quality Flags
    validation_status           VARCHAR(20) DEFAULT 'valid',  -- valid, warning, error
    validation_messages         JSONB,                    -- Array of validation issues
    
    -- Original Source Data (for audit)
    source_raw_data             JSONB NOT NULL,           -- Complete original record
    
    -- Audit
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_investigation FOREIGN KEY (investigation_id) 
        REFERENCES investigations(investigation_id),
    CONSTRAINT uq_source_record UNIQUE (source_system_id, source_record_id),
    CONSTRAINT chk_amount_currency CHECK (
        (amount = 0 AND currency_code IS NULL) OR 
        (amount != 0 AND currency_code IS NOT NULL)
    )
);

-- Indexes
CREATE INDEX idx_canonical_tx_investigation ON canonical.canonical_transaction(investigation_id);
CREATE INDEX idx_canonical_tx_datetime ON canonical.canonical_transaction(transaction_datetime);
CREATE INDEX idx_canonical_tx_debtor ON canonical.canonical_transaction(debtor_account_id);
CREATE INDEX idx_canonical_tx_creditor ON canonical.canonical_transaction(creditor_account_id);
CREATE INDEX idx_canonical_tx_amount ON canonical.canonical_transaction(amount);
CREATE INDEX idx_canonical_tx_source ON canonical.canonical_transaction(source_system_id, source_record_id);
```

#### Mapping Rules

**Van Bank A** (Nederlandse bank met IBANs):
```python
def map_bank_a_to_canonical(raw_record):
    return {
        "source_system_id": "bank_a",
        "source_record_id": raw_record["transaction_id"],
        "transaction_datetime": parse_datetime(raw_record["datum"], raw_record.get("tijd", "00:00:00")),
        "posting_date": parse_date(raw_record["datum"]),
        "amount": Decimal(raw_record["bedrag"]),
        "currency_code": "EUR",  # Bank A is always EUR
        "debtor_account_id": normalize_iban(raw_record["iban_van"]),
        "debtor_account_type": "iban",
        "creditor_account_id": normalize_iban(raw_record["iban_naar"]),
        "creditor_account_type": "iban",
        "transaction_type": infer_type(raw_record["bedrag"]),
        "payment_method": "wire",  # Bank A uses wire transfers
        "description": clean_text(raw_record["omschrijving"]),
        "source_raw_data": raw_record  # Keep original for audit
    }
```

**Van Bank B** (Internationale bank met account numbers):
```python
def map_bank_b_to_canonical(raw_record):
    return {
        "source_system_id": "bank_b",
        "source_record_id": raw_record["id"],
        "transaction_datetime": parse_iso_datetime(raw_record["timestamp"]),
        "posting_date": parse_date(raw_record["post_date"]),
        "amount": parse_amount_with_currency(raw_record["amount_string"])[0],  # Extract decimal
        "currency_code": parse_amount_with_currency(raw_record["amount_string"])[1],  # Extract currency
        "debtor_account_id": raw_record["from_account"],
        "debtor_account_type": "account_number",
        "creditor_account_id": raw_record["to_account"],
        "creditor_account_type": "account_number",
        "transaction_type": raw_record["type"].lower(),  # Normalize to lowercase
        "payment_method": map_payment_method(raw_record["method_code"]),
        "description": clean_text(raw_record["narrative"]),
        "source_raw_data": raw_record
    }
```

---

### 2. Canonical Communication

**Doel**: Uniforme representatie van communicatie events (calls, SMS, emails)

#### Schema

```sql
CREATE TABLE canonical.canonical_communication (
    -- Primary Key
    canonical_communication_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source Traceability
    source_system_id            VARCHAR(50) NOT NULL,     -- "telecom_a", "telecom_b"
    source_record_id            VARCHAR(100) NOT NULL,
    source_file_name            VARCHAR(255),
    ingestion_timestamp         TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Investigation Context
    investigation_id            VARCHAR(50) NOT NULL,
    
    -- Communication Core Attributes (STANDARDIZED)
    communication_type          VARCHAR(20) NOT NULL,     -- "call", "sms", "mms", "email"
    communication_datetime      TIMESTAMP NOT NULL,
    duration_seconds            INTEGER,                  -- NULL for non-call types
    
    -- Participant Attributes (STANDARDIZED)
    originator_id               VARCHAR(100) NOT NULL,    -- Phone/email normalized
    originator_type             VARCHAR(20) NOT NULL,     -- "msisdn", "email", "imei"
    originator_name             VARCHAR(255),
    recipient_id                VARCHAR(100) NOT NULL,
    recipient_type              VARCHAR(20) NOT NULL,
    recipient_name              VARCHAR(255),
    
    -- Communication Details (STANDARDIZED)
    direction                   VARCHAR(20),              -- "outbound", "inbound", "internal"
    call_status                 VARCHAR(20),              -- "completed", "missed", "rejected", "voicemail"
    location_info               JSONB,                    -- {cell_tower, lat, lon, country}
    
    -- Content (if applicable)
    message_content             TEXT,                     -- For SMS/MMS/email
    message_subject             VARCHAR(500),             -- For email
    attachment_count            INTEGER DEFAULT 0,
    
    -- Network Metadata
    network_operator            VARCHAR(100),
    connection_type             VARCHAR(50),              -- "2G", "3G", "4G", "5G", "wifi"
    
    -- Data Quality Flags
    validation_status           VARCHAR(20) DEFAULT 'valid',
    validation_messages         JSONB,
    
    -- Original Source Data
    source_raw_data             JSONB NOT NULL,
    
    -- Audit
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW(),
    
    -- Constraints
    CONSTRAINT fk_investigation FOREIGN KEY (investigation_id) 
        REFERENCES investigations(investigation_id),
    CONSTRAINT uq_source_record UNIQUE (source_system_id, source_record_id),
    CONSTRAINT chk_duration_for_calls CHECK (
        (communication_type != 'call') OR 
        (communication_type = 'call' AND duration_seconds IS NOT NULL)
    )
);

-- Indexes
CREATE INDEX idx_canonical_comm_investigation ON canonical.canonical_communication(investigation_id);
CREATE INDEX idx_canonical_comm_datetime ON canonical.canonical_communication(communication_datetime);
CREATE INDEX idx_canonical_comm_originator ON canonical.canonical_communication(originator_id);
CREATE INDEX idx_canonical_comm_recipient ON canonical.canonical_communication(recipient_id);
CREATE INDEX idx_canonical_comm_type ON canonical.canonical_communication(communication_type);
```

#### Mapping Rules

**Van Telecom A** (Nederlandse provider met MSISDN):
```python
def map_telecom_a_to_canonical(raw_record, record_type):
    base = {
        "source_system_id": "telecom_a",
        "source_record_id": raw_record["id"],
        "investigation_id": raw_record["investigation_id"],
        "source_raw_data": raw_record
    }
    
    if record_type == "call":
        return {
            **base,
            "communication_type": "call",
            "communication_datetime": parse_datetime(raw_record["call_date"], raw_record["call_time"]),
            "duration_seconds": int(raw_record["duration_seconds"]),
            "originator_id": normalize_phone(raw_record["caller_number"]),
            "originator_type": "msisdn",
            "recipient_id": normalize_phone(raw_record["called_number"]),
            "recipient_type": "msisdn",
            "direction": map_direction(raw_record["call_type"]),
            "call_status": "completed",  # Telecom A only logs completed calls
            "network_operator": "telecom_a"
        }
    
    elif record_type == "sms":
        return {
            **base,
            "communication_type": "sms",
            "communication_datetime": parse_datetime(raw_record["message_date"], raw_record["message_time"]),
            "duration_seconds": None,
            "originator_id": normalize_phone(raw_record["sender_number"]),
            "originator_type": "msisdn",
            "recipient_id": normalize_phone(raw_record["recipient_number"]),
            "recipient_type": "msisdn",
            "direction": "outbound",  # Telecom A perspective
            "message_content": raw_record["message_text"],
            "network_operator": "telecom_a"
        }
```

---

### 3. Canonical Person

**Doel**: Unified view van personen/entities in onderzoek

#### Schema

```sql
CREATE TABLE canonical.canonical_person (
    -- Primary Key
    canonical_person_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Investigation Context
    investigation_id            VARCHAR(50) NOT NULL,
    
    -- Identity Attributes (STANDARDIZED)
    person_type                 VARCHAR(20) NOT NULL,     -- "natural", "legal", "unknown"
    primary_identifier          VARCHAR(100) NOT NULL,    -- IBAN, phone, email, BSN
    identifier_type             VARCHAR(20) NOT NULL,     -- "iban", "msisdn", "email", "bsn"
    
    -- Name Attributes (STANDARDIZED)
    full_name                   VARCHAR(255),
    first_name                  VARCHAR(100),
    last_name                   VARCHAR(100),
    middle_name                 VARCHAR(100),
    name_prefix                 VARCHAR(20),              -- "van", "de", "van de"
    
    -- Contact Attributes
    phone_numbers               JSONB,                    -- Array of normalized phones
    email_addresses             JSONB,                    -- Array of emails
    postal_addresses            JSONB,                    -- Array of addresses
    
    -- Financial Attributes
    bank_accounts               JSONB,                    -- Array of {iban, bank_name}
    
    -- Demographics (if available)
    date_of_birth               DATE,
    nationality                 VARCHAR(2),               -- ISO 3166-1 alpha-2
    gender                      VARCHAR(20),
    
    -- Role in Investigation
    person_role                 VARCHAR(50),              -- "suspect", "victim", "witness", "related"
    risk_level                  VARCHAR(20),              -- "high", "medium", "low"
    
    -- Data Quality
    confidence_score            DECIMAL(3,2),             -- 0.00 to 1.00
    data_completeness_pct       INTEGER,                  -- 0 to 100
    
    -- Source Attribution
    source_systems              JSONB,                    -- Array of sources that mention this person
    first_seen                  TIMESTAMP,
    last_seen                   TIMESTAMP,
    
    -- Audit
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT fk_investigation FOREIGN KEY (investigation_id) 
        REFERENCES investigations(investigation_id)
);

-- Indexes
CREATE INDEX idx_canonical_person_investigation ON canonical.canonical_person(investigation_id);
CREATE INDEX idx_canonical_person_identifier ON canonical.canonical_person(primary_identifier, identifier_type);
CREATE INDEX idx_canonical_person_name ON canonical.canonical_person(last_name, first_name);
```

---

## 🔄 Mapping & Validation Pipeline

### Dagster Asset voor Canonical Mapping

```python
# orchestration/investigations/canonical_assets.py

from dagster import asset, AssetExecutionContext, Output
from typing import Dict, Any, List
import pandas as pd
from decimal import Decimal

@asset(
    group_name="canonical_integration",
    deps=["process_bank_transactions"],
)
def canonical_transactions(
    context: AssetExecutionContext,
    postgres: PostgresResource
):
    """
    Map raw transactions to canonical transaction model.
    Enforces semantic consistency across all source systems.
    """
    
    # Get raw transactions that haven't been canonicalized yet
    raw_df = postgres.query("""
        SELECT r.* 
        FROM raw_transactions r
        LEFT JOIN canonical.canonical_transaction c 
            ON c.source_system_id = r.source_id 
            AND c.source_record_id = r.transaction_id::text
        WHERE c.canonical_transaction_id IS NULL
    """)
    
    canonical_records = []
    validation_errors = []
    
    for idx, row in raw_df.iterrows():
        try:
            # Determine source system
            source_system = identify_source_system(row['source_id'])
            
            # Apply source-specific mapping
            if source_system == "bank_a":
                canonical = map_bank_a_to_canonical(row)
            elif source_system == "bank_b":
                canonical = map_bank_b_to_canonical(row)
            else:
                raise ValueError(f"Unknown source system: {source_system}")
            
            # Validate canonical record
            validation_result = validate_canonical_transaction(canonical)
            
            if validation_result['is_valid']:
                canonical['validation_status'] = 'valid'
                canonical['validation_messages'] = None
                canonical_records.append(canonical)
            else:
                canonical['validation_status'] = 'warning'
                canonical['validation_messages'] = validation_result['errors']
                canonical_records.append(canonical)
                validation_errors.append({
                    'source_id': row['source_id'],
                    'errors': validation_result['errors']
                })
                
        except Exception as e:
            context.log.error(f"Failed to map record {row['transaction_id']}: {e}")
            validation_errors.append({
                'source_id': row['source_id'],
                'error': str(e)
            })
    
    # Bulk insert canonical records
    if canonical_records:
        insert_canonical_transactions(postgres, canonical_records)
    
    yield Output(
        value=len(canonical_records),
        metadata={
            "records_mapped": len(canonical_records),
            "validation_errors": len(validation_errors),
            "error_rate": f"{len(validation_errors) / len(raw_df) * 100:.2f}%"
        }
    )


def validate_canonical_transaction(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate canonical transaction against business rules.
    """
    errors = []
    
    # Required fields
    required = ['source_system_id', 'transaction_datetime', 'amount', 'currency_code']
    for field in required:
        if not record.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Amount validation
    if record.get('amount') == 0 and record.get('currency_code'):
        errors.append("Zero amount should not have currency code")
    
    # IBAN validation (if present)
    if record.get('debtor_account_type') == 'iban':
        if not validate_iban_format(record.get('debtor_account_id')):
            errors.append(f"Invalid IBAN format: {record.get('debtor_account_id')}")
    
    # Currency code validation
    if record.get('currency_code'):
        if not validate_iso_currency(record.get('currency_code')):
            errors.append(f"Invalid ISO 4217 currency: {record.get('currency_code')}")
    
    # Transaction type validation
    valid_types = ['debit', 'credit', 'transfer', 'payment', 'withdrawal', 'deposit']
    if record.get('transaction_type') and record['transaction_type'] not in valid_types:
        errors.append(f"Invalid transaction type: {record.get('transaction_type')}")
    
    return {
        'is_valid': len(errors) == 0,
        'errors': errors if errors else None
    }


def normalize_iban(iban: str) -> str:
    """Normalize IBAN to canonical format."""
    if not iban:
        return None
    # Remove whitespace and convert to uppercase
    return iban.replace(' ', '').replace('-', '').upper()


def normalize_phone(phone: str) -> str:
    """Normalize phone number to E.164 format."""
    if not phone:
        return None
    # Remove all non-numeric characters
    digits = ''.join(filter(str.isdigit, phone))
    # Add country code if missing (assume NL +31)
    if not digits.startswith('31') and len(digits) == 9:
        digits = '31' + digits
    return '+' + digits
```

---

## 🧪 Data Quality Rules

### Validation Rules per Entity

**Canonical Transaction**:
```yaml
validation_rules:
  required_fields:
    - source_system_id
    - source_record_id
    - investigation_id
    - transaction_datetime
    - amount
    - currency_code
    
  format_checks:
    currency_code: 
      type: "regex"
      pattern: "^[A-Z]{3}$"
      message: "Must be ISO 4217 currency code"
    
    debtor_account_id:
      type: "conditional"
      condition: "debtor_account_type = 'iban'"
      validator: "validate_iban_format"
      message: "Invalid IBAN format"
    
    amount:
      type: "numeric"
      range: [-999999999.99, 999999999.99]
      precision: 2
      message: "Amount must be decimal with 2 decimal places"
  
  business_rules:
    - rule: "Zero amount transactions must not have currency"
      check: "(amount = 0 AND currency_code IS NULL) OR (amount != 0)"
    
    - rule: "Transaction must have at least one account"
      check: "debtor_account_id IS NOT NULL OR creditor_account_id IS NOT NULL"
    
    - rule: "Transaction datetime must be in past"
      check: "transaction_datetime <= NOW()"
```

**Canonical Communication**:
```yaml
validation_rules:
  required_fields:
    - source_system_id
    - communication_type
    - communication_datetime
    - originator_id
    - recipient_id
  
  conditional_required:
    - field: "duration_seconds"
      condition: "communication_type = 'call'"
      message: "Call records must have duration"
    
    - field: "message_content"
      condition: "communication_type IN ('sms', 'email')"
      message: "Message records must have content"
  
  format_checks:
    originator_id:
      type: "conditional"
      condition: "originator_type = 'msisdn'"
      validator: "validate_e164_phone"
      message: "Phone must be E.164 format"
    
    duration_seconds:
      type: "numeric"
      range: [0, 86400]  # Max 24 hours
      message: "Duration must be between 0 and 86400 seconds"
```

---

## 📚 Benefits & Use Cases

### 1. Cross-Source Integration

**Scenario**: Verdachte heeft accounts bij Bank A én Bank B

```sql
-- Without canonical model: Complex union with transformations
SELECT 
    CAST(bedrag AS DECIMAL) as amount,
    TO_DATE(datum, 'YYYY-MM-DD') as date,
    iban_van as account
FROM raw_transactions_bank_a
WHERE iban_van = 'NL91ABNA...'

UNION ALL

SELECT
    CAST(REPLACE(REPLACE(amount_str, '€', ''), ',', '.') AS DECIMAL),
    STR_TO_DATE(tx_date, '%d-%m-%Y'),
    from_account
FROM raw_transactions_bank_b
WHERE from_account = 'ACC123';

-- With canonical model: Simple query
SELECT 
    amount,
    transaction_datetime::date as date,
    debtor_account_id as account,
    source_system_id
FROM canonical.canonical_transaction
WHERE debtor_account_id IN ('NL91ABNA...', 'ACC123')
ORDER BY transaction_datetime;
```

### 2. Data Quality at Ingestion

**Validation happens during canonical mapping**:
```python
# Bad record from Bank B
raw_record = {
    "amount_string": "invalid",  # Not parseable
    "tx_date": "2025-99-99",     # Invalid date
    "from_account": None         # Missing required field
}

# Canonical mapper catches all issues
canonical = map_bank_b_to_canonical(raw_record)
# Result:
{
    "validation_status": "error",
    "validation_messages": [
        "Cannot parse amount: 'invalid'",
        "Invalid date format: '2025-99-99'",
        "Missing required field: from_account"
    ]
}

# Record still stored (for audit) but flagged
# Analytics layer can filter: WHERE validation_status = 'valid'
```

### 3. Semantic Consistency

**Same meaning = Same representation**:

| Concept | Bank A | Bank B | Canonical |
|---------|--------|--------|-----------|
| Amount | bedrag: 100.00 | amount_str: "€100,00" | amount: 100.00 |
| Date | datum: "2025-10-14" | tx_date: "14-10-2025" | transaction_datetime: TIMESTAMP |
| Account | iban_van: "NL91..." | from_account: "123" | debtor_account_id: "NL91..." + debtor_account_type: "iban" |
| Type | (inferred) | type: "CREDIT" | transaction_type: "credit" |

### 4. Extensibility

**Adding a new source (Bank C)**:

```python
# 1. Create mapping function
def map_bank_c_to_canonical(raw_record):
    return {
        "source_system_id": "bank_c",
        "transaction_datetime": parse_datetime(raw_record["ts"]),
        "amount": Decimal(raw_record["amt"]),
        "currency_code": raw_record["ccy"],
        "debtor_account_id": raw_record["debit_acct"],
        "debtor_account_type": "account_number",
        # ... map other fields
    }

# 2. Register in canonical_assets.py
elif source_system == "bank_c":
    canonical = map_bank_c_to_canonical(row)

# 3. Done! All downstream analytics work automatically
```

---

## 🔧 Implementation Checklist

### Phase 1: Schema Creation

- [ ] Create `canonical` schema in PostgreSQL
- [ ] Create `canonical_transaction` table
- [ ] Create `canonical_communication` table
- [ ] Create `canonical_person` table
- [ ] Add indexes voor performance
- [ ] Add foreign key constraints

### Phase 2: Mapping Functions

- [ ] Implement `map_bank_a_to_canonical()`
- [ ] Implement `map_telecom_a_to_canonical()`
- [ ] Implement validation functions
- [ ] Implement normalization functions (IBAN, phone)
- [ ] Unit tests voor alle mappers

### Phase 3: Dagster Integration

- [ ] Create `canonical_transactions` asset
- [ ] Create `canonical_communications` asset
- [ ] Add dependency: raw → canonical → analytical
- [ ] Error handling & logging
- [ ] Monitoring & alerts

### Phase 4: dbt Integration

- [ ] Update analytical models to source from canonical
- [ ] Add canonical layer tests
- [ ] Update lineage documentation
- [ ] Performance testing

### Phase 5: Documentation

- [ ] Document mapping rules per source
- [ ] Create data dictionary voor canonical fields
- [ ] Update architecture diagrams
- [ ] Training voor team

---

## 🎯 Migration Strategy

### Option 1: Big Bang (Not Recommended)

Stop processing → Migrate all data → Resume

**Cons**: Downtime, risky

### Option 2: Parallel Run (Recommended)

```
Week 1-2: Build canonical tables + mappers
Week 3: Start dual-write (raw + canonical)
Week 4-5: Backfill historical data
Week 6: Update analytical layer to use canonical
Week 7: Deprecate direct raw → analytical mapping
Week 8+: Monitor & optimize
```

**Implementation**:
```python
@asset(deps=["process_bank_transactions"])
def canonical_transactions(context, postgres):
    """Runs in parallel with existing pipeline"""
    # Map raw → canonical
    # Old analytical pipeline still works
    pass

# Week 6: Switch analytical source
# models/staging/stg_bank_transactions.sql
WITH source AS (
    -- OLD: SELECT * FROM {{ source('raw_transactions') }}
    -- NEW:
    SELECT * FROM {{ source('canonical_transaction') }}
    WHERE validation_status = 'valid'
)
```

---

## 📊 Monitoring & Metrics

### Canonical Layer Health Dashboard

```sql
-- Mapping coverage
SELECT 
    source_system_id,
    COUNT(*) as raw_records,
    COUNT(canonical_transaction_id) as mapped_records,
    ROUND(COUNT(canonical_transaction_id)::numeric / COUNT(*) * 100, 2) as mapping_rate_pct
FROM raw_transactions r
LEFT JOIN canonical.canonical_transaction c 
    ON c.source_record_id = r.transaction_id::text
GROUP BY source_system_id;

-- Validation status
SELECT 
    validation_status,
    COUNT(*) as count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER () * 100, 2) as percentage
FROM canonical.canonical_transaction
GROUP BY validation_status;

-- Data quality over time
SELECT 
    DATE_TRUNC('day', created_at) as date,
    COUNT(*) as total_records,
    SUM(CASE WHEN validation_status = 'valid' THEN 1 ELSE 0 END) as valid_records,
    ROUND(SUM(CASE WHEN validation_status = 'valid' THEN 1 ELSE 0 END)::numeric / COUNT(*) * 100, 2) as quality_pct
FROM canonical.canonical_transaction
GROUP BY DATE_TRUNC('day', created_at)
ORDER BY date DESC;
```

---

## 🚀 Next Steps

1. **Review & Approve Schema**: Team review van canonical entities
2. **Prioritize Entities**: Start met `canonical_transaction` (highest value)
3. **Prototype Mapper**: Bank A mapping als proof-of-concept
4. **Validate with Data Steward**: Ensure semantic correctness
5. **Implement & Test**: Full implementation met unit tests
6. **Backfill Historical Data**: Migrate existing records
7. **Update Analytical Layer**: Switch dbt models to canonical source
8. **Monitor & Optimize**: Dashboard + alerting

---

**Document Version**: 1.0  
**Last Updated**: 15 oktober 2025  
**Owner**: Data Architecture Team
