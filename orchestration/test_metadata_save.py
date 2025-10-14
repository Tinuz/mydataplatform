"""
Test complete metadata flow: generate and save to MinIO
"""
import pandas as pd
import sys
import json
import io
sys.path.insert(0, '/opt/dagster/app')

from investigations.assets import generate_validation_metadata, save_validation_metadata
from investigations.resources import MinioResource

# Create test DataFrame
df = pd.DataFrame({
    'iban': ['NL91ABNA0417164300', 'NL02RABO0123456789', 'NL91ABNA0417164300', 'NL02RABO0123456789'],
    'bedrag': [150.50, 250.00, -50.00, 1000.00],
    'datum': pd.to_datetime(['2025-10-01', '2025-10-02', '2025-10-03', '2025-10-04']),
    'omschrijving': ['Test 1', 'Test 2', 'Test 3', 'Test 4']
})

# Initialize MinIO resource
minio = MinioResource(
    endpoint='minio:9000',
    access_key='minioadmin',
    secret_key='minioadmin',
    bucket='investigations',
    secure=False
)

# Generate metadata
metadata = generate_validation_metadata(
    source_id='TEST-METADATA-001',
    filename='test_metadata_validation.csv',
    file_type='bank_transactions',
    df=df,
    raw_file_size=256
)

print("Generated metadata:")
print(json.dumps(metadata, indent=2, default=str))
print("\nSaving to MinIO...")

# Save to MinIO
try:
    save_validation_metadata(
        minio=minio,
        investigation_id='OND-2025-000002',
        source_id='TEST-METADATA-001',
        metadata=metadata
    )
    print("✅ Successfully saved metadata to MinIO!")
    print("Path: OND-2025-000002/metadata/TEST-METADATA-001_validation.json")
except Exception as e:
    print(f"❌ Error saving metadata: {e}")
    import traceback
    traceback.print_exc()
