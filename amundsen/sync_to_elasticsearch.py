#!/usr/bin/env python3
"""
Sync Neo4j metadata to Elasticsearch for Amundsen search
"""

from neo4j import GraphDatabase
from elasticsearch import Elasticsearch
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connection settings
NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASSWORD = "test"

ES_HOST = "http://localhost:9200"
ES_INDEX = "table_search_index"

def get_table_metadata():
    """Extract table metadata from Neo4j"""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Get table with all related data
        result = session.run("""
            MATCH (db:Database)-[:SCHEMA]->(schema:Schema),
                  (schema)-[:TABLE]->(table:Table)
            OPTIONAL MATCH (table)-[:COLUMN]->(col:Column)
            OPTIONAL MATCH (table)-[:TAGGED_BY]->(tag:Tag)
            OPTIONAL MATCH (table)-[:DESCRIPTION]->(desc:Programmatic_Description)
            OPTIONAL MATCH (table)-[:STAT]->(stat:Stat)
            RETURN 
                db.cluster as cluster,
                db.name as database,
                schema.name as schema,
                table.name as table_name,
                table.key as table_key,
                desc.description as description,
                collect(DISTINCT col.name) as columns,
                collect(DISTINCT tag.tag_name) as tags,
                collect(DISTINCT {name: stat.stat_name, value: stat.stat_val}) as stats
        """)
        
        records = list(result)
        driver.close()
        return records


def create_es_documents(metadata_records):
    """Convert Neo4j records to Elasticsearch documents"""
    documents = []
    
    for record in metadata_records:
        # Build column details
        columns = []
        for col_name in record['columns']:
            if col_name:  # Filter out None values
                columns.append({
                    'name': col_name,
                    'description': ''
                })
        
        # Build tags
        tags = [tag for tag in record['tags'] if tag]
        
        # Build statistics
        stats = []
        for stat in record['stats']:
            if stat.get('name'):
                stats.append({
                    'stat_type': stat['name'],
                    'stat_val': stat.get('value', '')
                })
        
        # Create document
        doc = {
            'name': record['table_name'],
            'key': record['table_key'] or f"{record['database']}.{record['schema']}.{record['table_name']}",
            'database': record['database'],
            'cluster': record['cluster'],
            'schema': record['schema'],
            'description': record['description'] or '',
            'columns': columns,
            'tags': tags,
            'badges': [],
            'programmatic_descriptions': [],
            'last_updated_timestamp': 0,
            'display_name': record['table_name'],
            'total_usage': 0,
            'schema_description': '',
            'column_names': [col['name'] for col in columns],
            'column_descriptions': [],
            'resource_type': 'table',
            'stats': stats
        }
        
        documents.append(doc)
    
    return documents


def index_to_elasticsearch(documents):
    """Index documents in Elasticsearch"""
    # Elasticsearch 8.x configuration
    es = Elasticsearch(
        [ES_HOST],
        verify_certs=False,
        ssl_show_warn=False
    )
    
    # Check connection
    logger.info("Testing Elasticsearch connection...")
    info = es.info()
    logger.info(f"Connected to Elasticsearch {info['version']['number']}")
    
    # Delete index if exists
    try:
        if es.indices.exists(index=ES_INDEX):
            logger.info(f"Deleting existing index: {ES_INDEX}")
            es.indices.delete(index=ES_INDEX)
    except:
        pass  # Index doesn't exist
    
    # Create index with mapping
    logger.info(f"Creating index: {ES_INDEX}")
    mapping = {
        "mappings": {
            "properties": {
                "name": {"type": "text", "analyzer": "simple", "fields": {"raw": {"type": "keyword"}}},
                "key": {"type": "keyword"},
                "database": {"type": "keyword"},
                "cluster": {"type": "keyword"},
                "schema": {"type": "keyword"},
                "description": {"type": "text"},
                "columns": {"type": "nested"},
                "tags": {"type": "keyword"},
                "column_names": {"type": "text"},
                "resource_type": {"type": "keyword"}
            }
        }
    }
    
    es.indices.create(index=ES_INDEX, **mapping)
    
    # Index documents
    for i, doc in enumerate(documents):
        doc_id = doc['key']
        logger.info(f"Indexing document {i+1}/{len(documents)}: {doc['name']}")
        es.index(index=ES_INDEX, id=doc_id, document=doc)
    
    # Refresh index
    es.indices.refresh(index=ES_INDEX)
    logger.info(f"✅ Indexed {len(documents)} documents to Elasticsearch")


def main():
    logger.info("=" * 60)
    logger.info("SYNCING NEO4J METADATA TO ELASTICSEARCH")
    logger.info("=" * 60)
    
    try:
        # Step 1: Extract from Neo4j
        logger.info("\n[1/3] Extracting metadata from Neo4j...")
        records = get_table_metadata()
        logger.info(f"Found {len(records)} tables in Neo4j")
        
        if not records:
            logger.warning("No tables found in Neo4j! Run databuilder_ingestion.py first.")
            return
        
        # Step 2: Convert to ES format
        logger.info("\n[2/3] Converting to Elasticsearch format...")
        documents = create_es_documents(records)
        logger.info(f"Created {len(documents)} search documents")
        
        # Step 3: Index in ES
        logger.info("\n[3/3] Indexing in Elasticsearch...")
        index_to_elasticsearch(documents)
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 SYNC COMPLETE!")
        logger.info("=" * 60)
        logger.info("\nSearch should now work in Amundsen UI!")
        logger.info("Try searching for: clean_204")
        
    except Exception as e:
        logger.error(f"❌ Sync failed: {str(e)}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
