"""
Investigations Code Location for Dagster

Dedicated location voor strafrechtelijke onderzoek data pipeline:

📥 BRONZE LAYER (Raw Ingestion):
   - File upload sensor (30s interval)
   - MinIO storage & metadata tracking
   - Asset Group: "investigations_ingestion"

🔄 SILVER LAYER (Canonical Mapping):
   - Canonical mapping sensor (60s interval) 
   - Data validation & normalization
   - Asset Group: "investigations_canonical"

📊 GOLD LAYER (Analytics):
   - Staging sensor (120s interval)
   - Analytical sensor (180s interval)
   - dbt transformations (staging → dimensions → facts)
   - Asset Groups: "investigations_staging", "investigations_analytical"

🎯 BENEFITS:
   - Dedicated code location = hot-reload zonder andere pipelines te beïnvloeden
   - Cleane group naming convention (investigations_*)
   - Gecentraliseerde resources & configuration
"""

from dagster import Definitions, load_assets_from_modules, define_asset_job

from . import assets
from . import analytics_assets
from . import canonical_assets
from . import dbt_assets
from . import sensors
from . import schedules
from . import jobs
from . import resources

# Load all assets
all_assets = load_assets_from_modules([assets, analytics_assets, canonical_assets, dbt_assets])

# Define the Dagster definitions for investigations location
defs = Definitions(
    assets=all_assets,
    sensors=[
        sensors.file_upload_sensor,
        sensors.check_canonical_data_sensor,
        sensors.check_staging_data_sensor,
        sensors.check_analytical_data_sensor,
    ],
    schedules=[
        schedules.analytics_schedule,
    ],
    jobs=[
        jobs.process_bank_transactions_job,
        jobs.process_telecom_data_job,
        jobs.analytics_job,
        jobs.canonical_mapping_job,
        jobs.staging_models_job,
        jobs.analytical_models_job,
    ],
    resources=resources.investigation_resources,
)
