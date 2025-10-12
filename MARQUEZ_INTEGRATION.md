# Marquez Integration Guide

## Wat is Marquez?

Marquez is een **metadata service** voor **data lineage tracking** gebouwd op de **OpenLineage** standaard. Het complementeert Amundsen door focus op:

- **Data Lineage**: Visualiseer data flows tussen datasets
- **Job Tracking**: Historie van alle pipeline runs (success/failure/duration)
- **Impact Analysis**: Wat breekt er als ik dataset X wijzig?
- **Performance Monitoring**: Bottleneck detectie in pipelines

## Architectuur

```
┌──────────────────────────────────────────────────────────┐
│                    DATA PLATFORM                          │
├──────────────────────────────────────────────────────────┤
│                                                           │
│  DAGSTER                    AMUNDSEN          MARQUEZ    │
│  (Orchestration)           (Discovery)       (Lineage)   │
│       │                         │                │        │
│       │ OpenLineage Events      │                │        │
│       └─────────────────────────┼────────────────┘        │
│                                 │                         │
│                            PostgreSQL                     │
│                         (Metadata Store)                  │
└──────────────────────────────────────────────────────────┘
```

## Current Setup

Je hebt al Marquez in je `docker-compose.yml`:

```yaml
marquez:
  image: marquezproject/marquez:latest
  container_name: dp_marquez
  ports:
    - "5000:5000"     # API
    - "5001:5001"     # Web UI
  depends_on:
    - postgres
  environment:
    MARQUEZ_PORT: 5000
    MARQUEZ_ADMIN_PORT: 5001
  volumes:
    - ./marquez/marquez-config.yml:/usr/src/app/marquez.yml
```

**Status**: Container draait maar stuurt nog geen events.

## Integration Options

### Option 1: Dagster + OpenLineage (Recommended)

Dagster heeft native OpenLineage support via `dagster-openlineage` package.

**Pros**:
- Official Dagster integration
- Automatic lineage extraction
- Asset-level granularity

**Cons**:
- Requires Dagster 1.6+ (je hebt 1.9.3 ✅)
- Extra dependency

**Implementation**:

1. **Install package** (in Dockerfile):
```dockerfile
RUN pip install dagster dagster-webserver dagster-openlineage
```

2. **Configure in dagster.yaml**:
```yaml
# orchestration/dagster_home/dagster.yaml
event_log_storage:
  module: dagster_openlineage
  class: OpenLineageEventLogStorage
  config:
    openlineage:
      transport:
        type: http
        url: http://marquez:5000
      namespace: dagster-weather-pipeline
```

3. **Assets automatically tracked**:
- `raw_weather_data` → `bronze/weather/*.parquet`
- `weather_quality_check` → quality metrics
- `clean_weather_data` → `silver/weather/*.parquet`
- `weather_to_postgres` → `weather.observations`

### Option 2: Manual OpenLineage Events

Custom events via Python client.

**Pros**:
- Full control over metadata
- Custom business context

**Cons**:
- More code maintenance
- Manual lineage definition

**Example**:
```python
from openlineage.client import OpenLineageClient
from openlineage.client.run import RunEvent, RunState, Job, Run

client = OpenLineageClient(url="http://marquez:5000")

# Start event
client.emit(RunEvent(
    eventType=RunState.START,
    job=Job(namespace="weather", name="raw_weather_data"),
    run=Run(runId=str(uuid4())),
    inputs=[],
    outputs=[Dataset(namespace="minio", name="bronze/weather")]
))
```

### Option 3: Airflow Lineage Backend (Not Applicable)

Je gebruikt Dagster, niet Airflow. Airflow heeft `airflow-provider-openlineage`.

## Recommended Approach

**Start met Option 1** (Dagster OpenLineage):

### Step 1: Update Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /opt/dagster/app

RUN pip install --no-cache-dir \
    dagster==1.9.3 \
    dagster-webserver==1.9.3 \
    dagster-openlineage==0.1.0 \  # Add this
    pandas \
    pyarrow \
    minio \
    psycopg2-binary \
    sqlalchemy \
    requests

COPY . .

ENV DAGSTER_HOME=/opt/dagster/app/dagster_home

EXPOSE 3000

# Startup script
RUN echo '#!/bin/bash\n\
dagster-daemon run &\n\
dagster-webserver -h 0.0.0.0 -p 3000 -w workspace.yaml\n\
' > /opt/dagster/start.sh && chmod +x /opt/dagster/start.sh

CMD ["/opt/dagster/start.sh"]
```

### Step 2: Create dagster.yaml

```yaml
# orchestration/dagster_home/dagster.yaml
run_storage:
  module: dagster.core.storage.runs
  class: SqliteRunStorage
  config:
    base_dir: /opt/dagster/app/dagster_home/storage

event_log_storage:
  module: dagster_openlineage
  class: OpenLineageEventLogStorage
  config:
    base_dir: /opt/dagster/app/dagster_home/storage
    openlineage:
      transport:
        type: http
        url: http://marquez:5000
        endpoint: /api/v1/lineage
        timeout: 5000
      namespace: weather-pipeline
      job_suffix: _dagster
```

### Step 3: Rebuild & Restart

```bash
docker-compose build dagster
docker-compose restart dagster
```

### Step 4: Verify Lineage

```bash
# Check Marquez API
curl http://localhost:5000/api/v1/namespaces

# Expected: {"namespaces": ["weather-pipeline"]}

# Check jobs
curl http://localhost:5000/api/v1/namespaces/weather-pipeline/jobs

# Check datasets
curl http://localhost:5000/api/v1/namespaces/weather-pipeline/datasets
```

### Step 5: View in UI

Open **http://localhost:5001** → Marquez Web UI

**Expected view**:
```
weather-pipeline
├── raw_weather_data
│   └── outputs: [minio://bronze/weather/*.parquet]
├── weather_quality_check
│   ├── inputs: [minio://bronze/weather/*.parquet]
│   └── outputs: [quality_metrics]
├── clean_weather_data
│   ├── inputs: [minio://bronze/weather/*.parquet]
│   └── outputs: [minio://silver/weather/*.parquet]
└── weather_to_postgres
    ├── inputs: [minio://silver/weather/*.parquet]
    └── outputs: [postgres://weather.observations]
```

## Lineage Metadata Captured

Per Dagster asset run:

| Field | Example |
|-------|---------|
| **Job Name** | `raw_weather_data_dagster` |
| **Run ID** | `4a4f32f0-0d59-4816-9c37-67e019baf98c` |
| **Start Time** | `2025-10-12T10:04:35Z` |
| **Duration** | `6.2s` |
| **Status** | `COMPLETED` / `FAILED` |
| **Inputs** | `[]` (for first asset) |
| **Outputs** | `[minio://bronze/weather/2025/10/12/09/weather_*.parquet]` |
| **Metadata** | Custom tags, quality scores |

## Use Cases

### 1. Debugging Pipeline Failures

**Scenario**: weather_to_postgres asset fails

**Marquez shows**:
- Last successful run: 2025-10-12 09:00
- Failed run: 2025-10-12 10:00
- Error: FK constraint violation
- Input dataset: `silver/weather/2025/10/12/weather_clean_*.parquet`
- Affected downstream: None (end of pipeline)

### 2. Impact Analysis

**Scenario**: Je wilt Open-Meteo API vervangen door KNMI API

**Marquez shows**:
```
raw_weather_data (modified)
    ↓
weather_quality_check (affected)
    ↓
clean_weather_data (affected)
    ↓
weather_to_postgres (affected)
    ↓
weather.observations (affected)
    ↓
weather.weather_near_towers (affected)
```

**Result**: 6 downstream components impacted!

### 3. Performance Monitoring

**Query**: "Welke asset duurt het langst?"

**Marquez dashboard**:
- raw_weather_data: avg 6s
- weather_quality_check: avg 2s
- clean_weather_data: avg 3s
- weather_to_postgres: avg 5s

**Total pipeline**: ~16s end-to-end

### 4. Data Freshness

**Alert**: "weather.observations > 2 hours old"

**Marquez shows**:
- Last successful run: 10:00 UTC
- Current time: 12:05 UTC
- Status: Pipeline hasn't run (schedule stopped?)

## Amundsen vs Marquez

Use **both** for complete observability:

| Question | Tool |
|----------|------|
| "Welke weather tables zijn er?" | **Amundsen** |
| "Wat is het schema van observations?" | **Amundsen** |
| "Wie is eigenaar van deze data?" | **Amundsen** |
| "Hoe komt data in observations?" | **Marquez** |
| "Waarom faalde de laatste run?" | **Marquez** |
| "Welke assets gebruiken dit als input?" | **Marquez** |
| "Hoe lang duurt de pipeline?" | **Marquez** |

## Next Steps

### Immediate (Recommended):
1. ✅ Add `dagster-openlineage` to Dockerfile
2. ✅ Create `dagster.yaml` with OpenLineage config
3. ✅ Rebuild Dagster container
4. ✅ Run pipeline and verify events in Marquez

### Future Enhancements:
- [ ] Add custom metadata (data quality scores)
- [ ] Configure retention policies (keep 30 days lineage)
- [ ] Set up Slack alerts for failed runs
- [ ] Create Marquez → Amundsen sync (lineage in catalog)

### Alternative (If OpenLineage doesn't work):
- Manual events in each asset using `openlineage-python`
- More control but requires code changes

## Resources

- Dagster OpenLineage: https://docs.dagster.io/integrations/openlineage
- Marquez Docs: https://marquezproject.github.io/marquez/
- OpenLineage Spec: https://openlineage.io/docs/spec/

---

**Status**: Ready to implement! Kies Option 1 voor snelste integratie.
