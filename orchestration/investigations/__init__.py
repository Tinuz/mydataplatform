"""
Investigations Package for Dagster

Automatic processing of strafrechtelijke onderzoek data:
- File detection sensor
- Type-based routing to processors
- Bank, telecom, forensic pipelines
- Status tracking in PostgreSQL
"""

from dagster import Definitions, load_assets_from_modules

from . import assets
from . import analytics_assets
from . import sensors
from . import schedules
from . import jobs
from . import resources

# Load all assets
all_assets = load_assets_from_modules([assets, analytics_assets])

# Define the Dagster definitions
defs = Definitions(
    assets=all_assets,
    sensors=[
        sensors.file_upload_sensor,
    ],
    schedules=[
        schedules.analytics_schedule,
    ],
    jobs=[
        jobs.process_bank_transactions_job,
        jobs.process_telecom_data_job,
        jobs.analytics_job,
    ],
    resources=resources.investigation_resources,
)
