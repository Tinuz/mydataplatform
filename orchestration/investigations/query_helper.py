"""
DuckDB Query Helper for Investigation Data

This module provides utilities to query Parquet files stored in MinIO
using DuckDB. Files are downloaded from MinIO and queried locally.
"""
import duckdb
import pandas as pd
import io
from typing import Optional, Dict, Any, List
from datetime import datetime
from minio import Minio


class InvestigationQueryHelper:
    """
    Helper class to query investigation Parquet data via DuckDB
    
    Features:
    - Downloads Parquet files from MinIO
    - SQL query execution via DuckDB
    - Predefined analysis queries
    - pandas DataFrame output
    """
    
    def __init__(
        self,
        minio_endpoint: str = "minio:9000",
        minio_access_key: str = "minio",
        minio_secret_key: str = "minio12345",
        bucket: str = "investigations"
    ):
        """Initialize DuckDB connection and MinIO client"""
        self.bucket = bucket
        self.minio_endpoint = minio_endpoint
        self.conn = duckdb.connect(':memory:')
        
        # Initialize MinIO client
        self.minio_client = Minio(
            minio_endpoint,
            access_key=minio_access_key,
            secret_key=minio_secret_key,
            secure=False
        )
        
        # Cache for downloaded data
        self._data_cache: Dict[str, pd.DataFrame] = {}
    
    def _load_parquet_files(self, prefix: str) -> pd.DataFrame:
        """
        Download and load all Parquet files from MinIO with given prefix
        
        Args:
            prefix: S3 prefix path (e.g., 'OND-2025-000002/processed/transactions/')
            
        Returns:
            Combined DataFrame from all Parquet files
        """
        # Check cache first
        if prefix in self._data_cache:
            return self._data_cache[prefix]
        
        # List all objects with prefix
        objects = self.minio_client.list_objects(self.bucket, prefix=prefix, recursive=True)
        
        dataframes = []
        for obj in objects:
            # Only process .parquet files
            if obj.object_name.endswith('.parquet'):
                # Download the file
                response = self.minio_client.get_object(self.bucket, obj.object_name)
                # Read parquet from bytes
                df = pd.read_parquet(io.BytesIO(response.read()))
                dataframes.append(df)
                response.close()
                response.release_conn()
        
        if not dataframes:
            raise ValueError(f"No Parquet files found at prefix: {prefix}")
        
        # Combine all dataframes
        combined_df = pd.concat(dataframes, ignore_index=True)
        
        # Cache the result
        self._data_cache[prefix] = combined_df
        
        return combined_df
    
    def query(self, sql: str, data_sources: Optional[Dict[str, pd.DataFrame]] = None) -> pd.DataFrame:
        """
        Execute arbitrary SQL query
        
        Args:
            sql: SQL query string (can reference dataframe names)
            data_sources: Optional dict of dataframe name -> DataFrame
            
        Returns:
            pandas DataFrame with results
        """
        try:
            # Register data sources as temp tables
            if data_sources:
                for name, df in data_sources.items():
                    self.conn.register(name, df)
            
            result = self.conn.execute(sql).fetchdf()
            return result
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")
    
    def get_transactions(
        self,
        investigation_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        min_amount: Optional[float] = None,
        iban: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get bank transactions for an investigation
        
        Args:
            investigation_id: Investigation ID (e.g., 'OND-2025-000002')
            start_date: Filter by date >= this (ISO format)
            end_date: Filter by date <= this (ISO format)
            min_amount: Minimum transaction amount
            iban: Filter by specific IBAN
            
        Returns:
            DataFrame with transaction records
        """
        prefix = f"{investigation_id}/processed/transactions/"
        df = self._load_parquet_files(prefix)
        
        # Apply filters
        if start_date:
            df = df[df['datum'] >= start_date]
        if end_date:
            df = df[df['datum'] <= end_date]
        if min_amount:
            df = df[df['bedrag'].abs() >= min_amount]
        if iban:
            df = df[df['iban'] == iban]
        
        return df.sort_values(['datum', 'processed_at'])
    
    def get_call_records(
        self,
        investigation_id: str,
        phone_number: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get call records for an investigation
        
        Args:
            investigation_id: Investigation ID
            phone_number: Filter by caller or callee
            start_date: Filter by timestamp >= this
            end_date: Filter by timestamp <= this
            
        Returns:
            DataFrame with call records
        """
        prefix = f"{investigation_id}/processed/call_records/"
        df = self._load_parquet_files(prefix)
        
        # Apply filters
        if phone_number:
            df = df[(df['caller'] == phone_number) | (df['callee'] == phone_number)]
        if start_date:
            df = df[df['timestamp'] >= start_date]
        if end_date:
            df = df[df['timestamp'] <= end_date]
        
        return df.sort_values('timestamp')
    
    def get_messages(
        self,
        investigation_id: str,
        phone_number: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get SMS/text message records for an investigation
        
        Args:
            investigation_id: Investigation ID
            phone_number: Filter by sender or recipient
            start_date: Filter by timestamp >= this
            end_date: Filter by timestamp <= this
            
        Returns:
            DataFrame with message records
        """
        prefix = f"{investigation_id}/processed/messages/"
        df = self._load_parquet_files(prefix)
        
        # Apply filters
        if phone_number:
            df = df[(df['sender'] == phone_number) | (df['recipient'] == phone_number)]
        if start_date:
            df = df[df['timestamp'] >= start_date]
        if end_date:
            df = df[df['timestamp'] <= end_date]
        
        return df.sort_values('timestamp')
    
    def get_transaction_summary(self, investigation_id: str) -> pd.DataFrame:
        """
        Get aggregated transaction statistics
        
        Returns:
            DataFrame with summary per IBAN:
            - total_transactions
            - total_debit (negative amounts)
            - total_credit (positive amounts)
            - net_amount
            - first_transaction
            - last_transaction
        """
        prefix = f"{investigation_id}/processed/transactions/"
        df = self._load_parquet_files(prefix)
        
        # Register as temp table for DuckDB
        self.conn.register('transactions_temp', df)
        
        sql = """
        SELECT 
            iban,
            COUNT(*) as total_transactions,
            SUM(CASE WHEN bedrag < 0 THEN bedrag ELSE 0 END) as total_debit,
            SUM(CASE WHEN bedrag > 0 THEN bedrag ELSE 0 END) as total_credit,
            SUM(bedrag) as net_amount,
            MIN(datum) as first_transaction,
            MAX(datum) as last_transaction,
            COUNT(DISTINCT DATE_TRUNC('day', datum)) as active_days
        FROM transactions_temp
        GROUP BY iban
        ORDER BY ABS(net_amount) DESC
        """
        
        return self.query(sql)
    
    def get_call_network(self, investigation_id: str) -> pd.DataFrame:
        """
        Get call network statistics (who calls whom)
        
        Returns:
            DataFrame with edges:
            - caller
            - callee
            - call_count
            - total_duration
            - avg_duration
            - first_call
            - last_call
        """
        prefix = f"{investigation_id}/processed/call_records/"
        df = self._load_parquet_files(prefix)
        
        self.conn.register('calls_temp', df)
        
        sql = """
        SELECT 
            caller,
            callee,
            COUNT(*) as call_count,
            SUM(duration_seconds) as total_duration_seconds,
            AVG(duration_seconds) as avg_duration_seconds,
            MIN(timestamp) as first_call,
            MAX(timestamp) as last_call
        FROM calls_temp
        GROUP BY caller, callee
        ORDER BY call_count DESC
        """
        
        return self.query(sql)
    
    def get_message_network(self, investigation_id: str) -> pd.DataFrame:
        """
        Get SMS message network statistics (who texts whom)
        
        Returns:
            DataFrame with edges:
            - sender
            - recipient
            - message_count
            - first_message
            - last_message
        """
        prefix = f"{investigation_id}/processed/messages/"
        df = self._load_parquet_files(prefix)
        
        self.conn.register('messages_temp', df)
        
        sql = """
        SELECT 
            sender,
            recipient,
            COUNT(*) as message_count,
            MIN(timestamp) as first_message,
            MAX(timestamp) as last_message
        FROM messages_temp
        GROUP BY sender, recipient
        ORDER BY message_count DESC
        """
        
        return self.query(sql)
    
    def get_daily_activity(self, investigation_id: str) -> pd.DataFrame:
        """
        Get daily activity summary (transactions + calls + messages)
        
        Returns:
            DataFrame with daily stats:
            - date
            - transaction_count
            - total_amount
            - call_count
            - total_call_duration
            - message_count
        """
        # Load all datasets
        try:
            trans_prefix = f"{investigation_id}/processed/transactions/"
            trans_df = self._load_parquet_files(trans_prefix)
            self.conn.register('transactions_temp', trans_df)
            has_transactions = True
        except ValueError:
            has_transactions = False
        
        try:
            calls_prefix = f"{investigation_id}/processed/call_records/"
            calls_df = self._load_parquet_files(calls_prefix)
            self.conn.register('calls_temp', calls_df)
            has_calls = True
        except ValueError:
            has_calls = False
        
        try:
            messages_prefix = f"{investigation_id}/processed/messages/"
            messages_df = self._load_parquet_files(messages_prefix)
            self.conn.register('messages_temp', messages_df)
            has_messages = True
        except ValueError:
            has_messages = False
        
        if not has_transactions and not has_calls and not has_messages:
            raise ValueError(f"No processed data found for {investigation_id}")
        
        # Build SQL based on what data we have
        sql_parts = []
        
        if has_transactions:
            sql_parts.append("""
            daily_transactions AS (
                SELECT 
                    DATE_TRUNC('day', datum) as date,
                    COUNT(*) as transaction_count,
                    SUM(bedrag) as total_amount
                FROM transactions_temp
                GROUP BY DATE_TRUNC('day', datum)
            )""")
        
        if has_calls:
            sql_parts.append("""
            daily_calls AS (
                SELECT 
                    DATE_TRUNC('day', timestamp) as date,
                    COUNT(*) as call_count,
                    SUM(duration_seconds) as total_call_duration
                FROM calls_temp
                GROUP BY DATE_TRUNC('day', timestamp)
            )""")
        
        if has_messages:
            sql_parts.append("""
            daily_messages AS (
                SELECT 
                    DATE_TRUNC('day', timestamp) as date,
                    COUNT(*) as message_count
                FROM messages_temp
                GROUP BY DATE_TRUNC('day', timestamp)
            )""")
        
        # Build the main SELECT with COALESCE for all data sources
        select_parts = []
        join_parts = []
        
        if has_transactions:
            select_parts.extend([
                "COALESCE(t.transaction_count, 0) as transaction_count",
                "COALESCE(t.total_amount, 0) as total_amount"
            ])
            base_table = "daily_transactions t"
        else:
            select_parts.extend([
                "0 as transaction_count",
                "0 as total_amount"
            ])
            base_table = None
        
        if has_calls:
            select_parts.extend([
                "COALESCE(c.call_count, 0) as call_count",
                "COALESCE(c.total_call_duration, 0) as total_call_duration"
            ])
            if base_table:
                join_parts.append("FULL OUTER JOIN daily_calls c ON t.date = c.date")
            else:
                base_table = "daily_calls c"
        else:
            select_parts.extend([
                "0 as call_count",
                "0 as total_call_duration"
            ])
        
        if has_messages:
            select_parts.append("COALESCE(m.message_count, 0) as message_count")
            if base_table:
                # Determine which alias to join on
                if has_transactions and has_calls:
                    join_parts.append("FULL OUTER JOIN daily_messages m ON COALESCE(t.date, c.date) = m.date")
                elif has_transactions:
                    join_parts.append("FULL OUTER JOIN daily_messages m ON t.date = m.date")
                else:
                    join_parts.append("FULL OUTER JOIN daily_messages m ON c.date = m.date")
            else:
                base_table = "daily_messages m"
        else:
            select_parts.append("0 as message_count")
        
        # Determine the date field based on what we have
        if has_transactions and has_calls and has_messages:
            date_field = "COALESCE(t.date, c.date, m.date) as date"
        elif has_transactions and has_calls:
            date_field = "COALESCE(t.date, c.date) as date"
        elif has_transactions and has_messages:
            date_field = "COALESCE(t.date, m.date) as date"
        elif has_calls and has_messages:
            date_field = "COALESCE(c.date, m.date) as date"
        elif has_transactions:
            date_field = "t.date as date"
        elif has_calls:
            date_field = "c.date as date"
        else:
            date_field = "m.date as date"
        
        sql = f"""
        WITH {', '.join(sql_parts)}
        SELECT 
            {date_field},
            {', '.join(select_parts)}
        FROM {base_table}
        {' '.join(join_parts)}
        ORDER BY date
        """
        
        return self.query(sql)
    
    def export_to_csv(
        self,
        investigation_id: str,
        output_path: str,
        data_type: str = 'transactions'
    ):
        """
        Export investigation data to CSV file
        
        Args:
            investigation_id: Investigation ID
            output_path: Path to output CSV file
            data_type: 'transactions' or 'call_records'
        """
        if data_type == 'transactions':
            df = self.get_transactions(investigation_id)
        elif data_type == 'call_records':
            df = self.get_call_records(investigation_id)
        else:
            raise ValueError(f"Unknown data_type: {data_type}")
        
        df.to_csv(output_path, index=False)
        return len(df)
    
    def close(self):
        """Close DuckDB connection"""
        if self.conn:
            self.conn.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# Convenience functions for quick queries

def quick_query(
    investigation_id: str,
    sql: str,
    minio_endpoint: str = "minio:9000",
    minio_access_key: str = "minio",
    minio_secret_key: str = "minio12345"
) -> pd.DataFrame:
    """
    Execute a quick DuckDB query against investigation data
    
    The query can reference 'transactions' and 'calls' tables
    
    Usage:
        df = quick_query(
            'OND-2025-000002',
            'SELECT * FROM transactions WHERE bedrag > 100 LIMIT 10'
        )
    """
    with InvestigationQueryHelper(minio_endpoint, minio_access_key, minio_secret_key) as helper:
        # Load and register both datasets
        try:
            trans_df = helper.get_transactions(investigation_id)
            helper.conn.register('transactions', trans_df)
        except:
            pass
        
        try:
            calls_df = helper.get_call_records(investigation_id)
            helper.conn.register('calls', calls_df)
        except:
            pass
        
        return helper.query(sql)


def get_investigation_stats(investigation_id: str) -> Dict[str, Any]:
    """
    Get complete statistics for an investigation
    
    Returns dict with:
    - transaction_summary
    - call_network
    - daily_activity
    """
    with InvestigationQueryHelper() as helper:
        try:
            transaction_summary = helper.get_transaction_summary(investigation_id)
            transaction_stats = {
                'total_ibans': len(transaction_summary),
                'total_transactions': int(transaction_summary['total_transactions'].sum()),
                'total_debit': float(transaction_summary['total_debit'].sum()),
                'total_credit': float(transaction_summary['total_credit'].sum()),
                'net_amount': float(transaction_summary['net_amount'].sum())
            }
        except Exception as e:
            transaction_stats = {'error': str(e)}
        
        try:
            call_network = helper.get_call_network(investigation_id)
            call_stats = {
                'total_call_pairs': len(call_network),
                'total_calls': int(call_network['call_count'].sum()),
                'total_duration_hours': float(call_network['total_duration_seconds'].sum() / 3600)
            }
        except Exception as e:
            call_stats = {'error': str(e)}
        
        return {
            'investigation_id': investigation_id,
            'generated_at': datetime.utcnow().isoformat(),
            'transactions': transaction_stats,
            'calls': call_stats
        }
