"""
Dagster sensors for investigations

Monitors for new file uploads and triggers processing
"""

from dagster import (
    sensor, 
    RunRequest, 
    SkipReason, 
    SensorEvaluationContext,
    AssetMaterialization,
    asset_sensor,
    AssetKey,
    EventLogEntry,
    DefaultSensorStatus
)
from .resources import PostgresResource
from .jobs import process_all_pending_job, canonical_mapping_job, staging_models_job, analytical_models_job
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


@sensor(
    name="check_canonical_data_sensor",
    description="Monitors for unmapped raw data and automatically triggers canonical mapping",
    minimum_interval_seconds=60,  # Check every minute
    default_status=DefaultSensorStatus.RUNNING,  # Explicitly enable
    job=canonical_mapping_job  # Auto-trigger this job when unmapped data found
)
def check_canonical_data_sensor(context: SensorEvaluationContext):
    """
    Sensor that monitors for unmapped raw data and automatically triggers mapping:
    - New raw_transactions not in canonical → trigger canonical_transactions asset
    - New raw_calls/messages not in canonical → trigger canonical_communications asset
    
    Automatically materializes canonical assets when unmapped data is detected.
    """
    try:
        # Use PostgresResource to check unmapped data
        postgres = PostgresResource()
        
        # Count unmapped transactions using execute_query for proper dict cursor
        # Only count transactions that haven't been attempted yet (no entry in canonical at all)
        # This prevents re-triggering for failed mappings
        result = postgres.execute_query("""
            SELECT COUNT(*) as unmapped_count
            FROM raw_transactions r
            WHERE NOT EXISTS (
                SELECT 1 FROM canonical.canonical_transaction c 
                WHERE c.source_system_id = r.source_id 
                AND c.source_record_id = r.transaction_id::text
            )
        """)
        unmapped_transactions = result[0]['unmapped_count'] if result else 0
        
        # Count unmapped communications (calls)
        result = postgres.execute_query("""
            SELECT 
                COALESCE(COUNT(DISTINCT r.call_id), 0) as unmapped_calls
            FROM raw_calls r
            WHERE NOT EXISTS (
                SELECT 1 FROM canonical.canonical_communication c
                WHERE c.source_system_id = r.source_id
                AND c.source_record_id = r.call_id::text
            )
        """)
        unmapped_calls = result[0]['unmapped_calls'] if result else 0
        
        # Count unmapped communications (messages)
        result = postgres.execute_query("""
            SELECT 
                COALESCE(COUNT(DISTINCT m.message_id), 0) as unmapped_messages
            FROM raw_messages m
            WHERE NOT EXISTS (
                SELECT 1 FROM canonical.canonical_communication c
                WHERE c.source_system_id = m.source_id
                AND c.source_record_id = m.message_id::text
            )
        """)
        unmapped_messages = result[0]['unmapped_messages'] if result else 0
        unmapped_communications = unmapped_calls + unmapped_messages
        
        # Check if there's anything to map
        if unmapped_transactions == 0 and unmapped_communications == 0:
            return SkipReason("✅ All raw data is canonical - nothing to map!")
        
        # Log detection and AUTO-TRIGGER canonical mapping!
        context.log.info(f"🔍 Found unmapped raw data:")
        if unmapped_transactions > 0:
            context.log.info(f"   📊 {unmapped_transactions} transactions need canonical mapping")
        if unmapped_communications > 0:
            context.log.info(f"   📞 {unmapped_communications} communications need canonical mapping ({unmapped_calls} calls, {unmapped_messages} messages)")
        
        context.log.info(f"🤖 AUTO-TRIGGERING canonical mapping job...")
        
        # Trigger the canonical_mapping_job to materialize canonical assets
        return RunRequest(
            run_key=f"canonical_mapping_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            tags={
                "sensor": "check_canonical_data_sensor",
                "unmapped_transactions": str(unmapped_transactions),
                "unmapped_communications": str(unmapped_communications),
                "automated": "true"
            }
        )
        
    except Exception as e:
        context.log.error(f"❌ Error in canonical data sensor: {e}")
        import traceback
        context.log.error(f"Traceback: {traceback.format_exc()}")
        return SkipReason(f"Sensor error: {str(e)}")


@sensor(
    name="check_staging_data_sensor",
    description="Monitors for new canonical data and automatically triggers dbt staging models",
    minimum_interval_seconds=120,  # Check every 2 minutes (slower than canonical)
    default_status=DefaultSensorStatus.RUNNING,
    job=staging_models_job
)
def check_staging_data_sensor(context: SensorEvaluationContext):
    """
    Sensor that checks for new canonical data that needs staging transformation.
    
    Monitors:
    - canonical.canonical_transaction (for new transactions)
    - canonical.canonical_communication (for new communications)
    
    Triggers staging_models_job when new canonical data is detected.
    
    Strategy: Track last processed timestamp to detect new records
    """
    try:
        postgres = PostgresResource(
            host="postgres",
            port=5432,
            database="superset",
            user="superset",
            password="superset"
        )
        
        # Get last staging build time from cursor (stored in sensor context)
        cursor_data = context.cursor or None
        last_check_time = cursor_data if cursor_data else '1970-01-01 00:00:00'
        
        context.log.info(f"🔍 Checking for canonical data newer than: {last_check_time}")
        
        # Check for new canonical transactions
        result = postgres.execute_query(f"""
            SELECT COUNT(*) as new_count, MAX(created_at) as latest_time
            FROM canonical.canonical_transaction
            WHERE created_at > '{last_check_time}'
            AND validation_status IN ('valid', 'warning')
        """)
        new_transactions = result[0]['new_count'] if result else 0
        latest_transaction_time = result[0]['latest_time'] if result and result[0]['latest_time'] else None
        
        # Check for new canonical communications
        result = postgres.execute_query(f"""
            SELECT COUNT(*) as new_count, MAX(created_at) as latest_time
            FROM canonical.canonical_communication
            WHERE created_at > '{last_check_time}'
            AND validation_status IN ('valid', 'warning')
        """)
        new_communications = result[0]['new_count'] if result else 0
        latest_communication_time = result[0]['latest_time'] if result and result[0]['latest_time'] else None
        
        # Determine the latest timestamp for cursor update (convert all to strings)
        latest_time = last_check_time
        if latest_transaction_time:
            latest_transaction_str = str(latest_transaction_time)
            if latest_transaction_str > latest_time:
                latest_time = latest_transaction_str
        if latest_communication_time:
            latest_communication_str = str(latest_communication_time)
            if latest_communication_str > latest_time:
                latest_time = latest_communication_str
        
        total_new = new_transactions + new_communications
        
        if total_new > 0:
            context.log.info(f"🔍 Found new canonical data:")
            context.log.info(f"   📊 {new_transactions} new transactions")
            context.log.info(f"   📞 {new_communications} new communications")
            context.log.info(f"🤖 AUTO-TRIGGERING dbt staging models job...")
            
            # Update cursor to latest processed time
            context.update_cursor(latest_time)
            
            return RunRequest(
                run_key=f"staging_build_{latest_time.replace(' ', '_').replace(':', '-')}",
                tags={
                    "sensor": "check_staging_data_sensor",
                    "new_transactions": str(new_transactions),
                    "new_communications": str(new_communications),
                    "automated": "true",
                    "data_timestamp": latest_time
                }
            )
        else:
            context.log.info(f"✅ No new canonical data since {last_check_time}")
            return SkipReason(f"✅ All canonical data is already in staging - no new data to transform")
            
    except Exception as e:
        context.log.error(f"❌ Error in staging data sensor: {e}")
        import traceback
        context.log.error(f"Traceback: {traceback.format_exc()}")
        return SkipReason(f"Sensor error: {str(e)}")


@sensor(
    name="check_analytical_data_sensor",
    description="Monitors for new staging data and automatically triggers dbt analytical models (dimensions and facts)",
    minimum_interval_seconds=180,  # Check every 3 minutes (slower than staging)
    default_status=DefaultSensorStatus.RUNNING,
    job=analytical_models_job
)
def check_analytical_data_sensor(context: SensorEvaluationContext):
    """
    Sensor that checks for new staging data that needs analytical transformation.
    
    Monitors:
    - staging.stg_bank_transactions (for dim_bank_account and fact_transaction)
    - staging.stg_telecom_calls (for dim_phone_number and fact_call)
    - staging.stg_telecom_messages (for fact_message)
    
    Triggers analytical_models_job when new staging data is detected.
    
    Strategy: Check if staging views have data that isn't in analytical tables yet
    """
    try:
        postgres = PostgresResource(
            host="postgres",
            port=5432,
            database="superset",
            user="superset",
            password="superset"
        )
        
        # Get last analytical build time from cursor
        cursor_data = context.cursor or None
        last_check_time = cursor_data if cursor_data else '1970-01-01 00:00:00'
        
        context.log.info(f"🔍 Checking for staging data newer than: {last_check_time}")
        
        # Check for new staging transactions (compare staging vs fact_transaction)
        # Note: staging views don't have created_at, so we check if row counts differ
        result = postgres.execute_query("""
            WITH staging_count AS (
                SELECT COUNT(*) as count FROM staging.stg_bank_transactions
            ),
            fact_count AS (
                SELECT COUNT(*) as count FROM canonical.fact_transaction
            )
            SELECT 
                staging_count.count as staging_count,
                fact_count.count as fact_count,
                (staging_count.count - fact_count.count) as new_count
            FROM staging_count, fact_count
        """)
        
        new_transactions = result[0]['new_count'] if result and result[0]['new_count'] > 0 else 0
        staging_transaction_count = result[0]['staging_count'] if result else 0
        fact_transaction_count = result[0]['fact_count'] if result else 0
        
        # Check for new staging calls
        result = postgres.execute_query("""
            WITH staging_count AS (
                SELECT COUNT(*) as count FROM staging.stg_telecom_calls
            ),
            fact_count AS (
                SELECT COUNT(*) as count FROM canonical.fact_call
            )
            SELECT 
                staging_count.count as staging_count,
                fact_count.count as fact_count,
                (staging_count.count - fact_count.count) as new_count
            FROM staging_count, fact_count
        """)
        
        new_calls = result[0]['new_count'] if result and result[0]['new_count'] > 0 else 0
        staging_call_count = result[0]['staging_count'] if result else 0
        fact_call_count = result[0]['fact_count'] if result else 0
        
        # Check for new staging messages
        result = postgres.execute_query("""
            WITH staging_count AS (
                SELECT COUNT(*) as count FROM staging.stg_telecom_messages
            ),
            fact_count AS (
                SELECT COUNT(*) as count FROM canonical.fact_message
            )
            SELECT 
                staging_count.count as staging_count,
                fact_count.count as fact_count,
                (staging_count.count - fact_count.count) as new_count
            FROM staging_count, fact_count
        """)
        
        new_messages = result[0]['new_count'] if result and result[0]['new_count'] > 0 else 0
        staging_message_count = result[0]['staging_count'] if result else 0
        fact_message_count = result[0]['fact_count'] if result else 0
        
        total_new = new_transactions + new_calls + new_messages
        
        if total_new > 0:
            context.log.info(f"🔍 Found new staging data:")
            context.log.info(f"   📊 {new_transactions} new transactions ({staging_transaction_count} staging vs {fact_transaction_count} fact)")
            context.log.info(f"   📞 {new_calls} new calls ({staging_call_count} staging vs {fact_call_count} fact)")
            context.log.info(f"   💬 {new_messages} new messages ({staging_message_count} staging vs {fact_message_count} fact)")
            context.log.info(f"🤖 AUTO-TRIGGERING dbt analytical models job...")
            
            # Update cursor with current timestamp
            from datetime import datetime
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            context.update_cursor(current_time)
            
            return RunRequest(
                run_key=f"analytical_build_{current_time.replace(' ', '_').replace(':', '-')}",
                tags={
                    "sensor": "check_analytical_data_sensor",
                    "new_transactions": str(new_transactions),
                    "new_calls": str(new_calls),
                    "new_messages": str(new_messages),
                    "automated": "true",
                    "build_timestamp": current_time
                }
            )
        else:
            context.log.info(f"✅ All staging data is in analytical layer:")
            context.log.info(f"   📊 Transactions: {staging_transaction_count} staging = {fact_transaction_count} fact")
            context.log.info(f"   📞 Calls: {staging_call_count} staging = {fact_call_count} fact")
            context.log.info(f"   💬 Messages: {staging_message_count} staging = {fact_message_count} fact")
            return SkipReason(f"✅ All staging data is in analytical layer - no new data to transform")
            
    except Exception as e:
        context.log.error(f"❌ Error in analytical data sensor: {e}")
        import traceback
        context.log.error(f"Traceback: {traceback.format_exc()}")
        return SkipReason(f"Sensor error: {str(e)}")
