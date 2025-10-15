"""
Marquez Lineage Integration for Canonical Data Model
Tracks data lineage from raw sources through canonical layer to dbt models
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict
import requests

# Marquez configuration
MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://marquez:5000")
NAMESPACE = "investigations-canonical"


def emit_canonical_lineage_start(job_name: str, run_id: Optional[str] = None) -> str:
    """
    Emit START event for canonical mapping job
    Returns run_id for tracking
    """
    if not run_id:
        run_id = str(uuid.uuid4())
    
    try:
        event = {
            "eventType": "START",
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "run": {
                "runId": run_id
            },
            "job": {
                "namespace": NAMESPACE,
                "name": job_name,
                "facets": {
                    "documentation": {
                        "_producer": "dagster-investigations",
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json",
                        "description": f"Maps {job_name} from raw sources to canonical integration layer"
                    }
                }
            },
            "inputs": [],
            "outputs": [],
            "producer": "dagster-investigations"
        }
        
        response = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Marquez: START event for {job_name}")
        else:
            print(f"⚠️  Marquez START failed: {response.status_code}")
            
        return run_id
        
    except Exception as e:
        print(f"⚠️  Marquez not available: {e}")
        return run_id


def emit_canonical_lineage_complete(
    job_name: str, 
    run_id: str, 
    source_system: str,
    raw_table: str,
    canonical_table: str,
    records_processed: int = 0,
    records_valid: int = 0,
    records_warning: int = 0,
    records_error: int = 0
):
    """
    Emit COMPLETE event for canonical mapping with data quality metrics
    """
    try:
        # Define input dataset (raw source)
        input_datasets = [{
            "namespace": "investigations-raw",
            "name": f"{source_system}.{raw_table}",
            "facets": {
                "dataSource": {
                    "_producer": "dagster-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                    "name": source_system.upper(),
                    "uri": f"postgresql://postgres:5432/superset?schema=public&table={raw_table}"
                },
                "documentation": {
                    "_producer": "dagster-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationDatasetFacet.json",
                    "description": f"Raw data from {source_system}"
                }
            }
        }]
        
        # Define output dataset (canonical layer)
        output_datasets = [{
            "namespace": "canonical-integration",
            "name": f"canonical.{canonical_table}",
            "facets": {
                "dataSource": {
                    "_producer": "dagster-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                    "name": "Canonical Integration Layer",
                    "uri": f"postgresql://postgres:5432/superset?schema=canonical&table={canonical_table}"
                },
                "documentation": {
                    "_producer": "dagster-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationDatasetFacet.json",
                    "description": f"Semantically consistent, validated {canonical_table} records"
                },
                "dataQualityMetrics": {
                    "_producer": "dagster-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
                    "rowCount": records_processed,
                    "columnMetrics": {
                        "validation_status": {
                            "count": records_processed,
                            "distinctCount": 3,
                            "nullCount": 0
                        }
                    }
                }
            },
            "outputFacets": {
                "outputStatistics": {
                    "_producer": "dagster-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/OutputStatisticsOutputDatasetFacet.json",
                    "rowCount": records_processed,
                    "size": records_processed * 1024  # Approximate size
                }
            }
        }]
        
        # Job facets with data quality metrics
        job_facets = {
            "documentation": {
                "_producer": "dagster-investigations",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json",
                "description": f"Canonical mapping for {canonical_table} with validation and data quality scoring"
            }
        }
        
        # Run facets with custom metrics
        run_facets = {
            "dataQuality": {
                "_producer": "dagster-investigations",
                "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataQualityMetricsInputDatasetFacet.json",
                "totalRecords": records_processed,
                "validRecords": records_valid,
                "warningRecords": records_warning,
                "errorRecords": records_error,
                "validationRate": round((records_valid / records_processed * 100), 2) if records_processed > 0 else 0,
                "qualityScore": round(((records_valid + records_warning) / records_processed * 100), 2) if records_processed > 0 else 0
            }
        }
        
        event = {
            "eventType": "COMPLETE",
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "run": {
                "runId": run_id,
                "facets": run_facets
            },
            "job": {
                "namespace": NAMESPACE,
                "name": job_name,
                "facets": job_facets
            },
            "inputs": input_datasets,
            "outputs": output_datasets,
            "producer": "dagster-investigations"
        }
        
        response = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            quality_score = run_facets["dataQuality"]["qualityScore"]
            print(f"✅ Marquez: COMPLETE event for {job_name} - {records_processed} records, {quality_score}% quality")
        else:
            print(f"⚠️  Marquez COMPLETE failed: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"⚠️  Marquez not available: {e}")


def emit_canonical_lineage_fail(job_name: str, run_id: str, error: Optional[str] = None):
    """
    Emit FAIL event for canonical mapping job
    """
    try:
        event = {
            "eventType": "FAIL",
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "run": {
                "runId": run_id,
                "facets": {
                    "errorMessage": {
                        "_producer": "dagster-investigations",
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ErrorMessageRunFacet.json",
                        "message": error or "Canonical mapping failed",
                        "programmingLanguage": "Python",
                        "stackTrace": ""
                    }
                }
            },
            "job": {
                "namespace": NAMESPACE,
                "name": job_name,
                "facets": {}
            },
            "inputs": [],
            "outputs": [],
            "producer": "dagster-investigations"
        }
        
        response = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"❌ Marquez: FAIL event for {job_name}")
        else:
            print(f"⚠️  Marquez FAIL logging failed: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Marquez not available: {e}")


def emit_dbt_model_lineage(
    model_name: str,
    run_id: str,
    canonical_sources: List[str],
    records_processed: int = 0
):
    """
    Emit lineage for dbt models that read from canonical layer
    """
    try:
        # Input datasets from canonical layer
        input_datasets = []
        for source in canonical_sources:
            input_datasets.append({
                "namespace": "canonical-integration",
                "name": f"canonical.{source}",
                "facets": {
                    "dataSource": {
                        "_producer": "dbt-investigations",
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                        "name": "Canonical Integration Layer",
                        "uri": f"postgresql://postgres:5432/superset?schema=canonical&table={source}"
                    }
                }
            })
        
        # Output dataset (dbt staging model)
        output_datasets = [{
            "namespace": "dbt-staging",
            "name": f"staging.{model_name}",
            "facets": {
                "dataSource": {
                    "_producer": "dbt-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                    "name": "dbt Staging Layer",
                    "uri": f"postgresql://postgres:5432/superset?schema=staging&table={model_name}"
                },
                "documentation": {
                    "_producer": "dbt-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationDatasetFacet.json",
                    "description": f"dbt staging model: {model_name}"
                }
            },
            "outputFacets": {
                "outputStatistics": {
                    "_producer": "dbt-investigations",
                    "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/OutputStatisticsOutputDatasetFacet.json",
                    "rowCount": records_processed
                }
            }
        }]
        
        event = {
            "eventType": "COMPLETE",
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "run": {
                "runId": run_id
            },
            "job": {
                "namespace": "dbt-staging",
                "name": f"dbt_run_{model_name}",
                "facets": {
                    "documentation": {
                        "_producer": "dbt-investigations",
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DocumentationJobFacet.json",
                        "description": f"dbt transformation: {model_name} from canonical sources"
                    }
                }
            },
            "inputs": input_datasets,
            "outputs": output_datasets,
            "producer": "dbt-investigations"
        }
        
        response = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Marquez: dbt lineage for {model_name}")
        else:
            print(f"⚠️  Marquez dbt lineage failed: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Marquez not available: {e}")
