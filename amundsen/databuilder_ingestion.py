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

if __name__ == "__main__":
    try:
        success = create_metadata()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\nMake sure:")
        print("  1. Amundsen services are running: docker-compose ps | grep amundsen")
        print("  2. Neo4j is accessible: curl http://localhost:7474")
        print("  3. Python neo4j driver is installed: pip install neo4j")
        sys.exit(1)
