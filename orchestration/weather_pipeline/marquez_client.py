"""
Simple Marquez Integration - Direct HTTP API calls
No complex dependencies, just requests library
"""

import os
import json
import uuid
from datetime import datetime
from typing import Optional, List, Dict
import requests

# Marquez configuration
MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://marquez:5000")
NAMESPACE = "weather-pipeline"


def emit_lineage_start(job_name: str, run_id: Optional[str] = None) -> str:
    """
    Emit START event to Marquez via HTTP
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
                "facets": {}
            },
            "inputs": [],
            "outputs": [],
            "producer": "dagster-weather-pipeline"
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


def emit_lineage_complete(job_name: str, run_id: str, inputs: List[Dict] = None, outputs: List[Dict] = None):
    """
    Emit COMPLETE event to Marquez via HTTP
    """
    try:
        # Build input datasets
        input_datasets = []
        if inputs:
            for input_ds in inputs:
                input_datasets.append({
                    "namespace": input_ds.get("namespace", "unknown"),
                    "name": input_ds.get("name", "unknown"),
                    "facets": {
                        "dataSource": {
                            "_producer": "dagster-weather-pipeline",
                            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                            "name": input_ds.get("source", "Unknown"),
                            "uri": input_ds.get("uri", "")
                        }
                    }
                })
        
        # Build output datasets
        output_datasets = []
        if outputs:
            for output in outputs:
                output_datasets.append({
                    "namespace": output.get("namespace", "unknown"),
                    "name": output.get("name", "unknown"),
                    "facets": {
                        "dataSource": {
                            "_producer": "dagster-weather-pipeline",
                            "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/DataSourceDatasetFacet.json",
                            "name": output.get("source", "Unknown"),
                            "uri": output.get("uri", "")
                        }
                    }
                })
        
        event = {
            "eventType": "COMPLETE",
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "run": {
                "runId": run_id
            },
            "job": {
                "namespace": NAMESPACE,
                "name": job_name,
                "facets": {}
            },
            "inputs": input_datasets,
            "outputs": output_datasets,
            "producer": "dagster-weather-pipeline"
        }
        
        response = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Marquez: COMPLETE event for {job_name} ({len(input_datasets)} inputs, {len(output_datasets)} outputs)")
        else:
            print(f"⚠️  Marquez COMPLETE failed: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Marquez not available: {e}")


def emit_lineage_fail(job_name: str, run_id: str, error: Optional[str] = None):
    """
    Emit FAIL event to Marquez via HTTP
    """
    try:
        event = {
            "eventType": "FAIL",
            "eventTime": datetime.utcnow().isoformat() + "Z",
            "run": {
                "runId": run_id,
                "facets": {
                    "errorMessage": {
                        "_producer": "dagster-weather-pipeline",
                        "_schemaURL": "https://openlineage.io/spec/facets/1-0-0/ErrorMessageRunFacet.json",
                        "message": error or "Unknown error",
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
            "producer": "dagster-weather-pipeline"
        }
        
        response = requests.post(
            f"{MARQUEZ_URL}/api/v1/lineage",
            json=event,
            timeout=5
        )
        
        if response.status_code in [200, 201]:
            print(f"✅ Marquez: FAIL event for {job_name}")
        else:
            print(f"⚠️  Marquez FAIL failed: {response.status_code}")
            
    except Exception as e:
        print(f"⚠️  Marquez not available: {e}")


# Helper function to wrap asset execution with lineage tracking
def track_lineage(job_name: str, outputs: List[Dict] = None):
    """
    Context manager for tracking lineage
    Usage:
        run_id = emit_lineage_start("raw_weather_data")
        try:
            # ... do work ...
            emit_lineage_complete("raw_weather_data", run_id, outputs)
        except Exception as e:
            emit_lineage_fail("raw_weather_data", run_id, str(e))
    """
    pass  # Implemented inline in assets
