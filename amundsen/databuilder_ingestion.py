#!/usr/bin/env python3
"""
Amundsen Databuilder Ingestion
Load cell tower metadata into Amundsen using direct Neo4j connection
"""

from neo4j import GraphDatabase
import sys

# Neo4j connection
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "test"

def create_metadata():
    """Create complete metadata structure in Neo4j"""
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        print("=== Creating Cell Tower Metadata in Amundsen ===\n")
        
        # 1. Create Database node
        print("1. Creating database node...")
        session.run("""
            MERGE (db:Database {key: 'postgres://dataplatform'})
            ON CREATE SET 
                db.name = 'postgres',
                db.cluster = 'dataplatform'
        """)
        
        # 2. Create Schema node
        print("2. Creating schema node...")
        session.run("""
            MERGE (schema:Schema {key: 'postgres://dataplatform.cell_towers'})
            ON CREATE SET
                schema.name = 'cell_towers'
            WITH schema
            MATCH (db:Database {key: 'postgres://dataplatform'})
            MERGE (db)-[:SCHEMA]->(schema)
        """)
        
        # 3. Create Table node
        print("3. Creating table node...")
        session.run("""
            MERGE (table:Table {key: 'postgres://dataplatform.cell_towers/clean_204'})
            ON CREATE SET
                table.name = 'clean_204',
                table.database = 'postgres',
                table.cluster = 'dataplatform',
                table.schema = 'cell_towers',
                table.description = 'Cleaned and validated cell tower data for the Netherlands (MCC 204). Contains location and technical information for 47,114 cell tower installations across all major carriers (KPN, Vodafone, T-Mobile). Data quality: 97% with 45,749 unique cells.',
                table.is_view = false
            WITH table
            MATCH (schema:Schema {key: 'postgres://dataplatform.cell_towers'})
            MERGE (schema)-[:TABLE]->(table)
        """)
        
        # 4. Create columns
        print("4. Creating columns...")
        columns = [
            ("radio", "VARCHAR", 0, "Radio Access Technology (RAT): GSM (2G), UMTS (3G), LTE (4G), or NR (5G)"),
            ("mcc", "INTEGER", 1, "Mobile Country Code - Always 204 for Netherlands (ITU-T E.212 standard)"),
            ("net", "INTEGER", 2, "Mobile Network Code (MNC) - Identifies the carrier (e.g., KPN, Vodafone, T-Mobile)"),
            ("area", "INTEGER", 3, "Location Area Code (LAC) - Geographic area identifier for network routing"),
            ("cell", "BIGINT", 4, "Cell ID - Unique identifier for the cell tower within the network"),
            ("unit", "INTEGER", 5, "Unit identifier - Optional sub-cell identifier (can be NULL)"),
            ("lon", "DOUBLE PRECISION", 6, "Longitude coordinate (WGS84) - ⚠️ SENSITIVE: Contains precise location data subject to GDPR"),
            ("lat", "DOUBLE PRECISION", 7, "Latitude coordinate (WGS84) - ⚠️ SENSITIVE: Contains precise location data subject to GDPR"),
            ("range", "INTEGER", 8, "Cell tower coverage range in meters - Indicates signal reach"),
            ("samples", "INTEGER", 9, "Number of measurement samples used for positioning accuracy"),
            ("changeable", "INTEGER", 10, "Flag indicating if location data can change (1=changeable, 0=fixed)"),
            ("created", "BIGINT", 11, "Unix timestamp when the record was created in the database"),
            ("updated", "BIGINT", 12, "Unix timestamp when the record was last updated"),
            ("averagesignal", "INTEGER", 13, "Average signal strength in dBm (negative values, e.g., -75 dBm)")
        ]
        
        for col_name, col_type, sort_order, description in columns:
            session.run("""
                MERGE (col:Column {key: $col_key})
                ON CREATE SET
                    col.name = $name,
                    col.type = $type,
                    col.sort_order = $sort_order,
                    col.description = $description
                WITH col
                MATCH (table:Table {key: 'postgres://dataplatform.cell_towers/clean_204'})
                MERGE (table)-[:COLUMN]->(col)
            """, col_key=f'postgres://dataplatform.cell_towers/clean_204/{col_name}',
                 name=col_name, type=col_type, sort_order=sort_order, description=description)
            print(f"   ✓ {col_name} ({col_type})")
        
        # 5. Create tags
        print("\n5. Creating tags...")
        tags = [
            ("telecommunications", "Business domain for telecom infrastructure data"),
            ("netherlands", "Geographic scope: Netherlands (MCC 204)"),
            ("production", "Production dataset - actively used in operations"),
            ("geo-data", "Contains geographic coordinates and location information"),
            ("pii", "Contains Personally Identifiable Information - handle with care")
        ]
        
        for tag_name, tag_desc in tags:
            session.run("""
                MERGE (tag:Tag {key: $tag_key})
                ON CREATE SET
                    tag.tag_type = 'default',
                    tag.tag_name = $tag_name,
                    tag.description = $description
                WITH tag
                MATCH (table:Table {key: 'postgres://dataplatform.cell_towers/clean_204'})
                MERGE (table)-[:TAGGED_BY]->(tag)
            """, tag_key=f'tag://{tag_name}', tag_name=tag_name, description=tag_desc)
            print(f"   ✓ {tag_name}")
        
        # 6. Add PII tags to lat/lon columns
        print("\n6. Marking PII columns...")
        for col in ['lon', 'lat']:
            session.run("""
                MATCH (col:Column {key: $col_key})
                MATCH (tag:Tag {key: 'tag://pii'})
                MERGE (col)-[:TAGGED_BY]->(tag)
            """, col_key=f'postgres://dataplatform.cell_towers/clean_204/{col}')
            print(f"   ✓ {col} marked as PII")
        
        # 7. Create owner/user
        print("\n7. Setting data ownership...")
        session.run("""
            MERGE (user:User {key: 'data-engineering@company.com'})
            ON CREATE SET
                user.email = 'data-engineering@company.com',
                user.first_name = 'Data Engineering',
                user.last_name = 'Team',
                user.full_name = 'Data Engineering Team'
            WITH user
            MATCH (table:Table {key: 'postgres://dataplatform.cell_towers/clean_204'})
            MERGE (table)-[:OWNER]->(user)
        """)
        print("   ✓ Owner: Data Engineering Team")
        
        # 8. Add statistics
        print("\n8. Adding table statistics...")
        session.run("""
            MATCH (table:Table {key: 'postgres://dataplatform.cell_towers/clean_204'})
            MERGE (stat:Stat {key: 'postgres://dataplatform.cell_towers/clean_204/record_count'})
            ON CREATE SET
                stat.stat_name = 'record_count',
                stat.stat_val = '47114',
                stat.start_epoch = 1728672000,
                stat.end_epoch = 1728672000
            MERGE (table)-[:STAT]->(stat)
            
            MERGE (stat2:Stat {key: 'postgres://dataplatform.cell_towers/clean_204/unique_cells'})
            ON CREATE SET
                stat2.stat_name = 'unique_cells',
                stat2.stat_val = '45749',
                stat2.start_epoch = 1728672000,
                stat2.end_epoch = 1728672000
            MERGE (table)-[:STAT]->(stat2)
            
            MERGE (stat3:Stat {key: 'postgres://dataplatform.cell_towers/clean_204/data_quality'})
            ON CREATE SET
                stat3.stat_name = 'data_quality',
                stat3.stat_val = '97%',
                stat3.start_epoch = 1728672000,
                stat3.end_epoch = 1728672000
            MERGE (table)-[:STAT]->(stat3)
        """)
        print("   ✓ record_count: 47,114")
        print("   ✓ unique_cells: 45,749")
        print("   ✓ data_quality: 97%")
        
        # 9. Add programmatic description (quality report)
        print("\n9. Adding quality report...")
        session.run("""
            MATCH (table:Table {key: 'postgres://dataplatform.cell_towers/clean_204'})
            MERGE (desc:Programmatic_Description {
                key: 'postgres://dataplatform.cell_towers/clean_204/_quality_report_'
            })
            ON CREATE SET
                desc.description_source = 'quality_report',
                desc.description = 'Data Quality Report: 97% quality score. Dataset contains 47,114 total records with 45,749 unique cell towers. All records validated for geographic coordinates within Netherlands boundaries. Signal strength measurements available for 98% of records.'
            MERGE (table)-[:DESCRIPTION]->(desc)
        """)
        print("   ✓ Quality report added")
        
        print("\n✅ Metadata successfully loaded into Amundsen!")
        print(f"\n📊 Summary:")
        print(f"   • Database: postgres://dataplatform")
        print(f"   • Schema: cell_towers")
        print(f"   • Table: clean_204")
        print(f"   • Columns: 14")
        print(f"   • Tags: 5")
        print(f"   • Statistics: 3")
        print(f"\n🌐 View in Amundsen UI: http://localhost:5005")
        
    driver.close()
    return True


def create_weather_metadata():
    """Create weather metadata structure in Neo4j"""
    
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        print("\n=== Creating Weather Metadata in Amundsen ===\n")
        
        # 1. Create/Get Database node
        print("1. Creating database node...")
        session.run("""
            MERGE (db:Database {key: 'postgres://dataplatform'})
            ON CREATE SET 
                db.name = 'postgres',
                db.cluster = 'dataplatform'
        """)
        
        # 2. Create Schema node
        print("2. Creating weather schema node...")
        session.run("""
            MERGE (schema:Schema {key: 'postgres://dataplatform.weather'})
            ON CREATE SET
                schema.name = 'weather'
            WITH schema
            MATCH (db:Database {key: 'postgres://dataplatform'})
            MERGE (db)-[:SCHEMA]->(schema)
        """)
        
        # 3. Create STATIONS Table
        print("3. Creating stations table...")
        session.run("""
            MERGE (table:Table {key: 'postgres://dataplatform.weather/stations'})
            ON CREATE SET
                table.name = 'stations',
                table.database = 'postgres',
                table.cluster = 'dataplatform',
                table.schema = 'weather',
                table.description = 'Weather station dimension table. Contains geographic coordinates and metadata for 7 major Dutch cities: Amsterdam, Rotterdam, Den Haag, Utrecht, Eindhoven, Groningen, and Maastricht. Updated hourly via Dagster orchestration.',
                table.is_view = false
            WITH table
            MATCH (schema:Schema {key: 'postgres://dataplatform.weather'})
            MERGE (schema)-[:TABLE]->(table)
        """)
        
        # 4. Create stations columns
        print("4. Creating stations columns...")
        stations_columns = [
            ("station_name", "VARCHAR(100)", "Primary key - Name of the weather station (city name)"),
            ("latitude", "FLOAT", "Geographic latitude coordinate (WGS84)"),
            ("longitude", "FLOAT", "Geographic longitude coordinate (WGS84)"),
            ("elevation", "FLOAT", "Station elevation above sea level (nullable)"),
            ("country", "VARCHAR(100)", "Country name (Netherlands)"),
            ("created_at", "TIMESTAMP", "Record creation timestamp"),
            ("updated_at", "TIMESTAMP", "Last update timestamp")
        ]
        
        for col_name, col_type, col_desc in stations_columns:
            session.run("""
                MATCH (table:Table {key: 'postgres://dataplatform.weather/stations'})
                MERGE (col:Column {key: 'postgres://dataplatform.weather/stations/' + $col_name})
                ON CREATE SET
                    col.name = $col_name,
                    col.type = $col_type,
                    col.description = $col_desc,
                    col.sort_order = $sort_order
                MERGE (table)-[:COLUMN]->(col)
            """, col_name=col_name, col_type=col_type, col_desc=col_desc, 
                sort_order=stations_columns.index((col_name, col_type, col_desc)))
        print(f"   ✓ Created {len(stations_columns)} columns")
        
        # 5. Create OBSERVATIONS Table
        print("\n5. Creating observations table...")
        session.run("""
            MERGE (table:Table {key: 'postgres://dataplatform.weather/observations'})
            ON CREATE SET
                table.name = 'observations',
                table.database = 'postgres',
                table.cluster = 'dataplatform',
                table.schema = 'weather',
                table.description = 'Weather observations fact table. Hourly weather measurements from Open-Meteo API including temperature, humidity, wind speed, pressure, and calculated feels-like temperature. Data quality validated by Dagster pipeline (100% pass rate).',
                table.is_view = false
            WITH table
            MATCH (schema:Schema {key: 'postgres://dataplatform.weather'})
            MERGE (schema)-[:TABLE]->(table)
        """)
        
        # 6. Create observations columns
        print("6. Creating observations columns...")
        obs_columns = [
            ("id", "INTEGER", "Auto-increment primary key"),
            ("station_name", "VARCHAR(100)", "Foreign key to stations.station_name"),
            ("timestamp", "TIMESTAMP", "Observation timestamp (UTC)"),
            ("temperature", "FLOAT", "Temperature in Celsius"),
            ("humidity", "INTEGER", "Relative humidity percentage (0-100)"),
            ("precipitation", "FLOAT", "Precipitation in mm"),
            ("rain", "FLOAT", "Rain amount in mm"),
            ("wind_speed", "FLOAT", "Wind speed in km/h"),
            ("wind_direction", "INTEGER", "Wind direction in degrees (0-360)"),
            ("pressure", "FLOAT", "Atmospheric pressure in hPa"),
            ("feels_like_temp", "FLOAT", "Calculated feels-like temperature using wind chill formula"),
            ("ingestion_time", "TIMESTAMP", "When data was ingested from API"),
            ("processed_at", "TIMESTAMP", "When data quality checks completed"),
            ("data_quality", "VARCHAR(50)", "Quality validation status"),
            ("created_at", "TIMESTAMP", "Record creation timestamp")
        ]
        
        for col_name, col_type, col_desc in obs_columns:
            session.run("""
                MATCH (table:Table {key: 'postgres://dataplatform.weather/observations'})
                MERGE (col:Column {key: 'postgres://dataplatform.weather/observations/' + $col_name})
                ON CREATE SET
                    col.name = $col_name,
                    col.type = $col_type,
                    col.description = $col_desc,
                    col.sort_order = $sort_order
                MERGE (table)-[:COLUMN]->(col)
            """, col_name=col_name, col_type=col_type, col_desc=col_desc,
                sort_order=obs_columns.index((col_name, col_type, col_desc)))
        print(f"   ✓ Created {len(obs_columns)} columns")
        
        # 7. Create WEATHER_NEAR_TOWERS View
        print("\n7. Creating weather_near_towers view...")
        session.run("""
            MERGE (table:Table {key: 'postgres://dataplatform.weather/weather_near_towers'})
            ON CREATE SET
                table.name = 'weather_near_towers',
                table.database = 'postgres',
                table.cluster = 'dataplatform',
                table.schema = 'weather',
                table.description = 'Analytics view combining weather observations with nearby cell towers. Uses Haversine formula to calculate distances within 50km radius. Enables analysis of weather conditions near 47k cell tower installations. Updated hourly.',
                table.is_view = true
            WITH table
            MATCH (schema:Schema {key: 'postgres://dataplatform.weather'})
            MERGE (schema)-[:TABLE]->(table)
        """)
        
        # 8. Create view columns
        print("8. Creating view columns...")
        view_columns = [
            ("radio", "TEXT", "Radio technology (GSM, UMTS, LTE)"),
            ("mcc", "INTEGER", "Mobile Country Code (204 = Netherlands)"),
            ("net", "INTEGER", "Mobile Network Code (carrier identifier)"),
            ("area", "INTEGER", "Location Area Code"),
            ("cell", "INTEGER", "Cell ID"),
            ("tower_lon", "FLOAT", "Cell tower longitude"),
            ("tower_lat", "FLOAT", "Cell tower latitude"),
            ("station_name", "VARCHAR(100)", "Weather station name"),
            ("distance_km", "FLOAT", "Distance from tower to station (Haversine)"),
            ("observation_time", "TIMESTAMP", "Weather observation timestamp"),
            ("temperature", "FLOAT", "Temperature in Celsius"),
            ("humidity", "INTEGER", "Relative humidity percentage"),
            ("wind_speed", "FLOAT", "Wind speed in km/h"),
            ("wind_direction", "INTEGER", "Wind direction in degrees"),
            ("precipitation", "FLOAT", "Precipitation in mm"),
            ("pressure", "FLOAT", "Atmospheric pressure in hPa"),
            ("feels_like_temp", "FLOAT", "Calculated feels-like temperature")
        ]
        
        for col_name, col_type, col_desc in view_columns:
            session.run("""
                MATCH (table:Table {key: 'postgres://dataplatform.weather/weather_near_towers'})
                MERGE (col:Column {key: 'postgres://dataplatform.weather/weather_near_towers/' + $col_name})
                ON CREATE SET
                    col.name = $col_name,
                    col.type = $col_type,
                    col.description = $col_desc,
                    col.sort_order = $sort_order
                MERGE (table)-[:COLUMN]->(col)
            """, col_name=col_name, col_type=col_type, col_desc=col_desc,
                sort_order=view_columns.index((col_name, col_type, col_desc)))
        print(f"   ✓ Created {len(view_columns)} columns")
        
        # 9. Add tags to all weather tables
        print("\n9. Adding tags...")
        weather_tags = [
            ("weather", "Weather domain data"),
            ("orchestrated", "Managed by Dagster pipeline"),
            ("quality-checked", "Validated by data quality rules"),
            ("hourly", "Updated every hour"),
            ("open-meteo", "Source: Open-Meteo API")
        ]
        
        for tag_name, tag_desc in weather_tags:
            session.run("""
                MATCH (table:Table)
                WHERE table.schema = 'weather'
                MERGE (tag:Tag {key: 'weather/' + $tag_name})
                ON CREATE SET
                    tag.tag_name = $tag_name,
                    tag.tag_type = 'default'
                MERGE (table)-[:TAGGED_BY]->(tag)
            """, tag_name=tag_name, tag_desc=tag_desc)
        print(f"   ✓ Added {len(weather_tags)} tags")
        
        # 10. Add statistics
        print("\n10. Adding statistics...")
        session.run("""
            MATCH (table:Table {key: 'postgres://dataplatform.weather/stations'})
            MERGE (stat1:Stat {key: 'postgres://dataplatform.weather/stations/station_count'})
            ON CREATE SET
                stat1.stat_name = 'station_count',
                stat1.stat_val = '7',
                stat1.start_epoch = 1728738000,
                stat1.end_epoch = 1728738000
            MERGE (table)-[:STAT]->(stat1)
        """)
        
        session.run("""
            MATCH (table:Table {key: 'postgres://dataplatform.weather/observations'})
            MERGE (stat2:Stat {key: 'postgres://dataplatform.weather/observations/data_quality'})
            ON CREATE SET
                stat2.stat_name = 'data_quality',
                stat2.stat_val = '100%',
                stat2.start_epoch = 1728738000,
                stat2.end_epoch = 1728738000
            MERGE (table)-[:STAT]->(stat2)
        """)
        
        session.run("""
            MATCH (view:Table {key: 'postgres://dataplatform.weather/weather_near_towers'})
            MERGE (stat3:Stat {key: 'postgres://dataplatform.weather/weather_near_towers/tower_coverage'})
            ON CREATE SET
                stat3.stat_name = 'tower_coverage',
                stat3.stat_val = '47,114',
                stat3.start_epoch = 1728738000,
                stat3.end_epoch = 1728738000
            MERGE (view)-[:STAT]->(stat3)
        """)
        print("   ✓ station_count: 7")
        print("   ✓ data_quality: 100%")
        print("   ✓ tower_coverage: 47,114")
        
        # 11. Add programmatic descriptions
        print("\n11. Adding quality reports...")
        session.run("""
            MATCH (table:Table {key: 'postgres://dataplatform.weather/observations'})
            MERGE (desc:Programmatic_Description {
                key: 'postgres://dataplatform.weather/observations/_dagster_quality_'
            })
            ON CREATE SET
                desc.description_source = 'dagster_quality',
                desc.description = 'Dagster Quality Report: 100% pass rate on 7 validation rules. Temperature range check (-30 to 45°C), humidity validation (0-100%), coordinate validation (Netherlands bounds), null value checks, and data freshness validation. Pipeline runs hourly with automatic quality gates.'
            MERGE (table)-[:DESCRIPTION]->(desc)
        """)
        print("   ✓ Quality report added to observations")
        
        print("\n✅ Weather metadata successfully loaded into Amundsen!")
        print(f"\n📊 Summary:")
        print(f"   • Schema: weather")
        print(f"   • Tables: 3 (stations, observations, weather_near_towers)")
        print(f"   • Total Columns: {len(stations_columns) + len(obs_columns) + len(view_columns)}")
        print(f"   • Tags: {len(weather_tags)}")
        print(f"   • Statistics: 3")
        
    driver.close()
    return True


if __name__ == "__main__":
    try:
        # Load cell towers metadata
        print("Loading Cell Towers metadata...")
        success1 = create_metadata()
        
        # Load weather metadata
        print("\n" + "="*60)
        success2 = create_weather_metadata()
        
        if success1 and success2:
            print("\n" + "="*60)
            print("🎉 ALL METADATA LOADED SUCCESSFULLY!")
            print("="*60)
            print("\n🌐 View in Amundsen UI: http://localhost:5005")
            print("Try searching for: clean_204, stations, observations, weather_near_towers")
        
        sys.exit(0 if (success1 and success2) else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Amundsen services are running: docker-compose ps | grep amundsen")
        print("  2. Neo4j is accessible: curl http://localhost:7474")
        print("  3. Python neo4j driver is installed: pip install neo4j")
        sys.exit(1)
