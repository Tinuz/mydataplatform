-- Maak/verwarm clean-tabel met validatie + normalisatie
CREATE SCHEMA IF NOT EXISTS {schema};

DROP TABLE IF EXISTS {schema}.{cleaned};

CREATE TABLE {schema}.{cleaned} AS
WITH base AS (
  SELECT
    TRIM(LOWER(radio))              AS radio,
    NULLIF(mcc, 0)::INT             AS mcc,
    NULLIF(net, 0)::INT             AS net,
    NULLIF(area, 0)::INT            AS area,
    NULLIF(cell, 0)::INT            AS cell,
    NULLIF(unit, 0)::INT            AS unit,
    NULLIF(lon, 0)::DOUBLE PRECISION  AS lon,
    NULLIF(lat, 0)::DOUBLE PRECISION  AS lat,
    NULLIF(range, 0)::BIGINT           AS range_m,
    NULLIF(samples, 0)::INT         AS samples,
    COALESCE(changeable, 0)::INT    AS changeable,
    to_timestamp(NULLIF(created, 0)) AS created_ts,
    to_timestamp(NULLIF(updated, 0)) AS updated_ts,
    averageSignal::INT              AS average_signal
  FROM {schema}.{staging}
  -- filter ruwe onmogelijkheden
  WHERE lat BETWEEN -90 AND 90
    AND lon BETWEEN -180 AND 180
)
, dedup AS (
  SELECT *,
         ROW_NUMBER() OVER (
           PARTITION BY mcc, net, area, cell, unit
           ORDER BY updated_ts DESC NULLS LAST, samples DESC NULLS LAST
         ) AS rn
  FROM base
)
SELECT
  radio, mcc, net, area, cell, unit,
  lon, lat, range_m, samples, changeable,
  created_ts, updated_ts, average_signal
FROM dedup
WHERE rn = 1;
