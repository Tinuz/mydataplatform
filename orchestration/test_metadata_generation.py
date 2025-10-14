"""
Test script to validate metadata generation
"""
import pandas as pd
import sys
sys.path.insert(0, '/opt/dagster/app')

from investigations.assets import generate_validation_metadata
import json

# Create test DataFrame
df = pd.DataFrame({
    'iban': ['NL91ABNA0417164300', 'NL02RABO0123456789', 'NL91ABNA0417164300', 'NL02RABO0123456789'],
    'bedrag': [150.50, 250.00, -50.00, 1000.00],
    'datum': pd.to_datetime(['2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04']),
    'omschrijving': ['Test 1', 'Test 2', 'Test 3', 'Test 4']
})

# Generate metadata
metadata = generate_validation_metadata(
    source_id='TEST-001',
    filename='test_metadata_validation.csv',
    file_type='bank_transactions',
    df=df,
    raw_file_size=256
)

# Print formatted JSON
print(json.dumps(metadata, indent=2, default=str))
