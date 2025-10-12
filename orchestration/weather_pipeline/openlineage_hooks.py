"""
OpenLineage integration for Dagster
Emits lineage events to Marquez
"""

import os
from typing import Any, Optional
from dagster import (
    op_hook,
    failure_hook,
    success_hook,
    OpExecutionContext,
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
    NominalTimeRunFacet,
    ParentRunFacet,
    JobFacet,
    DataSourceDatasetFacet,
    SchemaDatasetFacet,
    SchemaField
)
from datetime import datetime
import uuid

# Marquez configuration
MARQUEZ_URL = os.getenv("MARQUEZ_URL", "http://marquez:5000")
NAMESPACE = os.getenv("OPENLINEAGE_NAMESPACE", "weather-pipeline")

# Initialize OpenLineage client
client = OpenLineageClient(url=MARQUEZ_URL)


def emit_start_event(context: HookContext):
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
            inputs=[],
            outputs=[],
            producer="dagster-1.9.3"
        )
        
        client.emit(event)
        context.log.info(f"✅ OpenLineage START event sent to Marquez: {job_name}")
        
        # Store run_id in context for later use
        return run_id
        
    except Exception as e:
        context.log.warning(f"Failed to emit OpenLineage START event: {e}")
        return None


def emit_complete_event(context: HookContext, run_id: Optional[str] = None):
    """Emit COMPLETE event when asset materialization succeeds"""
    try:
        if not run_id:
            run_id = str(uuid.uuid4())
        
        job_name = context.op.name
        
        # Determine outputs based on asset name
        outputs = []
        if "raw_weather_data" in job_name:
            outputs.append(OutputDataset(
                namespace="minio",
                name="bronze/weather",
                facets={
                    "dataSource": DataSourceDatasetFacet(
                        name="MinIO",
                        uri="s3://lake/bronze/weather"
                    )
                }
            ))
        elif "clean_weather_data" in job_name:
            outputs.append(OutputDataset(
                namespace="minio",
                name="silver/weather",
                facets={
                    "dataSource": DataSourceDatasetFacet(
                        name="MinIO",
                        uri="s3://lake/silver/weather"
                    )
                }
            ))
        elif "weather_to_postgres" in job_name:
            outputs.append(OutputDataset(
                namespace="postgres",
                name="weather.observations",
                facets={
                    "dataSource": DataSourceDatasetFacet(
                        name="PostgreSQL",
                        uri="postgresql://postgres:5432/superset"
                    ),
                    "schema": SchemaDatasetFacet(
                        fields=[
                            SchemaField(name="station_name", type="VARCHAR(100)"),
                            SchemaField(name="timestamp", type="TIMESTAMP"),
                            SchemaField(name="temperature", type="FLOAT"),
                            SchemaField(name="humidity", type="INTEGER"),
                            SchemaField(name="wind_speed", type="FLOAT"),
                        ]
                    )
                }
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
            inputs=[],
            outputs=outputs,
            producer="dagster-1.9.3"
        )
        
        client.emit(event)
        context.log.info(f"✅ OpenLineage COMPLETE event sent to Marquez: {job_name}")
        
    except Exception as e:
        context.log.warning(f"Failed to emit OpenLineage COMPLETE event: {e}")


def emit_fail_event(context: HookContext, run_id: Optional[str] = None):
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
        context.log.info(f"✅ OpenLineage FAIL event sent to Marquez: {job_name}")
        
    except Exception as e:
        context.log.warning(f"Failed to emit OpenLineage FAIL event: {e}")


@success_hook
def openlineage_success_hook(context: HookContext):
    """Hook that runs on successful asset materialization"""
    emit_complete_event(context)


@failure_hook
def openlineage_failure_hook(context: HookContext):
    """Hook that runs on failed asset materialization"""
    emit_fail_event(context)
