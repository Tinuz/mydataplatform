# 📘 Data Engineer Onboarding Guide

**Welkom bij het Data Platform!** Deze guide helpt je om data in te laden vanuit verschillende bronnen.

---

## 🎯 Inhoudsopgave

1. [Platform Setup & Toegang](#1-platform-setup--toegang)
2. [CSV Bestanden Laden vanuit Cloud Storage](#2-csv-bestanden-laden-vanuit-cloud-storage)
3. [Streaming Data Setup](#3-streaming-data-setup)
4. [Data Ophalen via Externe API](#4-data-ophalen-via-externe-api)
5. [Best Practices & Troubleshooting](#5-best-practices--troubleshooting)

---

## 1. Platform Setup & Toegang

### 1.1 Start het Platform

```bash
# Clone de repository
git clone https://github.com/Tinuz/mydataplatform.git
cd mydataplatform

# Start alle services
docker-compose --profile standard up -d

# Optioneel: Start Amundsen (data catalog)
docker-compose --profile amundsen up -d

# Check of alles draait
docker-compose ps
```

### 1.2 Toegang tot Services

Open `dashboard.html` in je browser voor een overzicht van alle services, of gebruik:

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster** | http://localhost:3000 | - |
| **Superset** | http://localhost:8088 | admin/admin |
| **MinIO** | http://localhost:9001 | minio/minio12345 |
| **Weather API** | http://localhost:8000/api/v1/weather | API Key: `demo-weather-api-key-2025` |
| **PostgreSQL** | localhost:5432 | superset/superset |

### 1.3 Bekende Locaties

- **Pipeline code:** `orchestration/weather_pipeline/`
- **SQL scripts:** `etl/sql/`
- **API code:** `api/server.js`
- **Docs:** `docs/`

---

## 2. CSV Bestanden Laden vanuit Cloud Storage

### 2.1 Scenario: CSV in Google Cloud Storage

**Stap 1: Maak een nieuw Dagster asset**

Creëer `orchestration/weather_pipeline/assets/gcs_ingestion.py`:

```python
"""
GCS CSV Ingestion Asset
Laadt CSV bestanden vanuit Google Cloud Storage
"""

from dagster import asset, AssetExecutionContext, MetadataValue
import pandas as pd
import os
from google.cloud import storage
from sqlalchemy import create_engine

@asset(
    group_name="ingestion",
    compute_kind="gcs",
    description="Laadt customer data vanuit GCS bucket"
)
def gcs_customers_bronze(context: AssetExecutionContext) -> pd.DataFrame:
    """
    Stap 1: Download CSV van GCS naar bronze layer
    
    GCS Path: gs://my-company-data/customers/customers.csv
    Output: bronze.customers (PostgreSQL)
    """
    
    # GCS configuratie
    bucket_name = os.getenv("GCS_BUCKET", "my-company-data")
    blob_name = "customers/customers.csv"
    
    context.log.info(f"📥 Downloading from gs://{bucket_name}/{blob_name}")
    
    # Download van GCS
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    
    # Lees direct naar Pandas
    content = blob.download_as_string()
    df = pd.read_csv(content)
    
    context.log.info(f"✅ Downloaded {len(df)} rows")
    
    # Schrijf naar PostgreSQL (bronze schema)
    conn_string = os.getenv("POSTGRES_CONN")
    engine = create_engine(conn_string)
    
    df.to_sql(
        name="customers",
        schema="bronze",
        con=engine,
        if_exists="replace",
        index=False
    )
    
    # Log metadata voor Dagster UI
    context.add_output_metadata({
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "columns": MetadataValue.md(", ".join(df.columns)),
        "preview": MetadataValue.md(df.head().to_markdown()),
    })
    
    return df


@asset(
    group_name="transformation",
    compute_kind="pandas",
    deps=[gcs_customers_bronze]
)
def silver_customers(context: AssetExecutionContext) -> pd.DataFrame:
    """
    Stap 2: Clean en transformeer data (bronze → silver)
    
    Transformaties:
    - Valideer email format
    - Normaliseer country codes
    - Remove duplicates
    - Add ingestion timestamp
    """
    
    conn_string = os.getenv("POSTGRES_CONN")
    engine = create_engine(conn_string)
    
    # Lees bronze data
    df = pd.read_sql_table("customers", schema="bronze", con=engine)
    
    context.log.info(f"🔄 Transforming {len(df)} customers...")
    
    # Data cleaning
    df = df.drop_duplicates(subset=['customer_id'])
    df['email'] = df['email'].str.lower().str.strip()
    df['country_code'] = df['country_code'].str.upper()
    df['ingested_at'] = pd.Timestamp.now()
    
    # Validatie
    invalid_emails = df[~df['email'].str.contains('@', na=False)]
    if len(invalid_emails) > 0:
        context.log.warning(f"⚠️ Found {len(invalid_emails)} invalid emails")
    
    # Schrijf naar silver
    df.to_sql(
        name="customers",
        schema="silver",
        con=engine,
        if_exists="replace",
        index=False
    )
    
    context.log.info(f"✅ Silver layer: {len(df)} clean records")
    
    return df
```

**Stap 2: Configureer GCS credentials**

```bash
# Voeg toe aan docker-compose.yml onder dagster service
environment:
  GOOGLE_APPLICATION_CREDENTIALS: /opt/dagster/app/credentials/gcs-key.json
  GCS_BUCKET: my-company-data
  POSTGRES_CONN: "postgresql://superset:superset@postgres:5432/superset"

volumes:
  - ./orchestration:/opt/dagster/app
  - ./credentials:/opt/dagster/app/credentials  # ← Voeg toe
```

**Stap 3: Plaats GCS service account key**

```bash
mkdir credentials
# Plaats je gcs-key.json in credentials/
# BELANGRIJK: Voeg credentials/ toe aan .gitignore!
```

**Stap 4: Registreer het asset**

Update `orchestration/weather_pipeline/assets/__init__.py`:

```python
from dagster import load_assets_from_modules
from . import weather_assets, gcs_ingestion

# Load all assets
weather_assets_list = load_assets_from_modules([weather_assets])
gcs_assets_list = load_assets_from_modules([gcs_ingestion])

all_assets = weather_assets_list + gcs_assets_list
```

**Stap 5: Test de pipeline**

```bash
# Herstart Dagster
docker-compose restart dagster

# Open Dagster UI: http://localhost:3000
# Ga naar Assets → gcs_customers_bronze
# Klik "Materialize" om te testen
```

### 2.2 Alternatief: CSV in AWS S3

Voor S3, gebruik `boto3` in plaats van `google-cloud-storage`:

```python
import boto3
from io import StringIO

@asset
def s3_customers_bronze(context: AssetExecutionContext):
    """Laadt CSV van AWS S3"""
    
    # S3 client
    s3_client = boto3.client('s3',
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("AWS_SECRET_KEY")
    )
    
    # Download CSV
    obj = s3_client.get_object(
        Bucket='my-bucket',
        Key='data/customers.csv'
    )
    
    # Parse naar DataFrame
    df = pd.read_csv(StringIO(obj['Body'].read().decode('utf-8')))
    
    # ... rest zoals GCS voorbeeld
```

### 2.3 Alternatief: CSV in MinIO (Local S3)

MinIO is al geïnstalleerd in het platform:

```python
import boto3

@asset
def minio_customers_bronze(context: AssetExecutionContext):
    """Laadt CSV van MinIO (local S3)"""
    
    s3_client = boto3.client('s3',
        endpoint_url='http://minio:9000',
        aws_access_key_id='minio',
        aws_secret_access_key='minio12345',
        region_name='us-east-1'
    )
    
    # Upload eerst een test CSV (via MinIO UI of boto3)
    # Dan download:
    obj = s3_client.get_object(
        Bucket='lake',
        Key='customers.csv'
    )
    
    df = pd.read_csv(obj['Body'])
    # ... opslaan in PostgreSQL
```

---

## 3. Streaming Data Setup

### 3.1 Scenario: Real-time Sensor Data Stream

**Stap 1: Installeer Kafka dependencies**

Update `orchestration/requirements.txt`:

```txt
# ... bestaande packages
kafka-python==2.0.2
confluent-kafka==2.3.0
```

**Stap 2: Voeg Kafka toe aan docker-compose.yml**

```yaml
services:
  # ... bestaande services
  
  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    container_name: dp_zookeeper
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
      ZOOKEEPER_TICK_TIME: 2000
    ports:
      - "2181:2181"
    profiles: ["streaming"]

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    container_name: dp_kafka
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: PLAINTEXT:PLAINTEXT,PLAINTEXT_HOST:PLAINTEXT
      KAFKA_INTER_BROKER_LISTENER_NAME: PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
    profiles: ["streaming"]
```

**Stap 3: Start Kafka**

```bash
docker-compose --profile streaming up -d
```

**Stap 4: Maak een Kafka consumer sensor**

Creëer `orchestration/weather_pipeline/sensors/kafka_sensor.py`:

```python
"""
Kafka Stream Sensor
Luistert naar Kafka topic en triggert Dagster runs
"""

from dagster import sensor, RunRequest, SkipReason, SensorEvaluationContext
from kafka import KafkaConsumer
import json
import os

@sensor(
    name="kafka_sensor_data_stream",
    minimum_interval_seconds=10,
    description="Luistert naar sensor_data topic en verwerkt berichten"
)
def kafka_sensor_stream(context: SensorEvaluationContext):
    """
    Kafka Stream Sensor
    
    Topic: sensor_data
    Format: {"sensor_id": "S001", "value": 23.5, "timestamp": "2025-10-12T10:00:00Z"}
    
    Triggers: run_key voor batch processing
    """
    
    # Kafka consumer configuratie
    consumer = KafkaConsumer(
        'sensor_data',
        bootstrap_servers=os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:29092'),
        auto_offset_reset='earliest',
        enable_auto_commit=True,
        group_id='dagster-sensor-consumer',
        value_deserializer=lambda x: json.loads(x.decode('utf-8')),
        consumer_timeout_ms=5000  # Poll timeout
    )
    
    messages = []
    
    # Poll voor nieuwe berichten
    for message in consumer:
        messages.append(message.value)
        context.log.info(f"📨 Received: {message.value}")
    
    consumer.close()
    
    # Als er berichten zijn, trigger een run
    if messages:
        context.log.info(f"✅ Processing {len(messages)} messages")
        
        return RunRequest(
            run_key=f"kafka_batch_{len(messages)}_{message.timestamp}",
            run_config={
                "ops": {
                    "process_kafka_messages": {
                        "config": {
                            "messages": messages
                        }
                    }
                }
            }
        )
    else:
        return SkipReason("No new messages in Kafka topic")
```

**Stap 5: Maak een processing job**

```python
from dagster import job, op, In, Out

@op(
    out=Out(pd.DataFrame),
    config_schema={"messages": list}
)
def process_kafka_messages(context) -> pd.DataFrame:
    """Verwerk Kafka messages naar DataFrame"""
    
    messages = context.op_config["messages"]
    df = pd.DataFrame(messages)
    
    # Schrijf naar PostgreSQL
    conn_string = os.getenv("POSTGRES_CONN")
    engine = create_engine(conn_string)
    
    df.to_sql(
        name="sensor_readings",
        schema="streaming",
        con=engine,
        if_exists="append",
        index=False
    )
    
    context.log.info(f"✅ Inserted {len(df)} readings into streaming.sensor_readings")
    
    return df

@job
def kafka_streaming_job():
    """Job die getriggerd wordt door Kafka sensor"""
    process_kafka_messages()
```

**Stap 6: Test de stream**

```python
# Test producer - run dit in een Python shell
from kafka import KafkaProducer
import json
from datetime import datetime

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# Stuur test berichten
for i in range(10):
    message = {
        "sensor_id": f"S{i:03d}",
        "value": 20 + i * 0.5,
        "timestamp": datetime.utcnow().isoformat()
    }
    producer.send('sensor_data', message)
    print(f"Sent: {message}")

producer.flush()
```

### 3.2 Alternatief: WebSocket Stream

Voor real-time WebSocket streams:

```python
import asyncio
import websockets
import json

@op
async def websocket_stream_reader(context):
    """Luistert naar WebSocket en schrijft naar database"""
    
    uri = "wss://api.example.com/stream"
    
    async with websockets.connect(uri) as websocket:
        context.log.info("🔌 Connected to WebSocket")
        
        messages = []
        
        # Luister voor 60 seconden
        timeout = asyncio.get_event_loop().time() + 60
        
        while asyncio.get_event_loop().time() < timeout:
            try:
                message = await asyncio.wait_for(
                    websocket.recv(), 
                    timeout=1.0
                )
                data = json.loads(message)
                messages.append(data)
                
            except asyncio.TimeoutError:
                continue
        
        # Bulk insert naar database
        df = pd.DataFrame(messages)
        # ... opslaan
        
        context.log.info(f"✅ Processed {len(messages)} WebSocket messages")
```

---

## 4. Data Ophalen via Externe API

### 4.1 Scenario: REST API met Paginatie

**Stap 1: Maak een API ingestion asset**

Creëer `orchestration/weather_pipeline/assets/api_ingestion.py`:

```python
"""
External API Ingestion
Haalt data op via REST API met paginatie en rate limiting
"""

from dagster import asset, AssetExecutionContext, MetadataValue
import requests
import pandas as pd
from sqlalchemy import create_engine
import time
import os

@asset(
    group_name="api_ingestion",
    compute_kind="api",
    description="Haalt product data van externe API"
)
def api_products_bronze(context: AssetExecutionContext) -> pd.DataFrame:
    """
    Haalt product catalog van externe API met paginatie
    
    API: https://api.example.com/products
    Authentication: Bearer token
    Output: bronze.api_products
    """
    
    base_url = "https://api.example.com/products"
    api_key = os.getenv("EXTERNAL_API_KEY", "your-api-key-here")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    all_products = []
    page = 1
    has_more = True
    
    context.log.info(f"🌐 Starting API fetch from {base_url}")
    
    while has_more:
        try:
            # API call met paginatie
            response = requests.get(
                base_url,
                headers=headers,
                params={"page": page, "per_page": 100},
                timeout=30
            )
            response.raise_for_status()
            
            data = response.json()
            products = data.get("products", [])
            
            if not products:
                has_more = False
                break
            
            all_products.extend(products)
            context.log.info(f"📄 Page {page}: {len(products)} products")
            
            # Check if more pages exist
            has_more = data.get("has_more", False)
            page += 1
            
            # Rate limiting (respect API limits)
            time.sleep(0.5)  # 2 requests per second
            
        except requests.exceptions.RequestException as e:
            context.log.error(f"❌ API Error on page {page}: {str(e)}")
            break
    
    context.log.info(f"✅ Total products fetched: {len(all_products)}")
    
    # Convert naar DataFrame
    df = pd.DataFrame(all_products)
    
    # Schrijf naar bronze layer
    conn_string = os.getenv("POSTGRES_CONN")
    engine = create_engine(conn_string)
    
    df.to_sql(
        name="api_products",
        schema="bronze",
        con=engine,
        if_exists="replace",
        index=False
    )
    
    # Metadata voor Dagster UI
    context.add_output_metadata({
        "num_products": len(df),
        "api_pages_fetched": page - 1,
        "columns": MetadataValue.md(", ".join(df.columns)),
        "sample": MetadataValue.md(df.head(3).to_markdown()),
    })
    
    return df


@asset(
    deps=[api_products_bronze],
    group_name="api_ingestion",
    compute_kind="pandas"
)
def silver_api_products(context: AssetExecutionContext):
    """
    Transform en enrich API data
    
    Transformaties:
    - Parse nested JSON fields
    - Calculate price in EUR
    - Add category mapping
    - Validate SKU format
    """
    
    conn_string = os.getenv("POSTGRES_CONN")
    engine = create_engine(conn_string)
    
    # Lees bronze
    df = pd.read_sql_table("api_products", schema="bronze", con=engine)
    
    context.log.info(f"🔄 Transforming {len(df)} products...")
    
    # Parse nested JSON (bijvoorbeeld specifications field)
    if 'specifications' in df.columns:
        df['specs'] = df['specifications'].apply(
            lambda x: json.loads(x) if isinstance(x, str) else x
        )
    
    # Price conversion (USD → EUR)
    if 'price_usd' in df.columns:
        df['price_eur'] = df['price_usd'] * 0.92  # Example rate
    
    # Data quality checks
    invalid_skus = df[~df['sku'].str.match(r'^[A-Z]{2}\d{6}$', na=False)]
    if len(invalid_skus) > 0:
        context.log.warning(f"⚠️ {len(invalid_skus)} products with invalid SKU")
    
    # Schrijf naar silver
    df.to_sql(
        name="api_products",
        schema="silver",
        con=engine,
        if_exists="replace",
        index=False
    )
    
    context.log.info(f"✅ Silver layer: {len(df)} transformed products")
    
    return df
```

**Stap 2: Configureer API credentials**

```bash
# Voeg toe aan docker-compose.yml
environment:
  EXTERNAL_API_KEY: "your-secret-api-key"
  
# Of gebruik .env file (veiliger)
echo "EXTERNAL_API_KEY=your-secret-api-key" >> .env
```

**Stap 3: Schedule de API sync**

```python
# In schedules.py
from dagster import schedule, RunRequest

@schedule(
    cron_schedule="0 */4 * * *",  # Elke 4 uur
    job_name="api_ingestion_job",
    execution_timezone="Europe/Amsterdam"
)
def api_sync_schedule(context):
    """Sync externe API elke 4 uur"""
    return RunRequest(
        run_key=f"api_sync_{context.scheduled_execution_time.timestamp()}"
    )
```

### 4.2 GraphQL API Voorbeeld

Voor GraphQL APIs:

```python
import requests

@asset
def graphql_api_data(context: AssetExecutionContext):
    """Haalt data van GraphQL endpoint"""
    
    query = """
    query GetProducts($limit: Int!) {
        products(limit: $limit) {
            id
            name
            price
            category {
                name
            }
        }
    }
    """
    
    variables = {"limit": 100}
    
    response = requests.post(
        "https://api.example.com/graphql",
        json={"query": query, "variables": variables},
        headers={"Authorization": f"Bearer {os.getenv('API_KEY')}"}
    )
    
    data = response.json()
    products = data['data']['products']
    
    df = pd.DataFrame(products)
    # ... opslaan naar database
```

### 4.3 API met OAuth2 Authentication

```python
from requests_oauthlib import OAuth2Session

@asset
def oauth_api_data(context: AssetExecutionContext):
    """API call met OAuth2 flow"""
    
    client_id = os.getenv("OAUTH_CLIENT_ID")
    client_secret = os.getenv("OAUTH_CLIENT_SECRET")
    token_url = "https://api.example.com/oauth/token"
    
    # Get access token
    oauth = OAuth2Session(client_id)
    token = oauth.fetch_token(
        token_url,
        client_secret=client_secret,
        grant_type='client_credentials'
    )
    
    # Make authenticated request
    response = oauth.get("https://api.example.com/data")
    data = response.json()
    
    # ... process data
```

---

## 5. Best Practices & Troubleshooting

### 5.1 Data Quality Checks

Voeg altijd validatie toe:

```python
from dagster import asset, AssetCheckResult, AssetCheckSeverity

@asset
def validated_customers(context):
    """Asset met data quality checks"""
    
    df = # ... load data
    
    # Check 1: No nulls in critical columns
    null_check = df[['customer_id', 'email']].isnull().sum().sum()
    context.add_asset_check(
        AssetCheckResult(
            passed=null_check == 0,
            severity=AssetCheckSeverity.ERROR,
            description=f"Found {null_check} null values in critical columns"
        )
    )
    
    # Check 2: Email format validation
    invalid_emails = len(df[~df['email'].str.contains('@')])
    context.add_asset_check(
        AssetCheckResult(
            passed=invalid_emails == 0,
            severity=AssetCheckSeverity.WARNING,
            description=f"Found {invalid_emails} invalid email formats"
        )
    )
    
    return df
```

### 5.2 Incremental Loading

Voor grote datasets, gebruik incremental loading:

```python
@asset(
    partitions_def=DailyPartitionsDefinition(start_date="2025-01-01")
)
def incremental_data(context: AssetExecutionContext):
    """Laadt alleen nieuwe data per dag"""
    
    partition_date = context.asset_partition_key_for_output()
    
    # Query alleen data voor deze dag
    df = fetch_data_for_date(partition_date)
    
    # Append (niet replace!)
    df.to_sql(..., if_exists="append")
```

### 5.3 Error Handling & Retries

```python
from dagster import Backoff, Jitter, RetryPolicy

@asset(
    retry_policy=RetryPolicy(
        max_retries=3,
        delay=5,
        backoff=Backoff.EXPONENTIAL,
        jitter=Jitter.PLUS_MINUS
    )
)
def resilient_api_call(context):
    """Asset met retry policy bij failures"""
    
    try:
        # API call
        response = requests.get(...)
        response.raise_for_status()
        
    except requests.exceptions.Timeout:
        context.log.error("⏱️ API timeout - will retry")
        raise  # Dagster zal retries triggeren
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            context.log.warning("🚦 Rate limited - backing off")
            time.sleep(60)
            raise
        else:
            context.log.error(f"❌ HTTP {e.response.status_code}")
            raise
```

### 5.4 Monitoring & Alerts

Gebruik Marquez voor lineage en Dagster sensors voor alerts:

```python
@sensor(
    name="data_freshness_alert",
    minimum_interval_seconds=3600
)
def data_freshness_sensor(context):
    """Alert als data ouder is dan 24 uur"""
    
    engine = create_engine(os.getenv("POSTGRES_CONN"))
    
    query = """
    SELECT MAX(ingested_at) as last_update
    FROM bronze.customers
    """
    
    result = pd.read_sql(query, engine)
    last_update = result['last_update'].iloc[0]
    
    hours_old = (datetime.now() - last_update).total_seconds() / 3600
    
    if hours_old > 24:
        context.log.error(f"🚨 Data is {hours_old:.1f} hours old!")
        # Trigger alert (Slack, email, etc.)
```

### 5.5 Common Troubleshooting

**Problem: "ModuleNotFoundError: No module named 'xyz'"**
```bash
# Rebuild Dagster container met nieuwe dependencies
docker-compose build dagster
docker-compose restart dagster
```

**Problem: "Connection refused to external API"**
```bash
# Check of API key correct is
docker-compose exec dagster env | grep API_KEY

# Test API connectivity
docker-compose exec dagster curl -H "Authorization: Bearer $API_KEY" https://api.example.com
```

**Problem: "PostgreSQL connection error"**
```bash
# Check PostgreSQL status
docker-compose ps postgres

# Test connectie
docker-compose exec dagster psql $POSTGRES_CONN -c "SELECT 1"
```

**Problem: "Kafka consumer timeout"**
```bash
# Check Kafka status
docker-compose logs kafka --tail 50

# Test topic exists
docker-compose exec kafka kafka-topics --list --bootstrap-server localhost:9092
```

### 5.6 Performance Tips

1. **Gebruik batch processing** voor grote volumes
2. **Enable connection pooling** voor database calls
3. **Compress data** in transit (gzip)
4. **Partition data** by date/category
5. **Index foreign keys** in PostgreSQL

```sql
-- Add indexes voor betere query performance
CREATE INDEX idx_customers_email ON bronze.customers(email);
CREATE INDEX idx_sensor_timestamp ON streaming.sensor_readings(timestamp);
```

---

## 📚 Volgende Stappen

1. ✅ **Kies je data source** (CSV/Stream/API)
2. ✅ **Volg de stappen** in deze guide
3. ✅ **Test in Dagster UI** (http://localhost:3000)
4. ✅ **Check data in Superset** (http://localhost:8088)
5. ✅ **Monitor lineage in Marquez** (http://localhost:3001)
6. ✅ **Document in Amundsen** (http://localhost:5005)

**Hulp nodig?**
- 📖 Bekijk `docs/` voor meer guides
- 🔍 Check Dagster logs: `docker-compose logs dagster`
- 💬 Open een GitHub issue voor vragen

**Happy Data Engineering! 🚀**
