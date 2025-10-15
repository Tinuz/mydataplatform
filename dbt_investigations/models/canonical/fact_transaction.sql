{{
    config(
        materialized='table',
        contract={
            'enforced': false
        },
        tags=['fact', 'canonical', 'financial']
    )
}}

WITH source_transactions AS (
    -- Get transactions from staging
    SELECT
        transaction_id,
        investigation_id,
        source_id,
        datum AS transaction_date,
        -- Create timestamp from date (assume noon)
        datum + INTERVAL '12 hours' AS transaction_timestamp,
        iban_from,
        iban_to,
        bedrag AS amount,
        'EUR' AS currency,
        omschrijving AS description
    FROM {{ ref('stg_bank_transactions') }}
),

enriched_transactions AS (
    SELECT
        COALESCE(source_transactions.transaction_id, {{ generate_uuid() }}) AS transaction_id,
        source_transactions.investigation_id,
        source_transactions.source_id,
        source_transactions.transaction_date,
        source_transactions.transaction_timestamp,
        source_transactions.transaction_date AS posted_date,  -- Assume same for now
        source_transactions.iban_from,
        source_transactions.iban_to,
        -- Join to dim_bank_account to get account_key
        -- LEFT JOIN to handle cases where dimension not yet populated
        dim_from.account_key AS account_key_from,
        dim_to.account_key AS account_key_to,
        source_transactions.amount,
        COALESCE(source_transactions.currency, 'EUR') AS currency,
        -- Classify transaction type
        CASE
            WHEN source_transactions.amount > 0 THEN 'credit'
            WHEN source_transactions.amount < 0 THEN 'debit'
            ELSE 'neutral'
        END AS transaction_type,
        -- Categorize based on description (simplified)
        CASE
            WHEN LOWER(source_transactions.description) LIKE '%salary%' OR LOWER(source_transactions.description) LIKE '%salaris%' THEN 'income'
            WHEN LOWER(source_transactions.description) LIKE '%rent%' OR LOWER(source_transactions.description) LIKE '%huur%' THEN 'housing'
            WHEN LOWER(source_transactions.description) LIKE '%groceries%' OR LOWER(source_transactions.description) LIKE '%albert heijn%' OR LOWER(source_transactions.description) LIKE '%jumbo%' OR LOWER(source_transactions.description) LIKE '%boodschappen%' THEN 'groceries'
            WHEN LOWER(source_transactions.description) LIKE '%transfer%' OR LOWER(source_transactions.description) LIKE '%overschrijving%' THEN 'transfer'
            WHEN LOWER(source_transactions.description) LIKE '%netflix%' OR LOWER(source_transactions.description) LIKE '%spotify%' OR LOWER(source_transactions.description) LIKE '%subscription%' THEN 'subscription'
            WHEN LOWER(source_transactions.description) LIKE '%gas%' OR LOWER(source_transactions.description) LIKE '%water%' OR LOWER(source_transactions.description) LIKE '%electric%' OR LOWER(source_transactions.description) LIKE '%energie%' THEN 'utilities'
            ELSE 'other'
        END AS category,
        source_transactions.description,
        -- Extract counter party name from description (simplified)
        SPLIT_PART(source_transactions.description, ' ', -1) AS counter_party_name,
        CAST(NULL AS VARCHAR) AS reference,
        -- Flag suspicious transactions (simplified rules)
        CASE
            WHEN ABS(source_transactions.amount) > 10000 THEN TRUE
            WHEN LOWER(source_transactions.description) LIKE '%suspicious%' THEN TRUE
            ELSE FALSE
        END AS is_suspicious,
        -- Calculate risk score (simplified)
        CASE
            WHEN ABS(source_transactions.amount) > 50000 THEN 1.00
            WHEN ABS(source_transactions.amount) > 10000 THEN 0.75
            WHEN ABS(source_transactions.amount) > 5000 THEN 0.50
            WHEN ABS(source_transactions.amount) > 1000 THEN 0.25
            ELSE 0.10
        END AS risk_score,
        ARRAY[]::VARCHAR[] AS tags,
        {{ current_timestamp() }} AS created_at,
        {{ current_timestamp() }} AS updated_at
    FROM source_transactions
    LEFT JOIN {{ ref('dim_bank_account') }} AS dim_from
        ON source_transactions.iban_from = dim_from.iban
        AND dim_from.is_current = TRUE
    LEFT JOIN {{ ref('dim_bank_account') }} AS dim_to
        ON source_transactions.iban_to = dim_to.iban
        AND dim_to.is_current = TRUE
    -- Removed validate_iban check to allow all transactions
)

SELECT
    transaction_id,
    investigation_id,
    source_id,
    transaction_date,
    transaction_timestamp,
    posted_date,
    iban_from,
    iban_to,
    account_key_from,
    account_key_to,
    amount,
    currency,
    transaction_type,
    category,
    description,
    counter_party_name,
    reference,
    is_suspicious,
    risk_score,
    tags,
    created_at,
    updated_at
FROM enriched_transactions
