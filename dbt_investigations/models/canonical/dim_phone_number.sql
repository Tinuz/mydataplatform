{{
    config(
        materialized='table',
        contract={
            'enforced': false
        },
        tags=['dimension', 'canonical', 'telecom']
    )
}}

WITH source_phones AS (
    -- Get unique phone numbers from staging calls
    SELECT DISTINCT
        caller_number AS phone_number,
        NULL AS provider  -- Will be detected by macro
    FROM {{ ref('stg_telecom_calls') }}
    WHERE caller_number IS NOT NULL
    
    UNION
    
    SELECT DISTINCT
        called_number AS phone_number,
        NULL AS provider
    FROM {{ ref('stg_telecom_calls') }}
    WHERE called_number IS NOT NULL
    
    UNION
    
    -- Also get from messages
    SELECT DISTINCT
        sender_number AS phone_number,
        NULL AS provider
    FROM {{ ref('stg_telecom_messages') }}
    WHERE sender_number IS NOT NULL
    
    UNION
    
    SELECT DISTINCT
        recipient_number AS phone_number,
        NULL AS provider
    FROM {{ ref('stg_telecom_messages') }}
    WHERE recipient_number IS NOT NULL
),

normalized_phones AS (
    SELECT
        {{ generate_uuid() }} AS phone_key,
        {{ normalize_phone_number('phone_number') }} AS phone_number,
        {{ extract_country_code_from_phone(normalize_phone_number('phone_number')) }} AS country_code,
        -- Extract area code (simplified)
        CASE
            WHEN phone_number ~ '^\\+31' 
                THEN SUBSTRING(phone_number, 4, 2)
            ELSE NULL
        END AS area_code,
        -- Extract local number
        CASE
            WHEN phone_number ~ '^\\+31' 
                THEN SUBSTRING(phone_number, 6)
            ELSE phone_number
        END AS local_number,
        {{ get_phone_type('phone_number') }} AS phone_type,
        COALESCE(
            provider,
            {{ detect_phone_provider(normalize_phone_number('phone_number')) }}
        ) AS provider,
        {{ validate_phone_number(normalize_phone_number('phone_number')) }} AS is_valid,
        {{ current_timestamp() }} AS valid_from,
        CAST(NULL AS TIMESTAMP) AS valid_to,
        TRUE AS is_current,
        'demo_system' AS source_system,
        {{ current_timestamp() }} AS created_at,
        {{ current_timestamp() }} AS updated_at
    FROM source_phones
)

SELECT
    phone_key,
    phone_number,
    country_code,
    area_code,
    local_number,
    phone_type,
    provider,
    is_valid,
    valid_from,
    valid_to,
    is_current,
    source_system,
    created_at,
    updated_at
FROM normalized_phones
WHERE is_valid = TRUE  -- Only valid phone numbers
