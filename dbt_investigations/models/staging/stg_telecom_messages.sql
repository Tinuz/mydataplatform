{{
    config(
        materialized='view',
        tags=['staging', 'telecom']
    )
}}

-- Source: canonical.canonical_communication (validated and standardized)
-- Only includes records with communication_type = 'sms' and validation_status IN ('valid', 'warning')
WITH canonical_messages AS (
    SELECT
        canonical_communication_id,
        source_system_id,
        source_record_id,
        investigation_id,
        communication_datetime,
        originator_id,
        originator_name,
        recipient_id,
        recipient_name,
        direction,
        message_content,
        content_hash,
        network_operator,
        validation_status,
        created_at
    FROM {{ source('canonical', 'canonical_communication') }}
    WHERE communication_type = 'sms'
      AND validation_status IN ('valid', 'warning')  -- Only validated data
),

cleaned AS (
    SELECT
        canonical_communication_id AS message_id,
        investigation_id,
        source_system_id AS source_id,
        
        -- Phone numbers (already cleaned and E.164 formatted in canonical layer)
        originator_id AS sender_number,
        recipient_id AS recipient_number,
        originator_name AS sender_name,
        recipient_name AS recipient_name,
        
        -- Timestamp (already parsed)
        communication_datetime AS message_timestamp,
        communication_datetime::DATE AS message_date,
        communication_datetime::TIME AS message_time,
        
        -- Message content (already validated)
        message_content AS message_text,
        content_hash AS message_hash,
        
        -- Message details (already standardized)
        direction AS message_direction,
        network_operator,
        validation_status,
        
        created_at AS loaded_at
    FROM canonical_messages
    WHERE originator_id IS NOT NULL
       OR recipient_id IS NOT NULL  -- At least one number should exist
)

SELECT
    message_id,
    investigation_id,
    source_id,
    sender_number,
    recipient_number,
    sender_name,
    recipient_name,
    message_timestamp,
    message_date,
    message_time,
    message_text,
    message_hash,
    message_direction,
    network_operator,
    validation_status,
    loaded_at
FROM cleaned
