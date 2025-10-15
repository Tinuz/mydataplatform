{% macro validate_phone_number(column_name) %}
    CASE
        WHEN {{ column_name }} IS NULL THEN FALSE
        WHEN LENGTH({{ column_name }}) < 10 OR LENGTH({{ column_name }}) > 15 THEN FALSE
        -- Dutch mobile: 06xxxxxxxx or +316xxxxxxxx
        WHEN {{ column_name }} ~ '^(06|\\+316)[0-9]{8}$' THEN TRUE
        -- Dutch landline: 0[1-5,7-9]xxxxxxx or +31[1-5,7-9]xxxxxxx
        WHEN {{ column_name }} ~ '^(0[1-5,7-9]|\\+31[1-5,7-9])[0-9]{7,8}$' THEN TRUE
        -- International format: +[country][number]
        WHEN {{ column_name }} ~ '^\\+[0-9]{10,14}$' THEN TRUE
        ELSE FALSE
    END
{% endmacro %}

{% macro normalize_phone_number(column_name) %}
    CASE
        -- Dutch mobile starting with 06 -> +316
        WHEN {{ column_name }} ~ '^06[0-9]{8}$' 
            THEN '+31' || SUBSTRING({{ column_name }}, 2)
        
        -- Dutch landline starting with 0 -> +31
        WHEN {{ column_name }} ~ '^0[1-5,7-9][0-9]{7,8}$' 
            THEN '+31' || SUBSTRING({{ column_name }}, 2)
        
        -- Already in international format
        WHEN {{ column_name }} ~ '^\\+[0-9]+$' 
            THEN {{ column_name }}
        
        -- Default: prepend +31 (assume Dutch)
        ELSE '+31' || {{ column_name }}
    END
{% endmacro %}

{% macro extract_country_code_from_phone(column_name) %}
    CASE
        WHEN {{ column_name }} ~ '^\\+31' THEN '+31'
        WHEN {{ column_name }} ~ '^\\+32' THEN '+32'
        WHEN {{ column_name }} ~ '^\\+49' THEN '+49'
        WHEN {{ column_name }} ~ '^\\+33' THEN '+33'
        WHEN {{ column_name }} ~ '^\\+44' THEN '+44'
        WHEN {{ column_name }} ~ '^\\+' 
            THEN SUBSTRING({{ column_name }}, 1, 3)
        ELSE '+31' -- Default Dutch
    END
{% endmacro %}

{% macro get_phone_type(column_name) %}
    CASE
        -- Dutch mobile numbers
        WHEN {{ column_name }} ~ '^(\\+316|06)' THEN 'mobile'
        
        -- Dutch landlines
        WHEN {{ column_name }} ~ '^(\\+31[1-5,7-9]|0[1-5,7-9])' THEN 'landline'
        
        -- International mobile (heuristic)
        WHEN {{ column_name }} ~ '^\\+[0-9]{2}[6-9]' THEN 'mobile'
        
        -- Default
        ELSE 'unknown'
    END
{% endmacro %}

{% macro detect_phone_provider(column_name) %}
    -- This is a simplified heuristic. In production, use a lookup table.
    CASE
        WHEN {{ column_name }} ~ '^(\\+316[0-2]|06[0-2])' THEN 'KPN'
        WHEN {{ column_name }} ~ '^(\\+316[3-5]|06[3-5])' THEN 'Vodafone'
        WHEN {{ column_name }} ~ '^(\\+316[6-8]|06[6-8])' THEN 'T-Mobile'
        ELSE 'Unknown'
    END
{% endmacro %}
