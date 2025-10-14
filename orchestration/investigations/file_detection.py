"""
File type detection utilities

Detects data source type based on:
- Filename patterns
- File content (headers, keywords)
- File extension
"""

import re
from typing import Optional, Dict, List
import io
import logging

logger = logging.getLogger(__name__)


# File processor definitions
FILE_PROCESSORS = {
    'bank_transactions': {
        'description': 'Bank transaction data (CSV)',
        'patterns': [
            r'.*transacti.*\.csv$',
            r'.*mutaties.*\.csv$',
            r'.*rekening.*\.csv$',
            r'.*bank.*\.csv$',
        ],
        'keywords': ['iban', 'bedrag', 'tegenrekening', 'saldo', 'valutadatum'],
        'required_columns': ['iban', 'bedrag'],
        'pipeline': 'bank_transaction_pipeline',
        'output_type': 'transaction'
    },
    
    'call_records': {
        'description': 'Telephone call records (CSV)',
        'patterns': [
            r'.*call.*\.csv$',
            r'.*bel.*\.csv$',
            r'.*gesprek.*\.csv$',
            r'.*telecom.*\.csv$',
        ],
        'keywords': ['caller', 'callee', 'duration', 'cell_tower', 'imei', 'imsi'],
        'required_columns': ['caller', 'callee', 'duration'],
        'pipeline': 'telecom_call_pipeline',
        'output_type': 'call_record'
    },
    
    'sms_records': {
        'description': 'SMS/Text message records (CSV)',
        'patterns': [
            r'.*sms.*\.csv$',
            r'.*message.*\.csv$',
            r'.*berichten.*\.csv$',
        ],
        'keywords': ['sender', 'recipient', 'message', 'timestamp', 'phone'],
        'required_columns': ['sender', 'recipient', 'timestamp'],
        'pipeline': 'telecom_call_pipeline',  # Use same pipeline as call records for now
        'output_type': 'message'
    },
    
    'whatsapp_export': {
        'description': 'WhatsApp chat export',
        'patterns': [
            r'.*whatsapp.*\.(txt|csv|json)$',
            r'.*chat.*export.*\.(txt|csv)$',
        ],
        'keywords': ['whatsapp', 'chat', 'message', 'timestamp'],
        'required_columns': [],
        'pipeline': 'whatsapp_processing_pipeline',
        'output_type': 'message'
    },
    
    'forensic_metadata': {
        'description': 'Forensic file metadata (JSON)',
        'patterns': [
            r'.*metadata.*\.json$',
            r'.*filesystem.*\.json$',
            r'.*forensic.*\.json$',
        ],
        'keywords': ['file_path', 'created_time', 'modified_time', 'hash'],
        'required_columns': [],
        'pipeline': 'forensic_metadata_pipeline',
        'output_type': 'file_metadata'
    },
    
    'social_media': {
        'description': 'Social media export (JSON)',
        'patterns': [
            r'.*facebook.*\.json$',
            r'.*instagram.*\.json$',
            r'.*twitter.*\.json$',
            r'.*social.*\.json$',
        ],
        'keywords': ['posts', 'friends', 'messages', 'profile'],
        'required_columns': [],
        'pipeline': 'social_media_pipeline',
        'output_type': 'social_media'
    }
}


def detect_file_type_by_name(filename: str) -> Optional[str]:
    """
    Detect file type based on filename pattern
    
    Args:
        filename: Name of the file
        
    Returns:
        File type key or None
    """
    filename_lower = filename.lower()
    
    for file_type, config in FILE_PROCESSORS.items():
        for pattern in config['patterns']:
            if re.match(pattern, filename_lower, re.IGNORECASE):
                logger.info(f"Matched {filename} to {file_type} by pattern: {pattern}")
                return file_type
    
    return None


def detect_file_type_by_content(file_content: bytes, filename: str) -> Optional[str]:
    """
    Detect file type by reading first lines and checking for keywords
    
    Args:
        file_content: File content as bytes
        filename: Filename for extension check
        
    Returns:
        File type key or None
    """
    # Try CSV detection
    if filename.lower().endswith('.csv'):
        try:
            # Read first 5 lines
            lines = file_content.decode('utf-8', errors='ignore').split('\n')[:5]
            header = lines[0].lower() if lines else ""
            
            # Check each file type
            for file_type, config in FILE_PROCESSORS.items():
                keyword_matches = sum(1 for keyword in config['keywords'] if keyword in header)
                
                # If at least 2 keywords match, it's probably this type
                if keyword_matches >= 2:
                    logger.info(f"Matched content to {file_type} ({keyword_matches} keywords)")
                    return file_type
        except Exception as e:
            logger.warning(f"Error detecting CSV type: {e}")
    
    # Try JSON detection
    elif filename.lower().endswith('.json'):
        try:
            import json
            # Read first 1KB to check structure
            preview = file_content[:1024].decode('utf-8', errors='ignore')
            
            for file_type, config in FILE_PROCESSORS.items():
                keyword_matches = sum(1 for keyword in config['keywords'] if keyword in preview.lower())
                
                if keyword_matches >= 2:
                    logger.info(f"Matched JSON to {file_type} ({keyword_matches} keywords)")
                    return file_type
        except Exception as e:
            logger.warning(f"Error detecting JSON type: {e}")
    
    return None


def detect_file_type(filename: str, file_content: Optional[bytes] = None) -> Dict:
    """
    Comprehensive file type detection
    
    Args:
        filename: Name of the file
        file_content: Optional file content for deeper inspection
        
    Returns:
        Dict with detection results
    """
    # Try filename pattern first (fast)
    file_type = detect_file_type_by_name(filename)
    confidence = "high" if file_type else "none"
    
    # If no match or low confidence, try content inspection
    if not file_type and file_content:
        file_type = detect_file_type_by_content(file_content, filename)
        confidence = "medium" if file_type else "none"
    
    if file_type:
        processor_config = FILE_PROCESSORS[file_type]
        return {
            'file_type': file_type,
            'confidence': confidence,
            'description': processor_config['description'],
            'pipeline': processor_config['pipeline'],
            'output_type': processor_config['output_type'],
            'processor_config': processor_config
        }
    else:
        return {
            'file_type': 'unknown',
            'confidence': 'none',
            'description': 'Unknown file type',
            'pipeline': None,
            'output_type': None,
            'processor_config': None
        }


def validate_csv_structure(file_content: bytes, required_columns: List[str]) -> Dict:
    """
    Validate CSV has required columns
    
    Args:
        file_content: CSV file content
        required_columns: List of required column names
        
    Returns:
        Dict with validation results
    """
    try:
        import pandas as pd
        
        # Read first few lines to check structure
        df = pd.read_csv(io.BytesIO(file_content), nrows=5)
        
        # Normalize column names (lowercase, strip)
        df.columns = df.columns.str.lower().str.strip()
        
        # Check for required columns
        missing_columns = [col for col in required_columns if col.lower() not in df.columns]
        
        if missing_columns:
            return {
                'valid': False,
                'error': f"Missing required columns: {', '.join(missing_columns)}",
                'found_columns': list(df.columns),
                'missing_columns': missing_columns
            }
        
        return {
            'valid': True,
            'columns': list(df.columns),
            'row_count_preview': len(df)
        }
        
    except Exception as e:
        return {
            'valid': False,
            'error': f"CSV validation error: {str(e)}"
        }


def get_processor_for_source_type(source_type: str) -> Optional[str]:
    """
    Get pipeline name for given source type
    
    Args:
        source_type: Source type from data_sources table
        
    Returns:
        Pipeline name or None
    """
    # Map source_type to file_type
    type_mapping = {
        'bank': 'bank_transactions',
        'telecom': 'call_records',
        'sms': 'sms_records',
        'whatsapp': 'whatsapp_export',
        'forensic': 'forensic_metadata',
        'social_media': 'social_media'
    }
    
    file_type = type_mapping.get(source_type.lower())
    if file_type and file_type in FILE_PROCESSORS:
        return FILE_PROCESSORS[file_type]['pipeline']
    
    return None
