"""
Crypto Stream Resources

Reusable connections for Kafka and Iceberg.
"""

from dagster import resource, ConfigurableResource
from typing import Any
import os


class KafkaResource(ConfigurableResource):
    """Kafka connection resource"""
    
    bootstrap_servers: str = "kafka:9092"
    
    def get_producer(self):
        """Get Kafka producer instance"""
        from kafka import KafkaProducer
        import json
        
        return KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            compression_type='gzip'
        )
    
    def get_consumer(self, topic: str, group_id: str):
        """Get Kafka consumer instance"""
        from kafka import KafkaConsumer
        import json
        
        return KafkaConsumer(
            topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=group_id,
            value_deserializer=lambda x: json.loads(x.decode('utf-8')),
            enable_auto_commit=False
        )


class IcebergResource(ConfigurableResource):
    """Iceberg catalog resource"""
    
    catalog_uri: str = "http://iceberg-rest:8181"
    warehouse: str = "s3://lake/"
    
    def get_catalog(self):
        """Get Iceberg catalog instance"""
        from pyiceberg.catalog import load_catalog
        import os
        
        return load_catalog(
            "rest",
            **{
                "uri": self.catalog_uri,
                "warehouse": self.warehouse,
                "s3.endpoint": os.getenv("MINIO_ENDPOINT", "http://minio:9000"),
                "s3.access-key-id": os.getenv("AWS_ACCESS_KEY_ID", "minio"),
                "s3.secret-access-key": os.getenv("AWS_SECRET_ACCESS_KEY", "minio12345"),
                "s3.path-style-access": "true",
                "s3.region": os.getenv("AWS_REGION", "us-east-1"),
                "s3.secure": "false",  # Disable SSL for MinIO HTTP endpoint
            }
        )


# Resource instances
kafka_resource = KafkaResource(
    bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
)

iceberg_resource = IcebergResource(
    catalog_uri=os.getenv("ICEBERG_CATALOG_URI", "http://iceberg-rest:8181"),
    warehouse=os.getenv("ICEBERG_WAREHOUSE", "s3://lake/")
)
