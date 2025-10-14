# 🪙 Crypto Stream Analytics

**Real-time cryptocurrency trading data pipeline met Kafka + Apache Iceberg**

## 📊 Overzicht

Dit project demonstreert een moderne streaming data architectuur:

```
Binance WebSocket → Kafka → Iceberg (MinIO) → DuckDB/PostgreSQL → Superset
```

### Data Flow

1. **Ingestion**: WebSocket consumer luistert naar Binance trade streams
2. **Streaming**: Events worden naar Kafka topic `crypto_trades` geschreven
3. **Storage**: Kafka consumer schrijft batches naar Iceberg tables (Parquet files in MinIO)
4. **Query**: DuckDB (backend) en PostgreSQL (Superset) voor analytics
5. **Visualization**: Superset dashboards tonen real-time metrics

## 🏗️ Architectuur

### Bronze Layer (Raw Events)
- **Table**: `iceberg.crypto.trades_bronze`
- **Partitioning**: By `hour(event_time)` voor efficiënte queries
- **Schema**:
  ```sql
  symbol          VARCHAR   -- BTCUSDT, ETHUSDT
  price           DECIMAL   -- Trade price
  quantity        DECIMAL   -- Trade quantity
  event_time      TIMESTAMP -- Trade timestamp
  trade_id        BIGINT    -- Unique trade ID
  is_buyer_maker  BOOLEAN   -- Buy or sell
  ingested_at     TIMESTAMP -- Pipeline ingestion time
  ```

### Silver Layer (Aggregated)
- **Table**: `iceberg.crypto.trades_1min`
- **Partitioning**: By `hour(minute)`
- **Schema**:
  ```sql
  symbol       VARCHAR
  minute       TIMESTAMP
  open_price   DECIMAL
  high_price   DECIMAL
  low_price    DECIMAL
  close_price  DECIMAL
  volume       DECIMAL
  trade_count  BIGINT
  ```

### Gold Layer (Analytics)
- **Table**: `iceberg.crypto.daily_stats`
- **Partitioning**: By `day(date)`
- Daily aggregations, volatility metrics, etc.

## 🚀 Gebruik

### Start de Streaming Stack

```bash
# Start Kafka + Iceberg + bestaande services
docker-compose --profile streaming up -d

# Check of alles draait
docker-compose ps
```

### Run de WebSocket Producer

```bash
# Start de Binance → Kafka producer (in Dagster container)
docker-compose exec dagster python -m crypto_stream.producers.binance_producer

# Of draai als background process
docker-compose exec -d dagster python -m crypto_stream.producers.binance_producer
```

### Materialize Assets in Dagster

```bash
# Open Dagster UI: http://localhost:3000
# Navigate to: crypto_stream_location
# Assets:
#   - crypto_trades_bronze (Kafka → Iceberg)
#   - crypto_trades_1min (Bronze → Silver aggregation)
#   - crypto_daily_stats (Silver → Gold)
```

### Query Data with DuckDB

```python
# Query Iceberg tables using DuckDB
from crypto_stream.duckdb_helper import quick_query

# Recent trades
df = quick_query("""
    SELECT * FROM trades_bronze
    ORDER BY event_time DESC
    LIMIT 10
""")

# 1-minute candles
```

```

### Query Data in Trino

```sql
-- Connect to Trino: http://localhost:8080

-- Recent trades
SELECT * FROM iceberg.crypto.trades_bronze
ORDER BY event_time DESC
LIMIT 10;

-- 1-minute candles
SELECT 
  symbol,
  minute,
  open_price,
  close_price,
  high_price - low_price AS spread,
  volume
FROM iceberg.crypto.trades_1min
WHERE symbol = 'BTCUSDT'
  AND minute >= current_timestamp - INTERVAL '1' hour
ORDER BY minute DESC;

-- Daily volatility
SELECT 
  symbol,
  date,
  (high_price - low_price) / open_price * 100 AS volatility_pct,
  volume
FROM iceberg.crypto.daily_stats
WHERE date >= current_date - INTERVAL '7' day
ORDER BY date DESC, symbol;
```

### Time-Travel Queries

```sql
-- View table history
SELECT * FROM iceberg.crypto."trades_bronze$history"
ORDER BY made_current_at DESC;

-- Query data as it was 1 hour ago
SELECT COUNT(*) 
FROM iceberg.crypto.trades_bronze FOR VERSION AS OF <snapshot_id>
WHERE symbol = 'BTCUSDT';
```

## 📈 Superset Dashboards

Create dashboards in Superset:
1. **Live Price Ticker** - Real-time prices from silver layer
2. **Volume Heatmap** - Trading volume by symbol
3. **24h Volatility** - Price movements
4. **Trade Count** - Transactions per minute

## 🔧 Development

### Add New Cryptocurrency

Edit `producers/binance_producer.py`:
```python
SYMBOLS = [
    'btcusdt',  # Bitcoin
    'ethusdt',  # Ethereum
    'bnbusdt',  # Binance Coin
    'adausdt',  # Cardano (NEW!)
]
```

### Adjust Batch Size

Edit `assets/kafka_to_iceberg.py`:
```python
BATCH_SIZE = 1000  # Number of events per Iceberg write
BATCH_TIMEOUT = 30  # Seconds before flushing partial batch
```

## 📊 Monitoring

### Kafka Lag

```bash
# Check consumer lag
docker-compose exec kafka kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group crypto_stream_consumer
```

### Iceberg Table Stats

```sql
SELECT 
  file_count,
  total_records,
  total_size_mb
FROM iceberg.crypto."trades_bronze$files";
```

### Dagster Runs

Check run history in Dagster UI:
- Asset materialization frequency
- Run duration trends
- Error rates

## 🐛 Troubleshooting

**Problem: WebSocket connection drops**
```bash
# Check producer logs
docker-compose logs dagster --tail 50 | grep binance

# Restart producer
docker-compose restart dagster
```

**Problem: Kafka topic not created**
```bash
# List topics
docker-compose exec kafka kafka-topics.sh --list --bootstrap-server localhost:9092

# Create manually if needed
docker-compose exec kafka kafka-topics.sh --create \
  --topic crypto_trades \
  --bootstrap-server localhost:9092 \
  --partitions 3 \
  --replication-factor 1
```

**Problem: Iceberg catalog not accessible**
```bash
# Check Iceberg REST catalog
curl http://localhost:8181/v1/config

# Restart if needed
docker-compose restart iceberg-rest
```

## 📚 Resources

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/)
- [Binance WebSocket API](https://binance-docs.github.io/apidocs/spot/en/#websocket-market-streams)
- [DuckDB Documentation](https://duckdb.org/docs/)

## 🎯 Next Steps

- [ ] Add alerting voor abnormal price movements
- [ ] Implement data compaction strategy
- [ ] Add more crypto symbols (SOL, DOT, MATIC)
- [ ] Create prediction model (ML)
- [ ] Export metrics to Prometheus

## 👥 Owner

- **Team**: Data Engineering
- **Contact**: data-eng@company.com
- **Project Type**: Streaming Analytics (Pilot)
