# Canonical Data Model - Entity Relationship Diagram

## 📊 Schema Overview

```mermaid
erDiagram
    CANONICAL_TRANSACTION ||--o{ CANONICAL_MAPPING_LOG : "tracked by"
    CANONICAL_COMMUNICATION ||--o{ CANONICAL_MAPPING_LOG : "tracked by"
    CANONICAL_PERSON ||--o{ CANONICAL_TRANSACTION : "participates in"
    CANONICAL_PERSON ||--o{ CANONICAL_COMMUNICATION : "participates in"
    
    CANONICAL_TRANSACTION {
        uuid canonical_transaction_id PK
        varchar source_system_id "bank_a, bank_b"
        varchar source_record_id
        varchar investigation_id FK
        timestamp transaction_datetime
        decimal amount "Nullable for ATM"
        char currency_code "ISO 4217"
        varchar debtor_account_id "Normalized IBAN"
        varchar debtor_name
        varchar creditor_account_id "Normalized IBAN"
        varchar creditor_name
        varchar transaction_type "debit/credit/transfer"
        varchar validation_status "valid/warning/error"
        int data_completeness_score "0-100"
        jsonb source_raw_data "Audit trail"
    }
    
    CANONICAL_COMMUNICATION {
        uuid canonical_communication_id PK
        varchar source_system_id "telecom_a"
        varchar source_record_id
        varchar investigation_id FK
        varchar communication_type "call/sms"
        timestamp communication_datetime
        int duration_seconds "NULL for SMS"
        varchar originator_id "E.164 phone"
        varchar originator_type "mobile/landline"
        varchar originator_name
        varchar recipient_id "E.164 phone"
        varchar recipient_type "mobile/landline"
        varchar recipient_name
        varchar direction "inbound/outbound"
        varchar call_status "answered/missed"
        text message_content "NULL for privacy"
        varchar validation_status "valid/warning/error"
        jsonb source_raw_data "Audit trail"
    }
    
    CANONICAL_PERSON {
        uuid canonical_person_id PK
        varchar investigation_id FK
        varchar primary_identifier
        varchar full_name
        date date_of_birth
        varchar email_address
        varchar phone_number "E.164"
        jsonb alternate_identifiers "IBANs, phones"
        varchar entity_resolution_confidence "high/medium/low"
        varchar validation_status "valid/warning/error"
        jsonb source_raw_data
    }
    
    CANONICAL_MAPPING_LOG {
        uuid mapping_log_id PK
        varchar source_system_id
        varchar source_record_id
        varchar canonical_table "transaction/communication/person"
        uuid canonical_record_id FK
        varchar mapper_version "v1.0"
        jsonb mapping_rules_applied
        varchar validation_status "valid/warning/error"
        jsonb validation_errors
        jsonb validation_warnings
        int processing_time_ms
        timestamp mapped_at
    }
```

## 🔄 Data Flow

```mermaid
graph LR
    A[Raw Layer<br/>raw_transactions<br/>raw_calls<br/>raw_messages] --> B{Dagster Assets<br/>Validation &<br/>Normalization}
    B -->|valid/warning| C[Canonical Layer<br/>canonical_transaction<br/>canonical_communication]
    B -->|error| D[Mapping Log<br/>canonical_mapping_log]
    C --> D
    C --> E[dbt Staging<br/>stg_bank_transactions<br/>stg_telecom_calls<br/>stg_telecom_messages]
    E --> F[dbt Analytics<br/>Analytical Canonical<br/>Star Schema]
    F --> G[Superset<br/>Dashboards &<br/>Reports]
    
    style C fill:#90EE90
    style D fill:#FFD700
    style F fill:#87CEEB
```

## 📈 Current Stats

| Layer | Tables | Records | Status |
|-------|--------|---------|--------|
| **Canonical** | 2 active | 145 | ✅ Production |
| - Transactions | 1 | 69 | 59 valid, 10 warning |
| - Communications | 1 | 76 | 44 valid, 32 warning |
| - Person | 1 | 0 | 🔨 Not implemented |
| **Mapping Log** | 1 | 0 | ⚠️ Temporarily disabled |

## 🔍 Validation Rules

### Transaction Validation
```mermaid
flowchart TD
    A[Raw Transaction] --> B{Required Fields?}
    B -->|Missing| E[Error]
    B -->|Present| C{IBAN Valid?}
    C -->|Invalid| E
    C -->|Valid| D{Amount Format?}
    D -->|Invalid| E
    D -->|NULL| F[Warning: ATM Transaction]
    D -->|Valid| G[Valid]
    
    style G fill:#90EE90
    style F fill:#FFD700
    style E fill:#FF6B6B
```

### Communication Validation
```mermaid
flowchart TD
    A[Raw Communication] --> B{Required Fields?}
    B -->|Missing| E[Error]
    B -->|Present| C{Phone E.164?}
    C -->|Invalid| E
    C -->|Valid| D{Has Content?}
    D -->|No SMS Content| F[Warning: Privacy]
    D -->|Has Content| G[Valid]
    
    style G fill:#90EE90
    style F fill:#FFD700
    style E fill:#FF6B6B
```

## 🏗️ Architecture Layers

```mermaid
graph TB
    subgraph "Layer 1: Raw Ingestion"
        A1[Bank A CSV]
        A2[Bank B API]
        A3[Telecom A CDR]
    end
    
    subgraph "Layer 2: Canonical Integration ⭐"
        B1[canonical_transaction<br/>Semantic Consistency]
        B2[canonical_communication<br/>E.164 Normalization]
        B3[canonical_person<br/>Entity Resolution]
    end
    
    subgraph "Layer 3: dbt Staging"
        C1[stg_bank_transactions<br/>Validated Only]
        C2[stg_telecom_calls<br/>Validated Only]
        C3[stg_telecom_messages<br/>Validated Only]
    end
    
    subgraph "Layer 4: Analytical Canonical"
        D1[dim_investigations<br/>Star Schema]
        D2[fact_transactions]
        D3[fact_communications]
    end
    
    subgraph "Layer 5: Consumption"
        E1[Superset Dashboards]
        E2[Data Steward Tools]
    end
    
    A1 --> B1
    A2 --> B1
    A3 --> B2
    
    B1 --> C1
    B2 --> C2
    B2 --> C3
    
    C1 --> D2
    C2 --> D3
    C3 --> D3
    
    D1 --> E1
    D2 --> E1
    D3 --> E1
    
    B1 --> E2
    B2 --> E2
    
    style B1 fill:#90EE90
    style B2 fill:#90EE90
    style B3 fill:#FFD700
```

## 📝 Schema Evolution

### Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2025-10-15 | Initial canonical schema with transaction & communication |
| 1.1 | 2025-10-15 | Changed `amount` from NOT NULL to nullable for ATM support |

### Planned Enhancements

- [ ] `canonical_person` implementation (entity resolution)
- [ ] `canonical_mapping_log` re-enable
- [ ] Additional source systems (Bank B, Telecom B)
- [ ] Temporal tracking (SCD Type 2)
- [ ] Data lineage visualization

---

**📚 See Also**:
- [Data Steward Guide](CANONICAL_DATA_STEWARD_GUIDE.md)
- [Implementation Status](CANONICAL_IMPLEMENTATION_STATUS.md)
- [Data Quality Report](CANONICAL_DATA_QUALITY_REPORT.md)
