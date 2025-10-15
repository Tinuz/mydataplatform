{{
    config(
        materialized='table',
        contract={
            'enforced': false
        },
        tags=['fact', 'canonical', 'telecom']
    )
}}

WITH source_calls AS (
    -- Get calls from staging
    SELECT
        call_id,
        investigation_id,
        source_id,
        caller_number,
        called_number,
        call_timestamp,
        duration_seconds,
        call_type,
        loaded_at
    FROM {{ ref('stg_telecom_calls') }}
),

enriched_calls AS (
    SELECT
        call_id,
        investigation_id,
        source_id,
        call_timestamp AS call_date,
        CAST(call_timestamp AS DATE) AS call_date_only,
        CAST(call_timestamp AS TIME) AS call_time,
        caller_number,
        called_number,
        -- Join to dim_phone_number to get phone_key
        dim_caller.phone_key AS caller_phone_key,
        dim_called.phone_key AS called_phone_key,
        duration_seconds,
        -- Convert duration to minutes for easier analysis
        ROUND(duration_seconds / 60.0, 2) AS duration_minutes,
        COALESCE(call_type, 'unknown') AS call_type,
        -- Categorize call direction
        CASE
            WHEN call_type IN ('incoming', 'inbound') THEN 'inbound'
            WHEN call_type IN ('outgoing', 'outbound') THEN 'outbound'
            WHEN call_type IN ('missed', 'unanswered') THEN 'missed'
            ELSE 'unknown'
        END AS call_direction,
        -- Flag suspicious calls (long duration or unusual patterns)
        CASE
            WHEN duration_seconds > 3600 THEN TRUE  -- > 1 hour
            WHEN duration_seconds < 1 THEN TRUE  -- Very short
            ELSE FALSE
        END AS is_suspicious,
        -- Calculate risk score based on duration and time
        CASE
            WHEN duration_seconds > 7200 THEN 1.00  -- > 2 hours
            WHEN duration_seconds > 3600 THEN 0.75  -- > 1 hour
            WHEN duration_seconds > 1800 THEN 0.50  -- > 30 min
            WHEN EXTRACT(HOUR FROM call_timestamp) BETWEEN 0 AND 5 THEN 0.60  -- Late night
            WHEN EXTRACT(HOUR FROM call_timestamp) BETWEEN 22 AND 23 THEN 0.40  -- Night
            ELSE 0.10
        END AS risk_score,
        ARRAY[]::VARCHAR[] AS tags,
        {{ current_timestamp() }} AS created_at,
        {{ current_timestamp() }} AS updated_at
    FROM source_calls
    LEFT JOIN {{ ref('dim_phone_number') }} AS dim_caller
        ON source_calls.caller_number = dim_caller.phone_number
        AND dim_caller.is_current = TRUE
    LEFT JOIN {{ ref('dim_phone_number') }} AS dim_called
        ON source_calls.called_number = dim_called.phone_number
        AND dim_called.is_current = TRUE
)

SELECT
    call_id,
    investigation_id,
    source_id,
    call_date,
    call_date_only,
    call_time,
    caller_number,
    called_number,
    caller_phone_key,
    called_phone_key,
    duration_seconds,
    duration_minutes,
    call_type,
    call_direction,
    is_suspicious,
    risk_score,
    tags,
    created_at,
    updated_at
FROM enriched_calls
