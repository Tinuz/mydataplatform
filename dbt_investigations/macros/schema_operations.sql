-- Schema management operations for canonical data models

{% macro create_canonical_schema() %}
    {% set sql %}
        CREATE SCHEMA IF NOT EXISTS canonical;
        COMMENT ON SCHEMA canonical IS 'Canonical data models - governed by data contracts';
    {% endset %}
    {% do run_query(sql) %}
    {{ log("✓ Schema 'canonical' created or already exists", info=True) }}
{% endmacro %}

{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- if custom_schema_name is none -%}
        {{ target.schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}

{% macro get_schema_comment(schema_name) %}
    {% set query %}
        SELECT obj_description(
            (SELECT oid FROM pg_namespace WHERE nspname = '{{ schema_name }}')
        ) AS comment
    {% endset %}
    {% set results = run_query(query) %}
    {% if execute and results %}
        {{ return(results.columns[0].values()[0]) }}
    {% endif %}
{% endmacro %}
