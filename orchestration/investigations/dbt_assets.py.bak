"""
Dagster + dbt Integration for Canonical Data Models

Orchestrates the transformation pipeline:
1. Raw data processing → PostgreSQL
2. dbt staging models → Clean views
3. dbt canonical models → Standardized tables with contracts
4. dbt tests → Data quality validation
"""

from dagster import asset, AssetExecutionContext, Output, MetadataValue, OpExecutionContext
from dagster_dbt import DbtCliResource, dbt_assets, DagsterDbtTranslator, DagsterDbtTranslatorSettings
from pathlib import Path
import json
from typing import Any, Mapping

# Path to dbt project
DBT_PROJECT_DIR = Path(__file__).parent.parent.parent / "dbt_investigations"
DBT_PROFILES_DIR = DBT_PROJECT_DIR


# Simple wrapper asset for full dbt build (optional, for manual runs)
@asset(
    group_name="investigations_staging",
    compute_kind="dbt",
)
def dbt_investigations_full_build(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Build all dbt models for investigations project.
    
    NOTE: This is a simple wrapper. Use the @dbt_assets below for sensor-triggered runs.
    """
    dbt_build_result = dbt.cli(["build"], context=context, manifest=dbt.get_manifest_json())
    context.log.info(f"dbt build completed")
    return Output(value={"status": "completed"})


# Native dbt assets for staging models
@dbt_assets(
    manifest=DBT_PROJECT_DIR / "target" / "manifest.json",
    select="staging",
    project_dir=DBT_PROJECT_DIR,
    dagster_dbt_translator=DagsterDbtTranslator(
        settings=DagsterDbtTranslatorSettings(enable_asset_checks=True)
    )
)
def dbt_staging_models(context: OpExecutionContext, dbt: DbtCliResource):
    """
    Build dbt staging models (views).
    
    Staging models extract and clean data from canonical tables.
    These are materialized as views for performance.
    """
    yield from dbt.cli(["build", "--select", "staging"], context=context).stream()


# Native dbt assets for canonical models  
@dbt_assets(
    manifest=DBT_PROJECT_DIR / "target" / "manifest.json",
    select="canonical",
    project_dir=DBT_PROJECT_DIR,
    dagster_dbt_translator=DagsterDbtTranslator(
        settings=DagsterDbtTranslatorSettings(enable_asset_checks=True)
    )
)
def dbt_canonical_models(context: OpExecutionContext, dbt: DbtCliResource):
    """
    Run dbt canonical models with data contracts.
    
    Canonical models transform staging data into standardized entities:
    - dim_bank_account (IBAN parsing, bank name lookup)
    - dim_phone_number (normalization, provider detection)
    - fact_transaction (enrichment, risk scoring)
    
    Data contracts enforce schema guarantees at runtime.
    """
    dbt_run_result = dbt.cli(["run", "--select", "canonical"], context=context).wait()
    
    # Extract model run information
    run_results = dbt_run_result.result
    models_run = []
    
    if hasattr(run_results, 'results'):
        for result in run_results.results:
            if hasattr(result, 'node'):
                models_run.append({
                    'model': result.node.name,
                    'status': result.status,
                    'execution_time': result.execution_time if hasattr(result, 'execution_time') else None,
                    'rows_affected': result.adapter_response.get('rows_affected') if hasattr(result, 'adapter_response') else None
                })
    
    context.log.info(f"Ran {len(models_run)} canonical models with data contracts")
    
    return Output(
        value={'models': models_run, 'total': len(models_run)},
        metadata={
            "models_run": MetadataValue.int(len(models_run)),
            "details": MetadataValue.json(models_run),
        }
    )


@asset(
    group_name="investigations_analytical",
    compute_kind="dbt",
    deps=[dbt_canonical_models],
)
def dbt_test_canonical(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Run dbt tests on canonical models.
    
    Tests include:
    - Built-in tests (not_null, unique, relationships)
    - Custom tests (valid_iban_format, valid_phone_format)
    - Great Expectations tests (value_between, match_regex)
    
    Failed tests are stored for analysis.
    """
    dbt_test_result = dbt.cli(
        ["test", "--select", "canonical", "--store-failures"],
        context=context
    ).wait()
    
    # Extract test results
    test_results = dbt_test_result.result
    tests_run = []
    tests_passed = 0
    tests_failed = 0
    
    if hasattr(test_results, 'results'):
        for result in test_results.results:
            if hasattr(result, 'node'):
                status = result.status
                tests_run.append({
                    'test': result.node.name,
                    'status': status,
                    'failures': result.failures if hasattr(result, 'failures') else 0
                })
                
                if status == 'pass':
                    tests_passed += 1
                else:
                    tests_failed += 1
    
    context.log.info(f"Ran {len(tests_run)} tests: {tests_passed} passed, {tests_failed} failed")
    
    if tests_failed > 0:
        context.log.warning(f"⚠️ {tests_failed} tests failed! Check dbt logs for details.")
    
    return Output(
        value={
            'tests': tests_run,
            'total': len(tests_run),
            'passed': tests_passed,
            'failed': tests_failed,
            'success': tests_failed == 0
        },
        metadata={
            "tests_run": MetadataValue.int(len(tests_run)),
            "tests_passed": MetadataValue.int(tests_passed),
            "tests_failed": MetadataValue.int(tests_failed),
            "success": MetadataValue.bool(tests_failed == 0),
            "details": MetadataValue.json(tests_run),
        }
    )


@asset(
    group_name="investigations_analytical",
    compute_kind="dbt",
    deps=[dbt_canonical_models],
)
def dbt_docs_generate(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Generate dbt documentation site.
    
    Creates a static documentation site with:
    - Model lineage diagrams
    - Column-level documentation
    - Test results
    - Data contracts
    """
    dbt_docs_result = dbt.cli(["docs", "generate"], context=context).wait()
    
    docs_path = DBT_PROJECT_DIR / "target" / "index.html"
    
    context.log.info(f"Generated dbt docs at {docs_path}")
    context.log.info("Run 'dbt docs serve' to view documentation")
    
    return Output(
        value=str(docs_path),
        metadata={
            "docs_path": MetadataValue.path(str(docs_path)),
            "serve_command": MetadataValue.text("cd dbt_investigations && dbt docs serve"),
        }
    )


# Optional: Source freshness check
@asset(
    group_name="investigations_staging",
    compute_kind="dbt",
)
def dbt_source_freshness(context: AssetExecutionContext, dbt: DbtCliResource):
    """
    Check freshness of source data.
    
    Validates that processed_records table has recent data.
    """
    dbt_freshness_result = dbt.cli(["source", "freshness"], context=context).wait()
    
    freshness_results = dbt_freshness_result.result
    sources_checked = []
    
    if hasattr(freshness_results, 'results'):
        for result in freshness_results.results:
            if hasattr(result, 'node'):
                sources_checked.append({
                    'source': result.node.source_name,
                    'table': result.node.name,
                    'status': result.status,
                })
    
    context.log.info(f"Checked freshness for {len(sources_checked)} sources")
    
    return Output(
        value={'sources': sources_checked, 'total': len(sources_checked)},
        metadata={
            "sources_checked": MetadataValue.int(len(sources_checked)),
            "details": MetadataValue.json(sources_checked),
        }
    )
