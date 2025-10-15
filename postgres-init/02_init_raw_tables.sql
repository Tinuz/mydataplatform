-- Raw data tables for investigation records
-- These tables store detail records from uploaded files

-- Raw bank transactions
CREATE TABLE IF NOT EXISTS raw_transactions (
    transaction_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id VARCHAR(50) NOT NULL,
    source_id VARCHAR(50) NOT NULL,
    
    -- Transaction details
    iban_from VARCHAR(34),
    iban_to VARCHAR(34),
    bedrag DECIMAL(15, 2),
    datum DATE,
    omschrijving TEXT,
    
    -- Provider-specific fields (stored as JSONB for flexibility)
    raw_data JSONB,
    
    -- Metadata
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- Indexes for performance
    CONSTRAINT fk_source FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_raw_transactions_investigation ON raw_transactions(investigation_id);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_source ON raw_transactions(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_date ON raw_transactions(datum);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_iban_from ON raw_transactions(iban_from);
CREATE INDEX IF NOT EXISTS idx_raw_transactions_iban_to ON raw_transactions(iban_to);

-- Raw telecom call records
CREATE TABLE IF NOT EXISTS raw_calls (
    call_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id VARCHAR(50) NOT NULL,
    source_id VARCHAR(50) NOT NULL,
    
    -- Call details
    caller_number VARCHAR(20),
    called_number VARCHAR(20),
    call_date DATE,
    call_time TIME,
    duration_seconds INTEGER,
    call_type VARCHAR(20), -- inbound, outbound, missed
    
    -- Provider-specific fields
    raw_data JSONB,
    
    -- Metadata
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_call_source FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_raw_calls_investigation ON raw_calls(investigation_id);
CREATE INDEX IF NOT EXISTS idx_raw_calls_source ON raw_calls(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_calls_date ON raw_calls(call_date);
CREATE INDEX IF NOT EXISTS idx_raw_calls_caller ON raw_calls(caller_number);
CREATE INDEX IF NOT EXISTS idx_raw_calls_called ON raw_calls(called_number);

-- Raw telecom messages (SMS)
CREATE TABLE IF NOT EXISTS raw_messages (
    message_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    investigation_id VARCHAR(50) NOT NULL,
    source_id VARCHAR(50) NOT NULL,
    
    -- Message details
    sender_number VARCHAR(20),
    recipient_number VARCHAR(20),
    message_date DATE,
    message_time TIME,
    message_text TEXT,
    message_type VARCHAR(20), -- sms, mms, etc
    
    -- Provider-specific fields
    raw_data JSONB,
    
    -- Metadata
    loaded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT fk_message_source FOREIGN KEY (source_id) REFERENCES data_sources(source_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_raw_messages_investigation ON raw_messages(investigation_id);
CREATE INDEX IF NOT EXISTS idx_raw_messages_source ON raw_messages(source_id);
CREATE INDEX IF NOT EXISTS idx_raw_messages_date ON raw_messages(message_date);
CREATE INDEX IF NOT EXISTS idx_raw_messages_sender ON raw_messages(sender_number);
CREATE INDEX IF NOT EXISTS idx_raw_messages_recipient ON raw_messages(recipient_number);

-- Grant permissions
GRANT SELECT, INSERT, UPDATE, DELETE ON raw_transactions TO superset;
GRANT SELECT, INSERT, UPDATE, DELETE ON raw_calls TO superset;
GRANT SELECT, INSERT, UPDATE, DELETE ON raw_messages TO superset;

-- Comment tables for documentation
COMMENT ON TABLE raw_transactions IS 'Raw bank transaction records from uploaded CSV files';
COMMENT ON TABLE raw_calls IS 'Raw telecom call records from uploaded CSV files';
COMMENT ON TABLE raw_messages IS 'Raw telecom message (SMS/MMS) records from uploaded CSV files';
