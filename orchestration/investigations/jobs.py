"""
Dagster jobs for investigations processing

Defines the pipelines that process different data types
"""

from dagster import job, op, In, Out, OpExecutionContext, AssetSelection, define_asset_job
from .assets import detect_pending_files, process_bank_transactions, process_telecom_calls
from .analytics_assets import analytics_success_hook, analytics_failure_hook


@job(
    name="process_bank_transactions_job",
    description="Process bank transaction files for investigations",
    tags={"team": "investigations", "type": "bank"}
)
def process_bank_transactions_job():
    """
    Job that processes bank transaction files
    
    Pipeline:
    1. Detect pending bank files
    2. Process each file (CSV -> Parquet)
    3. Index in PostgreSQL
    """
    files = detect_pending_files()
    process_bank_transactions(files)


@job(
    name="process_telecom_data_job",
    description="Process telecom call/SMS records for investigations",
    tags={"team": "investigations", "type": "telecom"}
)
def process_telecom_data_job():
    """
    Job that processes telecom data files
    
    Pipeline:
    1. Detect pending telecom files
    2. Process call records
    3. Index in PostgreSQL
    """
    files = detect_pending_files()
    process_telecom_calls(files)


@job(
    name="process_all_pending_job",
    description="Process all pending files regardless of type",
    tags={"team": "investigations", "type": "all"}
)
def process_all_pending_job():
    """
    Job that processes all pending files
    
    Runs all processors in parallel
    """
    files = detect_pending_files()
    process_bank_transactions(files)
    process_telecom_calls(files)


# Analytics job - runs aggregations on processed data
analytics_job = define_asset_job(
    name="investigation_analytics_job",
    selection=AssetSelection.groups("investigations_analytics"),
    description="Generate analytics summaries from processed investigation data",
    tags={"team": "investigations", "type": "analytics"},
    hooks={analytics_success_hook, analytics_failure_hook}
)

# Canonical mapping job - maps raw data to canonical schema
canonical_mapping_job = define_asset_job(
    name="canonical_mapping_job",
    selection=AssetSelection.groups("investigations_canonical"),
    description="Automatically map raw data to canonical schema",
    tags={"team": "investigations", "type": "canonical", "automated": "true"}
)

# Staging models job - runs dbt staging models
staging_models_job = define_asset_job(
    name="staging_models_job",
    selection=AssetSelection.groups("investigations_staging"),
    description="Automatically build dbt staging models from canonical data",
    tags={"team": "investigations", "type": "staging", "automated": "true"}
)

# Analytical models job - runs dbt canonical models
analytical_models_job = define_asset_job(
    name="analytical_models_job",
    selection=AssetSelection.groups("investigations_analytical"),
    description="Automatically build analytical models (dimensions and facts) from staging data",
    tags={"team": "investigations", "type": "analytical", "automated": "true"}
)
