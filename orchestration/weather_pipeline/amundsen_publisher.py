"""
Amundsen Metadata Publisher
Syncs Dagster asset metadata to Amundsen data catalog
"""

import os
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime
import json


class AmundsenPublisher:
    """
    Publishes dataset metadata to Amundsen catalog
    
    Features:
    - Dataset descriptions and ownership
    - Column-level schema with descriptions
    - Quality badges (data quality scores)
    - Tags and classification
    - Lineage links to Marquez
    - Usage statistics
    """
    
    def __init__(self, amundsen_url: str = None):
        self.amundsen_url = amundsen_url or os.getenv("AMUNDSEN_METADATA_URL", "http://amundsen-metadata:5000")
        self.session = requests.Session()
        
    def publish_table_metadata(
        self,
        database: str,
        cluster: str,
        schema: str,
        table: str,
        description: str,
        columns: List[Dict[str, Any]],
        owners: List[str],
        tags: List[str] = None,
        quality_score: float = None,
        row_count: int = None,
        last_updated: datetime = None,
        source_uri: str = None,
        marquez_job: str = None
    ) -> bool:
        """
        Publish table metadata to Amundsen
        
        Args:
            database: Database name (e.g., 'minio', 'postgres')
            cluster: Cluster/environment (e.g., 'production')
            schema: Schema name (e.g., 'bronze', 'silver', 'weather')
            table: Table/dataset name
            description: Human-readable description
            columns: List of column definitions with name, type, description
            owners: List of owner emails/usernames
            tags: Classification tags (e.g., ['weather', 'external-api'])
            quality_score: Data quality score (0-100)
            row_count: Number of rows in dataset
            last_updated: Last update timestamp
            source_uri: S3/MinIO URI or connection string
            marquez_job: Related Marquez job name for lineage link
            
        Returns:
            bool: Success status
        """
        
        # Build table key (unique identifier in Amundsen)
        table_key = f"{database}://{cluster}.{schema}/{table}"
        
        try:
            # 1. Create/update table entity
            table_metadata = {
                "key": table_key,
                "name": table,
                "schema": schema,
                "cluster": cluster,
                "database": database,
                "description": description,
                "is_view": False,
                "tags": tags or [],
                "badges": self._generate_badges(quality_score),
                "programmatic_descriptions": self._generate_programmatic_descriptions(
                    quality_score, row_count, last_updated, source_uri, marquez_job
                )
            }
            
            response = self.session.put(
                f"{self.amundsen_url}/table",
                json=table_metadata
            )
            
            if response.status_code not in [200, 201]:
                print(f"⚠️  Failed to publish table {table_key}: {response.text}")
                return False
                
            print(f"✅ Published table metadata: {table_key}")
            
            # 2. Publish column metadata
            for col in columns:
                self._publish_column(table_key, col)
            
            # 3. Add ownership
            for owner in owners:
                self._add_owner(table_key, owner)
            
            return True
            
        except Exception as e:
            print(f"❌ Error publishing to Amundsen: {str(e)}")
            return False
    
    def _publish_column(self, table_key: str, column: Dict[str, Any]) -> bool:
        """Publish individual column metadata"""
        try:
            col_name = column.get("name")
            col_type = column.get("type", "string")
            col_desc = column.get("description", "")
            col_badges = column.get("badges", [])
            
            # Column stats (optional)
            stats = {}
            if "null_count" in column:
                stats["null_count"] = column["null_count"]
            if "unique_count" in column:
                stats["unique_count"] = column["unique_count"]
            if "min" in column:
                stats["min"] = str(column["min"])
            if "max" in column:
                stats["max"] = str(column["max"])
            
            column_metadata = {
                "key": f"{table_key}/{col_name}",
                "name": col_name,
                "type": col_type,
                "description": col_desc,
                "badges": col_badges,
                "stats": stats
            }
            
            response = self.session.put(
                f"{self.amundsen_url}/column",
                json=column_metadata
            )
            
            if response.status_code in [200, 201]:
                print(f"  ✓ Column: {col_name}")
                return True
            else:
                print(f"  ⚠️  Failed to publish column {col_name}")
                return False
                
        except Exception as e:
            print(f"  ❌ Error publishing column: {str(e)}")
            return False
    
    def _add_owner(self, table_key: str, owner: str) -> bool:
        """Add owner to table"""
        try:
            owner_metadata = {
                "key": table_key,
                "owner": owner
            }
            
            response = self.session.put(
                f"{self.amundsen_url}/table_owner",
                json=owner_metadata
            )
            
            if response.status_code in [200, 201]:
                print(f"  ✓ Owner: {owner}")
                return True
            else:
                return False
                
        except Exception as e:
            print(f"  ❌ Error adding owner: {str(e)}")
            return False
    
    def _generate_badges(self, quality_score: float = None) -> List[Dict[str, str]]:
        """Generate quality badges based on score"""
        badges = []
        
        if quality_score is not None:
            if quality_score >= 95:
                badges.append({
                    "badge_name": "high_quality",
                    "category": "data_quality"
                })
            elif quality_score >= 80:
                badges.append({
                    "badge_name": "good_quality",
                    "category": "data_quality"
                })
            elif quality_score < 80:
                badges.append({
                    "badge_name": "needs_attention",
                    "category": "data_quality"
                })
        
        return badges
    
    def _generate_programmatic_descriptions(
        self,
        quality_score: float = None,
        row_count: int = None,
        last_updated: datetime = None,
        source_uri: str = None,
        marquez_job: str = None
    ) -> Dict[str, str]:
        """Generate programmatic descriptions (key-value metadata)"""
        descriptions = {}
        
        if quality_score is not None:
            descriptions["quality_score"] = f"{quality_score:.1f}%"
        
        if row_count is not None:
            descriptions["row_count"] = f"{row_count:,}"
        
        if last_updated:
            descriptions["last_updated"] = last_updated.strftime("%Y-%m-%d %H:%M:%S")
        
        if source_uri:
            descriptions["source_uri"] = source_uri
        
        if marquez_job:
            descriptions["lineage_job"] = marquez_job
            descriptions["marquez_url"] = f"http://localhost:5001/#/jobs/{marquez_job}"
        
        return descriptions
    
    def search_tables(self, query: str, max_results: int = 10) -> List[Dict]:
        """
        Search for tables in Amundsen
        
        Args:
            query: Search term
            max_results: Maximum number of results
            
        Returns:
            List of table metadata dictionaries
        """
        try:
            response = self.session.get(
                f"{self.amundsen_url}/search/table",
                params={"query": query, "page_index": 0, "index": max_results}
            )
            
            if response.status_code == 200:
                return response.json().get("results", [])
            else:
                print(f"⚠️  Search failed: {response.text}")
                return []
                
        except Exception as e:
            print(f"❌ Search error: {str(e)}")
            return []
    
    def get_table_metadata(self, table_key: str) -> Optional[Dict]:
        """
        Retrieve table metadata from Amundsen
        
        Args:
            table_key: Table identifier (format: database://cluster.schema/table)
            
        Returns:
            Table metadata dictionary or None
        """
        try:
            response = self.session.get(
                f"{self.amundsen_url}/table",
                params={"key": table_key}
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"⚠️  Failed to retrieve {table_key}")
                return None
                
        except Exception as e:
            print(f"❌ Error retrieving metadata: {str(e)}")
            return None


def publish_weather_assets_to_amundsen():
    """
    Convenience function to publish all weather pipeline assets to Amundsen
    Can be called manually or from a Dagster sensor
    """
    publisher = AmundsenPublisher()
    
    # Define asset metadata
    assets = [
        {
            "database": "minio",
            "cluster": "production",
            "schema": "bronze",
            "table": "weather",
            "description": "Raw weather data from Open-Meteo API for 7 major Dutch cities. Ingested hourly with temperature, humidity, wind speed, and weather codes.",
            "columns": [
                {"name": "city", "type": "string", "description": "City name (Amsterdam, Rotterdam, Den Haag, Utrecht, Eindhoven, Groningen, Maastricht)"},
                {"name": "timestamp", "type": "timestamp", "description": "Observation timestamp (UTC)"},
                {"name": "temperature", "type": "float", "description": "Temperature in Celsius"},
                {"name": "humidity", "type": "int", "description": "Relative humidity percentage (0-100)"},
                {"name": "wind_speed", "type": "float", "description": "Wind speed in km/h"},
                {"name": "weather_code", "type": "int", "description": "WMO weather code (0=clear, 1-3=cloudy, 45=fog, 61=rain, etc.)"},
                {"name": "latitude", "type": "float", "description": "City latitude coordinate"},
                {"name": "longitude", "type": "float", "description": "City longitude coordinate"}
            ],
            "owners": ["data-engineering-team"],
            "tags": ["weather", "bronze-layer", "external-api", "hourly"],
            "marquez_job": "raw_weather_data"
        },
        {
            "database": "minio",
            "cluster": "production",
            "schema": "silver",
            "table": "weather",
            "description": "Cleaned and enriched weather data. Includes feels-like temperature calculation and weather condition labels. Quality validated and ready for analytics.",
            "columns": [
                {"name": "city", "type": "string", "description": "City name"},
                {"name": "timestamp", "type": "timestamp", "description": "Observation timestamp (UTC)"},
                {"name": "temperature", "type": "float", "description": "Temperature in Celsius"},
                {"name": "humidity", "type": "int", "description": "Relative humidity percentage"},
                {"name": "wind_speed", "type": "float", "description": "Wind speed in km/h"},
                {"name": "weather_code", "type": "int", "description": "WMO weather code"},
                {"name": "feels_like_temp", "type": "float", "description": "Calculated feels-like temperature based on wind chill and humidity"},
                {"name": "weather_condition", "type": "string", "description": "Human-readable weather condition (Clear, Cloudy, Rain, Snow, etc.)"},
                {"name": "latitude", "type": "float", "description": "City latitude"},
                {"name": "longitude", "type": "float", "description": "City longitude"}
            ],
            "owners": ["data-engineering-team"],
            "tags": ["weather", "silver-layer", "curated", "analytics-ready"],
            "marquez_job": "clean_weather_data"
        },
        {
            "database": "postgres",
            "cluster": "production",
            "schema": "weather",
            "table": "observations",
            "description": "Weather observations stored in PostgreSQL data warehouse. Final gold layer dataset serving dashboards and APIs. Updated hourly with latest weather data.",
            "columns": [
                {"name": "city", "type": "varchar(100)", "description": "City name"},
                {"name": "timestamp", "type": "timestamptz", "description": "Observation timestamp with timezone"},
                {"name": "temperature", "type": "numeric(5,2)", "description": "Temperature in Celsius"},
                {"name": "humidity", "type": "integer", "description": "Relative humidity percentage"},
                {"name": "wind_speed", "type": "numeric(5,2)", "description": "Wind speed in km/h"},
                {"name": "weather_code", "type": "integer", "description": "WMO weather code"},
                {"name": "feels_like_temp", "type": "numeric(5,2)", "description": "Calculated feels-like temperature"},
                {"name": "weather_condition", "type": "varchar(50)", "description": "Weather condition label"},
                {"name": "latitude", "type": "numeric(10,7)", "description": "City latitude"},
                {"name": "longitude", "type": "numeric(10,7)", "description": "City longitude"}
            ],
            "owners": ["data-engineering-team", "analytics-team"],
            "tags": ["weather", "gold-layer", "postgres", "production"],
            "marquez_job": "weather_to_postgres"
        }
    ]
    
    # Publish all assets
    success_count = 0
    for asset in assets:
        print(f"\n📝 Publishing: {asset['schema']}.{asset['table']}")
        if publisher.publish_table_metadata(**asset):
            success_count += 1
    
    print(f"\n✅ Successfully published {success_count}/{len(assets)} assets to Amundsen")
    return success_count == len(assets)


if __name__ == "__main__":
    # Test the publisher
    print("🚀 Testing Amundsen metadata publisher...")
    publish_weather_assets_to_amundsen()
