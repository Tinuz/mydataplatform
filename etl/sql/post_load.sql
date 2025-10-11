-- Handige indexen + analyze
CREATE INDEX IF NOT EXISTS idx_clean_cell ON {schema}.{cleaned}(mcc, net, area, cell, unit);
CREATE INDEX IF NOT EXISTS idx_clean_geo  ON {schema}.{cleaned}(lat, lon);

ANALYZE {schema}.{cleaned};