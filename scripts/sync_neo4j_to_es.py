#!/usr/bin/env python3
"""
Sync Amundsen Neo4j metadata to Elasticsearch for search
Simple direct sync without databuilder complexity
"""

import os
from neo4j import GraphDatabase
from elasticsearch import Elasticsearch
from datetime import datetime


class Neo4jToElasticsearchSync:
    """Syncs table metadata from Neo4j to Elasticsearch"""
    
    def __init__(self):
        # Neo4j connection
        self.neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        self.neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        self.neo4j_password = os.getenv('NEO4J_PASSWORD', 'test')
        self.neo4j_driver = GraphDatabase.driver(
            self.neo4j_uri,
            auth=(self.neo4j_user, self.neo4j_password)
        )
        
        # Elasticsearch connection
        self.es_host = os.getenv('ES_HOST', 'localhost')
        self.es_port = int(os.getenv('ES_PORT', '9200'))
        self.es_client = Elasticsearch([{
            'host': self.es_host,
            'port': self.es_port,
            'scheme': 'http'
        }])
        
        self.index_name = 'table_search_index'
    
    def close(self):
        self.neo4j_driver.close()
    
    def create_index(self):
        """Create Elasticsearch index with proper mappings"""
        
        index_body = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "analyzer": {
                        "default": {
                            "type": "standard"
                        }
                    }
                }
            },
            "mappings": {
                "properties": {
                    "name": {"type": "text", "analyzer": "standard", "fields": {"raw": {"type": "keyword"}}},
                    "key": {"type": "keyword"},
                    "description": {"type": "text"},
                    "cluster": {"type": "keyword"},
                    "database": {"type": "keyword"},
                    "schema": {"type": "keyword"},
                    "column_names": {"type": "text"},
                    "column_descriptions": {"type": "text"},
                    "tags": {"type": "keyword"},
                    "badges": {"type": "keyword"},
                    "last_updated_timestamp": {"type": "date"},
                    "programmatic_descriptions": {"type": "text"},
                    "total_usage": {"type": "long"}
                }
            }
        }
        
        # Delete index if exists
        if self.es_client.indices.exists(index=self.index_name):
            self.es_client.indices.delete(index=self.index_name)
            print(f"🗑️  Deleted existing index: {self.index_name}")
        
        # Create new index
        self.es_client.indices.create(index=self.index_name, body=index_body)
        print(f"✅ Created index: {self.index_name}")
    
    def fetch_tables_from_neo4j(self):
        """Fetch all table metadata from Neo4j"""
        
        query = """
        MATCH (db:Database)-[:CLUSTER]->(clstr:Cluster)-[:SCHEMA]->(schema:Schema)-[:TABLE]->(tbl:Table)
        OPTIONAL MATCH (tbl)-[:DESCRIPTION]->(tbl_dscrpt:Description)
        OPTIONAL MATCH (tbl)-[:COLUMN]->(col:Column)
        OPTIONAL MATCH (col)-[:DESCRIPTION]->(col_dscrpt:Description)
        OPTIONAL MATCH (tbl)-[:TAGGED_BY]->(tag:Tag)
        OPTIONAL MATCH (tbl)<-[:OWNER_OF]-(owner:User)
        
        WITH tbl, db, clstr, schema, tbl_dscrpt,
             collect(DISTINCT col.name) as column_names,
             collect(DISTINCT col_dscrpt.description) as column_descriptions,
             collect(DISTINCT tag.key) as tags,
             collect(DISTINCT owner.email) as owners
        
        RETURN 
            tbl.key as key,
            tbl.name as name,
            db.name as database,
            clstr.name as cluster,
            schema.name as schema,
            tbl_dscrpt.description as description,
            column_names,
            column_descriptions,
            tags,
            owners
        """
        
        tables = []
        with self.neo4j_driver.session() as session:
            result = session.run(query)
            for record in result:
                table = {
                    'key': record['key'],
                    'name': record['name'],
                    'database': record['database'],
                    'cluster': record['cluster'],
                    'schema': record['schema'],
                    'description': record['description'] or '',
                    'column_names': [c for c in record['column_names'] if c],
                    'column_descriptions': [d for d in record['column_descriptions'] if d],
                    'tags': [t for t in record['tags'] if t],
                    'owners': [o for o in record['owners'] if o],
                    'last_updated_timestamp': int(datetime.utcnow().timestamp()),
                    'total_usage': 0
                }
                tables.append(table)
        
        return tables
    
    def index_tables(self, tables):
        """Index tables in Elasticsearch"""
        
        for table in tables:
            doc_id = table['key']
            self.es_client.index(
                index=self.index_name,
                id=doc_id,
                body=table
            )
            print(f"  ✓ Indexed: {table['name']} ({table['schema']})")
        
        # Refresh index to make docs searchable immediately
        self.es_client.indices.refresh(index=self.index_name)
    
    def run_sync(self):
        """Run complete sync process"""
        
        print("🔄 Syncing Amundsen metadata: Neo4j → Elasticsearch")
        print(f"   Neo4j: {self.neo4j_uri}")
        print(f"   ES: http://{self.es_host}:{self.es_port}")
        print("=" * 70)
        
        try:
            # Step 1: Create index
            self.create_index()
            print()
            
            # Step 2: Fetch tables from Neo4j
            print("📊 Fetching tables from Neo4j...")
            tables = self.fetch_tables_from_neo4j()
            print(f"   Found {len(tables)} tables")
            print()
            
            # Step 3: Index in Elasticsearch
            print("📝 Indexing in Elasticsearch...")
            self.index_tables(tables)
            print()
            
            print("=" * 70)
            print(f"✅ Successfully synced {len(tables)} tables to Elasticsearch!")
            print()
            print("🔍 Test search:")
            print(f"   curl 'http://{self.es_host}:{self.es_port}/{self.index_name}/_search?q=weather'")
            print()
            print("🌐 View in Amundsen:")
            print("   http://localhost:5005")
            print("   Search for: weather, observations, bronze, silver")
            
            return True
            
        except Exception as e:
            print(f"❌ Error during sync: {str(e)}")
            import traceback
            traceback.print_exc()
            return False


def main():
    sync = Neo4jToElasticsearchSync()
    
    try:
        success = sync.run_sync()
        exit(0 if success else 1)
    finally:
        sync.close()


if __name__ == '__main__':
    main()
