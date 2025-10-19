-- ==============================================================================
-- Investigation Access Test Data
-- ==============================================================================
-- Creates sample investigations and assigns them to investigators
-- This demonstrates Row-Level Security with JWT-based authentication
-- ==============================================================================

-- Create additional test investigations
INSERT INTO investigations (investigation_id, name, status, description, start_date, created_by)
VALUES 
    ('OND-2025-000002', 'Fraude Onderzoek Alpha', 'active', 'Verdacht financieel patroon gedetecteerd', '2025-10-15', 'admin.user'),
    ('OND-2025-000003', 'Witwas Zaak Beta', 'active', 'Grote transacties naar offshore accounts', '2025-09-01', 'admin.user'),
    ('OND-2025-000004', 'KYC Verificatie Gamma', 'active', 'Klant identiteit verificatie vereist', '2025-10-01', 'admin.user'),
    ('OND-2025-000005', 'Belasting Ontduiking Delta', 'closed', 'Afgerond onderzoek naar belastingontduiking', '2025-08-01', 'admin.user')
ON CONFLICT (investigation_id) DO NOTHING;

-- Create sample raw transactions for each investigation
-- Note: Need to create data_sources first, using existing source_id
INSERT INTO raw_transactions (investigation_id, source_id, datum, bedrag, iban_from, iban_to, omschrijving)
VALUES
    -- Investigation 2 transactions
    ('OND-2025-000002', 'SRC-001', '2025-10-10', 15000.00, 'NL12BANK1234567890', 'NL98BANK0987654321', 'Verdachte overboeking'),
    ('OND-2025-000002', 'SRC-001', '2025-10-11', 25000.00, 'NL12BANK1234567890', 'DE89BANK1111222233', 'Internationale transfer'),
    ('OND-2025-000002', 'SRC-001', '2025-10-12', 8500.00, 'NL98BANK0987654321', 'FR14BANK4444555566', 'Contante storting'),
    
    -- Investigation 3 transactions
    ('OND-2025-000003', 'SRC-001', '2025-09-15', 250000.00, 'NL45BANK5555666677', 'KY99BANK9999888877', 'Offshore transfer'),
    ('OND-2025-000003', 'SRC-001', '2025-09-16', 180000.00, 'NL45BANK5555666677', 'PA88BANK7777666655', 'Panama account'),
    ('OND-2025-000003', 'SRC-001', '2025-09-20', 95000.00, 'BE33BANK1122334455', 'NL45BANK5555666677', 'Return transfer'),
    
    -- Investigation 4 transactions
    ('OND-2025-000004', 'SRC-001', '2025-10-05', 5000.00, 'NL77BANK9988776655', 'NL88BANK1122334455', 'KYC pending verification'),
    ('OND-2025-000004', 'SRC-001', '2025-10-06', 3200.00, 'NL77BANK9988776655', 'GB11BANK2233445566', 'UK transfer'),
    
    -- Investigation 5 transactions (closed case)
    ('OND-2025-000005', 'SRC-001', '2025-08-01', 12000.00, 'NL22BANK3344556677', 'LU66BANK7788990011', 'Closed case - resolved'),
    ('OND-2025-000005', 'SRC-001', '2025-08-05', 8000.00, 'LU66BANK7788990011', 'NL22BANK3344556677', 'Return payment')
ON CONFLICT DO NOTHING;

-- Create sample raw calls for investigations
INSERT INTO raw_calls (investigation_id, source_id, call_date, call_time, duration_seconds, caller_number, called_number, call_type)
VALUES
    -- Investigation 2 calls
    ('OND-2025-000002', 'SRC-001', '2025-10-10', '14:23:00', 420, '+31612345678', '+31687654321', 'outgoing'),
    ('OND-2025-000002', 'SRC-001', '2025-10-11', '09:15:00', 180, '+31612345678', '+49301234567', 'outgoing'),
    
    -- Investigation 3 calls
    ('OND-2025-000003', 'SRC-001', '2025-09-15', '16:30:00', 620, '+31698765432', '+507555123456', 'outgoing'),
    ('OND-2025-000003', 'SRC-001', '2025-09-16', '11:45:00', 380, '+32471234567', '+31698765432', 'incoming'),
    
    -- Investigation 4 calls
    ('OND-2025-000004', 'SRC-001', '2025-10-05', '13:20:00', 240, '+31687654321', '+44207123456', 'outgoing')
ON CONFLICT DO NOTHING;

-- Create sample raw messages
INSERT INTO raw_messages (investigation_id, source_id, message_date, message_time, sender_number, recipient_number, message_text, message_type)
VALUES
    -- Investigation 2 messages
    ('OND-2025-000002', 'SRC-001', '2025-10-10', '14:25:00', '+31612345678', '+31687654321', 'Alles geregeld voor morgen?', 'sms'),
    ('OND-2025-000002', 'SRC-001', '2025-10-11', '09:16:00', '+31612345678', '+49301234567', 'Transfer completed', 'whatsapp'),
    
    -- Investigation 3 messages
    ('OND-2025-000003', 'SRC-001', '2025-09-15', '16:35:00', '+31698765432', '+507555123456', 'Bedrag is onderweg', 'sms'),
    ('OND-2025-000003', 'SRC-001', '2025-09-16', '11:50:00', '+32471234567', '+31698765432', 'Ontvangen en verwerkt', 'whatsapp')
ON CONFLICT DO NOTHING;

-- ==============================================================================
-- ASSIGN INVESTIGATION ACCESS
-- ==============================================================================

-- Clear existing access (for clean test)
TRUNCATE user_investigation_access;

-- Grant access to jane.investigator for investigations 1 and 2
-- These are the investigations she should see when authenticated with JWT
INSERT INTO user_investigation_access (user_id, investigation_id, access_level, granted_by, granted_at, expires_at)
VALUES 
    ('jane.investigator', 'OND-2025-000001', 'read', 'admin.user', NOW(), NULL),
    ('jane.investigator', 'OND-2025-000002', 'write', 'admin.user', NOW(), NOW() + INTERVAL '30 days');

-- Grant access to another investigator for investigation 3
-- Create a new investigator user in database (fallback for testing)
INSERT INTO user_investigation_access (user_id, investigation_id, access_level, granted_by, granted_at, expires_at)
VALUES 
    ('john.engineer', 'OND-2025-000003', 'read', 'admin.user', NOW(), NULL);

-- Grant temporary access to investigation 4 (expires in 7 days)
INSERT INTO user_investigation_access (user_id, investigation_id, access_level, granted_by, granted_at, expires_at)
VALUES 
    ('jane.investigator', 'OND-2025-000004', 'read', 'admin.user', NOW(), NOW() + INTERVAL '7 days');

-- Investigation 5 has NO access grants (only admins/engineers can see it)

-- ==============================================================================
-- VERIFICATION QUERIES
-- ==============================================================================

-- Show all investigations
SELECT investigation_id, name, status 
FROM investigations 
ORDER BY investigation_id;

-- Show investigation access assignments
SELECT 
    user_id,
    investigation_id,
    access_level,
    granted_by,
    granted_at,
    expires_at,
    CASE 
        WHEN expires_at IS NULL THEN 'Never expires'
        WHEN expires_at > NOW() THEN 'Active (' || EXTRACT(DAY FROM expires_at - NOW()) || ' days left)'
        ELSE 'EXPIRED'
    END as status
FROM user_investigation_access
ORDER BY user_id, investigation_id;

-- Count data per investigation
SELECT 
    i.investigation_id,
    i.name,
    i.status,
    COUNT(DISTINCT t.transaction_id) as transaction_count,
    COUNT(DISTINCT c.call_id) as call_count,
    COUNT(DISTINCT m.message_id) as message_count
FROM investigations i
LEFT JOIN raw_transactions t ON i.investigation_id = t.investigation_id
LEFT JOIN raw_calls c ON i.investigation_id = c.investigation_id
LEFT JOIN raw_messages m ON i.investigation_id = m.investigation_id
GROUP BY i.investigation_id, i.name, i.status
ORDER BY i.investigation_id;

-- ==============================================================================
-- INFO
-- ==============================================================================

DO $$
BEGIN
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'Investigation Access Test Data Created';
  RAISE NOTICE '=================================================================';
  RAISE NOTICE 'Investigations:';
  RAISE NOTICE '  • OND-2025-000001: Original investigation';
  RAISE NOTICE '  • OND-2025-000002: Fraude Alpha (3 tx, 2 calls, 2 msgs)';
  RAISE NOTICE '  • OND-2025-000003: Witwas Beta (3 tx, 2 calls, 2 msgs)';
  RAISE NOTICE '  • OND-2025-000004: KYC Gamma (2 tx, 1 call, 0 msgs)';
  RAISE NOTICE '  • OND-2025-000005: Closed case (2 tx, 0 calls, 0 msgs)';
  RAISE NOTICE '';
  RAISE NOTICE 'Access Assignments:';
  RAISE NOTICE '  • jane.investigator → OND-2025-000001 (read, permanent)';
  RAISE NOTICE '  • jane.investigator → OND-2025-000002 (write, expires 30 days)';
  RAISE NOTICE '  • jane.investigator → OND-2025-000004 (read, expires 7 days)';
  RAISE NOTICE '  • john.engineer → OND-2025-000003 (read, permanent)';
  RAISE NOTICE '  • NO ACCESS → OND-2025-000005 (only admins/engineers)';
  RAISE NOTICE '';
  RAISE NOTICE 'Testing:';
  RAISE NOTICE '  • jane.investigator should see: 1, 2, 4 (3 investigations)';
  RAISE NOTICE '  • john.engineer should see: ALL (engineer role)';
  RAISE NOTICE '  • bob.analyst should see: ALL canonical data';
  RAISE NOTICE '  • admin.user should see: ALL (admin role)';
  RAISE NOTICE '=================================================================';
END $$;
