# Marvel Bandits Test Case

## 🎭 Case Beschrijving

**Investigation ID**: `OND-2025-MARVEL`  
**Case Name**: Marvel Bandits  
**Start Date**: 2024-01-01  
**Status**: Active Investigation

### Verdachten (Subjects of Investigation)

1. **Tony Stark** - Hoofdverdachte
   - IBAN: NL91ABNA0417164300
   - Telefoon: +31612345001
   - Rol: Vermeende leider van de organisatie

2. **Peter Parker** - Medeplichtige
   - IBAN: NL20RABO0123456789
   - Telefoon: +31612345002
   - Rol: Koerier/geldtransport

3. **Natasha Romanoff** - Financieel expert
   - IBAN: NL69INGB0123456789
   - Telefoon: +31612345003
   - Rol: Witwasstrategie

4. **Bruce Banner** - IT specialist
   - IBAN: NL43ABNA0123456789
   - Telefoon: +31612345004
   - Rol: Cybercrime en encryptie

## 📊 Test Data Overzicht

### Banktransacties (51 transacties van 4 verschillende banken)

**Bank A - ABN AMRO** (`bank_a_transactions.csv`) - 17 transacties
- Tony Stark's hoofdaccount (NL91ABNA0417164300)
- Formaat: Standard ABN AMRO export (transaction_id, datum, bedrag, iban_from, iban_to)
- Grote transacties: €4,500-€9,900 (smurfing patterns)
- Internationale transfers: Switzerland, Monaco, Cyprus
- ATM withdrawals (NULL amounts)

**Bank B - Rabobank** (`bank_b_transactions.csv`) - 12 transacties
- Peter Parker's account (NL20RABO0123456789)
- Formaat: Rabobank CSV (trx_id, date, amount, from_account, to_account)
- Crypto exchange deposits
- Round-trip payments (refunds naar Tony Stark)
- Cloud services en software licenses

**Bank C - ING** (`bank_c_transactions.csv`) - 14 transacties
- Natasha Romanoff's account (NL69INGB0123456789)
- Formaat: ING export (id, transaction_date, value, source_iban, dest_iban)
- Internationale transfers: Luxembourg, UK
- Technical services, data analysis
- ATM withdrawals voor cash handling

**Bank D - ABN AMRO Branch** (`bank_d_transactions.csv`) - 8 transacties
- Bruce Banner's account (NL43ABNA0123456789)
- Formaat: ABN AMRO branch format (trans_ref, trans_date, debit_account, credit_account)
- IT infrastructure, encryption software
- VPN services, platform access
- Hardware en network setup

**Totaal**: 51 transacties, ~€350,000, periode 1-25 juni 2024

### Telecom Data (80 communicaties van 3 verschillende providers)

#### Calls (50 records van 3 providers)

**Telecom A - KPN** (`telecom_a_calls.csv`) - 17 calls
- Tony Stark's nummer (+31612345001)
- Formaat: KPN CDR (call_id, call_date, call_time, from_number, to_number, duration_seconds)
- Cell towers: TOWER-AMS-001 (Amsterdam)
- Internationale calls: +41 (CH), +377 (MC), +357 (CY)
- Langste gesprekken (365-720 seconden)

**Telecom B - Vodafone** (`telecom_b_calls.csv`) - 15 calls
- Natasha Romanoff's nummer (+31612345003)
- Formaat: Vodafone format (cdr_id, date, time, caller_number, callee_number, call_duration)
- Cell towers: CELL-RTM-005 (Rotterdam)
- Internationale calls: +352 (LU), +44 (GB)
- Strategische communicatie

**Telecom C - T-Mobile** (`telecom_c_calls.csv`) - 18 calls
- Peter Parker (+31612345002) en Bruce Banner (+31612345004)
- Formaat: T-Mobile (record_id, event_date, origin, destination, duration_sec)
- Cell towers: BASE-AMS-003, BASE-UTR-002
- Operationele coördinatie tussen koerier en IT specialist

#### SMS Messages (30 records van 3 providers)

**Telecom A - KPN** (`telecom_a_messages.csv`) - 10 SMS
- Formaat: KPN SMS export (message_id, from_number, to_number, message_content)
- Tony Stark's gecodeerde berichten
- Content: "Package ready", "Swiss connection confirmed", "Monaco deal signed"

**Telecom B - Vodafone** (`telecom_b_messages.csv`) - 10 SMS
- Formaat: Vodafone (sms_id, sender, receiver, text_content)
- Natasha Romanoff's coördinatie
- Content: "Transfer complete", "Luxembourg confirmed", "Settlement processed"

**Telecom C - T-Mobile** (`telecom_c_messages.csv`) - 10 SMS
- Formaat: T-Mobile (msg_ref, origin_msisdn, dest_msisdn, message_body)
- Peter & Bruce operationele updates
- Content: "Delivery successful", "Hardware received", "Network configured"

### Tekstbestanden (Documents)

#### **documents/chat_logs.txt**
- Geïntercepteerde Signal messenger groep "Project Alpha"
- Expliciete coördinatie van witwaspraktijken
- Bitcoin wallet adressen genoemd
- Vermelding van VPN, TOR, encryptie
- Internationale contacten in 6 landen

#### **documents/crypto_wallets.txt**
- **Bitcoin wallets**: 12.45 BTC (~€485,000)
- **Ethereum wallets**: 287.5 ETH (~€520,000)
- **Altcoins**: XRP (€58K), ADA (€82K), DOT (€68K)
- Mixing services gedetecteerd (Wasabi Wallet)
- Cross-chain bridging (BTC → ETH → XRP)
- Totale crypto waarde: ~€1,75 miljoen
- Blockchain forensics: 95/100 risk score

#### **documents/meeting_notes.txt**
- 5 fysieke meetings gedocumenteerd (Amsterdam, Rotterdam, Utrecht, Schiphol, Den Haag)
- Counter-surveillance gedrag waargenomen
- Telefoon intercepts getranscribeerd
- Surveillance foto's: 127 images
- Vehicle tracking data
- Evidence chain gedocumenteerd

## 🎯 Key Patterns om te Detecteren

1. **Smurfing**: Meerdere kleine transacties net onder €10.000
2. **Round Trip**: Geld heen en weer tussen accounts
3. **Layering**: Complexe transactiepaden
4. **Communication Patterns**: Calls net voor grote transacties
5. **Cross-border**: Transfers naar belastingparadijzen

## 🚀 Usage

### 1. Load Test Data
```bash
cd /Users/leeum21/Documents/Werk/Projects/data-platform/test-data/marvel-bandits
./load_marvel_case.sh
```

Dit script:
- ✓ Creëert investigation record (OND-2025-MARVEL)
- ✓ Laadt 51 bank transacties van 4 verschillende banken:
  - Bank A (ABN AMRO): 17 transacties via direct COPY
  - Bank B (Rabobank): 12 transacties via temp table (column mapping)
  - Bank C (ING): 14 transacties via temp table (column mapping)
  - Bank D (ABN AMRO branch): 8 transacties via temp table (column mapping)
- ✓ Laadt 50 calls van 3 telecom providers:
  - Telecom A (KPN): 17 calls via direct COPY
  - Telecom B (Vodafone): 15 calls via temp table (column mapping)
  - Telecom C (T-Mobile): 18 calls via temp table (column mapping)
- ✓ Laadt 30 messages van 3 telecom providers:
  - Telecom A (KPN): 10 SMS via direct COPY
  - Telecom B (Vodafone): 10 SMS via temp table (column mapping)
  - Telecom C (T-Mobile): 10 SMS via temp table (column mapping)
- ✓ Vult alle `raw_data` JSONB velden met source metadata
- ✓ Verifieert counts (131 totale records van 7 verschillende bronnen)

**Expected output**: "Load Complete! ✓ - 131 records from 7 sources"

### 2. Run Dagster Assets
Na het laden, materialiseer de canonical mapping assets:

```bash
# Navigate to Dagster UI
open http://localhost:3000

# Klik op "Materialize" voor:
1. canonical_transactions (mapt 50 transacties)
2. canonical_communications (mapt 80 calls+messages)
```

**Expected results**:
- 51 canonical transactions (82-100% valid)
- 80 canonical communications (100% valid)
- Marquez lineage events uitgezonden met multi-source tracking
- Data quality metrics getrackt per bron

### 3. Verify Data
```bash
./verify_marvel_case.sh
```

Dit script toont:
- ✓ Raw data counts (131 records verwacht van 7 bronnen)
- ✓ Canonical data counts (131 records verwacht)
- ✓ Data quality percentages per laag en per bron
- ✓ Suspect activity analyse (transacties per verdachte)
- ✓ Source breakdown (4 banks + 3 telecom providers)
- ✓ Next steps als er problemen zijn

**Expected output**:
```
Raw Data: 131 records from 7 sources
  - 4 banks: ABN AMRO (17), Rabobank (12), ING (14), ABN AMRO branch (8)
  - 3 telecom: KPN (27), Vodafone (25), T-Mobile (28)
Canonical Data: 131 records
Quality: 85-100%
✅ Data mapping complete!
```

### 4. Clear Test Data (voor herhaalde uitvoering)
```bash
./clear_marvel_case.sh
```

⚠️ **Waarschuwing**: Dit verwijdert ALLE Marvel Bandits data!

Dit script:
- 🗑️ Verwijdert alle canonical records (OND-2025-MARVEL)
- 🗑️ Verwijdert alle raw records (OND-2025-MARVEL)
- 🗑️ Verwijdert investigation record
- ✓ Verifieert cleanup (0 records remaining)
- ✓ Bevestigt systeem klaar voor fresh load

**Expected output**: "Cleanup Complete! ✓"

### 5. Explore Data & Documentation

**Marquez Lineage**:
```bash
open http://localhost:3001
```
- Bekijk job lineage graphs
- Check data quality metrics
- Trace dataset dependencies

**dbt Documentation**:
```bash
open http://localhost:8011
```
- Canonical data model beschrijving
- Column-level documentation
- Lineage graphs (dbt niveau)

**Dashboard**:
```bash
open http://localhost:8080/dashboard.html
```
- Quick overview van platform
- Links naar alle services
- Data quality stats

**Tekstdocumenten**:
```bash
# Open documents directory
open ./documents/

# Files:
- chat_logs.txt (intercepted Signal messages)
- crypto_wallets.txt (blockchain forensics)
- meeting_notes.txt (surveillance logs)
```

## 📈 Expected Results

Na het laden en mappen van de data:

**Raw Layer**:
- 51 bank transactions van 4 banken:
  - bank_a (ABN AMRO): 17 records
  - bank_b (Rabobank): 12 records  
  - bank_c (ING): 14 records
  - bank_d (ABN AMRO branch): 8 records
- 50 calls van 3 providers:
  - telecom_a (KPN): 17 calls
  - telecom_b (Vodafone): 15 calls
  - telecom_c (T-Mobile): 18 calls
- 30 messages van 3 providers:
  - telecom_a (KPN): 10 SMS
  - telecom_b (Vodafone): 10 SMS
  - telecom_c (T-Mobile): 10 SMS
- **Total**: 131 raw records van 7 verschillende bronnen

**Canonical Layer**:
- 51 canonical transactions (source: bank_a, bank_b, bank_c, bank_d)
  - Valid: 43-46 records (transactions met bedrag)
  - Warning: 5-8 records (ATM withdrawals met NULL amount)
  - Quality score: 82-90%
- 80 canonical communications (source: telecom_a, telecom_b, telecom_c)
  - Valid: 50 calls (met duration)
  - Warning: 30 SMS (messages zonder duration)
  - Quality score: 62-65%
- **Total**: 131 canonical records van 7 bronnen
- **Overall Quality**: 72-85%

**Marquez Lineage**:
- 2 jobs tracked: canonical_transactions, canonical_communications
- Input datasets: raw_transactions (4 sources), raw_calls (3 sources), raw_messages (3 sources)
- Output datasets: canonical_transaction, canonical_communication
- Data quality facets: records_processed, records_valid, records_warning, validation_rate per source
- Complete lineage graphs visible in UI met multi-source tracking

**dbt Models**:
- `stg_transactions` reads from canonical.canonical_transaction
- `stg_communications` reads from canonical.canonical_communication
- `stg_persons` (not yet populated)

**Investigation Analytics**:
- Total money flow: ~€350,000
- Crypto conversions: €45,600
- Suspects involved: 4 (Tony, Peter, Natasha, Bruce)
- Data sources: 7 (4 banks + 3 telecom providers)
- International jurisdictions: 6 (NL, CH, LU, MC, CY, GB)
- Time period: June 1-25, 2024 (25 days)
- Communication/transaction ratio: 80/51 = 1.57 comms per transaction

## 🔍 Investigation Flows

### Flow 1: Follow the Money
1. Start bij Tony Stark IBAN
2. Trace naar Peter Parker (koerier)
3. Trace naar Natasha (witwasstrategie)
4. End bij crypto exchange

### Flow 2: Communication Analysis
1. Calls tussen verdachten
2. Timing analyse (call → transaction binnen 1 uur)
3. Burner phone patterns
4. Encrypted messaging hints

### Flow 3: Network Analysis
1. Transaction graph tussen alle verdachten
2. Find central node (Tony Stark)
3. Identify money mules
4. Trace international connections

## 📝 Notes

- Alle data is **synthetisch** en bevat geen echte persoonlijke informatie
- IBANs zijn **formeel correct** maar fictief
- Telefoonnummers volgen E.164 format maar zijn niet echt
- Bedragen zijn **realistisch** voor witwaspraktijken
- Timestamps zijn **gecoördineerd** voor pattern detection

---

**Created**: 15 oktober 2025  
**Last Updated**: 15 oktober 2025  
**Status**: Ready for Demo
