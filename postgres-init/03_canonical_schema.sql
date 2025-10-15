-- ============================================================================
-- Canonical Integration Layer - Database Schema
-- ============================================================================
-- Purpose: Enforce semantic consistency across heterogeneous source systems
-- Version: 1.0
-- Created: 2025-10-15
-- ============================================================================

-- Create canonical schema
CREATE SCHEMA IF NOT EXISTS canonical;

-- ============================================================================
-- 1. CANONICAL TRANSACTION
-- ============================================================================
-- Unified representation of financial transactions regardless of source
-- ============================================================================

CREATE TABLE IF NOT EXISTS canonical.canonical_transaction (
    -- Primary Key
    canonical_transaction_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source Traceability
    source_system_id            VARCHAR(50) NOT NULL,
    source_record_id            VARCHAR(100) NOT NULL,
    source_file_name            VARCHAR(255),
    ingestion_timestamp         TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Investigation Context
    investigation_id            VARCHAR(50) NOT NULL,
    
    -- Transaction Core Attributes (STANDARDIZED)
    transaction_reference       VARCHAR(100),
    transaction_datetime        TIMESTAMP NOT NULL,
    posting_date                DATE,
    value_date                  DATE,
    
    -- Monetary Attributes (STANDARDIZED)
    -- Note: amount can be NULL for ATM withdrawals without clear amounts
    amount                      DECIMAL(15,2),
    currency_code               CHAR(3) NOT NULL,
    
    -- Account Attributes (STANDARDIZED)
    debtor_account_id           VARCHAR(100),
    debtor_account_type         VARCHAR(20),
    debtor_name                 VARCHAR(255),
    debtor_bank_code            VARCHAR(20),
    creditor_account_id         VARCHAR(100),
    creditor_account_type       VARCHAR(20),
    creditor_name               VARCHAR(255),
    creditor_bank_code          VARCHAR(20),
    
    -- Transaction Details (STANDARDIZED)
    transaction_type            VARCHAR(50),
    payment_method              VARCHAR(50),
    description                 TEXT,
    reference_number            VARCHAR(100),
    
    -- Metadata
    is_cancelled                BOOLEAN DEFAULT FALSE,
    is_reversal                 BOOLEAN DEFAULT FALSE,
    related_transaction_id      UUID,
    
    -- Data Quality Flags
    validation_status           VARCHAR(20) DEFAULT 'valid',
    validation_messages         JSONB,
    data_completeness_score     INTEGER,
    
    -- Original Source Data (for audit)
    source_raw_data             JSONB NOT NULL,
    
    -- Audit
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW(),
    created_by                  VARCHAR(100) DEFAULT 'system',
    
    -- Constraints
    CONSTRAINT uq_canonical_tx_source UNIQUE (source_system_id, source_record_id),
    CONSTRAINT chk_canonical_tx_amount CHECK (
        (amount IS NULL) OR
        (amount = 0 AND currency_code IS NULL) OR 
        (amount != 0 AND currency_code IS NOT NULL)
    ),
    CONSTRAINT chk_canonical_tx_validation_status CHECK (
        validation_status IN ('valid', 'warning', 'error', 'pending')
    ),
    CONSTRAINT chk_canonical_tx_account_type CHECK (
        debtor_account_type IN ('iban', 'account_number', 'bic', 'swift', 'other', NULL)
    ),
    CONSTRAINT chk_canonical_tx_transaction_type CHECK (
        transaction_type IN ('debit', 'credit', 'transfer', 'payment', 'withdrawal', 'deposit', 'fee', 'interest', 'other', NULL)
    )
);

-- Indexes for canonical_transaction
CREATE INDEX idx_canonical_tx_investigation 
    ON canonical.canonical_transaction(investigation_id);

CREATE INDEX idx_canonical_tx_datetime 
    ON canonical.canonical_transaction(transaction_datetime);

CREATE INDEX idx_canonical_tx_debtor 
    ON canonical.canonical_transaction(debtor_account_id);

CREATE INDEX idx_canonical_tx_creditor 
    ON canonical.canonical_transaction(creditor_account_id);

CREATE INDEX idx_canonical_tx_amount 
    ON canonical.canonical_transaction(amount);

CREATE INDEX idx_canonical_tx_source 
    ON canonical.canonical_transaction(source_system_id, source_record_id);

CREATE INDEX idx_canonical_tx_validation 
    ON canonical.canonical_transaction(validation_status);

CREATE INDEX idx_canonical_tx_currency 
    ON canonical.canonical_transaction(currency_code);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION canonical.update_canonical_transaction_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_canonical_tx_updated_at
    BEFORE UPDATE ON canonical.canonical_transaction
    FOR EACH ROW
    EXECUTE FUNCTION canonical.update_canonical_transaction_timestamp();

-- Comments
COMMENT ON TABLE canonical.canonical_transaction IS 
    'Unified canonical representation of financial transactions from all source systems';

COMMENT ON COLUMN canonical.canonical_transaction.source_system_id IS 
    'Identifier of the source system (e.g., bank_a, bank_b)';

COMMENT ON COLUMN canonical.canonical_transaction.validation_status IS 
    'Data quality status: valid (passed all checks), warning (minor issues), error (failed validation), pending (not yet validated)';

COMMENT ON COLUMN canonical.canonical_transaction.source_raw_data IS 
    'Complete original record in JSONB format for audit trail and reprocessing';


-- ============================================================================
-- 2. CANONICAL COMMUNICATION
-- ============================================================================
-- Unified representation of communication events (calls, SMS, emails)
-- ============================================================================

CREATE TABLE IF NOT EXISTS canonical.canonical_communication (
    -- Primary Key
    canonical_communication_id  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source Traceability
    source_system_id            VARCHAR(50) NOT NULL,
    source_record_id            VARCHAR(100) NOT NULL,
    source_file_name            VARCHAR(255),
    ingestion_timestamp         TIMESTAMP NOT NULL DEFAULT NOW(),
    
    -- Investigation Context
    investigation_id            VARCHAR(50) NOT NULL,
    
    -- Communication Core Attributes (STANDARDIZED)
    communication_type          VARCHAR(20) NOT NULL,
    communication_datetime      TIMESTAMP NOT NULL,
    duration_seconds            INTEGER,
    
    -- Participant Attributes (STANDARDIZED)
    originator_id               VARCHAR(100) NOT NULL,
    originator_type             VARCHAR(20) NOT NULL,
    originator_name             VARCHAR(255),
    originator_location         JSONB,
    recipient_id                VARCHAR(100) NOT NULL,
    recipient_type              VARCHAR(20) NOT NULL,
    recipient_name              VARCHAR(255),
    recipient_location          JSONB,
    
    -- Communication Details (STANDARDIZED)
    direction                   VARCHAR(20),
    call_status                 VARCHAR(20),
    location_info               JSONB,
    
    -- Content (if applicable)
    message_content             TEXT,
    message_subject             VARCHAR(500),
    attachment_count            INTEGER DEFAULT 0,
    content_hash                VARCHAR(64),
    
    -- Network Metadata
    network_operator            VARCHAR(100),
    connection_type             VARCHAR(50),
    cell_tower_id               VARCHAR(100),
    imei                        VARCHAR(20),
    
    -- Data Quality Flags
    validation_status           VARCHAR(20) DEFAULT 'valid',
    validation_messages         JSONB,
    data_completeness_score     INTEGER,
    
    -- Original Source Data
    source_raw_data             JSONB NOT NULL,
    
    -- Audit
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW(),
    created_by                  VARCHAR(100) DEFAULT 'system',
    
    -- Constraints
    CONSTRAINT uq_canonical_comm_source UNIQUE (source_system_id, source_record_id),
    CONSTRAINT chk_canonical_comm_duration CHECK (
        (communication_type != 'call') OR 
        (communication_type = 'call' AND duration_seconds IS NOT NULL)
    ),
    CONSTRAINT chk_canonical_comm_type CHECK (
        communication_type IN ('call', 'sms', 'mms', 'email', 'voicemail', 'data', 'other')
    ),
    CONSTRAINT chk_canonical_comm_originator_type CHECK (
        originator_type IN ('msisdn', 'email', 'imei', 'imsi', 'ip', 'other')
    ),
    CONSTRAINT chk_canonical_comm_direction CHECK (
        direction IN ('outbound', 'inbound', 'internal', 'unknown', NULL)
    ),
    CONSTRAINT chk_canonical_comm_validation_status CHECK (
        validation_status IN ('valid', 'warning', 'error', 'pending')
    )
);

-- Indexes for canonical_communication
CREATE INDEX idx_canonical_comm_investigation 
    ON canonical.canonical_communication(investigation_id);

CREATE INDEX idx_canonical_comm_datetime 
    ON canonical.canonical_communication(communication_datetime);

CREATE INDEX idx_canonical_comm_originator 
    ON canonical.canonical_communication(originator_id);

CREATE INDEX idx_canonical_comm_recipient 
    ON canonical.canonical_communication(recipient_id);

CREATE INDEX idx_canonical_comm_type 
    ON canonical.canonical_communication(communication_type);

CREATE INDEX idx_canonical_comm_source 
    ON canonical.canonical_communication(source_system_id, source_record_id);

CREATE INDEX idx_canonical_comm_validation 
    ON canonical.canonical_communication(validation_status);

-- Full-text search index for message content
CREATE INDEX idx_canonical_comm_message_fts 
    ON canonical.canonical_communication 
    USING gin(to_tsvector('dutch', COALESCE(message_content, '')));

-- Trigger for updated_at
CREATE TRIGGER trg_canonical_comm_updated_at
    BEFORE UPDATE ON canonical.canonical_communication
    FOR EACH ROW
    EXECUTE FUNCTION canonical.update_canonical_transaction_timestamp();

-- Comments
COMMENT ON TABLE canonical.canonical_communication IS 
    'Unified canonical representation of communication events (calls, SMS, emails) from all telecom sources';

COMMENT ON COLUMN canonical.canonical_communication.communication_type IS 
    'Type of communication: call, sms, mms, email, voicemail, data, other';

COMMENT ON COLUMN canonical.canonical_communication.originator_type IS 
    'Type of originator identifier: msisdn (phone), email, imei, imsi, ip';


-- ============================================================================
-- 3. CANONICAL PERSON
-- ============================================================================
-- Unified entity resolution and person/organization profiles
-- ============================================================================

CREATE TABLE IF NOT EXISTS canonical.canonical_person (
    -- Primary Key
    canonical_person_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Investigation Context
    investigation_id            VARCHAR(50) NOT NULL,
    
    -- Identity Attributes (STANDARDIZED)
    person_type                 VARCHAR(20) NOT NULL DEFAULT 'unknown',
    primary_identifier          VARCHAR(100) NOT NULL,
    identifier_type             VARCHAR(20) NOT NULL,
    alternative_identifiers     JSONB,
    
    -- Name Attributes (STANDARDIZED)
    full_name                   VARCHAR(255),
    first_name                  VARCHAR(100),
    last_name                   VARCHAR(100),
    middle_name                 VARCHAR(100),
    name_prefix                 VARCHAR(20),
    name_suffix                 VARCHAR(20),
    aliases                     JSONB,
    
    -- Contact Attributes
    phone_numbers               JSONB,
    email_addresses             JSONB,
    postal_addresses            JSONB,
    
    -- Financial Attributes
    bank_accounts               JSONB,
    
    -- Organization Attributes (if person_type = 'legal')
    organization_name           VARCHAR(255),
    organization_type           VARCHAR(50),
    registration_number         VARCHAR(100),
    tax_number                  VARCHAR(100),
    
    -- Demographics (if available)
    date_of_birth               DATE,
    place_of_birth              VARCHAR(100),
    nationality                 VARCHAR(2),
    gender                      VARCHAR(20),
    
    -- Role in Investigation
    person_role                 VARCHAR(50),
    risk_level                  VARCHAR(20),
    notes                       TEXT,
    
    -- Data Quality
    confidence_score            DECIMAL(3,2),
    data_completeness_pct       INTEGER,
    
    -- Source Attribution
    source_systems              JSONB,
    first_seen                  TIMESTAMP,
    last_seen                   TIMESTAMP,
    mention_count               INTEGER DEFAULT 1,
    
    -- Audit
    created_at                  TIMESTAMP DEFAULT NOW(),
    updated_at                  TIMESTAMP DEFAULT NOW(),
    created_by                  VARCHAR(100) DEFAULT 'system',
    
    -- Constraints
    CONSTRAINT chk_canonical_person_type CHECK (
        person_type IN ('natural', 'legal', 'unknown')
    ),
    CONSTRAINT chk_canonical_person_identifier_type CHECK (
        identifier_type IN ('iban', 'msisdn', 'email', 'bsn', 'passport', 'kvk', 'btw', 'other')
    ),
    CONSTRAINT chk_canonical_person_role CHECK (
        person_role IN ('suspect', 'victim', 'witness', 'related', 'unknown', NULL)
    ),
    CONSTRAINT chk_canonical_person_risk CHECK (
        risk_level IN ('high', 'medium', 'low', 'unknown', NULL)
    ),
    CONSTRAINT chk_canonical_person_confidence CHECK (
        confidence_score IS NULL OR (confidence_score >= 0.00 AND confidence_score <= 1.00)
    ),
    CONSTRAINT chk_canonical_person_completeness CHECK (
        data_completeness_pct IS NULL OR (data_completeness_pct >= 0 AND data_completeness_pct <= 100)
    )
);

-- Indexes for canonical_person
CREATE INDEX idx_canonical_person_investigation 
    ON canonical.canonical_person(investigation_id);

CREATE INDEX idx_canonical_person_identifier 
    ON canonical.canonical_person(primary_identifier, identifier_type);

CREATE INDEX idx_canonical_person_name 
    ON canonical.canonical_person(last_name, first_name);

CREATE INDEX idx_canonical_person_type 
    ON canonical.canonical_person(person_type);

CREATE INDEX idx_canonical_person_role 
    ON canonical.canonical_person(person_role);

CREATE INDEX idx_canonical_person_risk 
    ON canonical.canonical_person(risk_level);

-- Full-text search for names
CREATE INDEX idx_canonical_person_name_fts 
    ON canonical.canonical_person 
    USING gin(to_tsvector('dutch', 
        COALESCE(full_name, '') || ' ' || 
        COALESCE(organization_name, '')
    ));

-- Trigger for updated_at
CREATE TRIGGER trg_canonical_person_updated_at
    BEFORE UPDATE ON canonical.canonical_person
    FOR EACH ROW
    EXECUTE FUNCTION canonical.update_canonical_transaction_timestamp();

-- Comments
COMMENT ON TABLE canonical.canonical_person IS 
    'Unified entity resolution: persons and organizations involved in investigations';

COMMENT ON COLUMN canonical.canonical_person.person_type IS 
    'Type of entity: natural (person), legal (organization), unknown';

COMMENT ON COLUMN canonical.canonical_person.confidence_score IS 
    'Entity resolution confidence score (0.00 to 1.00)';


-- ============================================================================
-- 4. CANONICAL MAPPING LOG
-- ============================================================================
-- Audit trail of raw → canonical mappings
-- ============================================================================

CREATE TABLE IF NOT EXISTS canonical.canonical_mapping_log (
    mapping_log_id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Source Info
    source_system_id            VARCHAR(50) NOT NULL,
    source_table                VARCHAR(100) NOT NULL,
    source_record_id            VARCHAR(100) NOT NULL,
    
    -- Target Info
    canonical_table             VARCHAR(100) NOT NULL,
    canonical_record_id         UUID NOT NULL,
    
    -- Mapping Details
    mapper_version              VARCHAR(20),
    mapping_rules_applied       JSONB,
    transformations_applied     JSONB,
    
    -- Validation Results
    validation_status           VARCHAR(20),
    validation_errors           JSONB,
    validation_warnings         JSONB,
    
    -- Performance
    processing_time_ms          INTEGER,
    
    -- Audit
    mapped_at                   TIMESTAMP DEFAULT NOW(),
    mapped_by                   VARCHAR(100) DEFAULT 'system'
);

CREATE INDEX idx_canonical_mapping_source 
    ON canonical.canonical_mapping_log(source_system_id, source_record_id);

CREATE INDEX idx_canonical_mapping_target 
    ON canonical.canonical_mapping_log(canonical_table, canonical_record_id);

CREATE INDEX idx_canonical_mapping_status 
    ON canonical.canonical_mapping_log(validation_status);

CREATE INDEX idx_canonical_mapping_timestamp 
    ON canonical.canonical_mapping_log(mapped_at);

COMMENT ON TABLE canonical.canonical_mapping_log IS 
    'Audit trail of all raw to canonical mappings with validation results';


-- ============================================================================
-- 5. VIEWS FOR EASY ACCESS
-- ============================================================================

-- Valid transactions only
CREATE OR REPLACE VIEW canonical.v_valid_transactions AS
SELECT * FROM canonical.canonical_transaction
WHERE validation_status = 'valid';

-- Valid communications only
CREATE OR REPLACE VIEW canonical.v_valid_communications AS
SELECT * FROM canonical.canonical_communication
WHERE validation_status = 'valid';

-- Transaction summary by source
CREATE OR REPLACE VIEW canonical.v_transaction_source_summary AS
SELECT 
    source_system_id,
    investigation_id,
    COUNT(*) as total_transactions,
    SUM(CASE WHEN validation_status = 'valid' THEN 1 ELSE 0 END) as valid_count,
    SUM(CASE WHEN validation_status = 'warning' THEN 1 ELSE 0 END) as warning_count,
    SUM(CASE WHEN validation_status = 'error' THEN 1 ELSE 0 END) as error_count,
    ROUND(AVG(data_completeness_score), 2) as avg_completeness,
    MIN(transaction_datetime) as first_transaction,
    MAX(transaction_datetime) as last_transaction,
    SUM(amount) as total_amount
FROM canonical.canonical_transaction
GROUP BY source_system_id, investigation_id;

COMMENT ON VIEW canonical.v_transaction_source_summary IS 
    'Summary statistics of canonical transactions grouped by source system';


-- ============================================================================
-- 6. GRANTS
-- ============================================================================

-- Grant read access to analytics role
GRANT USAGE ON SCHEMA canonical TO analytics_role;
GRANT SELECT ON ALL TABLES IN SCHEMA canonical TO analytics_role;

-- Grant write access to etl role
GRANT USAGE ON SCHEMA canonical TO etl_role;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA canonical TO etl_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA canonical TO etl_role;


-- ============================================================================
-- DEPLOYMENT NOTES
-- ============================================================================
-- 
-- 1. Run this script on superset database
-- 2. Verify tables created: \dt canonical.*
-- 3. Check indexes: \di canonical.*
-- 4. Test insert with sample data
-- 5. Update Dagster canonical_assets.py to use these tables
-- 
-- ============================================================================
