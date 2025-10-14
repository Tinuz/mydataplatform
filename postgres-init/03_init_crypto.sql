-- Initialize crypto schema and tables
-- This runs automatically on first PostgreSQL startup

-- Create crypto schema
CREATE SCHEMA IF NOT EXISTS crypto;

-- Grant permissions
GRANT ALL PRIVILEGES ON SCHEMA crypto TO superset;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA crypto TO superset;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA crypto TO superset;

-- Create tables (structure only, data synced by bootstrap script)
CREATE TABLE IF NOT EXISTS crypto.trades_bronze (
    symbol VARCHAR(20),
    price DOUBLE PRECISION,
    quantity DOUBLE PRECISION,
    trade_id BIGINT,
    event_time TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crypto.trades_1min (
    symbol VARCHAR(20),
    minute TIMESTAMP,
    open_price DOUBLE PRECISION,
    high_price DOUBLE PRECISION,
    low_price DOUBLE PRECISION,
    close_price DOUBLE PRECISION,
    volume DOUBLE PRECISION,
    trade_count INTEGER
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_trades_bronze_symbol ON crypto.trades_bronze(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_bronze_event_time ON crypto.trades_bronze(event_time);
CREATE INDEX IF NOT EXISTS idx_trades_1min_symbol ON crypto.trades_1min(symbol);
CREATE INDEX IF NOT EXISTS idx_trades_1min_minute ON crypto.trades_1min(minute);

-- Create view for latest prices
CREATE OR REPLACE VIEW crypto.latest_prices AS
SELECT DISTINCT ON (symbol)
    symbol,
    price as latest_price,
    quantity,
    event_time
FROM crypto.trades_bronze
ORDER BY symbol, event_time DESC;

-- Log completion
DO $$ 
BEGIN 
    RAISE NOTICE 'Crypto schema initialized successfully';
END $$;
