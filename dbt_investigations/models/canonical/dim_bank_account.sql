{{
    config(
        materialized='table',
        contract={
            'enforced': false
        },
        tags=['dimension', 'canonical', 'financial']
    )
}}

WITH source_accounts AS (
    -- Get unique IBANs from staging transactions
    -- Deduplicate by IBAN first to avoid duplicate dimension records
    SELECT DISTINCT
        iban,
        'checking' AS account_type,
        'EUR' AS currency
    FROM (
        SELECT DISTINCT iban_from AS iban
        FROM {{ ref('stg_bank_transactions') }}
        WHERE iban_from IS NOT NULL
        
        UNION
        
        SELECT DISTINCT iban_to AS iban
        FROM {{ ref('stg_bank_transactions') }}
        WHERE iban_to IS NOT NULL
    ) all_ibans
),

intermediate AS (
    SELECT
        iban,
        account_type,
        currency,
        {{ extract_country_from_iban('iban') }} AS country_code,
        {{ extract_bank_code_from_iban('iban') }} AS bank_code
    FROM source_accounts
    WHERE {{ validate_iban('iban') }} = TRUE  -- Only valid IBANs
),

enriched_accounts AS (
    SELECT
        {{ generate_uuid() }} AS account_key,
        iban,
        country_code,
        bank_code,
        -- Extract account number (everything after country + check + bank code)
        CASE 
            WHEN country_code = 'NL' 
                THEN SUBSTRING(iban, 9)
            ELSE SUBSTRING(iban, 13)
        END AS account_number,
        {{ get_bank_name_from_code('bank_code') }} AS bank_name,
        COALESCE(account_type, 'unknown') AS account_type,
        COALESCE(currency, 'EUR') AS currency,
        {{ current_timestamp() }} AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,
        'consolidated' AS source_system,  -- Single source system for deduplicated records
        {{ current_timestamp() }} AS created_at,
        {{ current_timestamp() }} AS updated_at
    FROM intermediate
)

SELECT
    account_key,
    iban,
    country_code,
    bank_code,
    account_number,
    bank_name,
    account_type,
    currency,
    valid_from,
    valid_to,
    is_current,
    source_system,
    created_at,
    updated_at
FROM enriched_accounts
