{% macro generate_uuid() %}
    -- DuckDB: uuid()
    -- PostgreSQL: gen_random_uuid()
    {% if target.type == 'duckdb' %}
        uuid()
    {% elif target.type == 'postgres' %}
        gen_random_uuid()
    {% else %}
        md5(random()::text || clock_timestamp()::text)::uuid
    {% endif %}
{% endmacro %}

{% macro current_timestamp() %}
    CURRENT_TIMESTAMP
{% endmacro %}

{% macro extract_date(timestamp_column) %}
    CAST({{ timestamp_column }} AS DATE)
{% endmacro %}

{% macro calculate_age(birth_date_column) %}
    DATE_PART('year', AGE(CURRENT_DATE, {{ birth_date_column }}))
{% endmacro %}

{% macro hash_sensitive_data(column_name) %}
    MD5({{ column_name }})
{% endmacro %}

{% macro mask_iban(column_name) %}
    SUBSTRING({{ column_name }}, 1, 8) || '****' || RIGHT({{ column_name }}, 4)
{% endmacro %}

{% macro mask_phone(column_name) %}
    LEFT({{ column_name }}, 4) || '****' || RIGHT({{ column_name }}, 3)
{% endmacro %}
