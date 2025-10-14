"""
OpenLineage integration for Investigations pipeline
Emits lineage events to Marquez for tracking data flow
"""

import os
from typing import Any, Optional, List
from dagster import (
    HookContext
)
from openlineage.client import OpenLineageClient
from openlineage.client.run import (
    RunEvent, 
    RunState, 
    Run, 
    Job,
    Dataset,
    InputDataset,
    OutputDataset
)
from openlineage.client.facet import (
    DataSourceDatasetFacet,
    SchemaDatasetFacet,
    SchemaField
)
from datetime import datetime
import uuid

# Marquez configuration
MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://marquez:5000")
NAMESPACE = "investigations-pipeline"

# Initialize OpenLineage client
client = OpenLineageClient(url=MARQUEZ_URL)


def emit_start_event(context: HookContext, inputs: List[Dataset] = None, outputs: List[Dataset] = None):
    """Emit START event when asset materialization begins"""
    try:
        run_id = str(uuid.uuid4())
        job_name = context.op.name
        
        event = RunEvent(
            eventType=RunState.START,
            eventTime=datetime.utcnow().isoformat() + "Z",
            run=Run(runId=run_id),
            job=Job(
                namespace=NAMESPACE,
                name=job_name,
                facets={}
            ),
            inputs=[InputDataset(namespace=NAMESPACE, name=ds.name) for ds in (inputs or [])],
            outputs=[OutputDataset(namespace=NAMESPACE, name=ds.name) for ds in (outputs or [])],
            producer="dagster-1.9.3"
        )
        
        client.emit(event)
        context.log.info(f"✅ Marquez: START event for {job_name}")
        
        # Store run_id in op context for later use
        return run_id
        
    except Exception as e:
        context.log.warning(f"Failed to emit OpenLineage START event: {e}")
        return None


def emit_complete_event(
    context: HookContext, 
    run_id: Optional[str] = None,
    inputs: List[Dataset] = None,
    outputs: List[Dataset] = None
):
    """Emit COMPLETE event when asset materialization succeeds"""
    try:
        if not run_id:
            run_id = str(uuid.uuid4())
        
        job_name = context.op.name
        
        # Create input datasets
        input_datasets = []
        if inputs:
            for ds in inputs:
                input_datasets.append(InputDataset(
                    namespace=NAMESPACE,
                    name=ds.name,
                    facets=ds.facets if hasattr(ds, 'facets') else {}
                ))
        
        # Create output datasets
        output_datasets = []
        if outputs:
            for ds in outputs:
                output_datasets.append(OutputDataset(
                    namespace=NAMESPACE,
                    name=ds.name,
                    facets=ds.facets if hasattr(ds, 'facets') else {}
                ))
        
        event = RunEvent(
            eventType=RunState.COMPLETE,
            eventTime=datetime.utcnow().isoformat() + "Z",
            run=Run(runId=run_id),
            job=Job(
                namespace=NAMESPACE,
                name=job_name,
                facets={}
            ),
            inputs=input_datasets,
            outputs=output_datasets,
            producer="dagster-1.9.3"
        )
        
        client.emit(event)
        context.log.info(f"✅ Marquez: COMPLETE event for {job_name} ({len(input_datasets)} inputs, {len(output_datasets)} outputs)")
        
    except Exception as e:
        context.log.warning(f"Failed to emit OpenLineage COMPLETE event: {e}")


def emit_fail_event(context: HookContext, run_id: Optional[str] = None, error_message: str = None):
    """Emit FAIL event when asset materialization fails"""
    try:
        if not run_id:
            run_id = str(uuid.uuid4())
        
        job_name = context.op.name
        
        event = RunEvent(
            eventType=RunState.FAIL,
            eventTime=datetime.utcnow().isoformat() + "Z",
            run=Run(runId=run_id),
            job=Job(
                namespace=NAMESPACE,
                name=job_name,
                facets={}
            ),
            inputs=[],
            outputs=[],
            producer="dagster-1.9.3"
        )
        
        client.emit(event)
        context.log.info(f"✅ Marquez: FAIL event sent for {job_name}")
        
    except Exception as e:
        context.log.warning(f"Failed to emit OpenLineage FAIL event: {e}")


def create_postgres_dataset(table_name: str, schema: List[SchemaField] = None) -> Dataset:
    """Create a PostgreSQL dataset descriptor"""
    facets = {
        "dataSource": DataSourceDatasetFacet(
            name="superset",
            uri="postgresql://postgres:5432/superset"
        )
    }
    
    if schema:
        facets["schema"] = SchemaDatasetFacet(fields=schema)
    
    return Dataset(
        namespace="postgres",
        name=f"superset.public.{table_name}",
        facets=facets
    )


def create_minio_dataset(investigation_id: str, data_type: str) -> Dataset:
    """Create a MinIO/S3 dataset descriptor"""
    bucket = "investigations"
    path = f"processed/{investigation_id}/{data_type}"
    
    return Dataset(
        namespace="minio",
        name=f"{bucket}/{path}",
        facets={
            "dataSource": DataSourceDatasetFacet(
                name="minio",
                uri=f"s3://minio:9000/{bucket}"
            )
        }
    )


def create_api_dataset(investigation_id: str) -> Dataset:
    """Create an API dataset descriptor for investigation data source"""
    return Dataset(
        namespace="investigations-api",
        name=f"data_sources.{investigation_id}",
        facets={
            "dataSource": DataSourceDatasetFacet(
                name="investigations-api",
                uri="http://investigations-api:3000"
            )
        }
    )
