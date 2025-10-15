{{
    config(
        materialized='table',
        contract={
            'enforced': false
        },
        tags=['fact', 'canonical', 'telecom']
    )
}}

WITH source_messages AS (
    -- Get messages from staging
    SELECT
        message_id,
        investigation_id,
        source_id,
        sender_number,
        recipient_number,
        message_timestamp,
        message_text,
        message_direction,  -- Use message_direction instead of message_type
        loaded_at
    FROM {{ ref('stg_telecom_messages') }}
),

enriched_messages AS (
    SELECT
        message_id,
        investigation_id,
        source_id,
        message_timestamp AS message_date,
        CAST(message_timestamp AS DATE) AS message_date_only,
        CAST(message_timestamp AS TIME) AS message_time,
        sender_number,
        recipient_number,
        -- Join to dim_phone_number to get phone_key
        dim_sender.phone_key AS sender_phone_key,
        dim_recipient.phone_key AS recipient_phone_key,
        message_text,
        -- Calculate message length
        LENGTH(COALESCE(message_text, '')) AS message_length,
        -- Count words in message
        ARRAY_LENGTH(
            STRING_TO_ARRAY(TRIM(COALESCE(message_text, '')), ' '), 
            1
        ) AS word_count,
        'sms' AS message_type,  -- Default to SMS
        -- Categorize message direction
        CASE
            WHEN message_direction IN ('sent', 'outgoing', 'outbound') THEN 'outbound'
            WHEN message_direction IN ('received', 'incoming', 'inbound') THEN 'inbound'
            ELSE 'unknown'
        END AS final_message_direction,
        -- Flag suspicious messages (contains keywords or unusual patterns)
        CASE
            WHEN LOWER(message_text) LIKE '%urgent%' THEN TRUE
            WHEN LOWER(message_text) LIKE '%password%' THEN TRUE
            WHEN LOWER(message_text) LIKE '%bank%' THEN TRUE
            WHEN LOWER(message_text) LIKE '%account%' THEN TRUE
            WHEN LOWER(message_text) LIKE '%transfer%' THEN TRUE
            WHEN LENGTH(message_text) > 500 THEN TRUE  -- Very long message
            ELSE FALSE
        END AS is_suspicious,
        -- Calculate risk score based on content and patterns
        CASE
            WHEN LOWER(message_text) LIKE '%password%' OR LOWER(message_text) LIKE '%pin%' THEN 1.00
            WHEN LOWER(message_text) LIKE '%bank%' OR LOWER(message_text) LIKE '%account%' THEN 0.75
            WHEN LOWER(message_text) LIKE '%urgent%' OR LOWER(message_text) LIKE '%transfer%' THEN 0.60
            WHEN LENGTH(message_text) > 500 THEN 0.50
            WHEN EXTRACT(HOUR FROM message_timestamp) BETWEEN 0 AND 5 THEN 0.40  -- Late night
            ELSE 0.10
        END AS risk_score,
        -- Extract potential keywords as tags
        CASE
            WHEN LOWER(message_text) LIKE '%bank%' THEN ARRAY['banking']
            WHEN LOWER(message_text) LIKE '%meet%' OR LOWER(message_text) LIKE '%appointment%' THEN ARRAY['meeting']
            WHEN LOWER(message_text) LIKE '%urgent%' THEN ARRAY['urgent']
            ELSE ARRAY[]::VARCHAR[]
        END AS tags,
        {{ current_timestamp() }} AS created_at,
        {{ current_timestamp() }} AS updated_at
    FROM source_messages
    LEFT JOIN {{ ref('dim_phone_number') }} AS dim_sender
        ON source_messages.sender_number = dim_sender.phone_number
        AND dim_sender.is_current = TRUE
    LEFT JOIN {{ ref('dim_phone_number') }} AS dim_recipient
        ON source_messages.recipient_number = dim_recipient.phone_number
        AND dim_recipient.is_current = TRUE
)

SELECT
    message_id,
    investigation_id,
    source_id,
    message_date,
    message_date_only,
    message_time,
    sender_number,
    recipient_number,
    sender_phone_key,
    recipient_phone_key,
    message_text,
    message_length,
    word_count,
    message_type,
    final_message_direction AS message_direction,
    is_suspicious,
    risk_score,
    tags,
    created_at,
    updated_at
FROM enriched_messages
