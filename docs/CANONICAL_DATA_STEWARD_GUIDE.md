# Canonical Data Model Documentation

## 📚 Voor Data Stewards

Dit document beschrijft hoe je het canonical datamodel kunt bekijken en begrijpen.

## 🎯 Wat is het Canonical Datamodel?

Het **canonical datamodel** is de semantisch consistente integratielaag tussen verschillende bronsystemen:

```
Raw Data (Bank A, Bank B, Telecom A) 
    ↓
Canonical Integration Layer ⭐ (Dit document)
    ↓
dbt Staging & Analytics
    ↓
Superset Dashboards
```

**Waarom belangrijk?**
- ✅ Eén versie van de waarheid
- ✅ Gevalideerde data quality
- ✅ Gestandaardiseerde velden (IBANs, phone numbers, dates)
- ✅ Cross-system consistency

## 📊 Huidige Status

### Canonical Tables

**1. canonical_transaction** (Financiële transacties)
- **Records**: 69 transacties
- **Valid**: 59 (85.5%)
- **Warning**: 10 (14.5%) - ATM transacties zonder bedrag
- **Sources**: Bank A

**2. canonical_communication** (Communicaties)
- **Records**: 76 communicaties
- **Valid**: 44 calls (57.9%)
- **Warning**: 32 SMS (42.1%) - geen content (privacy)
- **Sources**: Telecom A

**Totaal**: 145 gevalideerde records

## 🔍 Data Model Bekijken

### Optie 1: dbt Documentation (Aanbevolen)

Interactive web interface met:
- ERD diagram
- Column details en types
- Data lineage
- Test results

**Starten**:
```bash
cd /path/to/data-platform
docker exec -it dp_dagster bash
cd /opt/dagster/dbt_investigations
./serve_docs.sh
```

Open in browser: **http://localhost:8011**

### Optie 2: Database Viewer (pgAdmin/DBeaver)

**Connection Details**:
- Host: `localhost`
- Port: `5432`
- Database: `superset`
- Schema: `canonical`
- User: `superset`
- Password: `superset`

**Tables**:
- `canonical.canonical_transaction`
- `canonical.canonical_communication`
- `canonical.canonical_person` (nog niet geïmplementeerd)
- `canonical.canonical_mapping_log` (audit trail)

### Optie 3: SQL Queries

```sql
-- Overview transacties
SELECT 
    validation_status,
    COUNT(*) as aantal,
    AVG(data_completeness_score) as gem_compleetheid
FROM canonical.canonical_transaction
GROUP BY validation_status;

-- Overzicht communicaties
SELECT 
    communication_type,
    validation_status,
    COUNT(*) as aantal
FROM canonical.canonical_communication
GROUP BY communication_type, validation_status;

-- Data quality per bron
SELECT 
    source_system_id,
    validation_status,
    COUNT(*) as aantal
FROM canonical.canonical_transaction
GROUP BY source_system_id, validation_status;
```

## 📋 Schema Details

### canonical_transaction

**Belangrijkste velden**:
- `canonical_transaction_id` (UUID) - Unieke identifier
- `source_system_id` - Bronsysteem (bijv. 'bank_a')
- `transaction_datetime` - Gestandaardiseerde timestamp
- `amount` - Bedrag (kan NULL zijn voor ATM)
- `currency_code` - ISO 4217 code (bijv. 'EUR')
- `debtor_account_id` - IBAN van (genormaliseerd)
- `creditor_account_id` - IBAN naar (genormaliseerd)
- `validation_status` - 'valid', 'warning', of 'error'
- `data_completeness_score` - 0-100%

**Normalisatie regels**:
- IBANs: Hoofdletters, geen spaties, validatie via check digit
- Bedragen: DECIMAL(15,2)
- Datums: UTC timestamps
- Phone numbers: E.164 format (+31612345678)

### canonical_communication

**Belangrijkste velden**:
- `canonical_communication_id` (UUID) - Unieke identifier
- `source_system_id` - Bronsysteem (bijv. 'telecom_a')
- `communication_type` - 'call' of 'sms'
- `communication_datetime` - Gestandaardiseerde timestamp
- `originator_id` - Beller/zender (E.164 format)
- `recipient_id` - Gebelde/ontvanger (E.164 format)
- `duration_seconds` - Duur (alleen calls)
- `message_content` - SMS tekst (kan NULL zijn voor privacy)
- `validation_status` - 'valid', 'warning', of 'error'

## 📈 Data Quality Dashboard

Voor real-time monitoring, zie **Superset Dashboard** (coming soon):
- Mapping coverage per bron
- Validation status trends
- Data quality scores
- Rejected records analysis

## 🔧 Technische Details

**Locaties**:
- Schema DDL: `postgres-init/03_canonical_schema.sql`
- Mapping logica: `orchestration/investigations/canonical_assets.py`
- dbt models: `dbt_investigations/models/staging/`
- Documentatie: `dbt_investigations/models/staging/schema.yml`

**Dagster Assets**:
- `canonical_transactions` - Maps raw transactions
- `canonical_communications` - Maps raw calls + messages

**Validation Framework**:
- Required fields check
- Format validation (IBAN, phone, date)
- Cross-field consistency
- Data completeness scoring

## ❓ Veelgestelde Vragen

**Q: Waarom zijn sommige records 'warning' status?**
A: Warning betekent dat het record bruikbaar is maar niet 100% compleet. Bijvoorbeeld ATM transacties zonder bedrag, of SMS zonder content (privacy).

**Q: Waar kan ik rejected records zien?**
A: In `canonical.canonical_mapping_log` staan alle mapping pogingen inclusief errors met `validation_status='error'`.

**Q: Hoe weet ik welk veld van welk bronsysteem komt?**
A: `source_system_id` + `source_record_id` + `source_raw_data` (JSONB) bevatten volledige traceability.

**Q: Kan ik het schema aanpassen?**
A: Ja, maar alleen via DDL changes in `postgres-init/03_canonical_schema.sql` en mapping logica updates. Bespreek eerst met data engineering team.

## 📞 Contact

Voor vragen of problemen:
- Data Engineering Team
- Dagster UI: http://localhost:3000
- Superset: http://localhost:8088

---

**Last Updated**: 2025-10-15
**Version**: 1.0
**Records**: 145 (69 transactions + 76 communications)
