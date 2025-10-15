{{
    config(
        materialized='view',
        tags=['staging', 'financial']
    )
}}

-- Source: canonical.canonical_transaction (validated and standardized)
-- Only includes records with validation_status = 'valid' or 'warning'
WITH canonical_transactions AS (
    SELECT
        canonical_transaction_id,
        source_system_id,
        source_record_id,
        investigation_id,
        transaction_datetime,
        posting_date,
        value_date,
        amount,
        currency_code,
        debtor_account_id,
        debtor_name,
        creditor_account_id,
        creditor_name,
        transaction_type,
        payment_method,
        description,
        reference_number,
        validation_status,
        data_completeness_score,
        created_at
    FROM {{ source('canonical', 'canonical_transaction') }}
    WHERE validation_status IN ('valid', 'warning')  -- Only validated data
),

cleaned AS (
    SELECT
        -- Keys
        canonical_transaction_id AS transaction_id,
        investigation_id,
        source_system_id AS source_id,
        
        -- Standardized IBAN fields (already cleaned in canonical layer)
        debtor_account_id AS iban_from,
        creditor_account_id AS iban_to,
        
        -- Amount (already standardized)
        amount AS bedrag,
        
        -- Date fields (already parsed)
        transaction_datetime::DATE AS datum,
        posting_date,
        value_date,
        
        -- Description (already standardized)
        description AS omschrijving,
        
        -- Additional canonical fields
        debtor_name,
        creditor_name,
        transaction_type,
        payment_method,
        currency_code,
        validation_status,
        data_completeness_score,
        
        -- Metadata
        created_at AS loaded_at
    FROM canonical_transactions
    WHERE debtor_account_id IS NOT NULL
       OR creditor_account_id IS NOT NULL  -- At least one account should exist
)

SELECT
    transaction_id,
    investigation_id,
    source_id,
    iban_from,
    iban_to,
    bedrag,
    datum,
    posting_date,
    value_date,
    omschrijving,
    debtor_name,
    creditor_name,
    transaction_type,
    payment_method,
    currency_code,
    validation_status,
    data_completeness_score,
    loaded_at
FROM cleaned
