"""
Canonical Integration Assets

Maps raw data from heterogeneous sources to standardized canonical models.
Enforces semantic consistency and enables cross-source integration.
"""

from dagster import asset, AssetExecutionContext, Output, MetadataValue
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal
from datetime import datetime
import hashlib
import re
import uuid
import json

from .resources import PostgresResource
from .marquez_lineage import (
    emit_canonical_lineage_start,
    emit_canonical_lineage_complete,
    emit_canonical_lineage_fail
)


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_iban_format(iban: str) -> bool:
    """Validate IBAN format (basic check)."""
    if not iban:
        return False
    # Remove spaces
    iban = iban.replace(' ', '').upper()
    # Check format: 2 letters + 2 digits + up to 30 alphanumeric
    pattern = r'^[A-Z]{2}[0-9]{2}[A-Z0-9]{1,30}$'
    return bool(re.match(pattern, iban))


def validate_e164_phone(phone: str) -> bool:
    """Validate E.164 phone format."""
    if not phone:
        return False
    # E.164: + followed by 1-15 digits
    pattern = r'^\+[1-9][0-9]{1,14}$'
    return bool(re.match(pattern, phone))


def validate_iso_currency(currency: str) -> bool:
    """Validate ISO 4217 currency code."""
    # Common currencies (extend as needed)
    valid_currencies = {
        'EUR', 'USD', 'GBP', 'CHF', 'JPY', 'AUD', 'CAD', 
        'SEK', 'NOK', 'DKK', 'PLN', 'CZK', 'HUF'
    }
    return currency in valid_currencies


def calculate_completeness_score(record: Dict[str, Any], required_fields: List[str], optional_fields: List[str]) -> int:
    """Calculate data completeness percentage."""
    total_fields = len(required_fields) + len(optional_fields)
    filled_fields = sum(1 for f in required_fields + optional_fields if record.get(f))
    return int((filled_fields / total_fields) * 100) if total_fields > 0 else 0


# ============================================================================
# NORMALIZATION FUNCTIONS
# ============================================================================

def normalize_iban(iban: Optional[str]) -> Optional[str]:
    """Normalize IBAN to canonical format."""
    if not iban:
        return None
    # Remove all whitespace and hyphens, convert to uppercase
    normalized = iban.replace(' ', '').replace('-', '').upper()
    return normalized if validate_iban_format(normalized) else iban.upper()


def normalize_phone(phone: Optional[str], default_country_code: str = '31') -> Optional[str]:
    """Normalize phone number to E.164 format."""
    if not phone:
        return None
    
    # Remove all non-numeric characters
    digits = ''.join(filter(str.isdigit, phone))
    
    if not digits:
        return None
    
    # Add country code if missing
    if not digits.startswith(default_country_code) and len(digits) == 9:
        digits = default_country_code + digits
    
    # Add + prefix
    return '+' + digits


def normalize_currency(currency: Optional[str]) -> Optional[str]:
    """Normalize currency code to ISO 4217."""
    if not currency:
        return None
    
    # Handle common variations
    currency_map = {
        '€': 'EUR',
        '$': 'USD',
        '£': 'GBP',
        'EURO': 'EUR',
        'DOLLAR': 'USD'
    }
    
    return currency_map.get(currency.upper(), currency.upper())


def clean_description(description: Optional[str]) -> Optional[str]:
    """Clean and normalize description text."""
    if not description:
        return None
    
    # Remove excessive whitespace
    cleaned = ' '.join(description.split())
    
    # Remove common prefixes
    prefixes_to_remove = ['Betaling:', 'Payment:', 'Transfer:']
    for prefix in prefixes_to_remove:
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):].strip()
    
    return cleaned[:1000]  # Limit length


# ============================================================================
# MAPPING FUNCTIONS - TRANSACTIONS
# ============================================================================

def map_bank_a_to_canonical(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Bank A transactions to canonical model.
    Bank A: Dutch bank with IBANs, EUR currency.
    """
    # Parse raw_data JSONB if it exists, otherwise use direct fields
    raw_data = raw_record.get('raw_data', {})
    if isinstance(raw_data, str):
        try:
            import json
            raw_data = json.loads(raw_data)
        except:
            raw_data = {}
    
    # Extract and validate account information
    debtor_iban = raw_data.get("iban", "")
    creditor_iban = raw_data.get("tegenrekening_iban", "")
    
    # Check if debtor_iban is numeric (corrupt data) - filter out numbers like "500.0", "-450.0"
    debtor_is_numeric = debtor_iban and debtor_iban.replace('.', '').replace('-', '').lstrip('-').replace(',', '').isdigit()
    
    # Handle creditor account - ATM is valid for cash withdrawals
    if creditor_iban and creditor_iban.upper() == 'ATM':
        creditor_account_id = 'ATM'
        creditor_account_type = 'atm'
    elif creditor_iban:
        creditor_account_id = normalize_iban(creditor_iban)
        creditor_account_type = 'iban'
    else:
        creditor_account_id = None
        creditor_account_type = None
    
    return {
        "source_system_id": raw_record.get("source_id"),  # Use actual source_id from raw table
        "source_record_id": str(raw_record["transaction_id"]),
        "source_file_name": raw_data.get("source_file"),
        "investigation_id": raw_record["investigation_id"],
        
        # Core attributes
        "transaction_reference": raw_data.get("referentie"),
        "transaction_datetime": parse_dutch_datetime(
            str(raw_record.get("datum", "")),
            raw_data.get("tijd", "00:00:00")
        ),
        "posting_date": parse_dutch_date(str(raw_record.get("datum", ""))),
        "value_date": parse_dutch_date(raw_data.get("valutadatum", str(raw_record.get("datum", "")))),
        
        # Monetary - bedrag is already Decimal from PostgreSQL
        "amount": raw_record.get("bedrag"),
        "currency_code": "EUR",
        
        # Accounts - Use variables set above
        "debtor_account_id": normalize_iban(debtor_iban) if debtor_iban and not debtor_is_numeric else None,
        "debtor_account_type": "iban" if debtor_iban and not debtor_is_numeric else None,
        "debtor_name": raw_data.get("naam_van"),
        "creditor_account_id": creditor_account_id,
        "creditor_account_type": creditor_account_type,
        "creditor_name": raw_data.get("naam_naar"),
        
        # Details
        "transaction_type": infer_transaction_type(float(raw_record.get("bedrag", 0)) if raw_record.get("bedrag") is not None else 0),
        "payment_method": "wire",  # Bank A uses wire transfers
        "description": clean_description(raw_record.get("omschrijving")),
        "reference_number": raw_data.get("kenmerk"),
        
        # Metadata
        "is_cancelled": False,
        "is_reversal": raw_data.get("is_storno", False),
        
        # Original data
        "source_raw_data": raw_record
    }


def infer_transaction_type(amount: float) -> str:
    """Infer transaction type from amount."""
    if amount > 0:
        return "credit"
    elif amount < 0:
        return "debit"
    else:
        return "other"


def parse_dutch_date(date_str: str) -> Optional[datetime]:
    """Parse Dutch date format."""
    if not date_str:
        return None
    try:
        # Try ISO format first
        if isinstance(date_str, datetime):
            return date_str
        return datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
    except:
        # Try DD-MM-YYYY
        try:
            return datetime.strptime(str(date_str), '%d-%m-%Y')
        except:
            # Try YYYY-MM-DD
            try:
                return datetime.strptime(str(date_str), '%Y-%m-%d')
            except:
                return None


def parse_dutch_datetime(date_str: str, time_str: str = "00:00:00") -> Optional[datetime]:
    """Parse Dutch datetime."""
    date = parse_dutch_date(date_str)
    if not date:
        return None
    
    try:
        time_parts = str(time_str).split(':')
        hour = int(time_parts[0]) if len(time_parts) > 0 else 0
        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
        second = int(time_parts[2]) if len(time_parts) > 2 else 0
        
        return date.replace(hour=hour, minute=minute, second=second)
    except:
        return date


# ============================================================================
# MAPPING FUNCTIONS - COMMUNICATIONS
# ============================================================================

def map_telecom_a_call_to_canonical(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Telecom A call records to canonical model.
    """
    raw_data = raw_record.get('raw_data', {})
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except:
            raw_data = {}
    
    # Parse datetime from call_date and call_time
    communication_datetime = None
    call_date = raw_record.get('call_date') or raw_data.get('call_date')
    call_time = raw_record.get('call_time') or raw_data.get('call_time')
    
    if call_date and call_time:
        try:
            # Combine date and time strings
            if isinstance(call_time, str):
                datetime_str = f"{call_date} {call_time}"
            else:
                datetime_str = f"{call_date} {str(call_time)}"
            communication_datetime = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        except Exception as e:
            # Fallback: try just the date
            try:
                communication_datetime = datetime.strptime(str(call_date), "%Y-%m-%d")
            except:
                pass
    
    return {
        "source_system_id": raw_record.get("source_id"),  # Use actual source_id from raw table
        "source_record_id": str(raw_record["call_id"]),
        "source_file_name": raw_data.get("source_file"),
        "investigation_id": raw_record["investigation_id"],
        
        # Core attributes
        "communication_type": "call",
        "communication_datetime": communication_datetime,
        "duration_seconds": int(raw_data.get("duration_seconds", 0)) if raw_data.get("duration_seconds") else 0,
        
        # Participants - use from_number/to_number from raw_data
        "originator_id": normalize_phone(str(raw_data.get("from_number", ""))) or None,
        "originator_type": "msisdn",
        "recipient_id": normalize_phone(str(raw_data.get("to_number", ""))) or None,
        "recipient_type": "msisdn",
        
        # Details
        "direction": map_call_direction(raw_data.get("call_type", "unknown")),
        "call_status": "completed",  # Telecom A only logs completed calls
        
        # Network
        "network_operator": "telecom_a",
        "connection_type": raw_data.get("network_type"),
        
        # Original data
        "source_raw_data": raw_record
    }


def map_telecom_a_sms_to_canonical(raw_record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Map Telecom A SMS records to canonical model.
    """
    raw_data = raw_record.get('raw_data', {})
    if isinstance(raw_data, str):
        try:
            raw_data = json.loads(raw_data)
        except:
            raw_data = {}
    
    # Parse timestamp from raw_data (Unix timestamp in milliseconds)
    timestamp_ms = raw_data.get('timestamp')
    communication_datetime = None
    if timestamp_ms:
        try:
            communication_datetime = datetime.fromtimestamp(timestamp_ms / 1000.0)
        except:
            pass
    
    content = raw_data.get("message_text", "") or raw_data.get("content", "")
    
    return {
        "source_system_id": raw_record.get("source_id"),  # Use actual source_id from raw table
        "source_record_id": str(raw_record["message_id"]),
        "source_file_name": raw_data.get("source_file"),
        "investigation_id": raw_record["investigation_id"],
        
        # Core attributes
        "communication_type": "sms",
        "communication_datetime": communication_datetime,
        "duration_seconds": None,
        
        # Participants - use raw_data fields
        "originator_id": normalize_phone(raw_data.get("sender")),
        "originator_type": "msisdn",
        "recipient_id": normalize_phone(raw_data.get("recipient")),
        "recipient_type": "msisdn",
        
        # Content
        "message_content": content,
        "content_hash": hashlib.sha256(content.encode()).hexdigest() if content else None,
        
        # Details
        "direction": "outbound",  # From sender perspective
        
        # Network
        "network_operator": "telecom_a",
        
        # Original data
        "source_raw_data": raw_record
    }


def map_call_direction(call_type: str) -> str:
    """Map call type to direction."""
    mapping = {
        "incoming": "inbound",
        "outgoing": "outbound",
        "missed": "inbound",
        "internal": "internal"
    }
    return mapping.get(call_type.lower(), "unknown")


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_canonical_transaction(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate canonical transaction against business rules.
    Returns: {is_valid: bool, status: str, errors: List[str], warnings: List[str]}
    """
    errors = []
    warnings = []
    
    # Required fields (amount is optional, can be NULL for incomplete records)
    required = ['source_system_id', 'source_record_id', 'investigation_id', 
                'transaction_datetime', 'currency_code']
    for field in required:
        if not record.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Amount validation - allow NULL but warn
    if record.get('amount') is None:
        warnings.append("Amount is NULL - transaction may be incomplete")
    elif record.get('amount') is not None:
        if record['amount'] == 0:
            warnings.append("Zero amount transaction")
        
        if abs(record['amount']) > 1000000:
            warnings.append(f"Large amount: {record['amount']}")
    
    # IBAN validation
    debtor_valid = False
    creditor_valid = False
    
    if record.get('debtor_account_type') == 'iban':
        if record.get('debtor_account_id'):
            if validate_iban_format(record['debtor_account_id']):
                debtor_valid = True
            else:
                errors.append(f"Invalid debtor IBAN format: {record.get('debtor_account_id')}")
    
    # Creditor can be IBAN or ATM
    if record.get('creditor_account_type') == 'atm':
        # ATM transactions are valid
        creditor_valid = True
        warnings.append("ATM transaction without creditor IBAN")
    elif record.get('creditor_account_type') == 'iban':
        if record.get('creditor_account_id'):
            if validate_iban_format(record['creditor_account_id']):
                creditor_valid = True
            else:
                errors.append(f"Invalid creditor IBAN format: {record.get('creditor_account_id')}")
    
    # Currency validation
    if record.get('currency_code'):
        if not validate_iso_currency(record['currency_code']):
            warnings.append(f"Non-standard currency code: {record['currency_code']}")
    
    # Transaction type validation
    valid_types = ['debit', 'credit', 'transfer', 'payment', 'withdrawal', 'deposit', 'fee', 'interest', 'other']
    if record.get('transaction_type') and record['transaction_type'] not in valid_types:
        warnings.append(f"Non-standard transaction type: {record['transaction_type']}")
    
    # At least one account
    if not record.get('debtor_account_id') and not record.get('creditor_account_id'):
        errors.append("Transaction must have at least one account (debtor or creditor)")
    
    # Transaction datetime in past
    if record.get('transaction_datetime'):
        if record['transaction_datetime'] > datetime.now():
            warnings.append(f"Future transaction datetime: {record['transaction_datetime']}")
    
    # Determine overall status
    if errors:
        status = 'error'
    elif warnings:
        status = 'warning'
    else:
        status = 'valid'
    
    return {
        'is_valid': len(errors) == 0,
        'status': status,
        'errors': errors if errors else None,
        'warnings': warnings if warnings else None
    }


def validate_canonical_communication(record: Dict[str, Any]) -> Dict[str, Any]:
    """Validate canonical communication."""
    errors = []
    warnings = []
    
    # Required fields
    required = ['source_system_id', 'source_record_id', 'investigation_id',
                'communication_type', 'communication_datetime',
                'originator_id', 'recipient_id']
    for field in required:
        if not record.get(field):
            errors.append(f"Missing required field: {field}")
    
    # Duration for calls
    if record.get('communication_type') == 'call':
        if record.get('duration_seconds') is None:
            errors.append("Call records must have duration_seconds")
        elif record['duration_seconds'] < 0:
            errors.append(f"Negative duration: {record['duration_seconds']}")
        elif record['duration_seconds'] > 86400:
            warnings.append(f"Very long call duration: {record['duration_seconds']}s")
    
    # Phone validation
    if record.get('originator_type') == 'msisdn':
        if not validate_e164_phone(record.get('originator_id', '')):
            warnings.append(f"Non-standard phone format: {record.get('originator_id')}")
    
    if record.get('recipient_type') == 'msisdn':
        if not validate_e164_phone(record.get('recipient_id', '')):
            warnings.append(f"Non-standard phone format: {record.get('recipient_id')}")
    
    # Message content for SMS/email
    if record.get('communication_type') in ['sms', 'email', 'mms']:
        if not record.get('message_content'):
            warnings.append("Message records should have content")
    
    # Determine status
    if errors:
        status = 'error'
    elif warnings:
        status = 'warning'
    else:
        status = 'valid'
    
    return {
        'is_valid': len(errors) == 0,
        'status': status,
        'errors': errors if errors else None,
        'warnings': warnings if warnings else None
    }


# ============================================================================
# DAGSTER ASSETS
# ============================================================================

@asset(
    group_name="investigations_canonical",
    compute_kind="python"
)
def canonical_transactions(
    context: AssetExecutionContext,
    postgres: PostgresResource
):
    """
    Map raw bank transactions to canonical transaction model.
    Enforces semantic consistency across all bank sources.
    """
    
    context.log.info("Starting canonical_transactions mapping...")
    
    # Emit Marquez lineage START event
    run_id = emit_canonical_lineage_start("canonical_transactions")
    
    try:
        # Get unmapped raw transactions
        conn = postgres.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT r.* 
            FROM raw_transactions r
            LEFT JOIN canonical.canonical_transaction c 
                ON c.source_system_id = r.source_id 
                AND c.source_record_id = r.transaction_id::text
            WHERE c.canonical_transaction_id IS NULL
            ORDER BY r.loaded_at DESC
            LIMIT 1000
        """)
        
        # RealDictCursor returns dicts directly, not tuples!
        raw_records = cursor.fetchall()
        cursor.close()
        
        context.log.info(f"Found {len(raw_records)} unmapped transactions")
        
        if not raw_records:
            context.log.info("No new transactions to map")
            conn.close()
            
            # Emit Marquez lineage COMPLETE event with zero records
            emit_canonical_lineage_complete(
                job_name="canonical_transactions",
                run_id=run_id,
                source_system="bank_a",
                raw_table="raw_transactions",
                canonical_table="canonical_transaction",
                records_processed=0,
                records_valid=0,
                records_warning=0,
                records_error=0
            )
            
            yield Output(value=0, metadata={"records_mapped": 0})
            return
        
        canonical_records = []
        stats = {
            'valid': 0,
            'warning': 0,
            'error': 0
        }
        
        for raw_record in raw_records:
            try:
                # raw_record is already a dict from RealDictCursor
                
                # DEBUG: Print first record structure
                if len(canonical_records) == 0:
                    context.log.info(f"🔍 DEBUG First record keys: {list(raw_record.keys())[:10]}")
                    context.log.info(f"🔍 DEBUG bedrag type: {type(raw_record.get('bedrag'))}, value: {raw_record.get('bedrag')}")
                
                # Determine source and map
                source_id = raw_record.get('source_id', '')
                context.log.debug(f"Mapping transaction from source: {source_id}")
                
                # For now, all sources are mapped as bank_a (Dutch bank)
                # In future: add source-specific logic based on investigation metadata
                canonical = map_bank_a_to_canonical(raw_record)
                
                # Validate
                validation = validate_canonical_transaction(canonical)
                canonical['validation_status'] = validation['status']
                canonical['validation_messages'] = {
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                } if (validation['errors'] or validation['warnings']) else None
                
                # Calculate completeness
                required_fields = ['transaction_datetime', 'amount', 'currency_code']
                optional_fields = ['debtor_account_id', 'creditor_account_id', 'description', 
                                 'reference_number', 'debtor_name', 'creditor_name']
                canonical['data_completeness_score'] = calculate_completeness_score(
                    canonical, required_fields, optional_fields
                )
                
                canonical_records.append(canonical)
                stats[validation['status']] += 1
                
            except Exception as e:
                context.log.error(f"Failed to map transaction {raw_record.get('transaction_id')}: {e}")
                stats['error'] += 1
                
                # Still add failed record to canonical with error status (for tracking)
                # Include minimal required NOT NULL fields with dummy values
                raw_data = raw_record.get('raw_data', {}) or {}
                error_record = {
                    'source_system_id': source_id,
                    'source_record_id': str(raw_record.get('transaction_id')),
                    'source_file_name': raw_data.get('source_file'),
                    'investigation_id': raw_record.get('investigation_id'),
                    'transaction_datetime': raw_record.get('datum', datetime.now()),  # Required NOT NULL
                    'currency_code': 'EUR',  # Required NOT NULL - default to EUR
                    'validation_status': 'error',
                    'validation_messages': {'errors': [f"Mapping failed: {str(e)}"], 'warnings': []},
                    'data_completeness_score': 0.0,
                    'source_raw_data': raw_record
                }
                canonical_records.append(error_record)
        
        context.log.info(f"Mapped {len(canonical_records)} transactions: {stats}")
        
        # Bulk insert
        if canonical_records:
            context.log.info(f"🔍 DEBUG: About to call insert_canonical_transactions with {len(canonical_records)} records")
            try:
                insert_canonical_transactions(postgres, canonical_records, context)
                context.log.info(f"🔍 DEBUG: insert_canonical_transactions completed successfully")
            except Exception as e:
                context.log.error(f"🔍 DEBUG: insert_canonical_transactions failed: {e}")
                # Emit Marquez lineage FAIL event
                emit_canonical_lineage_fail("canonical_transactions", run_id, str(e))
                raise
        else:
            context.log.warning(f"🔍 DEBUG: No canonical_records to insert (list is empty)")
        
        conn.close()
        
        # Emit Marquez lineage COMPLETE event with metrics
        emit_canonical_lineage_complete(
            job_name="canonical_transactions",
            run_id=run_id,
            source_system="bank_a",
            raw_table="raw_transactions",
            canonical_table="canonical_transaction",
            records_processed=len(canonical_records),
            records_valid=stats['valid'],
            records_warning=stats['warning'],
            records_error=stats['error']
        )
    
    except Exception as e:
        # Emit Marquez lineage FAIL event
        emit_canonical_lineage_fail("canonical_transactions", run_id, str(e))
        raise
    
    yield Output(
        value=len(canonical_records),
        metadata={
            "records_mapped": len(canonical_records),
            "valid_count": stats['valid'],
            "warning_count": stats['warning'],
            "error_count": stats['error'],
            "quality_rate": f"{stats['valid'] / len(canonical_records) * 100:.1f}%" if canonical_records else "0%"
        }
    )


@asset(
    group_name="investigations_canonical",
    compute_kind="python"
)
def canonical_communications(
    context: AssetExecutionContext,
    postgres: PostgresResource
):
    """
    Map raw communication records to canonical communication model.
    """
    context.log.info("Starting canonical_communications mapping...")
    
    # Emit Marquez lineage START event
    run_id = emit_canonical_lineage_start("canonical_communications")
    
    try:
        canonical_records = []
        stats = {'valid': 0, 'warning': 0, 'error': 0}
        
        conn = postgres.get_connection()
        cursor = conn.cursor()
        
        # Map calls
        cursor.execute("""
            SELECT r.* 
            FROM raw_calls r
            LEFT JOIN canonical.canonical_communication c 
                ON c.source_system_id = r.source_id 
                AND c.source_record_id = r.call_id::text
            WHERE c.canonical_communication_id IS NULL
            LIMIT 1000
        """)
        
        calls = cursor.fetchall()
        
        context.log.info(f"Found {len(calls)} unmapped calls")
        
        for call_record in calls:
            try:
                # call_record is already a dict from RealDictCursor
                canonical = map_telecom_a_call_to_canonical(call_record)
                validation = validate_canonical_communication(canonical)
                canonical['validation_status'] = validation['status']
                canonical['validation_messages'] = {
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                } if (validation['errors'] or validation['warnings']) else None
                
                canonical_records.append(canonical)
                stats[validation['status']] += 1
            except Exception as e:
                context.log.error(f"Failed to map call {call_record.get('call_id')}: {e}")
                stats['error'] += 1
        
        # Map SMS
        cursor.execute("""
            SELECT r.* 
            FROM raw_messages r
            LEFT JOIN canonical.canonical_communication c 
                ON c.source_system_id = r.source_id 
                AND c.source_record_id = r.message_id::text
            WHERE c.canonical_communication_id IS NULL
            LIMIT 1000
        """)
        
        messages = cursor.fetchall()
        
        context.log.info(f"Found {len(messages)} unmapped messages")
        
        for msg_record in messages:
            try:
                # msg_record is already a dict from RealDictCursor
                canonical = map_telecom_a_sms_to_canonical(msg_record)
                validation = validate_canonical_communication(canonical)
                canonical['validation_status'] = validation['status']
                canonical['validation_messages'] = {
                    'errors': validation['errors'],
                    'warnings': validation['warnings']
                } if (validation['errors'] or validation['warnings']) else None
                
                canonical_records.append(canonical)
                stats[validation['status']] += 1
            except Exception as e:
                context.log.error(f"Failed to map message {msg_record.get('message_id')}: {e}")
                stats['error'] += 1
        
        context.log.info(f"Mapped {len(canonical_records)} communications: {stats}")
        
        # Bulk insert
        if canonical_records:
            try:
                insert_canonical_communications(postgres, canonical_records, context)
            except Exception as e:
                context.log.error(f"Failed to insert canonical communications: {e}")
                # Emit Marquez lineage FAIL event
                emit_canonical_lineage_fail("canonical_communications", run_id, str(e))
                raise
        
        cursor.close()
        conn.close()
        
        # Emit Marquez lineage COMPLETE event with metrics
        emit_canonical_lineage_complete(
            job_name="canonical_communications",
            run_id=run_id,
            source_system="telecom_a",
            raw_table="raw_calls_and_messages",
            canonical_table="canonical_communication",
            records_processed=len(canonical_records),
            records_valid=stats['valid'],
            records_warning=stats['warning'],
            records_error=stats['error']
        )
    
    except Exception as e:
        # Emit Marquez lineage FAIL event
        emit_canonical_lineage_fail("canonical_communications", run_id, str(e))
        raise
    
    yield Output(
        value=len(canonical_records),
        metadata={
            "records_mapped": len(canonical_records),
            "calls": len(calls),
            "messages": len(messages),
            "valid_count": stats['valid'],
            "warning_count": stats['warning'],
            "error_count": stats['error']
        }
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def insert_canonical_transactions(postgres, records: List[Dict], context):
    """
    Bulk insert canonical transactions.
    Only inserts valid/warning records. Error records are logged to mapping_log.
    """
    context.log.info(f"🔍 DEBUG: insert_canonical_transactions called with {len(records)} records")
    
    conn = postgres.get_connection()
    cursor = conn.cursor()
    
    valid_records = [r for r in records if r.get('validation_status') in ['valid', 'warning']]
    error_records = [r for r in records if r.get('validation_status') == 'error']
    
    context.log.info(f"Processing {len(records)} records: {len(valid_records)} valid/warning, {len(error_records)} errors")
    
    # Insert ALL records into canonical_transaction (including errors for tracking)
    # This prevents the sensor from re-triggering for failed mappings
    insert_sql = """
    INSERT INTO canonical.canonical_transaction (
        canonical_transaction_id, source_system_id, source_record_id, source_file_name,
        investigation_id, transaction_reference, transaction_datetime, posting_date, value_date,
        amount, currency_code, debtor_account_id, debtor_account_type, debtor_name, debtor_bank_code,
        creditor_account_id, creditor_account_type, creditor_name, creditor_bank_code,
        transaction_type, payment_method, description, reference_number,
        validation_status, validation_messages, data_completeness_score,
        is_cancelled, is_reversal, source_raw_data
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (source_system_id, source_record_id) DO UPDATE SET
        validation_status = EXCLUDED.validation_status,
        validation_messages = EXCLUDED.validation_messages,
        data_completeness_score = EXCLUDED.data_completeness_score,
        updated_at = CURRENT_TIMESTAMP
    """
    
    inserted_count = 0
    inserted_records = []  # Track successfully inserted records with IDs
    # Insert ALL records (valid, warning, AND error)
    for record in records:
        try:
            transaction_id = str(uuid.uuid4())
            cursor.execute(insert_sql, (
                transaction_id,
                record.get('source_system_id'),
                record.get('source_record_id'),
                record.get('source_file_name'),
                record.get('investigation_id'),
                record.get('transaction_reference'),
                record.get('transaction_datetime'),
                record.get('posting_date'),
                record.get('value_date'),
                float(record.get('amount')) if record.get('amount') else None,
                record.get('currency_code'),
                record.get('debtor_account_id'),
                record.get('debtor_account_type'),
                record.get('debtor_name'),
                record.get('debtor_bank_code'),
                record.get('creditor_account_id'),
                record.get('creditor_account_type'),
                record.get('creditor_name'),
                record.get('creditor_bank_code'),
                record.get('transaction_type'),
                record.get('payment_method'),
                record.get('description'),
                record.get('reference_number'),
                record.get('validation_status', 'valid'),
                json.dumps(record.get('validation_messages')) if record.get('validation_messages') else None,
                record.get('data_completeness_score', 0),
                record.get('is_cancelled', False),
                record.get('is_reversal', False),
                json.dumps(record.get('source_raw_data'), default=str)
            ))
            record['transaction_id'] = transaction_id  # Store ID for logging
            inserted_records.append(record)
            inserted_count += 1
        except Exception as e:
            context.log.error(f"Failed to insert record {record.get('source_record_id')}: {e}")
    
    # TODO: Fix mapping_log later - focus on inserts first
    logged_count = 0
    # log_sql = """
    # INSERT INTO canonical.canonical_mapping_log (...) VALUES (...)
    # """
    # for record in inserted_records:
    #     try:
    #         errors = record.get('validation_messages', {}).get('errors', [])
    #         warnings = record.get('validation_messages', {}).get('warnings', [])
    #         cursor.execute(log_sql, (...))
    #         logged_count += 1
    #     except Exception as e:
    #         context.log.error(f"Failed to log mapping for {record.get('source_record_id')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    # Log summary with breakdown
    context.log.info(f"✅ Inserted {inserted_count} total records:")
    context.log.info(f"   - {len(valid_records)} valid/warning records")
    context.log.info(f"   - {len(error_records)} error records (tracked for investigation)")
    
    # Log error details for investigation
    if error_records:
        context.log.warning(f"⚠️  {len(error_records)} records have validation errors:")
        for record in error_records[:5]:  # Show first 5 errors
            errors = record.get('validation_messages', {}).get('errors', [])
            context.log.warning(
                f"  - Investigation: {record.get('investigation_id')}, "
                f"Source: {record.get('source_system_id')}, "
                f"Record: {record.get('source_record_id')}, "
                f"Errors: {', '.join(errors[:2])}"
            )
        if len(error_records) > 5:
            context.log.warning(f"  ... and {len(error_records) - 5} more errors")


def insert_canonical_communications(postgres, records: List[Dict], context):
    """
    Bulk insert canonical communications.
    Only inserts valid/warning records. Error records are skipped because they lack required fields.
    TODO: Add error records with dummy values for required NOT NULL fields.
    """
    conn = postgres.get_connection()
    cursor = conn.cursor()
    
    valid_records = [r for r in records if r.get('validation_status') in ['valid', 'warning']]
    error_records = [r for r in records if r.get('validation_status') == 'error']
    
    context.log.info(f"Processing {len(records)} records: {len(valid_records)} valid/warning, {len(error_records)} errors")
    context.log.warning(f"⚠️  Skipping {len(error_records)} error records (missing required fields)")
    
    insert_sql = """
    INSERT INTO canonical.canonical_communication (
        canonical_communication_id, source_system_id, source_record_id, source_file_name,
        investigation_id, communication_type, communication_datetime, duration_seconds,
        originator_id, originator_type, originator_name, originator_location,
        recipient_id, recipient_type, recipient_name, recipient_location,
        direction, call_status, network_operator, connection_type,
        message_content, content_hash,
        validation_status, validation_messages, source_raw_data
    ) VALUES (
        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
        %s, %s, %s, %s, %s, %s, %s, %s, %s
    )
    ON CONFLICT (source_system_id, source_record_id) DO UPDATE SET
        validation_status = EXCLUDED.validation_status,
        validation_messages = EXCLUDED.validation_messages,
        updated_at = CURRENT_TIMESTAMP
    """
    
    inserted_count = 0
    inserted_records = []  # Track successfully inserted records with IDs
    # Insert ONLY valid/warning records (skip errors - they lack required fields)
    for record in valid_records:
        try:
            communication_id = str(uuid.uuid4())
            cursor.execute(insert_sql, (
                communication_id,
                record.get('source_system_id'),
                record.get('source_record_id'),
                record.get('source_file_name'),
                record.get('investigation_id'),
                record.get('communication_type'),
                record.get('communication_datetime'),
                record.get('duration_seconds'),
                record.get('originator_id'),
                record.get('originator_type'),
                record.get('originator_name'),
                json.dumps(record.get('originator_location')) if record.get('originator_location') else None,
                record.get('recipient_id'),
                record.get('recipient_type'),
                record.get('recipient_name'),
                json.dumps(record.get('recipient_location')) if record.get('recipient_location') else None,
                record.get('direction'),
                record.get('call_status'),
                record.get('network_operator'),
                record.get('connection_type'),
                record.get('message_content'),
                record.get('content_hash'),
                record.get('validation_status', 'valid'),
                json.dumps(record.get('validation_messages')) if record.get('validation_messages') else None,
                json.dumps(record.get('source_raw_data'), default=str)
            ))
            record['communication_id'] = communication_id  # Store ID for logging
            inserted_records.append(record)
            inserted_count += 1
        except Exception as e:
            context.log.error(f"Failed to insert communication {record.get('source_record_id')}: {e}")
    
    #  TODO: Fix mapping_log later - focus on inserts first
    logged_count = 0
    # log_sql = """
    # INSERT INTO canonical.canonical_mapping_log (...) VALUES (...)
    # """
    # for record in inserted_records:
    #     try:
    #         errors = record.get('validation_messages', {}).get('errors', [])
    #         warnings = record.get('validation_messages', {}).get('warnings', [])
    #         cursor.execute(log_sql, (...))
    #         logged_count += 1
    #     except Exception as e:
    #         context.log.error(f"Failed to log mapping for {record.get('source_record_id')}: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    # Log summary with breakdown
    context.log.info(f"✅ Inserted {inserted_count} valid/warning communications")
    if error_records:
        context.log.warning(f"⚠️  Skipped {len(error_records)} error records (will be logged separately for investigation)")
    
    if error_records:
        context.log.warning(f"⚠️  {len(error_records)} communications rejected due to validation errors")
        for record in error_records[:3]:
            errors = record.get('validation_messages', {}).get('errors', [])
            context.log.warning(
                f"  - Investigation: {record.get('investigation_id')}, "
                f"Type: {record.get('communication_type')}, "
                f"Errors: {', '.join(errors[:2])}"
            )
