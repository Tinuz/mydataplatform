{% test valid_iban_format(model, column_name) %}

WITH validation AS (
    SELECT
        {{ column_name }} AS iban_value,
        {{ validate_iban(column_name) }} AS is_valid
    FROM {{ model }}
    WHERE {{ column_name }} IS NOT NULL
)

SELECT
    iban_value,
    is_valid
FROM validation
WHERE is_valid = FALSE

{% endtest %}
