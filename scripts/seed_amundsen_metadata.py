#!/usr/bin/env python3
"""
Seed Amundsen Neo4j with Weather Pipeline Metadata
Directly writes to Neo4j graph database using Cypher queries
"""

import os
from neo4j import GraphDatabase
from datetime import datetime


class AmundsenSeeder:
    """Seeds Amundsen Neo4j with dataset metadata"""
    
    def __init__(self, uri="bolt://localhost:7687", user="neo4j", password="test"):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
    
    def close(self):
        self.driver.close()
    
    def create_indexes(self):
        """Create Neo4j indexes for better performance"""
        with self.driver.session() as session:
            # Create indexes on key fields
            indexes = [
                "CREATE INDEX table_key_idx IF NOT EXISTS FOR (t:Table) ON (t.key)",
                "CREATE INDEX column_key_idx IF NOT EXISTS FOR (c:Column) ON (c.key)",
                "CREATE INDEX schema_key_idx IF NOT EXISTS FOR (s:Schema) ON (s.key)",
                "CREATE INDEX cluster_key_idx IF NOT EXISTS FOR (c:Cluster) ON (c.key)",
                "CREATE INDEX database_key_idx IF NOT EXISTS FOR (d:Database) ON (d.key)",
                "CREATE INDEX tag_key_idx IF NOT EXISTS FOR (t:Tag) ON (t.key)",
                "CREATE INDEX user_email_idx IF NOT EXISTS FOR (u:User) ON (u.email)",
            ]
            
            for index_query in indexes:
                try:
                    session.run(index_query)
                except Exception as e:
                    # Index might already exist
                    pass
            
            print("✅ Created Neo4j indexes for performance")
    
    def clear_existing_data(self):
        """Clear existing weather-related data"""
        with self.driver.session() as session:
            # Delete existing weather tables
            session.run("""
                MATCH (t:Table)
                WHERE t.key STARTS WITH 'minio://' OR t.key STARTS WITH 'postgres://dataplatform.weather'
                DETACH DELETE t
            """)
            print("✅ Cleared existing weather metadata")
    
    def create_table(self, session, table_key, table_name, schema, cluster, database, description, tags=None):
        """Create a table node in Neo4j"""
        
        query = """
        MERGE (db:Database {name: $database, key: $database})
        MERGE (clstr:Cluster {name: $cluster, key: $cluster})
        MERGE (schema:Schema {name: $schema, key: $database + '://' + $cluster + '.' + $schema})
        MERGE (tbl:Table {
            name: $table_name,
            key: $table_key,
            cluster: $cluster,
            database: $database,
            schema: $schema
        })
        MERGE (db)-[:CLUSTER]->(clstr)
        MERGE (clstr)-[:SCHEMA]->(schema)
        MERGE (schema)-[:TABLE]->(tbl)
        
        // Add description
        MERGE (tbl)-[:DESCRIPTION]->(tbl_dscrpt:Description {description: $description})
        
        // Set table attributes with defaults
        SET tbl.is_view = false,
            tbl.last_updated_timestamp = timestamp()
        
        RETURN tbl
        """
        
        result = session.run(query, 
            database=database,
            cluster=cluster,
            schema=schema,
            table_name=table_name,
            table_key=table_key,
            description=description
        )
        
        # Add tags
        if tags:
            for tag in tags:
                session.run("""
                    MATCH (tbl:Table {key: $table_key})
                    MERGE (tag:Tag {key: $tag, tag_type: 'default'})
                    SET tag.tag_count = coalesce(tag.tag_count, 0) + 1
                    MERGE (tbl)-[:TAGGED_BY]->(tag)
                """, table_key=table_key, tag=tag)
        
        print(f"✅ Created table: {table_key}")
        return result
    
    def add_column(self, session, table_key, column_name, column_type, description, col_order):
        """Add a column to a table"""
        
        column_key = f"{table_key}/{column_name}"
        
        query = """
        MATCH (tbl:Table {key: $table_key})
        MERGE (col:Column {
            name: $column_name,
            key: $column_key,
            type: $column_type,
            sort_order: $col_order,
            col_type: $column_type
        })
        MERGE (tbl)-[:COLUMN]->(col)
        MERGE (col)-[:DESCRIPTION]->(col_dscrpt:Description {description: $description})
        RETURN col
        """
        
        session.run(query,
            table_key=table_key,
            column_name=column_name,
            column_key=column_key,
            column_type=column_type,
            col_order=col_order,
            description=description
        )
    
    def add_owner(self, session, table_key, owner_email):
        """Add an owner to a table"""
        
        query = """
        MATCH (tbl:Table {key: $table_key})
        MERGE (user:User {email: $owner_email, key: $owner_email})
        MERGE (user)-[:OWNER_OF]->(tbl)
        RETURN user
        """
        
        session.run(query, table_key=table_key, owner_email=owner_email)
    
    def seed_bronze_weather(self):
        """Seed bronze layer weather dataset"""
        with self.driver.session() as session:
            table_key = "minio://production.bronze/weather"
            
            self.create_table(
                session,
                table_key=table_key,
                table_name="weather",
                schema="bronze",
                cluster="production",
                database="minio",
                description="Raw weather data from Open-Meteo API for 7 major Dutch cities. Ingested hourly with temperature, humidity, wind speed, and weather codes.",
                tags=["weather", "bronze-layer", "external-api", "hourly"]
            )
            
            # Add columns
            columns = [
                ("city", "string", "City name (Amsterdam, Rotterdam, Den Haag, Utrecht, Eindhoven, Groningen, Maastricht)", 0),
                ("timestamp", "timestamp", "Observation timestamp (UTC)", 1),
                ("temperature", "float", "Temperature in Celsius", 2),
                ("humidity", "int", "Relative humidity percentage (0-100)", 3),
                ("wind_speed", "float", "Wind speed in km/h", 4),
                ("weather_code", "int", "WMO weather code", 5),
                ("latitude", "float", "City latitude coordinate", 6),
                ("longitude", "float", "City longitude coordinate", 7)
            ]
            
            for col_name, col_type, col_desc, sort_order in columns:
                self.add_column(session, table_key, col_name, col_type, col_desc, sort_order)
            
            # Add owners
            self.add_owner(session, table_key, "data-engineering@company.com")
            
            print(f"  ✓ Added 8 columns")
            print(f"  ✓ Added owner: data-engineering@company.com")
    
    def seed_silver_weather(self):
        """Seed silver layer weather dataset"""
        with self.driver.session() as session:
            table_key = "minio://production.silver/weather"
            
            self.create_table(
                session,
                table_key=table_key,
                table_name="weather",
                schema="silver",
                cluster="production",
                database="minio",
                description="Cleaned and enriched weather data. Includes feels-like temperature calculation and weather condition labels. Quality validated and ready for analytics.",
                tags=["weather", "silver-layer", "curated", "analytics-ready"]
            )
            
            # Add columns
            columns = [
                ("city", "string", "City name", 0),
                ("timestamp", "timestamp", "Observation timestamp (UTC)", 1),
                ("temperature", "float", "Temperature in Celsius", 2),
                ("humidity", "int", "Relative humidity percentage", 3),
                ("wind_speed", "float", "Wind speed in km/h", 4),
                ("weather_code", "int", "WMO weather code", 5),
                ("feels_like_temp", "float", "Calculated feels-like temperature based on wind chill and humidity", 6),
                ("weather_condition", "string", "Human-readable weather condition (Clear, Cloudy, Rain, Snow, etc.)", 7),
                ("latitude", "float", "City latitude", 8),
                ("longitude", "float", "City longitude", 9)
            ]
            
            for col_name, col_type, col_desc, sort_order in columns:
                self.add_column(session, table_key, col_name, col_type, col_desc, sort_order)
            
            self.add_owner(session, table_key, "data-engineering@company.com")
            
            print(f"  ✓ Added 10 columns")
            print(f"  ✓ Added owner: data-engineering@company.com")
    
    def seed_gold_weather(self):
        """Seed gold layer weather dataset"""
        with self.driver.session() as session:
            table_key = "postgres://dataplatform.weather/observations"
            
            self.create_table(
                session,
                table_key=table_key,
                table_name="observations",
                schema="weather",
                cluster="dataplatform",
                database="postgres",
                description="Production-ready weather observations stored in PostgreSQL data warehouse. Serves dashboards, APIs, and business applications. Single source of truth for weather data.",
                tags=["weather", "gold-layer", "postgres", "production"]
            )
            
            # Add columns
            columns = [
                ("city", "varchar(100)", "City name", 0),
                ("timestamp", "timestamptz", "Observation timestamp with timezone", 1),
                ("temperature", "numeric(5,2)", "Temperature in Celsius", 2),
                ("humidity", "integer", "Relative humidity percentage (0-100)", 3),
                ("wind_speed", "numeric(5,2)", "Wind speed in km/h", 4),
                ("weather_code", "integer", "WMO weather code", 5),
                ("feels_like_temp", "numeric(5,2)", "Calculated feels-like temperature", 6),
                ("weather_condition", "varchar(50)", "Human-readable weather condition", 7),
                ("latitude", "numeric(10,7)", "City latitude", 8),
                ("longitude", "numeric(10,7)", "City longitude", 9)
            ]
            
            for col_name, col_type, col_desc, sort_order in columns:
                self.add_column(session, table_key, col_name, col_type, col_desc, sort_order)
            
            # Add owners
            self.add_owner(session, table_key, "data-engineering@company.com")
            self.add_owner(session, table_key, "analytics@company.com")
            
            print(f"  ✓ Added 10 columns")
            print(f"  ✓ Added owners: data-engineering, analytics")
    
    def run_seed(self):
        """Run complete seeding process"""
        print("🚀 Seeding Amundsen Neo4j with Weather Pipeline metadata...")
        print("=" * 70)
        
        try:
            # Create indexes first for performance
            self.create_indexes()
            print()
            
            # Clear existing data
            self.clear_existing_data()
            print()
            
            # Seed datasets
            print("📝 Seeding Bronze Layer...")
            self.seed_bronze_weather()
            print()
            
            print("📝 Seeding Silver Layer...")
            self.seed_silver_weather()
            print()
            
            print("📝 Seeding Gold Layer...")
            self.seed_gold_weather()
            print()
            
            print("=" * 70)
            print("✅ Successfully seeded Amundsen with 3 datasets!")
            print()
            print("🔍 View in Amundsen: http://localhost:5005")
            print("   Search for: 'weather', 'bronze', 'silver', 'observations'")
            
        except Exception as e:
            print(f"❌ Error seeding Amundsen: {str(e)}")
            raise


def main():
    # Neo4j connection details from docker-compose
    NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "test")
    
    seeder = AmundsenSeeder(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    
    try:
        seeder.run_seed()
    finally:
        seeder.close()


if __name__ == "__main__":
    main()
