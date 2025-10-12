"""
Sensors for Dagster Pipeline
Amundsen sync sensor - publishes metadata to data catalog
"""

import os
from dagster import sensor, DefaultSensorStatus

# Import Amundsen publisher
try:
    from .amundsen_publisher import publish_weather_assets_to_amundsen
    AMUNDSEN_PUBLISHER_AVAILABLE = True
except ImportError:
    AMUNDSEN_PUBLISHER_AVAILABLE = False
    print("⚠️  Amundsen publisher not available")


@sensor(
    name="amundsen_metadata_sync", 
    minimum_interval_seconds=300,  # Run every 5 minutes
    default_status=DefaultSensorStatus.RUNNING
)
def amundsen_sync_sensor(context):
    """
    Sensor that automatically syncs Dagster asset metadata to Amundsen catalog
    
    Triggers:
    - Every 5 minutes (configurable)
    - After successful asset materializations
    
    What it does:
    - Publishes table metadata (descriptions, owners, tags)
    - Publishes column schemas with descriptions
    - Adds data quality badges
    - Links to Marquez lineage graphs
    
    Usage:
    - Enables this sensor in Dagster UI or via CLI
    - Metadata will automatically appear in Amundsen
    - Data stewards can search and discover datasets
    """
    
    if not AMUNDSEN_PUBLISHER_AVAILABLE:
        context.log.warning("⚠️  Amundsen publisher not available - skipping sync")
        return
    
    try:
        context.log.info("🔄 Starting Amundsen metadata sync...")
        
        # Publish all weather assets to Amundsen
        success = publish_weather_assets_to_amundsen()
        
        if success:
            context.log.info("✅ Amundsen sync completed successfully")
        else:
            context.log.warning("⚠️  Amundsen sync completed with some failures")
        
    except Exception as e:
        context.log.error(f"❌ Amundsen sync failed: {str(e)}")
    
    # Sensor doesn't request any runs - it's a maintenance task
    return

