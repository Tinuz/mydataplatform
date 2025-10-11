#!/usr/bin/env python3
"""
Complete Amundsen Data Ingestion Script
Loads metadata into both Neo4j AND Elasticsearch for full search functionality
"""

import sys
import logging
from pyhocon import ConfigFactory
from databuilder.extractor.postgres_metadata_extractor import PostgresMetadataExtractor
from databuilder.extractor.sql_alchemy_extractor import SQLAlchemyExtractor
from databuilder.job.job import DefaultJob
from databuilder.loader.file_system_elasticsearch_json_loader import FSElasticsearchJSONLoader
from databuilder.loader.file_system_neo4j_csv_loader import FsNeo4jCSVLoader
from databuilder.publisher.elasticsearch_publisher import ElasticsearchPublisher
from databuilder.publisher.neo4j_csv_publisher import Neo4jCsvPublisher
from databuilder.task.task import DefaultTask
from databuilder.transformer.base_transformer import NoopTransformer

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Connection settings
NEO4J_ENDPOINT = 'bolt://localhost:7687'
NEO4J_USER = 'neo4j'
NEO4J_PASSWORD = 'test'
ES_ENDPOINT = 'http://localhost:9200'

POSTGRES_CONN = 'postgresql://superset:superset@localhost:5432/superset'

def create_neo4j_job():
    """Extract metadata and load into Neo4j"""
    logger.info("Starting Neo4j metadata extraction...")
    
    tmp_folder = '/tmp/amundsen/neo4j'
    node_files_folder = f'{tmp_folder}/nodes'
    relationship_files_folder = f'{tmp_folder}/relationships'

    job_config = ConfigFactory.from_dict({
        f'extractor.postgres_metadata.{PostgresMetadataExtractor.WHERE_CLAUSE_SUFFIX_KEY}': 
            "c.table_schema = 'cell_towers' AND c.table_name = 'clean_204'",
        f'extractor.postgres_metadata.extractor.sqlalchemy.{SQLAlchemyExtractor.CONN_STRING}': 
            POSTGRES_CONN,
        f'loader.filesystem_csv_neo4j.{FsNeo4jCSVLoader.NODE_DIR_PATH}': 
            node_files_folder,
        f'loader.filesystem_csv_neo4j.{FsNeo4jCSVLoader.RELATION_DIR_PATH}': 
            relationship_files_folder,
        f'loader.filesystem_csv_neo4j.{FsNeo4jCSVLoader.SHOULD_DELETE_CREATED_DIR}': 
            True,
        f'publisher.neo4j.{Neo4jCsvPublisher.NODE_FILES_DIR}': 
            node_files_folder,
        f'publisher.neo4j.{Neo4jCsvPublisher.RELATION_FILES_DIR}': 
            relationship_files_folder,
        f'publisher.neo4j.{Neo4jCsvPublisher.NEO4J_END_POINT_KEY}': 
            NEO4J_ENDPOINT,
        f'publisher.neo4j.{Neo4jCsvPublisher.NEO4J_USER}': 
            NEO4J_USER,
        f'publisher.neo4j.{Neo4jCsvPublisher.NEO4J_PASSWORD}': 
            NEO4J_PASSWORD,
        f'publisher.neo4j.{Neo4jCsvPublisher.JOB_PUBLISH_TAG}': 
            'unique_tag',
    })

    job = DefaultJob(
        conf=job_config,
        task=DefaultTask(
            extractor=PostgresMetadataExtractor(),
            loader=FsNeo4jCSVLoader()
        ),
        publisher=Neo4jCsvPublisher()
    )
    
    return job


def create_es_job():
    """Extract metadata and load into Elasticsearch"""
    logger.info("Starting Elasticsearch index creation...")
    
    tmp_folder = '/tmp/amundsen/es'

    job_config = ConfigFactory.from_dict({
        f'extractor.postgres_metadata.{PostgresMetadataExtractor.WHERE_CLAUSE_SUFFIX_KEY}': 
            "c.table_schema = 'cell_towers' AND c.table_name = 'clean_204'",
        f'extractor.postgres_metadata.extractor.sqlalchemy.{SQLAlchemyExtractor.CONN_STRING}': 
            POSTGRES_CONN,
        f'loader.filesystem.elasticsearch.{FSElasticsearchJSONLoader.FILE_PATH_CONFIG_KEY}': 
            tmp_folder,
        f'loader.filesystem.elasticsearch.{FSElasticsearchJSONLoader.FILE_MODE_CONFIG_KEY}': 
            'w',
        f'publisher.elasticsearch.{ElasticsearchPublisher.FILE_PATH_CONFIG_KEY}': 
            tmp_folder,
        f'publisher.elasticsearch.{ElasticsearchPublisher.FILE_MODE_CONFIG_KEY}': 
            'r',
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_CLIENT_CONFIG_KEY}': 
            ES_ENDPOINT,
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_NEW_INDEX_CONFIG_KEY}': 
            'table_search_index',
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_DOC_TYPE_CONFIG_KEY}': 
            '_doc',
        f'publisher.elasticsearch.{ElasticsearchPublisher.ELASTICSEARCH_ALIAS_CONFIG_KEY}': 
            'table_search_index',
    })

    job = DefaultJob(
        conf=job_config,
        task=DefaultTask(
            extractor=PostgresMetadataExtractor(),
            loader=FSElasticsearchJSONLoader(),
            transformer=NoopTransformer()
        ),
        publisher=ElasticsearchPublisher()
    )
    
    return job


def main():
    logger.info("=" * 60)
    logger.info("AMUNDSEN COMPLETE DATA INGESTION")
    logger.info("=" * 60)
    
    try:
        # Step 1: Load into Neo4j
        logger.info("\n[1/2] Loading metadata into Neo4j...")
        neo4j_job = create_neo4j_job()
        neo4j_job.launch()
        logger.info("✅ Neo4j metadata loaded successfully!")
        
        # Step 2: Load into Elasticsearch
        logger.info("\n[2/2] Loading search index into Elasticsearch...")
        es_job = create_es_job()
        es_job.launch()
        logger.info("✅ Elasticsearch index created successfully!")
        
        logger.info("\n" + "=" * 60)
        logger.info("🎉 INGESTION COMPLETE!")
        logger.info("=" * 60)
        logger.info("\nYou can now:")
        logger.info("  • Search for 'clean_204' in Amundsen UI")
        logger.info("  • Browse columns and metadata")
        logger.info("  • View tags and statistics")
        logger.info("\nAmundsen UI: http://localhost:5005")
        
    except Exception as e:
        logger.error(f"❌ Ingestion failed: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
