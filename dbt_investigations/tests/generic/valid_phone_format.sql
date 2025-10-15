{% test valid_phone_format(model, column_name) %}

WITH validation AS (
    SELECT
        {{ column_name }} AS phone_value,
        {{ validate_phone_number(column_name) }} AS is_valid
    FROM {{ model }}
    WHERE {{ column_name }} IS NOT NULL
)

SELECT
    phone_value,
    is_valid
FROM validation
WHERE is_valid = FALSE

{% endtest %}
