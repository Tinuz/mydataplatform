# Canonical Data Model - JSON Schemas

This directory contains JSON Schema definitions for the data platform's canonical data model. These schemas document the structure, types, and validation rules for both the canonical (raw integration) layer and the dbt analytical models.

## Overview

The canonical data model consists of two main layers:

### 1. Canonical Layer (PostgreSQL)
Standardized integration layer that consolidates data from multiple source systems:
- **canonical_transaction**: Financial transaction data from various banks
- **canonical_communication**: Telecom data (calls, SMS, messages) from various providers

### 2. Analytical Layer (dbt Models)
Dimensional model for analytical queries and reporting:

**Dimensions:**
- **dim_bank_account**: Bank account dimension with IBAN keys
- **dim_phone_number**: Phone number dimension with MSISDN keys

**Facts:**
- **fact_transaction**: Transaction facts with enrichment, categorization, and risk scoring
- **fact_call**: Call facts with duration analysis and risk scoring
- **fact_message**: Message facts with content analysis and risk scoring

## Schema Files

### Canonical Layer

#### canonical_transaction.json
**Purpose**: Standardized financial transaction data from multiple banking sources (Rabobank, ING, ABN AMRO, etc.)

**Key Features**:
- Source traceability (system ID, record ID, file name)
- Investigation context linking
- Standardized transaction attributes (IBAN, amounts, dates)
- Party details (debtor/creditor accounts and names)
- Data quality flags (validation status, completeness score)
- Original source data preserved as JSON

**Required Fields**:
- `source_system_id`, `source_record_id`, `investigation_id`
- `transaction_datetime`, `currency_code`
- `source_raw_data`

**Constraints**:
- `transaction_type`: debit, credit, transfer, payment, withdrawal, deposit, fee, interest, other
- `validation_status`: valid, warning, error, pending
- `currency_code`: ISO 4217 3-letter code (e.g., EUR, USD)
- Amount can be NULL for ATM withdrawals

#### canonical_communication.json
**Purpose**: Standardized communication data from multiple telecom providers (KPN, Vodafone, T-Mobile, etc.)

**Key Features**:
- Multiple communication types (call, sms, mms, email, voicemail)
- Participant details (originator/recipient with type classification)
- Network metadata (operator, cell tower, IMEI)
- Location information (stored as JSON)
- Message content (for SMS/email)
- Data quality and validation

**Required Fields**:
- `source_system_id`, `source_record_id`, `investigation_id`
- `communication_type`, `communication_datetime`
- `originator_id`, `originator_type`, `recipient_id`, `recipient_type`
- `source_raw_data`

**Constraints**:
- `communication_type`: call, sms, mms, email, voicemail, data, other
- `originator_type`/`recipient_type`: msisdn, email, imei, imsi, ip, other
- `direction`: outbound, inbound, internal, unknown
- `duration_seconds` required for calls

### Analytical Layer (dbt)

#### dim_bank_account.json
**Purpose**: Slowly Changing Dimension (SCD) for bank accounts

**Fields**:
- `account_key`: Surrogate key (string, generated from IBAN)
- `iban`: International Bank Account Number (pattern validated)

**Usage**: Referenced by `fact_transaction` via `account_key_from` and `account_key_to`

#### dim_phone_number.json
**Purpose**: Slowly Changing Dimension (SCD) for phone numbers

**Fields**:
- `phone_key`: Surrogate key (string, generated from phone number)
- `phone_number`: MSISDN format phone number (10-15 digits, optional +)

**Usage**: Referenced by `fact_call` and `fact_message` via sender/recipient phone keys

#### fact_transaction.json
**Purpose**: Enriched transaction facts with business logic and analytics

**Key Features**:
- Links to `dim_bank_account` via foreign keys
- Automatic categorization (income, housing, groceries, transfer, subscription, utilities, other)
- Transaction type classification (credit, debit, neutral)
- Suspicious transaction flagging (amount > €10,000)
- Risk scoring (0.0 to 1.0 based on amount)
- Tagging support for custom categorization

**Required Fields**:
- `transaction_id`, `investigation_id`, `amount`

**Business Logic**:
- Category extracted from description keywords
- Counter party name extracted from description
- Risk score calculated based on amount thresholds:
  - > €50,000: 1.00 (critical)
  - > €10,000: 0.75 (high)
  - > €5,000: 0.50 (medium)
  - > €1,000: 0.25 (low)
  - ≤ €1,000: 0.10 (minimal)

#### fact_call.json
**Purpose**: Enriched call records with analytical dimensions

**Key Features**:
- Links to `dim_phone_number` for caller and called party
- Duration in both seconds and minutes
- Call direction standardization (inbound, outbound, missed, unknown)
- Suspicious call detection (> 1 hour or < 1 second)
- Risk scoring based on duration and time of day
- Time-based analysis fields (date, time split)

**Required Fields**:
- `call_id`, `investigation_id`, `duration_seconds`, `call_direction`

**Business Logic**:
- Risk scoring:
  - > 2 hours: 1.00 (critical)
  - > 1 hour: 0.75 (high)
  - > 30 minutes: 0.50 (medium)
  - 00:00-05:00 (late night): 0.60
  - 22:00-23:00 (night): 0.40
  - Normal: 0.10

#### fact_message.json
**Purpose**: Enriched SMS/message records with content analysis

**Key Features**:
- Links to `dim_phone_number` for sender and recipient
- Message length and word count metrics
- Content-based suspicious keyword detection
- Risk scoring based on content patterns
- Automatic tag extraction (banking, meeting, urgent)
- Time-based analysis fields

**Required Fields**:
- `message_id`, `investigation_id`, `message_length`, `message_direction`

**Business Logic**:
- Suspicious keywords: urgent, password, bank, account, transfer
- Risk scoring:
  - Contains "password" or "pin": 1.00 (critical)
  - Contains "bank" or "account": 0.75 (high)
  - Contains "urgent" or "transfer": 0.60 (medium)
  - Length > 500 chars: 0.50
  - Late night (00:00-05:00): 0.40
  - Normal: 0.10
- Auto-tagging from content patterns

## Data Flow

```
Source Systems (MinIO/GCS)
    ↓
Raw Layer (PostgreSQL raw schema)
    ↓
Canonical Layer (canonical_transaction, canonical_communication)
    ↓
dbt Staging Layer
    ↓
dbt Analytical Layer (dimensions + facts)
    ↓
Superset/API Consumers
```

## Lineage Tracking

All layers are tracked in Marquez/OpenLineage:
- **Namespace: minio-storage** → File uploads
- **Namespace: investigations-raw** → Raw processing jobs
- **Namespace: postgresql-raw** → Raw database tables
- **Namespace: canonical-integration** → Canonical transformation
- **Namespace: dbt-staging** → dbt staging models
- **Namespace: dbt-analytical** → dbt analytical models (dimensions + facts)

## Usage Examples

### Validating Data Against Schema

```python
import json
import jsonschema

# Load schema
with open('docs/schemas/canonical_transaction.json') as f:
    schema = json.load(f)

# Validate data
transaction = {
    "source_system_id": "rabobank",
    "source_record_id": "TX123456",
    "investigation_id": "INV-2024-001",
    "transaction_datetime": "2024-01-15T14:30:00Z",
    "currency_code": "EUR",
    "amount": 1500.00,
    "source_raw_data": {}
}

jsonschema.validate(instance=transaction, schema=schema)
```

### Generating OpenAPI Documentation

These schemas can be referenced in OpenAPI specs:

```yaml
components:
  schemas:
    CanonicalTransaction:
      $ref: './docs/schemas/canonical_transaction.json'
    CanonicalCommunication:
      $ref: './docs/schemas/canonical_communication.json'
```

### TypeScript Type Generation

Generate TypeScript interfaces:

```bash
# Using json-schema-to-typescript
npx json-schema-to-typescript docs/schemas/*.json --output api/types/
```

## Maintenance

### Updating Schemas

1. Update the PostgreSQL table definition in `postgres-init/03_canonical_schema.sql`
2. Update the corresponding JSON schema in `docs/schemas/`
3. Regenerate any dependent types or documentation
4. Update dbt model schemas in `dbt_investigations/models/*/schema.yml`
5. Test validation with sample data

### Schema Versioning

Schemas follow semantic versioning in the `$id` field:
- **Major**: Breaking changes (field removal, type changes)
- **Minor**: Non-breaking additions (new optional fields)
- **Patch**: Documentation updates, constraint clarifications

## JSON Schema Standard

All schemas use:
- **draft-07** for maximum compatibility
- **$schema**: Declares JSON Schema version
- **$id**: Unique identifier for the schema
- **additionalProperties: false**: Strict validation (no extra fields)
- **format**: Date, time, UUID, email validation
- **pattern**: Regex validation for codes and identifiers
- **enum**: Restricted value sets for categorical fields

## Related Documentation

- [Pipeline Overview](../pipeline_overview.md)
- [dbt Documentation](../dbt_investigations/README.md)
- [Marquez Lineage](../orchestration/investigations/marquez_lineage.py)
- [PostgreSQL Canonical Schema](../postgres-init/03_canonical_schema.sql)

## Contributing

When adding new fields or models:
1. Update the source schema (SQL DDL or dbt model)
2. Update the corresponding JSON schema
3. Add descriptions and constraints
4. Update this README with examples
5. Validate with sample data
6. Update API documentation if applicable
