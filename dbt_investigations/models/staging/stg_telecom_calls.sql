{{
    config(
        materialized='view',
        tags=['staging', 'telecom']
    )
}}

-- Source: canonical.canonical_communication (validated and standardized)
-- Only includes records with communication_type = 'call' and validation_status IN ('valid', 'warning')
WITH canonical_calls AS (
    SELECT
        canonical_communication_id,
        source_system_id,
        source_record_id,
        investigation_id,
        communication_datetime,
        duration_seconds,
        originator_id,
        originator_name,
        recipient_id,
        recipient_name,
        direction,
        call_status,
        network_operator,
        connection_type,
        validation_status,
        created_at
    FROM {{ source('canonical', 'canonical_communication') }}
    WHERE communication_type = 'call'
      AND validation_status IN ('valid', 'warning')  -- Only validated data
),

cleaned AS (
    SELECT
        canonical_communication_id AS call_id,
        investigation_id,
        source_system_id AS source_id,
        
        -- Phone numbers (already cleaned and E.164 formatted in canonical layer)
        originator_id AS caller_number,
        recipient_id AS called_number,
        originator_name AS caller_name,
        recipient_name AS called_name,
        
        -- Timestamp (already parsed)
        communication_datetime AS call_timestamp,
        communication_datetime::DATE AS call_date,
        communication_datetime::TIME AS call_time,
        
        -- Duration (already validated)
        COALESCE(duration_seconds, 0) AS duration_seconds,
        
        -- Call details (already standardized)
        direction AS call_direction,
        call_status AS call_type,
        network_operator,
        connection_type,
        validation_status,
        
        created_at AS loaded_at
    FROM canonical_calls
    WHERE originator_id IS NOT NULL
       OR recipient_id IS NOT NULL  -- At least one number should exist
)

SELECT
    call_id,
    investigation_id,
    source_id,
    caller_number,
    called_number,
    caller_name,
    called_name,
    call_timestamp,
    call_date,
    call_time,
    duration_seconds,
    call_direction,
    call_type,
    network_operator,
    connection_type,
    validation_status,
    loaded_at
FROM cleaned
