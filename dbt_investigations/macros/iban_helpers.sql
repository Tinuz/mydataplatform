{% macro validate_iban(column_name) %}
    CASE
        WHEN {{ column_name }} IS NULL THEN FALSE
        WHEN LENGTH({{ column_name }}) < 15 OR LENGTH({{ column_name }}) > 34 THEN FALSE
        WHEN SUBSTRING({{ column_name }}, 1, 2) !~ '^[A-Z]{2}$' THEN FALSE
        WHEN SUBSTRING({{ column_name }}, 3, 2) !~ '^[0-9]{2}$' THEN FALSE
        WHEN {{ column_name }} !~ '^[A-Z]{2}[0-9]{2}[A-Z0-9]+$' THEN FALSE
        ELSE TRUE
    END
{% endmacro %}

{% macro extract_country_from_iban(column_name) %}
    SUBSTRING({{ column_name }}, 1, 2)
{% endmacro %}

{% macro extract_bank_code_from_iban(column_name) %}
    CASE 
        -- NL: positions 5-8 are bank code
        WHEN SUBSTRING({{ column_name }}, 1, 2) = 'NL' 
            THEN SUBSTRING({{ column_name }}, 5, 4)
        -- BE: positions 5-7 are bank code
        WHEN SUBSTRING({{ column_name }}, 1, 2) = 'BE' 
            THEN SUBSTRING({{ column_name }}, 5, 3)
        -- DE: positions 5-12 are bank code
        WHEN SUBSTRING({{ column_name }}, 1, 2) = 'DE' 
            THEN SUBSTRING({{ column_name }}, 5, 8)
        -- Default: extract 4 characters after check digits
        ELSE SUBSTRING({{ column_name }}, 5, 4)
    END
{% endmacro %}

{% macro get_bank_name_from_code(bank_code) %}
    CASE {{ bank_code }}
        WHEN 'ABNA' THEN 'ABN AMRO'
        WHEN 'INGB' THEN 'ING Bank'
        WHEN 'RABO' THEN 'Rabobank'
        WHEN 'TRIO' THEN 'Triodos Bank'
        WHEN 'SNSB' THEN 'SNS Bank'
        WHEN 'ASNB' THEN 'ASN Bank'
        WHEN 'RBRB' THEN 'RegioBank'
        WHEN 'BUNQ' THEN 'bunq'
        WHEN 'KNAB' THEN 'Knab'
        WHEN 'REVOLT' THEN 'Revolut'
        ELSE 'Unknown Bank'
    END
{% endmacro %}
