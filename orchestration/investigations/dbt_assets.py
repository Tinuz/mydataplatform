"""
dbt Integration - Staging and Analytical Models

Simple @asset wrappers that execute dbt models via subprocess.
"""

from dagster import asset, AssetExecutionContext, Output
import subprocess
import json
import uuid
from pathlib import Path
import time
from .marquez_lineage import emit_dbt_model_lineage

# Absolute path to dbt project in container
DBT_PROJECT_DIR = "/opt/dagster/dbt_investigations"


def run_dbt_command(context: AssetExecutionContext, command: list, timeout: int = 300) -> dict:
    """
    Execute dbt command with proper error handling and timeout.
    
    Args:
        context: Dagster execution context for logging
        command: dbt command as list (e.g. ["build", "--select", "tag:staging"])
        timeout: Maximum execution time in seconds (default 5 minutes)
    
    Returns:
        dict with stdout, stderr, returncode
    """
    full_command = ["dbt"] + command + ["--profiles-dir", "."]
    
    context.log.info(f"Running dbt command: {' '.join(full_command)}")
    start_time = time.time()
    
    try:
        result = subprocess.run(
            full_command,
            cwd=DBT_PROJECT_DIR,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        context.log.info(f"dbt command completed in {elapsed:.2f}s with return code {result.returncode}")
        
        # Always log output for debugging
        if result.stdout:
            context.log.info(f"dbt stdout:\n{result.stdout[-2000:]}")  # Last 2000 chars
        
        if result.returncode != 0:
            context.log.error(f"dbt stderr:\n{result.stderr}")
            raise Exception(f"dbt {command[0]} failed with return code {result.returncode}")
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "elapsed_seconds": elapsed
        }
    
    except subprocess.TimeoutExpired:
        context.log.error(f"dbt command timed out after {timeout}s")
        raise Exception(f"dbt {command[0]} timed out after {timeout}s")
    
    except Exception as e:
        context.log.error(f"Unexpected error running dbt: {str(e)}")
        raise


@asset(
    group_name="investigations_staging",
    compute_kind="dbt",
)
def dbt_staging_models(context: AssetExecutionContext):
    """
    Execute dbt staging models (views).
    
    Models:
    - stg_bank_transactions
    - stg_telecom_calls
    - stg_telecom_messages
    """
    run_id = str(uuid.uuid4())
    result = run_dbt_command(context, ["build", "--select", "tag:staging"], timeout=180)
    
    # Emit Marquez lineage for staging models
    # Note: In production, you'd parse dbt manifest.json to get exact row counts
    emit_dbt_model_lineage(
        model_name="stg_transactions",
        run_id=run_id,
        canonical_sources=["canonical_transaction"],
        records_processed=0  # Could parse from dbt logs
    )
    
    emit_dbt_model_lineage(
        model_name="stg_communications",
        run_id=run_id,
        canonical_sources=["canonical_communication"],
        records_processed=0
    )
    
    yield Output(
        value=None, 
        metadata={
            "elapsed_seconds": result["elapsed_seconds"],
            "returncode": result["returncode"],
            "marquez_run_id": run_id
        }
    )


@asset(
    group_name="investigations_analytical",
    compute_kind="dbt",
    deps=[dbt_staging_models],
)
def dbt_canonical_models(context: AssetExecutionContext):
    """
    Execute dbt canonical models (dimensions & facts).
    
    Models:
    - dim_bank_account, dim_phone_number
    - fact_transaction, fact_call, fact_message
    """
    run_id = str(uuid.uuid4())
    result = run_dbt_command(context, ["build", "--select", "tag:canonical"], timeout=180)
    
    # Emit Marquez lineage for analytical models
    emit_dbt_model_lineage(
        model_name="fact_financial_network",
        run_id=run_id,
        canonical_sources=["stg_transactions"],
        records_processed=0
    )
    
    emit_dbt_model_lineage(
        model_name="fact_communication_pattern",
        run_id=run_id,
        canonical_sources=["stg_communications"],
        records_processed=0
    )
    
    yield Output(
        value=None, 
        metadata={
            "elapsed_seconds": result["elapsed_seconds"],
            "returncode": result["returncode"],
            "marquez_run_id": run_id
        }
    )


@asset(
    group_name="investigations_analytical",
    compute_kind="dbt",
    deps=[dbt_canonical_models],
)
def dbt_test_all(context: AssetExecutionContext):
    """Run all dbt tests."""
    result = run_dbt_command(context, ["test"], timeout=120)
    
    yield Output(
        value=None, 
        metadata={
            "elapsed_seconds": result["elapsed_seconds"],
            "returncode": result["returncode"]
        }
    )
