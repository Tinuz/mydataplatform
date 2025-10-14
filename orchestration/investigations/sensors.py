"""
Dagster sensors for investigations

Monitors for new file uploads and triggers processing
"""

from dagster import sensor, RunRequest, SkipReason, SensorEvaluationContext
from .resources import PostgresResource
from .jobs import process_all_pending_job
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


@sensor(
    name="file_upload_sensor",
    description="Detects new file uploads and triggers processing",
    minimum_interval_seconds=30,  # Check every 30 seconds
    job=process_all_pending_job
)
def file_upload_sensor(context: SensorEvaluationContext):
    """
    Sensor that watches for files with pending status
    
    Triggers appropriate job based on file type
    """
    # Get pending files from database
    postgres = PostgresResource()
    
    try:
        pending_sources = postgres.get_pending_sources()
        
        if not pending_sources:
            return SkipReason("No pending files found")
        
        context.log.info(f"Found {len(pending_sources)} pending files")
        
        # Group files by investigation for batch processing
        investigations_with_pending = {}
        for source in pending_sources:
            inv_id = source['investigation_id']
            if inv_id not in investigations_with_pending:
                investigations_with_pending[inv_id] = []
            investigations_with_pending[inv_id].append(source)
        
        # Yield run requests
        run_timestamp = datetime.now().isoformat()
        for inv_id, sources in investigations_with_pending.items():
            # Trigger processing job for this investigation
            yield RunRequest(
                run_key=f"process_{inv_id}_{len(sources)}_{run_timestamp}",
                run_config={
                    "ops": {
                        "detect_pending_files": {
                            "config": {
                                "investigation_id": inv_id
                            }
                        }
                    }
                },
                tags={
                    "investigation_id": inv_id,
                    "file_count": str(len(sources)),
                    "sensor": "file_upload_sensor",
                    "run_timestamp": run_timestamp
                }
            )
            
            context.log.info(f"Triggered processing for {inv_id} ({len(sources)} files)")
        
        # Update cursor to track progress
        context.update_cursor(run_timestamp)
        
    except Exception as e:
        context.log.error(f"Error in file_upload_sensor: {e}")
        return SkipReason(f"Sensor error: {str(e)}")
