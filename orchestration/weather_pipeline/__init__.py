"""
Weather Data Pipeline
Orchestrated with Dagster, quality checks with Great Expectations
"""

from dagster import Definitions, load_assets_from_modules

from . import assets
from .schedules import weather_hourly_schedule

# Load all assets from the assets module
all_assets = load_assets_from_modules([assets])

# Define the Dagster code location
defs = Definitions(
    assets=all_assets,
    schedules=[weather_hourly_schedule],
)
