-- ============================================================================
-- Database Improvement Migration
-- ============================================================================
-- Purpose: Fix referential integrity and cleanup unused schemas
-- Date: 15 oktober 2025
-- Ticket: PLATFORM-CLEANUP-001
-- ============================================================================

BEGIN;

-- ============================================================================
-- PART 1: Drop Unused Schemas
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '🗑️  Dropping unused schemas...'; END $$;

-- Drop weather schema (broken view, no data)
DROP SCHEMA IF EXISTS weather CASCADE;

-- Drop crypto schema (no data, not used)
DROP SCHEMA IF EXISTS crypto CASCADE;

-- Drop cell_towers schema (no tables)
DROP SCHEMA IF EXISTS cell_towers CASCADE;

DO $$ BEGIN RAISE NOTICE '✅ Unused schemas dropped'; END $$;

-- ============================================================================
-- PART 2: Drop Views (to allow column type changes)
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '👁️  Dropping views temporarily...'; END $$;

-- Drop canonical views (will be recreated in 03_canonical_schema.sql on next restart)
DROP VIEW IF EXISTS canonical.v_valid_transactions CASCADE;
DROP VIEW IF EXISTS canonical.v_valid_communications CASCADE;
DROP VIEW IF EXISTS canonical.v_transaction_source_summary CASCADE;

-- Drop staging views (dbt models - will be recreated on next dbt run)
DROP VIEW IF EXISTS staging.stg_bank_transactions CASCADE;
DROP VIEW IF EXISTS staging.stg_telecom_calls CASCADE;
DROP VIEW IF EXISTS staging.stg_telecom_messages CASCADE;

DO $$ BEGIN RAISE NOTICE '✅ Views dropped (will be recreated after migration)'; END $$;

-- ============================================================================
-- PART 3: Fix Type Inconsistencies
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '🔧 Fixing investigation_id type inconsistencies...'; END $$;

-- Fix raw_transactions
ALTER TABLE raw_transactions 
  ALTER COLUMN investigation_id TYPE VARCHAR(20);

-- Fix raw_calls
ALTER TABLE raw_calls 
  ALTER COLUMN investigation_id TYPE VARCHAR(20);

-- Fix raw_messages
ALTER TABLE raw_messages 
  ALTER COLUMN investigation_id TYPE VARCHAR(20);

-- Fix canonical_transaction
ALTER TABLE canonical.canonical_transaction
  ALTER COLUMN investigation_id TYPE VARCHAR(20);

-- Fix canonical_communication
ALTER TABLE canonical.canonical_communication
  ALTER COLUMN investigation_id TYPE VARCHAR(20);

DO $$ BEGIN RAISE NOTICE '✅ Types fixed to VARCHAR(20)'; END $$;

-- ============================================================================
-- PART 4: Add Foreign Keys to raw_* tables
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '🔗 Adding foreign key constraints...'; END $$;

-- raw_transactions → investigations
ALTER TABLE raw_transactions
  ADD CONSTRAINT fk_raw_tx_investigation
  FOREIGN KEY (investigation_id) 
  REFERENCES investigations(investigation_id) 
  ON DELETE CASCADE;

-- raw_calls → investigations  
ALTER TABLE raw_calls
  ADD CONSTRAINT fk_raw_calls_investigation
  FOREIGN KEY (investigation_id) 
  REFERENCES investigations(investigation_id) 
  ON DELETE CASCADE;

-- raw_messages → investigations
ALTER TABLE raw_messages
  ADD CONSTRAINT fk_raw_msg_investigation
  FOREIGN KEY (investigation_id) 
  REFERENCES investigations(investigation_id) 
  ON DELETE CASCADE;

DO $$ BEGIN RAISE NOTICE '✅ Foreign keys added to raw_* tables'; END $$;

-- ============================================================================
-- PART 5: Add Foreign Keys to canonical.* tables
-- ============================================================================

-- canonical_transaction → investigations
ALTER TABLE canonical.canonical_transaction
  ADD CONSTRAINT fk_canonical_tx_investigation
  FOREIGN KEY (investigation_id)
  REFERENCES investigations(investigation_id)
  ON DELETE CASCADE;

-- canonical_communication → investigations
ALTER TABLE canonical.canonical_communication
  ADD CONSTRAINT fk_canonical_comm_investigation
  FOREIGN KEY (investigation_id)
  REFERENCES investigations(investigation_id)
  ON DELETE CASCADE;

DO $$ BEGIN RAISE NOTICE '✅ Foreign keys added to canonical.* tables'; END $$;

-- ============================================================================
-- PART 6: Add Indexes on Foreign Keys (if not exist)
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '📊 Creating indexes on foreign keys...'; END $$;

-- Already exist from init scripts, but add IF NOT EXISTS for safety
CREATE INDEX IF NOT EXISTS idx_raw_tx_investigation_fk 
  ON raw_transactions(investigation_id);
  
CREATE INDEX IF NOT EXISTS idx_raw_calls_investigation_fk 
  ON raw_calls(investigation_id);
  
CREATE INDEX IF NOT EXISTS idx_raw_msg_investigation_fk 
  ON raw_messages(investigation_id);

CREATE INDEX IF NOT EXISTS idx_canonical_tx_investigation_fk
  ON canonical.canonical_transaction(investigation_id);

CREATE INDEX IF NOT EXISTS idx_canonical_comm_investigation_fk
  ON canonical.canonical_communication(investigation_id);

DO $$ BEGIN RAISE NOTICE '✅ Indexes created'; END $$;

-- ============================================================================
-- PART 7: Add Table Comments (Documentation)
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '📝 Adding table documentation...'; END $$;

-- Canonical integration tables
COMMENT ON TABLE canonical.canonical_transaction IS
  'Integration Layer: Normalized financial transactions.
   Mapped from raw_transactions with validation and standardization.
   Source system agnostic representation. Created by Dagster canonical_assets.';

COMMENT ON TABLE canonical.canonical_communication IS
  'Integration Layer: Normalized communications (calls + SMS).
   Mapped from raw_calls and raw_messages with validation.
   Source system agnostic representation. Created by Dagster canonical_assets.';

-- Mark unused tables
COMMENT ON TABLE canonical.canonical_person IS
  '⚠️  PLANNED FEATURE: Entity resolution layer.
   Status: Not implemented. Planned for Q2 2025.
   Purpose: Link persons across investigations and data sources.';

COMMENT ON TABLE canonical.canonical_mapping_log IS
  '⚠️  PLANNED FEATURE: Mapping audit trail.
   Status: Not implemented. Disabled in canonical_assets.py.
   Purpose: Track mapping decisions for data lineage.';

-- Analytical layer tables
COMMENT ON TABLE canonical.fact_transaction IS
  'Analytical Layer: Transaction facts in star schema.
   Built by dbt from canonical_transaction.
   Optimized for BI queries in Superset.';

COMMENT ON TABLE canonical.fact_call IS
  'Analytical Layer: Call facts in star schema.
   Built by dbt from canonical_communication (type=call).
   Optimized for BI queries in Superset.';

COMMENT ON TABLE canonical.fact_message IS
  'Analytical Layer: Message facts in star schema.
   Built by dbt from canonical_communication (type=sms).
   Optimized for BI queries in Superset.';

COMMENT ON TABLE canonical.dim_bank_account IS
  'Analytical Layer: Bank account dimension.
   Built by dbt from canonical_transaction.
   Slowly changing dimension for account attributes.';

COMMENT ON TABLE canonical.dim_phone_number IS
  'Analytical Layer: Phone number dimension.
   Built by dbt from canonical_communication.
   Slowly changing dimension for phone attributes.';

DO $$ BEGIN RAISE NOTICE '✅ Table comments added'; END $$;

-- ============================================================================
-- PART 8: Verify Migration
-- ============================================================================

DO $$ BEGIN RAISE NOTICE '🔍 Verifying migration...'; END $$;

-- Check foreign keys exist
DO $$
DECLARE
    fk_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO fk_count
    FROM information_schema.table_constraints
    WHERE constraint_type = 'FOREIGN KEY'
      AND table_name IN ('raw_transactions', 'raw_calls', 'raw_messages')
      AND constraint_name LIKE 'fk_%investigation';
    
    IF fk_count = 3 THEN
        RAISE NOTICE '✅ All raw_* foreign keys verified (% keys)', fk_count;
    ELSE
        RAISE EXCEPTION '❌ Expected 3 foreign keys, found %', fk_count;
    END IF;
END $$;

DO $$ BEGIN
    RAISE NOTICE '✅ Migration completed successfully!';
    RAISE NOTICE '';
    RAISE NOTICE '📊 Summary:';
    RAISE NOTICE '  - Dropped 3 unused schemas (weather, crypto, cell_towers)';
    RAISE NOTICE '  - Fixed 5 investigation_id type inconsistencies';
    RAISE NOTICE '  - Added 5 foreign key constraints';
    RAISE NOTICE '  - Added 5 indexes on foreign keys';
    RAISE NOTICE '  - Added table documentation comments';
    RAISE NOTICE '';
    RAISE NOTICE '⚠️  Next steps:';
    RAISE NOTICE '  1. Restart Dagster: docker restart dp_dagster';
    RAISE NOTICE '  2. Run cleanup script: ./cleanup_platform.sh';
    RAISE NOTICE '  3. Verify demo data: ./test-data/marvel-bandits/verify_marvel_case.sh';
END $$;

COMMIT;

-- ============================================================================
-- SUCCESS!
-- ============================================================================
