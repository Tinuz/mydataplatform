"""
Analytics Assets for Investigation Data

These assets create aggregated views and summaries from processed
investigation data, storing results in PostgreSQL for easy access
from Superset and other BI tools.
"""
from dagster import asset, OpExecutionContext, Output, MetadataValue, success_hook, failure_hook, HookContext
from typing import Dict, Any
import pandas as pd
from datetime import datetime

from .resources import PostgresResource
from .query_helper import InvestigationQueryHelper
from .openlineage_hooks import (
    emit_complete_event,
    emit_fail_event,
    create_postgres_dataset,
    create_minio_dataset,
    Dataset
)
from openlineage.client.facet import SchemaField


def emit_lineage(context, asset_name: str, inputs: list, outputs: list):
    """Helper to emit lineage events without full HookContext"""
    class ContextWrapper:
        def __init__(self, ctx):
            self.op = type('obj', (object,), {'name': asset_name})
            self.log = ctx.log
    
    emit_complete_event(ContextWrapper(context), inputs=inputs, outputs=outputs)


@success_hook
def analytics_success_hook(context: HookContext):
    """Emit OpenLineage COMPLETE event on asset success"""
    asset_name = context.op.name
    
    # Define inputs and outputs based on asset
    inputs = []
    outputs = []
    
    if asset_name == "investigation_daily_summary":
        # Input: Parquet files from MinIO
        inputs = [
            create_minio_dataset("*", "bank_transactions"),
            create_minio_dataset("*", "call_records"),
            create_minio_dataset("*", "messages")
        ]
        # Output: PostgreSQL table
        outputs = [create_postgres_dataset("investigation_daily_summary")]
    
    elif asset_name == "investigation_iban_summary":
        inputs = [create_minio_dataset("*", "bank_transactions")]
        outputs = [create_postgres_dataset("investigation_iban_summary")]
    
    elif asset_name == "investigation_call_network":
        inputs = [create_minio_dataset("*", "call_records")]
    elif asset_name == "investigation_message_network":
        inputs = [create_minio_dataset("*", "messages")]
        outputs = [create_postgres_dataset("investigation_message_network")]
    
    elif asset_name == "investigation_stats_summary":
        # This asset reads from other analytics tables
        inputs = [
            create_postgres_dataset("investigation_daily_summary"),
            create_postgres_dataset("investigation_iban_summary"),
            create_postgres_dataset("investigation_call_network"),
            create_postgres_dataset("investigation_message_network")
        ]
        outputs = [create_postgres_dataset("investigation_stats")]
    
    emit_complete_event(context, inputs=inputs, outputs=outputs)


@failure_hook
def analytics_failure_hook(context: HookContext):
    """Emit OpenLineage FAIL event on asset failure"""
    emit_fail_event(context, error_message=str(context.op_exception) if hasattr(context, 'op_exception') else None)


@asset(
    group_name="investigations_analytics",
    description="Daily transaction and call activity summary per investigation",
    op_tags={"kind": "sql"},
)
def investigation_daily_summary(
    context: OpExecutionContext,
    postgres: PostgresResource
) -> Dict[str, Any]:
    """
    Create daily activity summaries for all active investigations
    
    Aggregates:
    - Transaction counts and amounts per day
    - Call counts and durations per day
    - Combined activity timeline
    
    Stores in: investigation_daily_summary table
    """
    # Get all active investigations
    query = """
        SELECT DISTINCT investigation_id 
        FROM investigations 
        WHERE status = 'active'
    """
    investigations = postgres.execute_query(query)
    
    if not investigations:
        context.log.info("No active investigations found")
        return {'investigations_processed': 0}
    
    total_rows = 0
    
    # Create/truncate summary table
    postgres.execute_update("""
        CREATE TABLE IF NOT EXISTS investigation_daily_summary (
            investigation_id VARCHAR(50),
            activity_date DATE,
            transaction_count INTEGER DEFAULT 0,
            transaction_amount DECIMAL(15,2) DEFAULT 0,
            call_count INTEGER DEFAULT 0,
            call_duration_seconds INTEGER DEFAULT 0,
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (investigation_id, activity_date)
        )
    """)
    
    # Clear existing data (we'll regenerate)
    postgres.execute_update("TRUNCATE TABLE investigation_daily_summary")
    
    with InvestigationQueryHelper() as helper:
        for inv in investigations:
            inv_id = inv['investigation_id']
            
            try:
                # Get daily activity
                daily_df = helper.get_daily_activity(inv_id)
                
                if len(daily_df) == 0:
                    context.log.warning(f"No activity data for {inv_id}")
                    continue
                
                # Insert into PostgreSQL
                for _, row in daily_df.iterrows():
                    postgres.execute_update("""
                        INSERT INTO investigation_daily_summary 
                        (investigation_id, activity_date, transaction_count, 
                         transaction_amount, call_count, call_duration_seconds, message_count)
                        VALUES (%(inv_id)s, %(date)s, %(trans_count)s, 
                                %(trans_amount)s, %(call_count)s, %(call_duration)s, %(msg_count)s)
                        ON CONFLICT (investigation_id, activity_date) 
                        DO UPDATE SET
                            transaction_count = EXCLUDED.transaction_count,
                            transaction_amount = EXCLUDED.transaction_amount,
                            call_count = EXCLUDED.call_count,
                            call_duration_seconds = EXCLUDED.call_duration_seconds,
                            message_count = EXCLUDED.message_count,
                            created_at = NOW()
                    """, {
                        'inv_id': inv_id,
                        'date': row['date'].date() if pd.notna(row['date']) else None,
                        'trans_count': int(row['transaction_count']),
                        'trans_amount': float(row['total_amount']),
                        'call_count': int(row['call_count']),
                        'call_duration': int(row['total_call_duration']),
                        'msg_count': int(row.get('message_count', 0))
                    })
                
                total_rows += len(daily_df)
                context.log.info(f"✅ {inv_id}: {len(daily_df)} days summarized")
                
            except Exception as e:
                context.log.warning(f"⚠️  {inv_id}: {str(e)}")
                continue
    
    # Emit lineage to Marquez
    emit_lineage(
        context,
        "investigation_daily_summary",
        inputs=[
            create_minio_dataset("*", "bank_transactions"),
            create_minio_dataset("*", "call_records"),
            create_minio_dataset("*", "messages")
        ],
        outputs=[create_postgres_dataset("investigation_daily_summary")]
    )
    
    return {
        'investigations_processed': len(investigations),
        'total_summary_rows': total_rows
    }



@asset(
    group_name="investigations_analytics",
    description="IBAN transaction summary per investigation",
    op_tags={"kind": "sql"}
)
def investigation_iban_summary(
    context: OpExecutionContext,
    postgres: PostgresResource
) -> Dict[str, Any]:
    """
    Create IBAN-level transaction summaries
    
    Aggregates:
    - Total transactions per IBAN
    - Debit/credit totals
    - Net amounts
    - Date ranges
    
    Stores in: investigation_iban_summary table
    """
    # Get all active investigations
    query = """
        SELECT DISTINCT investigation_id 
        FROM investigations 
        WHERE status = 'active'
    """
    investigations = postgres.execute_query(query)
    
    if not investigations:
        context.log.info("No active investigations found")
        return {'investigations_processed': 0}
    
    total_rows = 0
    
    # Create/truncate summary table
    postgres.execute_update("""
        CREATE TABLE IF NOT EXISTS investigation_iban_summary (
            investigation_id VARCHAR(50),
            iban VARCHAR(34),
            total_transactions INTEGER,
            total_debit DECIMAL(15,2),
            total_credit DECIMAL(15,2),
            net_amount DECIMAL(15,2),
            first_transaction DATE,
            last_transaction DATE,
            active_days INTEGER,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (investigation_id, iban)
        )
    """)
    
    postgres.execute_update("TRUNCATE TABLE investigation_iban_summary")
    
    with InvestigationQueryHelper() as helper:
        for inv in investigations:
            inv_id = inv['investigation_id']
            
            try:
                # Get transaction summary
                summary_df = helper.get_transaction_summary(inv_id)
                
                if len(summary_df) == 0:
                    context.log.warning(f"No transactions for {inv_id}")
                    continue
                
                # Insert into PostgreSQL
                for _, row in summary_df.iterrows():
                    postgres.execute_update("""
                        INSERT INTO investigation_iban_summary 
                        (investigation_id, iban, total_transactions, total_debit,
                         total_credit, net_amount, first_transaction, last_transaction,
                         active_days)
                        VALUES (%(inv_id)s, %(iban)s, %(total_trans)s, %(debit)s,
                                %(credit)s, %(net)s, %(first_date)s, %(last_date)s,
                                %(active_days)s)
                        ON CONFLICT (investigation_id, iban) 
                        DO UPDATE SET
                            total_transactions = EXCLUDED.total_transactions,
                            total_debit = EXCLUDED.total_debit,
                            total_credit = EXCLUDED.total_credit,
                            net_amount = EXCLUDED.net_amount,
                            first_transaction = EXCLUDED.first_transaction,
                            last_transaction = EXCLUDED.last_transaction,
                            active_days = EXCLUDED.active_days,
                            created_at = NOW()
                    """, {
                        'inv_id': inv_id,
                        'iban': str(row['iban']),
                        'total_trans': int(row['total_transactions']),
                        'debit': float(row['total_debit']),
                        'credit': float(row['total_credit']),
                        'net': float(row['net_amount']),
                        'first_date': row['first_transaction'].date() if pd.notna(row['first_transaction']) else None,
                        'last_date': row['last_transaction'].date() if pd.notna(row['last_transaction']) else None,
                        'active_days': int(row['active_days'])
                    })
                
                total_rows += len(summary_df)
                context.log.info(f"✅ {inv_id}: {len(summary_df)} IBANs summarized")
                
            except Exception as e:
                context.log.warning(f"⚠️  {inv_id}: {str(e)}")
                continue
    
    # Emit lineage to Marquez
    emit_lineage(
        context,
        "investigation_iban_summary",
        inputs=[create_minio_dataset("*", "bank_transactions")],
        outputs=[create_postgres_dataset("investigation_iban_summary")]
    )
    
    return {
        'investigations_processed': len(investigations),
        'total_ibans': total_rows
    }


@asset(
    group_name="investigations_analytics",
    description="Call network relationships per investigation",
    op_tags={"kind": "sql"}
)
def investigation_call_network(
    context: OpExecutionContext,
    postgres: PostgresResource
) -> Dict[str, Any]:
    """
    Create call network analysis
    
    Aggregates:
    - Caller-callee relationships
    - Call counts and durations
    - Temporal patterns
    
    Stores in: investigation_call_network table
    """
    # Get all active investigations
    query = """
        SELECT DISTINCT investigation_id 
        FROM investigations 
        WHERE status = 'active'
    """
    investigations = postgres.execute_query(query)
    
    if not investigations:
        context.log.info("No active investigations found")
        return {'investigations_processed': 0}
    
    total_rows = 0
    
    # Create/truncate summary table
    postgres.execute_update("""
        CREATE TABLE IF NOT EXISTS investigation_call_network (
            investigation_id VARCHAR(50),
            caller VARCHAR(20),
            callee VARCHAR(20),
            call_count INTEGER,
            total_duration_seconds INTEGER,
            avg_duration_seconds DECIMAL(10,2),
            first_call TIMESTAMP,
            last_call TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (investigation_id, caller, callee)
        )
    """)
    
    postgres.execute_update("TRUNCATE TABLE investigation_call_network")
    
    with InvestigationQueryHelper() as helper:
        for inv in investigations:
            inv_id = inv['investigation_id']
            
            try:
                # Get call network
                network_df = helper.get_call_network(inv_id)
                
                if len(network_df) == 0:
                    context.log.warning(f"No calls for {inv_id}")
                    continue
                
                # Insert into PostgreSQL
                for _, row in network_df.iterrows():
                    postgres.execute_update("""
                        INSERT INTO investigation_call_network 
                        (investigation_id, caller, callee, call_count,
                         total_duration_seconds, avg_duration_seconds,
                         first_call, last_call)
                        VALUES (%(inv_id)s, %(caller)s, %(callee)s, %(count)s,
                                %(total_dur)s, %(avg_dur)s, %(first)s, %(last)s)
                        ON CONFLICT (investigation_id, caller, callee) 
                        DO UPDATE SET
                            call_count = EXCLUDED.call_count,
                            total_duration_seconds = EXCLUDED.total_duration_seconds,
                            avg_duration_seconds = EXCLUDED.avg_duration_seconds,
                            first_call = EXCLUDED.first_call,
                            last_call = EXCLUDED.last_call,
                            created_at = NOW()
                    """, {
                        'inv_id': inv_id,
                        'caller': str(row['caller']),
                        'callee': str(row['callee']),
                        'count': int(row['call_count']),
                        'total_dur': int(row['total_duration_seconds']),
                        'avg_dur': float(row['avg_duration_seconds']),
                        'first': row['first_call'],
                        'last': row['last_call']
                    })
                
                total_rows += len(network_df)
                context.log.info(f"✅ {inv_id}: {len(network_df)} call relationships")
                
            except Exception as e:
                context.log.warning(f"⚠️  {inv_id}: {str(e)}")
                continue
    
    # Emit lineage to Marquez
    emit_lineage(
        context,
        "investigation_call_network",
        inputs=[create_minio_dataset("*", "call_records")],
        outputs=[create_postgres_dataset("investigation_call_network")]
    )
    
    return {
        'investigations_processed': len(investigations),
        'total_relationships': total_rows
    }


@asset(
    group_name="investigations_analytics",
    description="SMS/Message communication network analysis",
    op_tags={"kind": "sql"}
)
def investigation_message_network(
    context: OpExecutionContext,
    postgres: PostgresResource
) -> Dict[str, Any]:
    """
    Create SMS/message network analysis
    
    For each sender-recipient pair:
    - Total message count
    - First and last message timestamps
    
    Stores in: investigation_message_network table
    """
    # Get all active investigations
    query = """
        SELECT DISTINCT investigation_id 
        FROM investigations 
        WHERE status = 'active'
    """
    investigations = postgres.execute_query(query)
    
    if not investigations:
        context.log.info("No active investigations found")
        return {'investigations_processed': 0}
    
    total_rows = 0
    
    # Create table
    postgres.execute_update("""
        CREATE TABLE IF NOT EXISTS investigation_message_network (
            investigation_id VARCHAR(50),
            sender VARCHAR(50),
            recipient VARCHAR(50),
            message_count INTEGER,
            first_message TIMESTAMP,
            last_message TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            PRIMARY KEY (investigation_id, sender, recipient)
        )
    """)
    
    postgres.execute_update("TRUNCATE TABLE investigation_message_network")
    
    with InvestigationQueryHelper() as helper:
        for inv in investigations:
            inv_id = inv['investigation_id']
            
            try:
                # Get message network
                network_df = helper.get_message_network(inv_id)
                
                if len(network_df) == 0:
                    context.log.warning(f"No messages for {inv_id}")
                    continue
                
                # Insert into PostgreSQL
                for _, row in network_df.iterrows():
                    postgres.execute_update("""
                        INSERT INTO investigation_message_network 
                        (investigation_id, sender, recipient, message_count,
                         first_message, last_message)
                        VALUES (%(inv_id)s, %(sender)s, %(recipient)s, %(count)s,
                                %(first)s, %(last)s)
                        ON CONFLICT (investigation_id, sender, recipient) 
                        DO UPDATE SET
                            message_count = EXCLUDED.message_count,
                            first_message = EXCLUDED.first_message,
                            last_message = EXCLUDED.last_message,
                            created_at = NOW()
                    """, {
                        'inv_id': inv_id,
                        'sender': str(row['sender']),
                        'recipient': str(row['recipient']),
                        'count': int(row['message_count']),
                        'first': row['first_message'],
                        'last': row['last_message']
                    })
                
                total_rows += len(network_df)
                context.log.info(f"✅ {inv_id}: {len(network_df)} message relationships")
                
            except ValueError as e:
                # No message data for this investigation
                context.log.info(f"ℹ️  {inv_id}: No message data")
                continue
            except Exception as e:
                context.log.warning(f"⚠️  {inv_id}: {str(e)}")
                continue
    
    # Emit lineage to Marquez
    emit_lineage(
        context,
        "investigation_message_network",
        inputs=[create_minio_dataset("*", "messages")],
        outputs=[create_postgres_dataset("investigation_message_network")]
    )
    
    return {
        'investigations_processed': len(investigations),
        'total_relationships': total_rows
    }


@asset(
    group_name="investigations_analytics",
    description="High-level investigation statistics",
    deps=[investigation_daily_summary, investigation_iban_summary, investigation_call_network, investigation_message_network],
    op_tags={"kind": "sql"}
)
def investigation_stats_summary(
    context: OpExecutionContext,
    postgres: PostgresResource
) -> Dict[str, Any]:
    """
    Create high-level investigation statistics
    
    Aggregates from:
    - Daily summaries
    - IBAN summaries
    - Call networks
    - Message networks
    
    Stores in: investigation_stats table
    """
    # Get all active investigations
    query = """
        SELECT investigation_id, name, created_at
        FROM investigations 
        WHERE status = 'active'
    """
    investigations = postgres.execute_query(query)
    
    if not investigations:
        context.log.info("No active investigations found")
        return {'investigations_processed': 0}
    
    # Create stats table
    postgres.execute_update("""
        CREATE TABLE IF NOT EXISTS investigation_stats (
            investigation_id VARCHAR(50) PRIMARY KEY,
            investigation_name VARCHAR(200),
            total_transactions INTEGER DEFAULT 0,
            total_transaction_amount DECIMAL(15,2) DEFAULT 0,
            unique_ibans INTEGER DEFAULT 0,
            total_calls INTEGER DEFAULT 0,
            total_call_duration_hours DECIMAL(10,2) DEFAULT 0,
            unique_phone_numbers INTEGER DEFAULT 0,
            total_messages INTEGER DEFAULT 0,
            unique_message_participants INTEGER DEFAULT 0,
            first_activity_date DATE,
            last_activity_date DATE,
            active_days INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    
    for inv in investigations:
        inv_id = inv['investigation_id']
        inv_name = inv['name']
        
        # Get transaction stats
        trans_stats = postgres.execute_query("""
            SELECT 
                COALESCE(SUM(transaction_count), 0) as total_transactions,
                COALESCE(SUM(transaction_amount), 0) as total_amount,
                MIN(activity_date) as first_date,
                MAX(activity_date) as last_date,
                COUNT(DISTINCT activity_date) as active_days
            FROM investigation_daily_summary
            WHERE investigation_id = %(inv_id)s
        """, {'inv_id': inv_id})
        
        # Get IBAN stats
        iban_stats = postgres.execute_query("""
            SELECT COUNT(DISTINCT iban) as unique_ibans
            FROM investigation_iban_summary
            WHERE investigation_id = %(inv_id)s
        """, {'inv_id': inv_id})
        
        # Get call stats
        call_stats = postgres.execute_query("""
            SELECT 
                COALESCE(SUM(call_count), 0) as total_calls,
                COALESCE(SUM(total_duration_seconds), 0) as total_duration
            FROM investigation_call_network
            WHERE investigation_id = %(inv_id)s
        """, {'inv_id': inv_id})
        
        # Get unique phone numbers
        phone_stats = postgres.execute_query("""
            SELECT COUNT(DISTINCT phone) as unique_phones
            FROM (
                SELECT DISTINCT caller as phone FROM investigation_call_network WHERE investigation_id = %(inv_id)s
                UNION
                SELECT DISTINCT callee as phone FROM investigation_call_network WHERE investigation_id = %(inv_id)s
            ) phones
        """, {'inv_id': inv_id})
        
        # Get message stats
        message_stats = postgres.execute_query("""
            SELECT 
                COALESCE(SUM(message_count), 0) as total_messages
            FROM investigation_message_network
            WHERE investigation_id = %(inv_id)s
        """, {'inv_id': inv_id})
        
        # Get unique message participants (senders + recipients)
        message_participant_stats = postgres.execute_query("""
            SELECT COUNT(DISTINCT participant) as unique_participants
            FROM (
                SELECT DISTINCT sender as participant FROM investigation_message_network WHERE investigation_id = %(inv_id)s
                UNION
                SELECT DISTINCT recipient as participant FROM investigation_message_network WHERE investigation_id = %(inv_id)s
            ) participants
        """, {'inv_id': inv_id})
        
        # Combine stats
        trans = trans_stats[0] if trans_stats else {}
        ibans = iban_stats[0] if iban_stats else {}
        calls = call_stats[0] if call_stats else {}
        phones = phone_stats[0] if phone_stats else {}
        messages = message_stats[0] if message_stats else {}
        message_participants = message_participant_stats[0] if message_participant_stats else {}
        
        # Insert/update
        postgres.execute_update("""
            INSERT INTO investigation_stats 
            (investigation_id, investigation_name, total_transactions, total_transaction_amount,
             unique_ibans, total_calls, total_call_duration_hours, unique_phone_numbers,
             total_messages, unique_message_participants,
             first_activity_date, last_activity_date, active_days)
            VALUES (%(inv_id)s, %(name)s, %(trans)s, %(amount)s, %(ibans)s, %(calls)s, 
                    %(hours)s, %(phones)s, %(messages)s, %(msg_participants)s,
                    %(first)s, %(last)s, %(days)s)
            ON CONFLICT (investigation_id) 
            DO UPDATE SET
                investigation_name = EXCLUDED.investigation_name,
                total_transactions = EXCLUDED.total_transactions,
                total_transaction_amount = EXCLUDED.total_transaction_amount,
                unique_ibans = EXCLUDED.unique_ibans,
                total_calls = EXCLUDED.total_calls,
                total_call_duration_hours = EXCLUDED.total_call_duration_hours,
                unique_phone_numbers = EXCLUDED.unique_phone_numbers,
                total_messages = EXCLUDED.total_messages,
                unique_message_participants = EXCLUDED.unique_message_participants,
                first_activity_date = EXCLUDED.first_activity_date,
                last_activity_date = EXCLUDED.last_activity_date,
                active_days = EXCLUDED.active_days,
                updated_at = NOW()
        """, {
            'inv_id': inv_id,
            'name': inv_name,
            'trans': trans.get('total_transactions', 0),
            'amount': trans.get('total_amount', 0),
            'ibans': ibans.get('unique_ibans', 0),
            'calls': calls.get('total_calls', 0),
            'hours': float(calls.get('total_duration', 0)) / 3600,
            'phones': phones.get('unique_phones', 0),
            'messages': messages.get('total_messages', 0),
            'msg_participants': message_participants.get('unique_participants', 0),
            'first': trans.get('first_date'),
            'last': trans.get('last_date'),
            'days': trans.get('active_days', 0)
        })
        
        context.log.info(f"✅ {inv_id}: Stats updated")
    
    # Emit lineage to Marquez
    emit_lineage(
        context,
        "investigation_stats_summary",
        inputs=[
            create_postgres_dataset("investigation_daily_summary"),
            create_postgres_dataset("investigation_iban_summary"),
            create_postgres_dataset("investigation_call_network"),
            create_postgres_dataset("investigation_message_network")
        ],
        outputs=[create_postgres_dataset("investigation_stats")]
    )
    
    return {
        'investigations_processed': len(investigations)
    }

